from datetime import date, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User, Campus, StudentProfile
from apps.catalog.models import Category, Item
from apps.chat.models import Conversation, Message
from apps.rentals.models import Rental


class ChatSystemTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

        self.campus, _ = Campus.objects.get_or_create(name='Institut Teknologi Mahasiswa', defaults={'short_name': 'ITM'})

        # Pemilik
        self.owner = User.objects.create_user(
            username='pemilik_chat', email='pemilik@chat.id', password='Password123!',
            full_name='Budi Pemilik', is_verified_student=True
        )
        StudentProfile.objects.create(user=self.owner, nim='1001', campus=self.campus, major='Informatika')

        # Penyewa
        self.renter = User.objects.create_user(
            username='penyewa_chat', email='penyewa@chat.id', password='Password123!',
            full_name='Ani Penyewa', is_verified_student=True
        )
        StudentProfile.objects.create(user=self.renter, nim='1002', campus=self.campus, major='Desain')

        # Pihak ketiga yang tidak berkepentingan
        self.third_party = User.objects.create_user(
            username='stranger_chat', email='stranger@chat.id', password='Password123!',
            full_name='Joko Asing', is_verified_student=True
        )
        StudentProfile.objects.create(user=self.third_party, nim='1003', campus=self.campus, major='Elektro')

        self.category = Category.objects.create(name='Fotografi', slug='fotografi', order=1)
        self.item = Item.objects.create(
            owner=self.owner, category=self.category, title='Sony Alpha A6400',
            estimated_value=2000000, price_per_day=80000, deposit_amount=300000,
            min_days=1, max_days=5, pickup_area='Kantin Pusat', is_active=True
        )

        self.conversation = Conversation.objects.create(
            item=self.item, renter=self.renter, owner=self.owner
        )

    def tearDown(self):
        cache.clear()

    def test_contact_info_masking_before_payment(self):
        """Uji penyamaran nomor telepon, tautan, dan email sebelum pembayaran berhasil."""
        # 1. Nomor HP 08...
        msg1 = Message.objects.create(
            conversation=self.conversation, sender=self.renter,
            body='Halo, bisa hubungi saya di 08123456789 ya'
        )
        self.assertIn('[disamarkan sampai pembayaran]', msg1.get_display_body())
        self.assertNotIn('08123456789', msg1.get_display_body())

        # 2. Nomor HP +62...
        msg2 = Message.objects.create(
            conversation=self.conversation, sender=self.renter,
            body='Nomor saya +6281298765432'
        )
        self.assertIn('[disamarkan sampai pembayaran]', msg2.get_display_body())
        self.assertNotIn('+6281298765432', msg2.get_display_body())

        # 3. 8 digit berurutan
        msg3 = Message.objects.create(
            conversation=self.conversation, sender=self.renter,
            body='Kode pin 12345678'
        )
        self.assertIn('[disamarkan sampai pembayaran]', msg3.get_display_body())

        # 4. Tautan web / wa.me / t.me
        msg4 = Message.objects.create(
            conversation=self.conversation, sender=self.renter,
            body='Chat ke wa.me/6281234567 atau https://t.me/username'
        )
        self.assertIn('[disamarkan sampai pembayaran]', msg4.get_display_body())
        self.assertNotIn('wa.me', msg4.get_display_body())
        self.assertNotIn('https://t.me', msg4.get_display_body())

        # 5. Email
        msg5 = Message.objects.create(
            conversation=self.conversation, sender=self.renter,
            body='Kirim file ke mahasiswa@kampus.ac.id'
        )
        self.assertIn('[disamarkan sampai pembayaran]', msg5.get_display_body())
        self.assertNotIn('mahasiswa@kampus.ac.id', msg5.get_display_body())

    def test_contact_info_not_masked_after_payment(self):
        """Uji bahwa setelah transaksi sewa dibayar, kontak langsung tidak lagi disamarkan."""
        # Buat rental dengan status dibayar
        Rental.objects.create(
            item=self.item, renter=self.renter, owner=self.owner,
            start_date=date(2026, 11, 1), end_date=date(2026, 11, 3), days=3,
            price_per_day_snapshot=80000, rent_total=240000, deposit_total=300000, grand_total=540000,
            status=Rental.Status.DIBAYAR
        )

        msg = Message.objects.create(
            conversation=self.conversation, sender=self.renter,
            body='Nomor WA saya 08123456789 dan email ani@kampus.ac.id'
        )
        display_body = msg.get_display_body()
        self.assertNotIn('[disamarkan sampai pembayaran]', display_body)
        self.assertIn('08123456789', display_body)
        self.assertIn('ani@kampus.ac.id', display_body)

    def test_xss_escaping_in_message(self):
        """Uji bahwa script berbahaya di-escape secara otomatis."""
        msg = Message.objects.create(
            conversation=self.conversation, sender=self.renter,
            body='<script>alert("XSS")</script><b>Bold</b>'
        )
        display = msg.get_display_body()
        self.assertNotIn('<script>', display)
        self.assertIn('&lt;script&gt;', display)

    def test_conversation_access_control(self):
        """Uji bahwa hanya peserta percakapan yang berhak mengakses ruang chat."""
        # 1. Penyewa (peserta) -> 200 OK
        self.client.force_login(self.renter)
        resp_renter = self.client.get(reverse('chat:conversation', kwargs={'conversation_id': self.conversation.id}))
        self.assertEqual(resp_renter.status_code, 200)

        # 2. Pemilik (peserta) -> 200 OK
        self.client.force_login(self.owner)
        resp_owner = self.client.get(reverse('chat:conversation', kwargs={'conversation_id': self.conversation.id}))
        self.assertEqual(resp_owner.status_code, 200)

        # 3. Pihak ketiga asing -> 403 Forbidden
        self.client.force_login(self.third_party)
        resp_stranger = self.client.get(reverse('chat:conversation', kwargs={'conversation_id': self.conversation.id}))
        self.assertEqual(resp_stranger.status_code, 403)

    def test_only_renter_can_start_conversation(self):
        """Uji bahwa hanya penyewa yang boleh memulai percakapan, pemilik tidak bisa spam ke barangnya sendiri."""
        item2 = Item.objects.create(
            owner=self.owner, category=self.category, title='Lensa Makro',
            estimated_value=1000000, price_per_day=40000, deposit_amount=150000,
            min_days=1, max_days=3, pickup_area='Lab'
        )

        # Penyewa memulai -> Berhasil redirect ke percakapan baru
        self.client.force_login(self.renter)
        resp = self.client.get(reverse('chat:start_conversation', kwargs={'item_slug': item2.slug}))
        self.assertEqual(resp.status_code, 302)
        conv = Conversation.objects.get(item=item2, renter=self.renter)
        self.assertRedirects(resp, reverse('chat:conversation', kwargs={'conversation_id': conv.id}))

        # Pemilik mencoba memulai ke barangnya sendiri -> Ditolak / dialihkan kembali ke detail barang
        self.client.force_login(self.owner)
        resp_owner = self.client.get(reverse('chat:start_conversation', kwargs={'item_slug': item2.slug}))
        self.assertEqual(resp_owner.status_code, 302)
        self.assertRedirects(resp_owner, reverse('catalog:item_detail', kwargs={'slug': item2.slug}))

    def test_message_character_limit_500(self):
        """Uji bahwa pesan dibatasi maksimal 500 karakter."""
        self.client.force_login(self.renter)
        long_text = "A" * 650
        self.client.post(
            reverse('chat:send_message', kwargs={'conversation_id': self.conversation.id}),
            {'body': long_text}
        )
        saved_msg = Message.objects.filter(conversation=self.conversation).last()
        self.assertEqual(len(saved_msg.body), 500)

    def test_message_rate_limiting_20_per_minute(self):
        """Uji pembatasan laju 20 pesan per menit per pengguna."""
        self.client.force_login(self.renter)
        url = reverse('chat:send_message', kwargs={'conversation_id': self.conversation.id})

        # Kirim 20 pesan berturut-turut -> Sukses
        for i in range(20):
            resp = self.client.post(url, {'body': f'Pesan nomor {i}'}, HTTP_HX_REQUEST='true')
            self.assertEqual(resp.status_code, 200)

        # Pesan ke-21 dalam 1 menit -> 429 Too Many Requests
        resp_limit = self.client.post(url, {'body': 'Pesan ke-21 yang melebihi batas'}, HTTP_HX_REQUEST='true')
        self.assertEqual(resp_limit.status_code, 429)
        self.assertIn('Batas pengiriman pesan tercapai', resp_limit.content.decode('utf-8'))

    def test_masking_comprehensive_links_and_long_numbers(self):
        """Uji penyamaran tautan www dan nomor telepon panjang dengan tanda hubung/spasi."""
        msg = Message.objects.create(
            conversation=self.conversation, sender=self.renter,
            body='Cek www.instagram.com/mahasiswa atau hubungi 0812-3456-7890-12345 ya'
        )
        display = msg.get_display_body()
        self.assertIn('[disamarkan sampai pembayaran]', display)
        self.assertNotIn('www.instagram.com', display)
        self.assertNotIn('0812-3456-7890-12345', display)

    def test_contact_unmasked_after_sale_order_payment(self):
        """Uji bahwa transaksi jual beli membuka penyamaran kontak setelah pesanan dibayar."""
        from apps.sales.models import SaleItem, SaleOrder
        cat_sale = Category.objects.create(name='Buku', slug='buku-chat', scope=Category.Scope.JUAL)
        sale_item = SaleItem.objects.create(
            owner=self.owner, category=cat_sale, title='Buku Algoritma',
            price=50000, condition=SaleItem.Condition.BAIK, status=SaleItem.Status.DIPESAN
        )
        conv_sale = Conversation.objects.create(
            sale_item=sale_item, renter=self.renter, owner=self.owner
        )
        msg_pre = Message.objects.create(
            conversation=conv_sale, sender=self.renter,
            body='Nomor saya 085512345678'
        )
        # Sebelum pembayaran -> Disamarkan
        self.assertIn('[disamarkan sampai pembayaran]', msg_pre.get_display_body())

        # Buat order dengan status DIBAYAR
        order = SaleOrder.objects.create(
            item=sale_item, buyer=self.renter, seller=self.owner,
            price_snapshot=50000, commission=2500,
            reserved_until=timezone.now() + timedelta(hours=6),
            status=SaleOrder.Status.DIBAYAR
        )
        # Setelah pembayaran -> Tidak disamarkan
        self.assertNotIn('[disamarkan sampai pembayaran]', msg_pre.get_display_body())
        self.assertIn('085512345678', msg_pre.get_display_body())

    def test_new_rental_inquiry_masked_even_if_past_rental_was_completed(self):
        """Uji bahwa sewa baru yang belum dibayar tetap disamarkan meskipun pernah ada transaksi sewa selesai di masa lalu."""
        # 1. Transaksi lama telah selesai
        past_rental = Rental.objects.create(
            item=self.item, renter=self.renter, owner=self.owner,
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), days=2,
            price_per_day_snapshot=80000, rent_total=160000, grand_total=160000,
            status=Rental.Status.SELESAI
        )
        # 2. Percakapan terikat pada sewa baru yang belum dibayar (menunggu_persetujuan)
        new_rental = Rental.objects.create(
            item=self.item, renter=self.renter, owner=self.owner,
            start_date=date(2026, 12, 1), end_date=date(2026, 12, 3), days=2,
            price_per_day_snapshot=80000, rent_total=160000, grand_total=160000,
            status=Rental.Status.MENUNGGU_PERSETUJUAN
        )
        self.conversation.rental = new_rental
        self.conversation.save(update_fields=['rental'])

        msg_new = Message.objects.create(
            conversation=self.conversation, sender=self.renter,
            body='Halo saya mau sewa lagi nomor saya 089912345678'
        )
        # Harus tetap disamarkan karena sewa yang terikat saat ini belum dibayar
        self.assertIn('[disamarkan sampai pembayaran]', msg_new.get_display_body())
        self.assertNotIn('089912345678', msg_new.get_display_body())

    def test_admin_short_body_uses_masked_display(self):
        """Uji bahwa tampilan short_body di Django admin menghormati penyamaran kontak sebelum pembayaran."""
        from apps.chat.admin import MessageAdmin
        from django.contrib.admin.sites import AdminSite
        msg = Message.objects.create(
            conversation=self.conversation, sender=self.renter,
            body='Hubungi saya di 08123456789 atau email tester@kampus.ac.id'
        )
        admin_obj = MessageAdmin(Message, AdminSite())
        short = admin_obj.short_body(msg)
        self.assertIn('[disamarkan sampai pembayaran]', short)
        self.assertNotIn('08123456789', short)

