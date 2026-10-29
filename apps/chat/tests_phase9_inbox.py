from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache

from apps.accounts.models import User, Campus, StudentProfile
from apps.catalog.models import Category, Item
from apps.sales.models import SaleItem
from apps.chat.models import Conversation, Message


class Phase9InboxTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

        self.campus, _ = Campus.objects.get_or_create(
            name='Institut Teknologi Mahasiswa', defaults={'short_name': 'ITM'}
        )

        self.user1 = User.objects.create_user(
            username='user1_inbox', email='user1@inbox.id', password='Password123!',
            full_name='Rina Pengguna', is_verified_student=True
        )
        StudentProfile.objects.create(user=self.user1, nim='1101', campus=self.campus, major='Informatika')

        self.user2 = User.objects.create_user(
            username='user2_inbox', email='user2@inbox.id', password='Password123!',
            full_name='Doni Pemilik', is_verified_student=True
        )
        StudentProfile.objects.create(user=self.user2, nim='1102', campus=self.campus, major='Sistem Informasi')

        self.category = Category.objects.create(name='Elektronik', slug='elektronik', order=1)

        # Barang Sewa
        self.rental_item = Item.objects.create(
            owner=self.user2, category=self.category, title='Kamera DSLR Canon',
            estimated_value=3000000, price_per_day=50000, deposit_amount=100000,
            min_days=1, max_days=7, pickup_area='Perpustakaan', is_active=True
        )

        # Barang Jual
        self.sale_item = SaleItem.objects.create(
            owner=self.user2, category=self.category, title='Buku Algoritma',
            condition='bekas_sangat_baik', price=65000, pickup_area='Fakultas Ilmu Komputer',
            status=SaleItem.Status.AKTIF
        )

    def tearDown(self):
        cache.clear()

    def test_inbox_header_title_button_and_pill_removal(self):
        """Uji judul 'Kotak masuk pesan', tombol 'Jelajahi barang', dan tidak adanya pill 'Pesan Platform'."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat:inbox'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        self.assertIn('Kotak masuk pesan', html)
        self.assertNotIn('Kotak Masuk Percakapan', html)
        self.assertNotIn('Pesan Platform', html)
        self.assertIn('Jelajahi barang', html)

    def test_privacy_note_sewa_dan_jual_tanpa_kata_terjamin(self):
        """Uji catatan privasi menyebut sewa dan jual beli serta tidak mengandung kata 'terjamin'."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat:inbox'))
        html = response.content.decode('utf-8')

        self.assertIn('Privasi dan perlindungan escrow', html)
        self.assertIn('sewa atau jual beli', html)
        self.assertNotIn('terjamin', html.lower())

    def test_filter_chips_present(self):
        """Uji adanya filter Semua, Sewa, Jual beli, dan Belum dibaca."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat:inbox'))
        html = response.content.decode('utf-8')

        self.assertIn('Semua', html)
        self.assertIn('Sewa', html)
        self.assertIn('Jual beli', html)
        self.assertIn('Belum dibaca', html)

    def test_empty_conversations_grouped_in_single_summary_row(self):
        """Uji percakapan tanpa pesan dikelompokkan dan diringkas dalam satu baris, bukan kartu chat terpisah."""
        # Buat 2 percakapan tanpa pesan
        conv_empty_1 = Conversation.objects.create(
            item=self.rental_item, renter=self.user1, owner=self.user2
        )
        conv_empty_2 = Conversation.objects.create(
            sale_item=self.sale_item, renter=self.user1, owner=self.user2
        )

        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat:inbox'))
        html = response.content.decode('utf-8')

        self.assertIn('2 percakapan baru tanpa pesan', html)
        # Pastikan tidak ada teks 'Belum ada pesan terkirim. Klik untuk memulai percakapan.' di daftar utama
        self.assertNotIn('Belum ada pesan terkirim. Klik untuk memulai percakapan.', html)

    def test_active_conversation_with_unread_badge_and_tab_filtering(self):
        """Uji percakapan aktif dengan pesan muncul normal, badge unread tampil, dan filter tab berfungsi."""
        # 1 percakapan sewa aktif dengan 1 pesan unread
        conv_sewa = Conversation.objects.create(
            item=self.rental_item, renter=self.user1, owner=self.user2
        )
        Message.objects.create(
            conversation=conv_sewa, sender=self.user2, body='Halo, kamera masih ready.'
        )

        # 1 percakapan jual aktif tanpa pesan unread
        conv_jual = Conversation.objects.create(
            sale_item=self.sale_item, renter=self.user1, owner=self.user2
        )
        msg_jual = Message.objects.create(
            conversation=conv_jual, sender=self.user1, body='Buku masih ada gan?'
        )

        self.client.force_login(self.user1)

        # Tab Semua
        resp_all = self.client.get(reverse('chat:inbox'))
        html_all = resp_all.content.decode('utf-8')
        self.assertIn('Kamera DSLR Canon', html_all)
        self.assertIn('Buku Algoritma', html_all)
        self.assertIn('1 baru', html_all)

        # Tab Sewa
        resp_sewa = self.client.get(reverse('chat:inbox') + '?tab=sewa')
        html_sewa = resp_sewa.content.decode('utf-8')
        self.assertIn('Kamera DSLR Canon', html_sewa)
        self.assertNotIn('Buku Algoritma', html_sewa)

        # Tab Jual beli
        resp_jual = self.client.get(reverse('chat:inbox') + '?tab=jual_beli')
        html_jual = resp_jual.content.decode('utf-8')
        self.assertNotIn('Kamera DSLR Canon', html_jual)
        self.assertIn('Buku Algoritma', html_jual)

        # Tab Belum dibaca
        resp_unread = self.client.get(reverse('chat:inbox') + '?tab=belum_dibaca')
        html_unread = resp_unread.content.decode('utf-8')
        self.assertIn('Kamera DSLR Canon', html_unread)
        self.assertNotIn('Buku Algoritma', html_unread)
