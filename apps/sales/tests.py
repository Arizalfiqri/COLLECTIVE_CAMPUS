import hashlib
from datetime import timedelta
from django.conf import settings
from django.test import TestCase, Client, TransactionTestCase, override_settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.accounts.models import User, StudentProfile, Campus, MeetingPoint
from apps.catalog.models import Category
from apps.core.models import TermsVersion, Notification
from apps.chat.models import Conversation, Message
from apps.rentals.models import Review, Rental
from apps.rentals.management.commands.process_deadlines import run_process_deadlines
from apps.sales.models import SaleItem, SaleItemPhoto, SellerTermsAcceptance, SaleOrder, SaleAgreement, SaleDispute, SaleReview
from apps.sales.forms import SaleItemForm
from apps.sales.services import (
    get_seller_tier,
    get_seller_max_price,
    check_prohibited_keywords,
    SaleOrderError,
    SaleOrderStateError,
    SaleOrderPermissionError,
    SaleOrderValidationError,
    create_sale_order,
    mark_sale_order_paid,
    mark_sale_order_handed_over,
    confirm_sale_order_received,
    settle_sale_order,
    cancel_sale_order,
    open_sale_dispute,
    resolve_sale_dispute,
    create_sale_review,
)


class SellerTierAndPriceLimitsTest(TestCase):
    """Pengujian tingkat penjual dan batas harga jualan (Fase 8A Butir 3)."""

    def setUp(self):
        self.campus = Campus.objects.create(name='Institut Teknologi Sumatera', short_name='ITERA', city='Lampung Selatan')
        self.user = User.objects.create_user(username='penjual_muda', email='penjual@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.user, campus=self.campus, nim='121140001')

    def test_new_seller_default_tier(self):
        """Penjual tanpa riwayat penjualan berstatus 'baru' dengan batas harga default Rp1.000.000."""
        self.assertEqual(get_seller_tier(self.user), 'baru')
        self.assertEqual(get_seller_max_price(self.user), 1_000_000)

    def test_trusted_seller_tier(self):
        """Penjual dengan minimal 5 penjualan selesai dan rating >= 4.5 berstatus 'tepercaya'."""
        self.user._seller_completed_sales = 5
        self.user._seller_disputes_count = 0
        self.user._seller_rating = 4.6
        self.assertEqual(get_seller_tier(self.user), 'tepercaya')
        self.assertEqual(get_seller_max_price(self.user), 3_000_000)

    def test_top_seller_tier(self):
        """Penjual dengan minimal 15 penjualan selesai dan rating >= 4.7 berstatus 'sangat_tepercaya'."""
        self.user._seller_completed_sales = 15
        self.user._seller_disputes_count = 0
        self.user._seller_rating = 4.8
        self.assertEqual(get_seller_tier(self.user), 'sangat_tepercaya')
        self.assertEqual(get_seller_max_price(self.user), 8_000_000)

    def test_trusted_seller_with_disputes_falls_back(self):
        """Penjual dengan penjualan >= 5 namun memiliki sengketa tetap berstatus 'baru'."""
        self.user._seller_completed_sales = 10
        self.user._seller_disputes_count = 1
        self.user._seller_rating = 4.9
        self.assertEqual(get_seller_tier(self.user), 'baru')
        self.assertEqual(get_seller_max_price(self.user), 1_000_000)

    def test_trusted_seller_with_low_rating_falls_back(self):
        """Penjual dengan penjualan >= 5 namun rating < 4.5 tetap berstatus 'baru'."""
        self.user._seller_completed_sales = 10
        self.user._seller_disputes_count = 0
        self.user._seller_rating = 4.2
        self.assertEqual(get_seller_tier(self.user), 'baru')
        self.assertEqual(get_seller_max_price(self.user), 1_000_000)

    def test_form_rejects_price_exceeding_tier_limit(self):
        """Form menolak harga yang melampaui batas tingkat penjual baru."""
        cat = Category.objects.create(name='Buku Kuliah', slug='buku-kuliah', scope=Category.Scope.JUAL)
        data = {
            'category': cat.pk,
            'title': 'Buku Teks Kedokteran Lengkap',
            'description': 'Kondisi mulus tanpa coretan, lengkap semua jilid.',
            'condition': 'seperti_baru',
            'price': 1_500_000,  # Melampaui 1.000.000 untuk penjual baru
            'pickup_area': 'Perpustakaan Pusat',
            'agree_terms': True,
        }
        form = SaleItemForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('price', form.errors)
        self.assertIn('Harga melebihi batas maksimum', form.errors['price'][0])

    def test_form_accepts_price_within_tier_limit(self):
        """Form menerima harga yang berada di dalam batas tingkat penjual."""
        cat = Category.objects.create(name='Elektronik Thrift', slug='elektronik-thrift', scope=Category.Scope.JUAL)
        data = {
            'category': cat.pk,
            'title': 'Kalkulator Ilmiah Casio FX-991EX',
            'description': 'Berfungsi normal dengan solar cell dan baterai prima.',
            'condition': 'baik',
            'price': 250_000,
            'pickup_area': 'Gedung Kuliah E',
            'agree_terms': True,
        }
        form = SaleItemForm(data=data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)


class ProhibitedKeywordsFilterTest(TestCase):
    """Pengujian deteksi kata kunci terlarang dari pengaturan (Fase 8A Butir 4)."""

    def test_prohibited_keyword_detection(self):
        is_proh, matched = check_prohibited_keywords("Jual miras beralkohol impor")
        self.assertTrue(is_proh)
        self.assertEqual(matched, 'miras')

        is_proh, matched = check_prohibited_keywords("Jual pod vape second siap pakai")
        self.assertTrue(is_proh)
        self.assertIn(matched, ['pod', 'vape'])

        is_proh, matched = check_prohibited_keywords("Buku catatan kuliah semester 4")
        self.assertFalse(is_proh)
        self.assertIsNone(matched)

    def test_form_rejects_prohibited_keywords(self):
        campus = Campus.objects.create(name='Universitas Lampung', short_name='UNILA', city='Bandar Lampung')
        user = User.objects.create_user(username='user_kw', email='user_kw@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=user, campus=campus, nim='121140002')
        cat, _ = Category.objects.get_or_create(slug='lainnya-jual', defaults={'name': 'Lainnya', 'scope': Category.Scope.JUAL})

        data = {
            'category': cat.pk,
            'title': 'Jual Akun Game Mobile Legend Sultan',
            'description': 'Banyak skin epic dan legend.',
            'condition': 'baru_segel',
            'price': 500_000,
            'pickup_area': 'Kantin',
            'agree_terms': True,
        }
        form = SaleItemForm(data=data, user=user)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        self.assertIn('terlarang', form.errors['__all__'][0].lower())


class TermsAcceptanceAndCreationTest(TestCase):
    """Pengujian kewajiban S&K penjual dan rekaman jejak audit SHA-256 (Fase 8A Butir 4)."""

    def setUp(self):
        self.campus = Campus.objects.create(name='ITERA', short_name='ITERA', city='Lampung')
        self.user = User.objects.create_user(username='penjual_sk', email='penjual_sk@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.user, campus=self.campus, nim='121140003')

        self.cat, _ = Category.objects.get_or_create(
            slug='pakaian-thrift-test',
            defaults={'name': 'Pakaian Thrift Test', 'scope': Category.Scope.JUAL}
        )
        self.client = Client()
        self.client.login(username='penjual_sk', password='Password123!')

        # Pastikan ada TermsVersion jenis jual_penjual
        self.terms_version, _ = TermsVersion.objects.get_or_create(
            term_type=TermsVersion.Type.JUAL_PENJUAL,
            version='v1.0-jual',
            defaults={
                'content': 'Draft S&K Penjual Resmi KampusRent: barang sah, deskripsi jujur, tanpa barang terlarang.',
                'is_active': True,
            }
        )

    def _get_dummy_photo(self):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO()
        img = Image.new('RGB', (100, 100), color=(50, 100, 150))
        img.save(buf, format='JPEG')
        buf.seek(0)
        return SimpleUploadedFile('test_photo.jpg', buf.read(), content_type='image/jpeg')

    def test_mandatory_terms_acceptance_on_server(self):
        """Memasang barang tanpa mencentang S&K ditolak oleh server."""
        data = {
            'category': self.cat.pk,
            'title': 'Jaket Denim Thrift Size L',
            'description': 'Kondisi 95% bagus, warna biru dongker original.',
            'condition': 'seperti_baru',
            'price': 120_000,
            'pickup_area': 'Gedung F',
            'photos': [self._get_dummy_photo()],
            # agree_terms TIDAK dicentang
        }
        response = self.client.post('/jual/baru/', data)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('agree_terms', form.errors)
        self.assertIn('Anda wajib menyetujui Syarat & Ketentuan Penjual', form.errors['agree_terms'][0])
        self.assertEqual(SaleItem.objects.count(), 0)

    def test_terms_acceptance_recorded_with_hash(self):
        """Persetujuan S&K dicatat di SellerTermsAcceptance dengan hash SHA-256 dan snapshot."""
        data = {
            'category': self.cat.pk,
            'title': 'Kemeja Flanel Uniqlo Size M',
            'description': 'Koleksi pribadi jarang dipakai, warna masih sangat pekat.',
            'condition': 'seperti_baru',
            'price': 90_000,
            'pickup_area': 'Kantin Asrama',
            'photos': [self._get_dummy_photo()],
            'agree_terms': 'on',
        }
        response = self.client.post('/jual/baru/', data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SaleItem.objects.count(), 1)

        sale_item = SaleItem.objects.first()
        self.assertEqual(sale_item.title, 'Kemeja Flanel Uniqlo Size M')
        self.assertEqual(sale_item.status, SaleItem.Status.AKTIF)

        # Cek rekaman persetujuan S&K
        acceptance = SellerTermsAcceptance.objects.filter(
            user=self.user,
            terms_version=self.terms_version
        ).first()
        self.assertIsNotNone(acceptance)
        self.assertEqual(acceptance.terms_hash, self.terms_version.calculate_sha256())
        self.assertIn('Draft S&K Penjual', acceptance.text_snapshot)

    def test_unverified_student_cannot_post_sale_item(self):
        """Mahasiswa yang belum verifikasi KTM diarahkan ke panduan verifikasi."""
        unverified_user = User.objects.create_user(username='user_polos', email='polos@kampus.id', password='Password123!', is_verified_student=False)
        self.client.login(username='user_polos', password='Password123!')
        response = self.client.get('/jual/baru/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/verifikasi-ktm/', response.url)

    def test_flaws_required_when_condition_has_flaws(self):
        """Kolom flaws wajib diisi bila kondisi 'ada_cacat' atau 'cukup'."""
        data = {
            'category': self.cat.pk,
            'title': 'Celana Chino Thrift',
            'description': 'Kondisi ada sobek kecil di saku belakang.',
            'condition': 'ada_cacat',
            'flaws': '',  # Kosong
            'price': 50_000,
            'pickup_area': 'Parkiran',
            'agree_terms': True,
        }
        form = SaleItemForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('flaws', form.errors)


class DynamicCampusFilterTest(TestCase):
    """Pengujian filter kampus dinamis hanya menampilkan kampus dengan listing jual aktif (Fase 8A Butir 5)."""

    def setUp(self):
        self.campus_a = Campus.objects.create(name='Kampus Ada Barang', short_name='KAB', city='Bandar Lampung')
        self.campus_b = Campus.objects.create(name='Kampus Kosong', short_name='KK', city='Metro')

        self.user_a = User.objects.create_user(username='penjual_a', email='a@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.user_a, campus=self.campus_a, nim='121140010')

        self.user_b = User.objects.create_user(username='penjual_b', email='b@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.user_b, campus=self.campus_b, nim='121140020')

        self.cat, _ = Category.objects.get_or_create(slug='perabot-kos', defaults={'name': 'Perabot Kos', 'scope': Category.Scope.JUAL})
        self.client = Client()

    def test_dynamic_campus_listing_in_catalog(self):
        """Katalog jual beli hanya memuat kampus A yang memiliki barang jualan aktif."""
        # Buat barang aktif di Kampus A
        SaleItem.objects.create(
            owner=self.user_a,
            category=self.cat,
            title='Meja Belajar Lipat Minimalis',
            slug='meja-belajar-lipat-minimalis',
            description='Kokoh, kaki besi, cocok untuk kos.',
            condition='baik',
            price=75_000,
            pickup_area='Kos Mawar',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=30),
        )

        response = self.client.get('/jual-beli/')
        self.assertEqual(response.status_code, 200)

        campuses_in_context = response.context['campuses']
        self.assertIn(self.campus_a, campuses_in_context)
        self.assertNotIn(self.campus_b, campuses_in_context)


class SaleItemDeadlinesAndRenewalTest(TestCase):
    """Pengujian batas waktu 60 hari otomatis, notifikasi, dan perpanjangan (Fase 8A Butir 4)."""

    def setUp(self):
        self.campus = Campus.objects.create(name='ITERA', short_name='ITERA', city='Lampung')
        self.user = User.objects.create_user(username='penjual_dl', email='dl@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.user, campus=self.campus, nim='121140030')
        self.cat, _ = Category.objects.get_or_create(slug='hobi-olahraga', defaults={'name': 'Hobi dan olahraga', 'scope': Category.Scope.JUAL})

        self.sale_item = SaleItem.objects.create(
            owner=self.user,
            category=self.cat,
            title='Raket Badminton Yonex Nanoray',
            slug='raket-badminton-yonex-nanoray',
            description='Tarikan senar 26 lbs, siap pakai.',
            condition='baik',
            price=300_000,
            pickup_area='GOR Kampus',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() - timedelta(days=1),  # Sudah lewat batas 60 hari
        )

    def test_process_deadlines_expires_sale_item_idempotent(self):
        """process_deadlines mengubah status ke kedaluwarsa dan mengirimkan notifikasi secara idempoten."""
        res1 = run_process_deadlines()
        self.assertEqual(res1['expired_sale_items'], 1)

        self.sale_item.refresh_from_db()
        self.assertEqual(self.sale_item.status, SaleItem.Status.KEDALUWARSA)

        # Pastikan notifikasi tersimpan
        notif = Notification.objects.filter(user=self.user, title="Listing jualan kedaluwarsa").first()
        self.assertIsNotNone(notif)
        self.assertIn('Raket Badminton Yonex Nanoray', notif.message)

        # Eksekusi kedua harus idempoten (0 kedaluwarsa baru, tanpa duplikasi notif)
        res2 = run_process_deadlines()
        self.assertEqual(res2['expired_sale_items'], 0)
        self.assertEqual(Notification.objects.filter(user=self.user, title="Listing jualan kedaluwarsa").count(), 1)

    def test_owner_can_renew_expired_sale_item(self):
        """Pemilik dapat memperpanjang masa tayang listing yang kedaluwarsa."""
        self.sale_item.status = SaleItem.Status.KEDALUWARSA
        self.sale_item.save()

        client = Client()
        client.login(username='penjual_dl', password='Password123!')
        response = client.post(f'/jual/{self.sale_item.slug}/perpanjang/')
        self.assertEqual(response.status_code, 302)

        self.sale_item.refresh_from_db()
        self.assertEqual(self.sale_item.status, SaleItem.Status.AKTIF)
        self.assertGreater(self.sale_item.expires_at, timezone.now() + timedelta(days=58))


class SaleItemChatAndContactMaskingTest(TestCase):
    """Pengujian ruang pesan untuk barang jual dan penyamaran kontak sebelum bayar (Fase 8A Butir 7)."""

    def setUp(self):
        self.campus = Campus.objects.create(name='ITERA', short_name='ITERA', city='Lampung')
        self.seller = User.objects.create_user(username='penjual_chat', email='seller@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim='121140040')

        self.buyer = User.objects.create_user(username='pembeli_chat', email='buyer@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.buyer, campus=self.campus, nim='121140041')

        self.cat = Category.objects.create(name='Buku Kuliah', slug='buku-chat', scope=Category.Scope.JUAL)
        self.sale_item = SaleItem.objects.create(
            owner=self.seller,
            category=self.cat,
            title='Diktat Fisika Dasar 1A',
            slug='diktat-fisika-dasar-1a',
            description='Lengkap dengan modul praktikum.',
            condition='seperti_baru',
            price=45_000,
            pickup_area='Lab Fisika',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60),
        )

    def test_conversation_check_constraint_exactly_one_item(self):
        """Percakapan wajib terhubung tepat ke salah satu: item ATAU sale_item."""
        # Keduanya None -> gagal constraint
        conv_none = Conversation(renter=self.buyer, owner=self.seller, item=None, sale_item=None)
        with self.assertRaises((IntegrityError, ValidationError)):
            conv_none.full_clean()
            conv_none.save()

    def test_start_chat_with_seller(self):
        """Pembeli dapat memulai obrolan dengan penjual lewat /pesan/mulai-jual/<slug>/."""
        client = Client()
        client.login(username='pembeli_chat', password='Password123!')
        response = client.get(f'/pesan/mulai-jual/{self.sale_item.slug}/')
        self.assertEqual(response.status_code, 302)

        conv = Conversation.objects.filter(sale_item=self.sale_item, renter=self.buyer).first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.owner, self.seller)
        self.assertIsNone(conv.item)

    def test_seller_cannot_chat_with_themselves(self):
        """Penjual tidak dapat membuka percakapan dengan dirinya sendiri."""
        client = Client()
        client.login(username='penjual_chat', password='Password123!')
        response = client.get(f'/pesan/mulai-jual/{self.sale_item.slug}/')
        self.assertEqual(response.status_code, 302)
        # Tetap tidak membuat percakapan
        self.assertEqual(Conversation.objects.count(), 0)

    def test_contact_masking_before_payment(self):
        """Nomor HP, link WA, dan email disamarkan karena pada tahap 1 belum ada transaksi uang."""
        conv = Conversation.objects.create(
            sale_item=self.sale_item,
            renter=self.buyer,
            owner=self.seller,
        )
        self.assertFalse(conv.has_successful_payment())

        msg = Message.objects.create(
            conversation=conv,
            sender=self.buyer,
            body="Halo, hubungi saya di wa.me/6281234567890 atau email buyer@test.com"
        )

        client = Client()
        client.login(username='penjual_chat', password='Password123!')
        response = client.get(f'/pesan/{conv.pk}/')
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertNotIn("6281234567890", content)
        self.assertNotIn("buyer@test.com", content)
        self.assertIn("[disamarkan sampai pembayaran]", content)


class PublicDisplayForbiddenWordsTest(TestCase):
    """Memastikan tidak ada kebocoran istilah jaminan/deposit pada tampilan modul jual beli (Fase 8A Butir 9)."""

    def setUp(self):
        self.campus = Campus.objects.create(name='ITERA', short_name='ITERA', city='Lampung')
        self.user = User.objects.create_user(username='seller_pub', email='sp@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.user, campus=self.campus, nim='121140050')

        self.cat = Category.objects.create(name='Pakaian Thrift', slug='pakaian-pub', scope=Category.Scope.JUAL)
        self.sale_item = SaleItem.objects.create(
            owner=self.user,
            category=self.cat,
            title='Jaket Hoodie Thrift Abu-Abu',
            slug='jaket-hoodie-thrift-abu-abu',
            description='Bahan katun tebal, nyaman dipakai kuliah.',
            condition='seperti_baru',
            price=85_000,
            original_price=250_000,
            pickup_area='Masjid At-Thalabah',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60),
        )
        self.client = Client()

    def test_no_deposit_leak_in_sales_catalog(self):
        """Katalog jual beli tidak memuat kata 'uang jaminan' atau 'deposit'."""
        response = self.client.get('/jual-beli/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8').lower()
        self.assertNotIn('uang jaminan', content)
        self.assertNotIn('deposit', content)

    def test_no_deposit_leak_in_sale_item_detail(self):
        """Halaman detail barang jualan tidak memuat kata 'uang jaminan' atau 'deposit'."""
        response = self.client.get(f'/jual-beli/{self.sale_item.slug}/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8').lower()
        self.assertNotIn('uang jaminan', content)
        self.assertNotIn('deposit', content)
        # Menampilkan kartu penjual dan penghematan
        self.assertIn('hemat', content)
        self.assertIn('aman bertransaksi', content)


class BuySaleItemViewTest(TestCase):
    """Pengujian alur pembelian barang, validasi syarat pembeli, dan pembuatan pesanan (Fase 8B Butir 3)."""

    def setUp(self):
        self.campus = Campus.objects.create(name='ITERA', short_name='ITERA', city='Lampung')
        self.seller = User.objects.create_user(username='penjual_8b', email='p8b@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim='121140060')

        self.buyer = User.objects.create_user(username='pembeli_8b', email='b8b@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.buyer, campus=self.campus, nim='121140061')

        self.other_user = User.objects.create_user(username='orang_lain', email='ol@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.other_user, campus=self.campus, nim='121140062')

        self.cat = Category.objects.create(name='Buku', slug='buku-8b', scope=Category.Scope.JUAL)
        self.item = SaleItem.objects.create(
            owner=self.seller,
            category=self.cat,
            title='Kalkulator Saintifik 8B',
            slug='kalkulator-saintifik-8b',
            description='Kondisi sangat mulus terawat.',
            condition='seperti_baru',
            price=150_000,
            pickup_area='Kantin Gedung C',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60),
        )
        self.client = Client()

    def test_anonymous_redirected_to_login(self):
        """Pengguna belum masuk diarahkan ke halaman login."""
        response = self.client.post(f'/jual-beli/{self.item.slug}/beli/', {'terms_accepted': '1'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/masuk/', response.url)

    def test_cannot_buy_own_item(self):
        """Penjual tidak dapat membeli barang miliknya sendiri."""
        self.client.login(username='penjual_8b', password='Password123!')
        response = self.client.post(f'/jual-beli/{self.item.slug}/beli/', {'terms_accepted': '1'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, SaleItem.Status.AKTIF)
        messages = list(response.context['messages'])
        self.assertTrue(any('sendiri' in str(m) for m in messages))

    def test_mandatory_terms_validation_on_server(self):
        """Server wajib menolak jika kotak centang S&K pembeli tidak dicentang."""
        self.client.login(username='pembeli_8b', password='Password123!')
        response = self.client.post(f'/jual-beli/{self.item.slug}/beli/', {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, SaleItem.Status.AKTIF)
        from apps.sales.models import SaleOrder
        self.assertEqual(SaleOrder.objects.count(), 0)
        messages = list(response.context['messages'])
        self.assertTrue(any('Syarat & Ketentuan' in str(m) for m in messages))

    def test_successful_buy_creates_order_and_redirects(self):
        """Pembeli yang terverifikasi dan menyetujui S&K berhasil membuat pesanan."""
        self.client.login(username='pembeli_8b', password='Password123!')
        response = self.client.post(f'/jual-beli/{self.item.slug}/beli/', {'terms_accepted': '1'})
        self.assertEqual(response.status_code, 302)

        from apps.sales.models import SaleOrder, SaleAgreement
        order = SaleOrder.objects.first()
        self.assertIsNotNone(order)
        self.assertTrue(order.code.startswith('KJ-'))
        self.assertEqual(order.buyer, self.buyer)
        self.assertEqual(order.seller, self.seller)
        self.assertEqual(order.price_snapshot, 150_000)
        self.assertEqual(order.status, SaleOrder.Status.MENUNGGU_PEMBAYARAN)

        # Status item berubah menjadi dipesan
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, SaleItem.Status.DIPESAN)

        # Agreement tercatat
        self.assertTrue(SaleAgreement.objects.filter(order=order, buyer=self.buyer).exists())

        # URL redirect tepat ke /pesanan/<kode>/
        self.assertEqual(response.url, f'/pesanan/{order.code}/')

    def test_order_detail_view_access_and_idor_protection(self):
        """Halaman pesanan hanya dapat diakses peserta pesanan (anti-IDOR)."""
        from apps.sales.services import create_sale_order
        order = create_sale_order(
            item=self.item,
            buyer=self.buyer,
            terms_accepted=True,
            ip_address='127.0.0.1',
            user_agent='TestClient'
        )

        # Pembeli bisa mengakses
        self.client.login(username='pembeli_8b', password='Password123!')
        res_buyer = self.client.get(f'/pesanan/{order.code}/')
        self.assertEqual(res_buyer.status_code, 200)

        # Penjual bisa mengakses
        self.client.login(username='penjual_8b', password='Password123!')
        res_seller = self.client.get(f'/pesanan/{order.code}/')
        self.assertEqual(res_seller.status_code, 200)

        # Orang luar ditolak (403 Forbidden - Anti-IDOR)
        self.client.login(username='orang_lain', password='Password123!')
        res_other = self.client.get(f'/pesanan/{order.code}/')
        self.assertEqual(res_other.status_code, 403)


class SaleOrderHandoverInspectionTest(TestCase):
    """Pengujian alur serah terima, kesepakatan jadwal temu, inspeksi, dan sengketa (Fase 8B Butir 5)."""

    def setUp(self):
        from apps.accounts.models import MeetingPoint
        from apps.sales.services import create_sale_order, mark_sale_order_paid
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.campus_a = Campus.objects.create(name='ITERA', short_name='ITERA', city='Lampung Selatan')
        self.campus_b = Campus.objects.create(name='UNILA', short_name='UNILA', city='Bandar Lampung')

        self.seller = User.objects.create_user(username='penjual_5b', email='p5b@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.seller, campus=self.campus_a, nim='121140070')

        self.buyer = User.objects.create_user(username='pembeli_5b', email='b5b@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.buyer, campus=self.campus_b, nim='121140071')

        self.outsider = User.objects.create_user(username='outsider_5b', email='o5b@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.outsider, campus=self.campus_a, nim='121140072')

        self.mp_public_a = MeetingPoint.objects.create(campus=self.campus_a, name='Gerbang Utama ITERA', is_public=True)
        self.mp_private_a = MeetingPoint.objects.create(campus=self.campus_a, name='Lab Khusus Elektro ITERA', is_public=False)

        self.cat, _ = Category.objects.get_or_create(slug='elektronik-jual', defaults={'name': 'Elektronik', 'scope': Category.Scope.JUAL})
        self.item = SaleItem.objects.create(
            owner=self.seller,
            category=self.cat,
            title='Arduino Kit Lengkap',
            slug='arduino-kit-lengkap-5b',
            description='Kondisi baru belum pernah disolder.',
            condition='seperti_baru',
            price=200_000,
            pickup_area='Gerbang Depan',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60),
        )

        self.order = create_sale_order(
            item=self.item,
            buyer=self.buyer,
            terms_accepted=True,
            ip_address='127.0.0.1',
            user_agent='TestRunner'
        )
        # Bayar pesanan
        mark_sale_order_paid(self.order)
        self.order.refresh_from_db()
        self.client = Client()

    def test_set_meetup_cross_campus_validation(self):
        """Untuk serah terima lintas kampus, hanya MeetingPoint publik yang diizinkan."""
        from apps.sales.services import set_sale_order_meetup, SaleOrderValidationError

        meetup_time = timezone.now() + timedelta(days=2)

        # Coba titik temu non-publik untuk beda kampus -> gagal
        with self.assertRaises(SaleOrderValidationError):
            set_sale_order_meetup(
                self.order,
                user=self.seller,
                meetup_at=meetup_time,
                meeting_point=self.mp_private_a
            )

        # Titik temu publik -> berhasil
        updated_order = set_sale_order_meetup(
            self.order,
            user=self.buyer,
            meetup_at=meetup_time,
            meeting_point=self.mp_public_a
        )
        self.assertEqual(updated_order.meeting_point, self.mp_public_a)
        self.assertEqual(updated_order.meetup_at, meetup_time)

    def test_seller_handover_success_with_photo(self):
        """Penjual menandai diserahkan dan foto opsional tersimpan."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.sales.models import SaleOrder

        self.client.login(username='penjual_5b', password='Password123!')

        # 1x1 pixel JPEG
        dummy_img = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
            b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff'
            b'\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f'
            b'\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08'
            b'\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
        )
        photo = SimpleUploadedFile('handover.jpg', dummy_img, content_type='image/jpeg')

        response = self.client.post(
            f'/pesanan/{self.order.code}/serah-terima/',
            {'handover_photo': photo, 'notes': 'Diserahkan langsung di pos satpam'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, SaleOrder.Status.DISERAHKAN)
        self.assertIsNotNone(self.order.handed_over_at)
        self.assertIn('handover_photo', self.order.listing_snapshot)

    def test_buyer_cannot_mark_handover(self):
        """Pembeli tidak dapat menandai serah terima (hanya penjual)."""
        self.client.login(username='pembeli_5b', password='Password123!')
        response = self.client.post(f'/pesanan/{self.order.code}/serah-terima/', follow=True)
        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, SaleOrder.Status.DIBAYAR)
        messages = list(response.context['messages'])
        self.assertTrue(any('Hanya penjual' in str(m) for m in messages))

    def test_buyer_confirm_received(self):
        """Pembeli konfirmasi penerimaan barang -> pesanan selesai dan dana cair ke penjual."""
        from apps.sales.services import mark_sale_order_handed_over
        from apps.sales.models import SaleOrder, SaleItem
        from apps.payments.models import WalletTransaction

        mark_sale_order_handed_over(self.order, user=self.seller)

        self.client.login(username='pembeli_5b', password='Password123!')
        response = self.client.post(f'/pesanan/{self.order.code}/konfirmasi/', follow=True)
        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, SaleOrder.Status.SELESAI)
        self.assertIsNotNone(self.order.completed_at)

        # Status item menjadi terjual
        self.order.item.refresh_from_db()
        self.assertEqual(self.order.item.status, SaleItem.Status.TERJUAL)

        # Dompet penjual terkredit
        wallet_tx = WalletTransaction.objects.filter(sale_order=self.order, kind=WalletTransaction.Kind.KREDIT_PENJUALAN).first()
        self.assertIsNotNone(wallet_tx)
        self.assertEqual(wallet_tx.user, self.seller)
        self.assertEqual(wallet_tx.amount, self.order.net_to_seller)

    def test_buyer_dispute_submission(self):
        """Pembeli mengajukan sengketa barang dengan alasan dan bukti foto."""
        from apps.sales.services import mark_sale_order_handed_over
        from apps.sales.models import SaleOrder
        from django.core.files.uploadedfile import SimpleUploadedFile

        mark_sale_order_handed_over(self.order, user=self.seller)

        self.client.login(username='pembeli_5b', password='Password123!')

        dummy_img = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
            b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff'
            b'\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f'
            b'\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08'
            b'\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
        )
        photo1 = SimpleUploadedFile('evidence1.jpg', dummy_img, content_type='image/jpeg')

        response = self.client.post(
            f'/pesanan/{self.order.code}/sengketa/',
            {
                'issue_type': 'rusak',
                'reason': 'Kabel konektor patah dan modul microcontroller tidak merespons.',
                'dispute_photos': [photo1]
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, SaleOrder.Status.SENGKETA)
        self.assertIn('rusak', self.order.cancel_reason)
        self.assertIn('dispute_photos', self.order.listing_snapshot)

    def test_auto_settlement_after_48h_inspection(self):
        """Batas waktu inspeksi 48 jam terlewati tanpa sanggahan -> otomatis selesai lewat process_deadlines."""
        from apps.sales.services import mark_sale_order_handed_over
        from apps.sales.models import SaleOrder

        mark_sale_order_handed_over(self.order, user=self.seller)
        self.order.refresh_from_db()

        # Set handed_over_at ke 50 jam yang lalu
        self.order.handed_over_at = timezone.now() - timedelta(hours=50)
        self.order.save(update_fields=['handed_over_at'])

        results = run_process_deadlines()
        self.assertGreaterEqual(results.get('auto_completed_sales', 0), 1)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, SaleOrder.Status.SELESAI)
        self.assertIsNotNone(self.order.completed_at)


class SaleOrderSettlementCancellationTest(TestCase):
    """Pengujian penyelesaian pesanan, pembatalan, refund, dan invarian buku besar (Fase 8B Butir 6)."""

    def setUp(self):
        from apps.sales.services import create_sale_order, mark_sale_order_paid
        from apps.payments.models import LedgerEntry, WalletTransaction

        self.campus = Campus.objects.create(name='ITERA', short_name='ITERA', city='Lampung Selatan')
        self.seller = User.objects.create_user(username='penjual_6b', email='p6b@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim='121140080')

        self.buyer = User.objects.create_user(username='pembeli_6b', email='b6b@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.buyer, campus=self.campus, nim='121140081')

        self.cat = Category.objects.create(name='Buku', slug='buku-6b', scope=Category.Scope.JUAL)
        self.item = SaleItem.objects.create(
            owner=self.seller,
            category=self.cat,
            title='Buku Kalkulus Purcel Edisi 9',
            slug='buku-kalkulus-purcel-6b',
            description='Kondisi bersih tanpa coretan tinta.',
            condition='baik',
            price=100_000,
            pickup_area='Perpustakaan Lt 2',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60),
        )

        self.client = Client()

    def test_settle_sale_order_idempotent_and_ledger_balanced(self):
        """Penyelesaian pesanan bersifat idempoten, memotong komisi 5% (min Rp2.000), dan buku besar seimbang."""
        from apps.sales.services import create_sale_order, mark_sale_order_paid, mark_sale_order_handed_over, settle_sale_order
        from apps.sales.models import SaleItem, SaleOrder
        from apps.payments.models import LedgerEntry, WalletTransaction

        order = create_sale_order(
            item=self.item,
            buyer=self.buyer,
            terms_accepted=True,
            ip_address='127.0.0.1',
            user_agent='TestRunner'
        )
        mark_sale_order_paid(order)
        mark_sale_order_handed_over(order, user=self.seller)

        # Hitung komisi 5% dari 100.000 = 5.000 (>= 2.000)
        expected_commission = 5_000
        expected_net = 95_000

        # Eksekusi pertama
        settled_1 = settle_sale_order(order, actor=self.buyer)
        self.assertEqual(settled_1.status, SaleOrder.Status.SELESAI)
        self.assertEqual(settled_1.commission, expected_commission)
        self.assertEqual(settled_1.net_to_seller, expected_net)
        self.assertIsNotNone(settled_1.completed_at)

        # Status item berubah menjadi terjual
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, SaleItem.Status.TERJUAL)

        # Eksekusi kedua (idempoten)
        settled_2 = settle_sale_order(order, actor=self.buyer)
        self.assertEqual(settled_2.status, SaleOrder.Status.SELESAI)

        # Verifikasi buku besar pesanan
        entries = order.ledger_entries.all()
        masuk_entries = entries.filter(kind=LedgerEntry.Kind.MASUK_PENJUALAN)
        komisi_entries = entries.filter(kind=LedgerEntry.Kind.KELUAR_KOMISI_PENJUALAN)
        payout_entries = entries.filter(kind=LedgerEntry.Kind.KELUAR_PAYOUT_PENJUAL)

        self.assertEqual(masuk_entries.count(), 1)
        self.assertEqual(masuk_entries.first().amount, 100_000)

        self.assertEqual(komisi_entries.count(), 1)
        self.assertEqual(komisi_entries.first().amount, expected_commission)

        self.assertEqual(payout_entries.count(), 1)
        self.assertEqual(payout_entries.first().amount, expected_net)

        total_masuk = sum(e.amount for e in entries if e.kind.startswith('masuk_'))
        total_keluar = sum(e.amount for e in entries if e.kind.startswith('keluar_'))
        self.assertEqual(total_masuk, total_keluar)

        # Dompet penjual terkredit persis satu transaksi
        wallet_txs = WalletTransaction.objects.filter(sale_order=order, kind=WalletTransaction.Kind.KREDIT_PENJUALAN)
        self.assertEqual(wallet_txs.count(), 1)
        self.assertEqual(wallet_txs.first().amount, expected_net)
        self.assertEqual(wallet_txs.first().user, self.seller)

    def test_cancel_sale_order_before_payment(self):
        """Pembatalan sebelum pembayaran bebas dilakukan pembeli/penjual, barang kembali aktif tanpa saldo terpengaruh."""
        from apps.sales.services import create_sale_order, cancel_sale_order
        from apps.sales.models import SaleItem, SaleOrder
        from apps.payments.models import WalletTransaction, LedgerEntry

        order = create_sale_order(
            item=self.item,
            buyer=self.buyer,
            terms_accepted=True,
            ip_address='127.0.0.1',
            user_agent='TestRunner'
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, SaleItem.Status.DIPESAN)

        # Pembeli membatalkan
        cancelled = cancel_sale_order(order, user=self.buyer, reason="Berubah pikiran")
        self.assertEqual(cancelled.status, SaleOrder.Status.DIBATALKAN)
        self.assertEqual(cancelled.cancelled_by, self.buyer)

        # Barang kembali aktif
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, SaleItem.Status.AKTIF)

        # Tidak ada mutasi dompet atau buku besar
        self.assertEqual(WalletTransaction.objects.filter(sale_order=order).count(), 0)
        self.assertEqual(LedgerEntry.objects.filter(sale_order=order).count(), 0)

    def test_cancel_sale_order_after_payment_refunds_buyer(self):
        """Pembatalan setelah bayar oleh penjual me-refund 100% ke dompet pembeli dan buku besar seimbang."""
        from apps.sales.services import create_sale_order, mark_sale_order_paid, cancel_sale_order
        from apps.sales.models import SaleItem, SaleOrder
        from apps.payments.models import WalletTransaction, LedgerEntry

        order = create_sale_order(
            item=self.item,
            buyer=self.buyer,
            terms_accepted=True,
            ip_address='127.0.0.1',
            user_agent='TestRunner'
        )
        mark_sale_order_paid(order)

        # Penjual membatalkan pesanan (misal barang rusak saat persiapan temu)
        cancelled = cancel_sale_order(order, user=self.seller, reason="Stok fisik rusak saat disiapkan")
        self.assertEqual(cancelled.status, SaleOrder.Status.DIBATALKAN)
        self.assertEqual(cancelled.cancelled_by, self.seller)

        # Barang kembali aktif
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, SaleItem.Status.AKTIF)

        # Dompet pembeli menerima kredit_refund_penjualan
        refund_tx = WalletTransaction.objects.filter(sale_order=order, kind=WalletTransaction.Kind.KREDIT_REFUND_PENJUALAN).first()
        self.assertIsNotNone(refund_tx)
        self.assertEqual(refund_tx.user, self.buyer)
        self.assertEqual(refund_tx.amount, 100_000)

        # Buku besar seimbang: masuk_penjualan (100.000) == keluar_refund_penyewa (100.000)
        total_masuk = sum(order.ledger_entries.filter(kind__startswith='masuk_').values_list('amount', flat=True))
        total_keluar = sum(order.ledger_entries.filter(kind__startswith='keluar_').values_list('amount', flat=True))
        self.assertEqual(total_masuk, 100_000)
        self.assertEqual(total_keluar, 100_000)

    def test_buyer_cannot_cancel_after_payment(self):
        """Pembeli tidak dapat membatalkan pesanan sepihak setelah pembayaran diverifikasi."""
        from apps.sales.services import create_sale_order, mark_sale_order_paid, cancel_sale_order, SaleOrderPermissionError
        from apps.sales.models import SaleOrder

        order = create_sale_order(
            item=self.item,
            buyer=self.buyer,
            terms_accepted=True,
            ip_address='127.0.0.1',
            user_agent='TestRunner'
        )
        mark_sale_order_paid(order)

        # Pembeli mencoba membatalkan -> ditolak
        with self.assertRaises(SaleOrderPermissionError):
            cancel_sale_order(order, user=self.buyer, reason="Ingin membatalkan")


class SaleOrderDashboardAndWalletTest(TestCase):
    """Pengujian integrasi pesanan jual beli ke Dashboard dan Dompet (Fase 8B Butir 7)."""

    def setUp(self):
        from apps.sales.services import create_sale_order, mark_sale_order_paid, mark_sale_order_handed_over, settle_sale_order

        self.campus = Campus.objects.create(name='ITERA', short_name='ITERA', city='Lampung Selatan')
        self.seller = User.objects.create_user(username='penjual_7b', email='p7b@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim='121140090')

        self.buyer = User.objects.create_user(username='pembeli_7b', email='b7b@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.buyer, campus=self.campus, nim='121140091')

        self.cat = Category.objects.create(name='Aksesoris', slug='aksesoris-7b', scope=Category.Scope.JUAL)
        self.item = SaleItem.objects.create(
            owner=self.seller,
            category=self.cat,
            title='Lampu Belajar Meja Minimalis',
            slug='lampu-belajar-meja-7b',
            description='Cahaya warm white 3 tingkat kecerahan.',
            condition='seperti_baru',
            price=80_000,
            pickup_area='Gedung C ITERA',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60),
        )

        self.order = create_sale_order(
            item=self.item,
            buyer=self.buyer,
            terms_accepted=True,
            ip_address='127.0.0.1',
            user_agent='TestRunner'
        )
        self.client = Client()

    def test_dashboard_displays_buyer_purchase_orders(self):
        """Dashboard pembeli memuat sub-tab pembelian dengan pesanan beli dan link ke detail pesanan."""
        self.client.login(username='pembeli_7b', password='Password123!')
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

        # Konteks memuat daftar pesanan beli
        self.assertIn('my_sale_purchases', response.context)
        self.assertEqual(len(response.context['my_sale_purchases']), 1)
        self.assertEqual(response.context['my_sale_purchases'][0].code, self.order.code)

        # HTML memuat kode pesanan dan link
        content = response.content.decode('utf-8')
        self.assertIn(self.order.code, content)
        self.assertIn(f'/pesanan/{self.order.code}/', content)
        self.assertIn('Lampu Belajar Meja Minimalis', content)

    def test_dashboard_displays_seller_sales_orders(self):
        """Dashboard penjual memuat sub-tab penjualan dengan pesanan jual masuk."""
        self.client.login(username='penjual_7b', password='Password123!')
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

        # Konteks memuat daftar pesanan penjualan
        self.assertIn('my_sale_orders', response.context)
        self.assertEqual(len(response.context['my_sale_orders']), 1)
        self.assertEqual(response.context['my_sale_orders'][0].code, self.order.code)

        content = response.content.decode('utf-8')
        self.assertIn(self.order.code, content)
        self.assertIn(f'/pesanan/{self.order.code}/', content)

    def test_wallet_displays_sale_proceeds_and_order_link(self):
        """Dompet menampilkan jenis mutasi kredit penjualan dengan tautan ke pesanan #KJ-XXXXXX."""
        from apps.sales.services import mark_sale_order_paid, mark_sale_order_handed_over, settle_sale_order

        mark_sale_order_paid(self.order)
        mark_sale_order_handed_over(self.order, user=self.seller)
        settle_sale_order(self.order, actor=self.buyer)

        self.client.login(username='penjual_7b', password='Password123!')
        response = self.client.get('/dompet/')
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn(self.order.code, content)
        self.assertIn(f'/pesanan/{self.order.code}/', content)
        self.assertIn('Kredit Penjualan', content)


class SaleOrderComprehensiveEdgeCasesTest(TransactionTestCase):
    """
    Pengujian komprehensif seluruh kasus batas, invariant, dan konkurensi (Fase 8B Butir 9):
    1. Pencegahan pembelian ganda konkuren (race condition / double purchase prevention via select_for_update).
    2. Idempotensi sinkronisasi pembayaran dan penyelesaian dana (idempotent settlement).
    3. Invarian buku besar di semua jalur siklus hidup (settle, cancel sebelum bayar, cancel setelah bayar).
    4. Validasi server-side persetujuan S&K wajib.
    5. Proteksi anti-IDOR di seluruh endpoint /pesanan/.
    6. Batas waktu inspeksi 48 jam & auto-cancel janji temu 7 hari (process_deadlines).
    7. Kekekalan snapshot listing (immutable snapshot).
    """

    def setUp(self):
        self.campus = Campus.objects.create(name='Institut Teknologi Sumatera', short_name='ITERA', city='Lampung Selatan')
        self.seller = User.objects.create_user(username='seller_edge', email='seller_edge@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim='121140095')

        self.buyer1 = User.objects.create_user(username='buyer1_edge', email='b1_edge@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.buyer1, campus=self.campus, nim='121140096')

        self.buyer2 = User.objects.create_user(username='buyer2_edge', email='b2_edge@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.buyer2, campus=self.campus, nim='121140097')

        self.third_user = User.objects.create_user(username='third_user_edge', email='t3_edge@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.third_user, campus=self.campus, nim='121140098')

        self.category = Category.objects.create(name='Peralatan Belajar', slug='peralatan-belajar-edge', scope=Category.Scope.JUAL)
        self.item = SaleItem.objects.create(
            owner=self.seller,
            category=self.category,
            title='Kalkulator Ilmiah CASIO fx-991EX',
            slug='kalkulator-ilmiah-casio-fx-991ex',
            description='Kondisi mulus tombol responsif fungsi normal.',
            condition='seperti_baru',
            price=150_000,
            pickup_area='Perpustakaan Lt 1',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60),
        )

        self.terms = TermsVersion.objects.create(
            version="1.0",
            term_type=TermsVersion.Type.JUAL_PEMBELI,
            content="Syarat dan ketentuan pembelian resmi kampus.",
            is_active=True
        )
        self.client = Client()

    def test_concurrent_double_purchase_prevents_duplicate_orders(self):
        """Pencegahan pembelian ganda konkuren: select_for_update memastikan hanya 1 pesanan yang terbentuk."""
        import threading

        results = []
        errors = []

        def buy_item(buyer):
            try:
                order = create_sale_order(self.item, buyer, terms_accepted=True)
                results.append(order)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=buy_item, args=(self.buyer1,))
        t2 = threading.Thread(target=buy_item, args=(self.buyer2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Tepat satu berhasil dan satu gagal
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], SaleOrderError)
        self.assertEqual(SaleOrder.objects.filter(item=self.item).count(), 1)

        # Percobaan pembelian berikutnya secara sekuensial juga pasti ditolak
        with self.assertRaises(SaleOrderError):
            create_sale_order(self.item, self.third_user, terms_accepted=True)

    def test_idempotent_payment_sync_and_settlement(self):
        """Penyelesaian dana pesanan idempoten: panggilan berulang tidak memicu mutasi duplikat."""
        from apps.payments.models import LedgerEntry, WalletTransaction

        order = create_sale_order(self.item, self.buyer1, terms_accepted=True)
        mark_sale_order_paid(order)
        mark_sale_order_handed_over(order, user=self.seller)

        # Penyelesaian pertama
        settle_sale_order(order, actor=self.buyer1)
        order.refresh_from_db()
        self.assertEqual(order.status, SaleOrder.Status.SELESAI)

        komisi_count_1 = LedgerEntry.objects.filter(sale_order=order, kind=LedgerEntry.Kind.KELUAR_KOMISI_PENJUALAN).count()
        payout_count_1 = LedgerEntry.objects.filter(sale_order=order, kind=LedgerEntry.Kind.KELUAR_PAYOUT_PENJUAL).count()
        wallet_count_1 = WalletTransaction.objects.filter(sale_order=order, kind=WalletTransaction.Kind.KREDIT_PENJUALAN).count()

        self.assertEqual(komisi_count_1, 1)
        self.assertEqual(payout_count_1, 1)
        self.assertEqual(wallet_count_1, 1)

        # Penyelesaian kedua (idempoten)
        settle_sale_order(order, actor=self.buyer1)
        komisi_count_2 = LedgerEntry.objects.filter(sale_order=order, kind=LedgerEntry.Kind.KELUAR_KOMISI_PENJUALAN).count()
        payout_count_2 = LedgerEntry.objects.filter(sale_order=order, kind=LedgerEntry.Kind.KELUAR_PAYOUT_PENJUAL).count()
        wallet_count_2 = WalletTransaction.objects.filter(sale_order=order, kind=WalletTransaction.Kind.KREDIT_PENJUALAN).count()

        self.assertEqual(komisi_count_2, 1)
        self.assertEqual(payout_count_2, 1)
        self.assertEqual(wallet_count_2, 1)

    def test_ledger_invariants_across_all_lifecycle_paths(self):
        """Invarian buku besar seimbang matematis di semua jalur siklus hidup pesanan."""
        from apps.payments.models import LedgerEntry, WalletTransaction

        # Jalur 1: Selesai Normal -> Masuk == Keluar Komisi + Keluar Payout
        order1 = create_sale_order(self.item, self.buyer1, terms_accepted=True)
        mark_sale_order_paid(order1)
        mark_sale_order_handed_over(order1, user=self.seller)
        settle_sale_order(order1)

        masuk_1 = sum(order1.ledger_entries.filter(kind__startswith='masuk_').values_list('amount', flat=True))
        keluar_1 = sum(order1.ledger_entries.filter(kind__startswith='keluar_').values_list('amount', flat=True))
        self.assertEqual(masuk_1, keluar_1)
        self.assertEqual(masuk_1, 150_000)

        # Jalur 2: Batal Sebelum Bayar -> 0 entri buku besar, barang kembali aktif
        item2 = SaleItem.objects.create(
            owner=self.seller, category=self.category, title='Item Cancel Path 2',
            slug='item-cancel-path-2', price=100_000, status=SaleItem.Status.AKTIF
        )
        order2 = create_sale_order(item2, self.buyer1, terms_accepted=True)
        cancel_sale_order(order2, user=self.buyer1, reason="Batal sebelum bayar")
        order2.refresh_from_db()
        item2.refresh_from_db()
        self.assertEqual(order2.status, SaleOrder.Status.DIBATALKAN)
        self.assertEqual(item2.status, SaleItem.Status.AKTIF)
        self.assertEqual(order2.ledger_entries.count(), 0)

        # Jalur 3: Batal Setelah Bayar -> Masuk == Keluar Refund, saldo pembeli kembali
        item3 = SaleItem.objects.create(
            owner=self.seller, category=self.category, title='Item Cancel Path 3',
            slug='item-cancel-path-3', price=120_000, status=SaleItem.Status.AKTIF
        )
        order3 = create_sale_order(item3, self.buyer1, terms_accepted=True)
        mark_sale_order_paid(order3)
        cancel_sale_order(order3, user=self.seller, reason="Stok fisik rusak")
        order3.refresh_from_db()
        item3.refresh_from_db()
        self.assertEqual(order3.status, SaleOrder.Status.DIBATALKAN)
        self.assertEqual(item3.status, SaleItem.Status.AKTIF)

        masuk_3 = sum(order3.ledger_entries.filter(kind__startswith='masuk_').values_list('amount', flat=True))
        keluar_3 = sum(order3.ledger_entries.filter(kind__startswith='keluar_').values_list('amount', flat=True))
        self.assertEqual(masuk_3, keluar_3)
        self.assertEqual(masuk_3, 120_000)
        self.assertTrue(WalletTransaction.objects.filter(user=self.buyer1, sale_order=order3, kind=WalletTransaction.Kind.KREDIT_REFUND_PENJUALAN).exists())

    def test_server_side_mandatory_terms_validation(self):
        """Validasi sisi server mewajibkan centang S&K pembeli sebelum pesanan terbentuk."""
        self.client.login(username='buyer1_edge', password='Password123!')

        # POST tanpa persetujuan S&K -> ditolak dan diarahkan kembali dengan flash message
        res_fail = self.client.post(f'/jual-beli/{self.item.slug}/beli/', data={})
        self.assertEqual(res_fail.status_code, 302)
        self.assertRedirects(res_fail, f'/jual-beli/{self.item.slug}/')
        self.assertEqual(SaleOrder.objects.filter(item=self.item).count(), 0)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, SaleItem.Status.AKTIF)

        res_follow = self.client.post(f'/jual-beli/{self.item.slug}/beli/', data={}, follow=True)
        self.assertContains(res_follow, "Syarat &amp; Ketentuan Pembeli")

        # POST dengan persetujuan S&K -> berhasil 302 ke detail pesanan
        res_ok = self.client.post(f'/jual-beli/{self.item.slug}/beli/', data={'terms_accepted': '1'})
        self.assertEqual(res_ok.status_code, 302)
        order = SaleOrder.objects.filter(item=self.item).first()
        self.assertIsNotNone(order)
        self.assertRedirects(res_ok, f'/pesanan/{order.code}/')
        self.assertTrue(SaleAgreement.objects.filter(order=order).exists())

    def test_anti_idor_protection_all_sale_order_views(self):
        """Semua endpoint /pesanan/ terlindungi dari akses ilegal pihak ketiga (anti-IDOR)."""
        order = create_sale_order(self.item, self.buyer1, terms_accepted=True)
        mark_sale_order_paid(order)

        # Login sebagai pengguna ketiga (bukan pembeli, bukan penjual, bukan staf)
        self.client.login(username='third_user_edge', password='Password123!')

        code = order.code
        # 1. Detail pesanan
        res = self.client.get(f'/pesanan/{code}/')
        self.assertEqual(res.status_code, 403)

        # 2. Perjanjian digital
        res = self.client.get(f'/pesanan/{code}/perjanjian/')
        self.assertEqual(res.status_code, 403)

        # 3. Pengaturan jadwal temu
        res = self.client.post(f'/pesanan/{code}/jadwal-temu/', data={'notes': 'Hacked'})
        self.assertEqual(res.status_code, 403)

        # 4. Serah terima
        res = self.client.post(f'/pesanan/{code}/serah-terima/', data={})
        self.assertEqual(res.status_code, 403)

        # 5. Konfirmasi terima
        res = self.client.post(f'/pesanan/{code}/konfirmasi/', data={})
        self.assertEqual(res.status_code, 403)

        # 6. Sengketa
        res = self.client.post(f'/pesanan/{code}/sengketa/', data={'reason': 'Illegal dispute'})
        self.assertEqual(res.status_code, 403)

        # 7. Pembatalan
        res = self.client.post(f'/pesanan/{code}/batal/', data={'cancel_reason': 'Illegal cancel'})
        self.assertEqual(res.status_code, 403)

        # 8. Bayar
        res = self.client.post(f'/midtrans/pesanan/{code}/bayar/', data={})
        self.assertEqual(res.status_code, 403)

    def test_auto_complete_after_48h_inspection_and_7d_meetup_timeout(self):
        """Batas waktu inspeksi 48 jam & kedaluwarsa temu 7 hari diproses otomatis oleh process_deadlines."""
        # 1. Pesanan diserahkan > 48 jam yang lalu
        order_inspected = create_sale_order(self.item, self.buyer1, terms_accepted=True)
        mark_sale_order_paid(order_inspected)
        mark_sale_order_handed_over(order_inspected, user=self.seller)
        order_inspected.handed_over_at = timezone.now() - timedelta(hours=50)
        order_inspected.save(update_fields=['handed_over_at'])

        # 2. Pesanan dibayar > 7 hari yang lalu tanpa serah terima
        item_unmet = SaleItem.objects.create(
            owner=self.seller, category=self.category, title='Item Unmet 7 Hari',
            slug='item-unmet-7-hari', price=200_000, status=SaleItem.Status.AKTIF
        )
        order_unmet = create_sale_order(item_unmet, self.buyer2, terms_accepted=True)
        mark_sale_order_paid(order_unmet)
        order_unmet.paid_at = timezone.now() - timedelta(days=8)
        order_unmet.save(update_fields=['paid_at'])

        # Jalankan process_deadlines
        results = run_process_deadlines()
        self.assertGreaterEqual(results['auto_completed_sales'], 1)
        self.assertGreaterEqual(results['expired_sale_meetups'], 1)

        order_inspected.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(order_inspected.status, SaleOrder.Status.SELESAI)
        self.assertEqual(self.item.status, SaleItem.Status.TERJUAL)

        order_unmet.refresh_from_db()
        item_unmet.refresh_from_db()
        self.assertEqual(order_unmet.status, SaleOrder.Status.DIBATALKAN)
        self.assertEqual(item_unmet.status, SaleItem.Status.AKTIF)

    def test_immutable_listing_snapshot_verification(self):
        """Snapshot listing bersifat permanen dan tidak terpengaruh perubahan objek barang setelahnya."""
        order = create_sale_order(self.item, self.buyer1, terms_accepted=True)

        original_title = self.item.title
        original_price = self.item.price
        original_desc = self.item.description

        # Penjual atau admin mengedit barang asli
        self.item.title = "Judul Baru Yang Diedit Setelah Pembelian"
        self.item.price = 999_999
        self.item.description = "Deskripsi diubah secara manipulatif"
        self.item.save(update_fields=['title', 'price', 'description'])

        order.refresh_from_db()

        # Invarian: snapshot di pesanan tetap sama persis dengan kondisi saat dipesan
        self.assertEqual(order.price_snapshot, original_price)
        self.assertEqual(order.listing_snapshot['title'], original_title)
        self.assertEqual(order.listing_snapshot['price'], original_price)
        self.assertEqual(order.listing_snapshot['description'], original_desc)


class SaleDisputeResolutionTest(TestCase):
    """Pengujian komprehensif alur sengketa, mediasi admin, dan dampaknya terhadap tingkat penjual."""

    def setUp(self):
        self.campus = Campus.objects.create(name="Institut Teknologi Sumatera", short_name="ITERA", city="Lampung Selatan")
        self.meeting_point = MeetingPoint.objects.create(campus=self.campus, name="Gerbang Utama ITERA", is_public=True)
        self.seller = User.objects.create_user(username="seller_dispute", email="seller_dispute@univ.ac.id", password="password123", is_verified_student=True)
        self.buyer = User.objects.create_user(username="buyer_dispute", email="buyer_dispute@univ.ac.id", password="password123", is_verified_student=True)
        self.third_user = User.objects.create_user(username="third_dispute", email="third@univ.ac.id", password="password123", is_verified_student=True)
        self.admin = User.objects.create_superuser(username="admin_dispute", email="admin@univ.ac.id", password="password123")

        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim="12114001")
        StudentProfile.objects.create(user=self.buyer, campus=self.campus, nim="12114002")
        StudentProfile.objects.create(user=self.third_user, campus=self.campus, nim="12114003")

        self.category, _ = Category.objects.get_or_create(slug='elektronik-jual', defaults={'name': 'Elektronik', 'scope': Category.Scope.JUAL})
        self.terms = TermsVersion.objects.create(
            version="1.0",
            term_type=TermsVersion.Type.JUAL_PEMBELI,
            content="Syarat dan ketentuan pembelian resmi.",
            is_active=True
        )

        self.item = SaleItem.objects.create(
            owner=self.seller,
            category=self.category,
            title="Mikrokontroler ESP32 NodeMCU",
            slug="mikrokontroler-esp32-nodemcu",
            price=100_000,
            condition="seperti_baru",
            pickup_area="Gedung C ITERA",
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60),
        )

    def _create_handed_over_order(self):
        from apps.sales.services import (
            create_sale_order, mark_sale_order_paid,
            set_sale_order_meetup, mark_sale_order_handed_over
        )
        order = create_sale_order(self.item, self.buyer, terms_accepted=True)
        mark_sale_order_paid(order)
        set_sale_order_meetup(order, user=self.seller, meetup_at=timezone.now(), meeting_point=self.meeting_point)
        mark_sale_order_handed_over(order, user=self.seller, notes="Barang telah diserahkan")
        return order

    def test_open_sale_dispute_creation(self):
        """Pembeli membuka sengketa barang tidak sesuai deskripsi."""
        from apps.sales.services import open_sale_dispute
        from apps.sales.models import SaleDispute

        order = self._create_handed_over_order()
        open_sale_dispute(
            order=order,
            user=self.buyer,
            reason="Layar LCD tergores dalam dan tombol power macet.",
            dispute_type=SaleDispute.Type.TIDAK_SESUAI_DESKRIPSI
        )

        order.refresh_from_db()
        self.assertEqual(order.status, SaleOrder.Status.SENGKETA)
        self.assertTrue(hasattr(order, 'dispute'))

        dispute = order.dispute
        self.assertEqual(dispute.opened_by, self.buyer)
        self.assertEqual(dispute.dispute_type, SaleDispute.Type.TIDAK_SESUAI_DESKRIPSI)
        self.assertEqual(dispute.status, SaleDispute.Status.TERBUKA)
        self.assertIn("Layar LCD tergores", dispute.reason)

    def test_open_sale_dispute_seller_absent_records_violation(self):
        """Sengketa jenis penjual_tidak_hadir mencatat pelanggaran dan menurunkan tingkat penjual."""
        from apps.sales.services import open_sale_dispute, get_seller_tier
        from apps.sales.models import SaleDispute

        order = self._create_handed_over_order()
        open_sale_dispute(
            order=order,
            user=self.buyer,
            reason="Penjual tidak hadir di gerbang utama setelah ditunggu 45 menit.",
            dispute_type=SaleDispute.Type.PENJUAL_TIDAK_HADIR
        )

        dispute = SaleDispute.objects.get(order=order)
        self.assertTrue(dispute.seller_violation_recorded)

        # Penjual dengan 20 transaksi selesai tetapi ada catatan pelanggaran tidak bisa menjadi tepercaya
        self.seller._seller_completed_sales = 20
        self.seller._seller_rating = 5.0
        self.assertEqual(get_seller_tier(self.seller), 'baru')

    def test_resolve_dispute_full_refund_to_buyer(self):
        """Putusan admin refund penuh: dompet pembeli menerima dana penuh, pesanan dibatalkan, barang kembali aktif."""
        from apps.sales.services import open_sale_dispute, resolve_sale_dispute
        from apps.sales.models import SaleDispute
        from apps.payments.models import LedgerEntry, WalletTransaction

        order = self._create_handed_over_order()
        open_sale_dispute(order, self.buyer, reason="Barang rusak total", dispute_type=SaleDispute.Type.RUSAK_SAAT_SERAH_TERIMA)
        dispute = SaleDispute.objects.get(order=order)

        resolve_sale_dispute(dispute, decision=SaleDispute.Decision.REFUND_PEMBELI, notes="Barang rusak parah, refund pembeli.", admin_user=self.admin)

        dispute.refresh_from_db()
        order.refresh_from_db()
        self.item.refresh_from_db()

        self.assertEqual(dispute.status, SaleDispute.Status.SELESAI)
        self.assertEqual(dispute.decision, SaleDispute.Decision.REFUND_PEMBELI)
        self.assertEqual(order.status, SaleOrder.Status.DIBATALKAN)
        self.assertEqual(self.item.status, SaleItem.Status.AKTIF)

        # Cek kredit dompet pembeli
        buyer_tx = WalletTransaction.objects.filter(sale_order=order, user=self.buyer).first()
        self.assertIsNotNone(buyer_tx)
        self.assertEqual(buyer_tx.amount, 100_000)
        self.assertEqual(buyer_tx.kind, WalletTransaction.Kind.KREDIT_REFUND_PENJUALAN)

        # Cek buku besar seimbang
        ledger = LedgerEntry.objects.filter(sale_order=order, kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA).first()
        self.assertIsNotNone(ledger)
        self.assertEqual(ledger.amount, 100_000)

    def test_resolve_dispute_full_payout_to_seller(self):
        """Putusan admin lepas ke penjual: penjual menerima payout (dikurangi komisi 5%), pesanan selesai."""
        from apps.sales.services import open_sale_dispute, resolve_sale_dispute
        from apps.sales.models import SaleDispute
        from apps.payments.models import LedgerEntry, WalletTransaction

        order = self._create_handed_over_order()
        open_sale_dispute(order, self.buyer, reason="Laporan klaim palsu", dispute_type=SaleDispute.Type.LAINNYA)
        dispute = SaleDispute.objects.get(order=order)

        resolve_sale_dispute(dispute, decision=SaleDispute.Decision.LEPAS_KE_PENJUAL, notes="Klaim pembeli tidak beralasan.", admin_user=self.admin)

        dispute.refresh_from_db()
        order.refresh_from_db()
        self.item.refresh_from_db()

        self.assertEqual(dispute.status, SaleDispute.Status.SELESAI)
        self.assertEqual(dispute.decision, SaleDispute.Decision.LEPAS_KE_PENJUAL)
        self.assertEqual(order.status, SaleOrder.Status.SELESAI)
        self.assertEqual(self.item.status, SaleItem.Status.TERJUAL)

        # Komisi 5% dari 100.000 = 5.000, payout = 95.000
        seller_tx = WalletTransaction.objects.filter(sale_order=order, user=self.seller).first()
        self.assertIsNotNone(seller_tx)
        self.assertEqual(seller_tx.amount, 95_000)
        self.assertEqual(seller_tx.kind, WalletTransaction.Kind.KREDIT_PENJUALAN)

    def test_resolve_dispute_partial_split_preserves_invariants(self):
        """Putusan admin sebagian (split): refund pembeli + komisi + payout penjual = total pesanan."""
        from apps.sales.services import open_sale_dispute, resolve_sale_dispute
        from apps.sales.models import SaleDispute
        from apps.payments.models import LedgerEntry, WalletTransaction

        order = self._create_handed_over_order()
        open_sale_dispute(order, self.buyer, reason="Kabel bawaan hilang", dispute_type=SaleDispute.Type.TIDAK_SESUAI_DESKRIPSI)
        dispute = SaleDispute.objects.get(order=order)

        # Admin memutuskan refund pembeli Rp30.000, sisa Rp70.000 ke penjual
        resolve_sale_dispute(
            dispute,
            decision=SaleDispute.Decision.SEBAGIAN,
            nominal=30_000,
            notes="Potongan harga Rp30.000 untuk kabel yang hilang.",
            admin_user=self.admin
        )

        dispute.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(dispute.status, SaleDispute.Status.SELESAI)
        self.assertEqual(order.status, SaleOrder.Status.SELESAI)

        # Dompet pembeli dapat 30.000
        buyer_tx = WalletTransaction.objects.filter(sale_order=order, user=self.buyer).first()
        self.assertEqual(buyer_tx.amount, 30_000)

        # Dompet penjual dapat 70.000 - komisi (5% dari 70.000 = 3.500) = 66.500
        seller_tx = WalletTransaction.objects.filter(sale_order=order, user=self.seller).first()
        self.assertEqual(seller_tx.amount, 66_500)

        # Buku besar seimbang presisi
        outflows = LedgerEntry.objects.filter(
            sale_order=order,
            kind__in=[
                LedgerEntry.Kind.KELUAR_REFUND_PENYEWA,
                LedgerEntry.Kind.KELUAR_KOMISI_PENJUALAN,
                LedgerEntry.Kind.KELUAR_PAYOUT_PENJUAL,
            ]
        )
        total_out = sum(entry.amount for entry in outflows)
        self.assertEqual(total_out, 100_000)

    def test_resolve_dispute_idempotency(self):
        """Eksekusi ganda pada sengketa yang telah selesai tidak menduplikasi transaksi."""
        from apps.sales.services import open_sale_dispute, resolve_sale_dispute
        from apps.sales.models import SaleDispute
        from apps.payments.models import WalletTransaction

        order = self._create_handed_over_order()
        open_sale_dispute(order, self.buyer, reason="Masalah fisik", dispute_type=SaleDispute.Type.RUSAK_SAAT_SERAH_TERIMA)
        dispute = SaleDispute.objects.get(order=order)

        resolve_sale_dispute(dispute, decision=SaleDispute.Decision.REFUND_PEMBELI, admin_user=self.admin)
        tx_count_before = WalletTransaction.objects.filter(sale_order=order).count()

        # Panggilan kedua
        resolve_sale_dispute(dispute, decision=SaleDispute.Decision.REFUND_PEMBELI, admin_user=self.admin)
        tx_count_after = WalletTransaction.objects.filter(sale_order=order).count()

        self.assertEqual(tx_count_before, tx_count_after)

    def test_admin_dispute_display_methods(self):
        """Metode display SaleDisputeAdmin menghasilkan komponen HTML yang valid."""
        from apps.sales.admin import SaleDisputeAdmin
        from apps.sales.models import SaleDispute
        from apps.sales.services import open_sale_dispute
        from django.contrib.admin.sites import AdminSite

        order = self._create_handed_over_order()
        open_sale_dispute(order, self.buyer, reason="Kamera berdebu", dispute_type=SaleDispute.Type.TIDAK_SESUAI_DESKRIPSI)
        dispute = SaleDispute.objects.get(order=order)

        admin_instance = SaleDisputeAdmin(SaleDispute, AdminSite())

        comp_html = admin_instance.snapshot_comparison_display(dispute)
        self.assertIn("Snapshot Saat Dipesan", comp_html)
        self.assertIn(self.item.title, comp_html)

        timeline_html = admin_instance.timeline_display(dispute)
        self.assertIn("Pesanan Dibuat", timeline_html)
        self.assertIn("Sengketa Diajukan", timeline_html)

        agreement_html = admin_instance.agreement_display(dispute)
        self.assertIn(order.code, agreement_html)


class SaleReviewTest(TestCase):
    """Pengujian komprehensif ulasan dua arah jual beli dan pembaruan reputasi penjual (Fase 8C Butir 2)."""

    def setUp(self):
        self.campus = Campus.objects.create(name="Institut Teknologi Sumatera", short_name="ITERA", city="Lampung Selatan")
        self.meeting_point = MeetingPoint.objects.create(campus=self.campus, name="Gedung Kuliah Umum", is_public=True)
        self.seller = User.objects.create_user(username="seller_review", email="seller_rev@univ.ac.id", password="password123", is_verified_student=True)
        self.buyer = User.objects.create_user(username="buyer_review", email="buyer_rev@univ.ac.id", password="password123", is_verified_student=True)
        self.other_user = User.objects.create_user(username="other_review", email="other_rev@univ.ac.id", password="password123", is_verified_student=True)

        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim="121140001")
        StudentProfile.objects.create(user=self.buyer, campus=self.campus, nim="121140002")
        StudentProfile.objects.create(user=self.other_user, campus=self.campus, nim="121140003")

        self.category, _ = Category.objects.get_or_create(slug='elektronik-jual', defaults={'name': 'Elektronik', 'scope': Category.Scope.JUAL})
        self.terms = TermsVersion.objects.create(
            version="1.0",
            term_type=TermsVersion.Type.JUAL_PEMBELI,
            content="Syarat & Ketentuan Jual Beli ITERA",
            is_active=True
        )

        self.item = SaleItem.objects.create(
            owner=self.seller,
            category=self.category,
            title="Kalkulator Saintifik Casio fx-991EX",
            description="Kondisi prima lengkap dengan box asli.",
            condition=SaleItem.Condition.SEPERTI_BARU,
            price=200_000,
            original_price=350_000,
            pickup_area="ITERA Kampus",
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=30),
        )

    def _create_completed_order(self, item=None):
        from apps.sales.services import set_sale_order_meetup
        itm = item or self.item
        order = create_sale_order(
            item=itm,
            buyer=self.buyer,
            terms_accepted=True,
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0"
        )
        mark_sale_order_paid(order, payment_type='gopay')
        order.refresh_from_db()
        set_sale_order_meetup(order, user=self.seller, meetup_at=timezone.now(), meeting_point=self.meeting_point)
        order.refresh_from_db()
        mark_sale_order_handed_over(order, user=self.seller, notes="Diserahkan langsung")
        order.refresh_from_db()
        confirm_sale_order_received(order, user=self.buyer)
        order.refresh_from_db()
        return order

    def test_sale_review_bidirectional_creation(self):
        """Pembeli dan penjual dapat saling mengulas secara dua arah setelah pesanan selesai."""
        order = self._create_completed_order()

        # Pembeli mengulas penjual
        buyer_review = create_sale_review(
            order=order,
            reviewer=self.buyer,
            rating=5,
            comment="Barang sangat mulus dan sesuai deskripsi. Penjual ramah!"
        )
        self.assertEqual(buyer_review.role, SaleReview.Role.PENJUAL)
        self.assertEqual(buyer_review.reviewee, self.seller)
        self.assertEqual(buyer_review.rating, 5)

        # Penjual mengulas pembeli
        seller_review = create_sale_review(
            order=order,
            reviewer=self.seller,
            rating=5,
            comment="Pembeli tepat waktu di titik temu GKU."
        )
        self.assertEqual(seller_review.role, SaleReview.Role.PEMBELI)
        self.assertEqual(seller_review.reviewee, self.buyer)
        self.assertEqual(seller_review.rating, 5)

        self.assertEqual(order.reviews.count(), 2)

    def test_sale_review_only_after_completed(self):
        """Ulasan ditolak jika pesanan belum selesai."""
        order = create_sale_order(
            item=self.item,
            buyer=self.buyer,
            terms_accepted=True
        )
        with self.assertRaises(SaleOrderStateError):
            create_sale_review(order, self.buyer, rating=5, comment="Belum bayar tapi mau ulas")

    def test_sale_review_permission_and_one_time_only(self):
        """Pihak ketiga dilarang mengulas, dan pengulas tidak dapat mengirim ulasan dua kali."""
        order = self._create_completed_order()

        # Pihak ketiga
        with self.assertRaises(SaleOrderPermissionError):
            create_sale_review(order, self.other_user, rating=5, comment="Saya bukan siapa-siapa")

        # Pembeli mengulas
        create_sale_review(order, self.buyer, rating=4, comment="Bagus")

        # Pembeli mencoba mengulas lagi -> ditolak
        with self.assertRaises(SaleOrderValidationError):
            create_sale_review(order, self.buyer, rating=5, comment="Mau ubah ulasan")

    def test_sale_review_validation(self):
        """Validasi rating di luar rentang 1-5 dan batas komentar 300 karakter."""
        order = self._create_completed_order()

        with self.assertRaises(SaleOrderValidationError):
            create_sale_review(order, self.buyer, rating=0, comment="Rating nol")

        with self.assertRaises(SaleOrderValidationError):
            create_sale_review(order, self.buyer, rating=6, comment="Rating enam")

        long_comment = "a" * 301
        with self.assertRaises(SaleOrderValidationError):
            create_sale_review(order, self.buyer, rating=5, comment=long_comment)

    def test_sale_review_updates_seller_tier(self):
        """Ulasan jual beli memutakhirkan reputasi penjual (rating rata-rata) dan tingkat penjual."""
        # Awalnya penjual berstatus 'baru'
        self.assertEqual(get_seller_tier(self.seller), 'baru')

        # Buat 5 barang terjual untuk seller
        for i in range(5):
            itm = SaleItem.objects.create(
                owner=self.seller,
                category=self.category,
                title=f"Barang Ke-{i+1}",
                description="Deskripsi",
                condition=SaleItem.Condition.BAIK,
                price=50_000,
                pickup_area="ITERA",
                status=SaleItem.Status.AKTIF,
                expires_at=timezone.now() + timedelta(days=30),
            )
            ord_i = self._create_completed_order(item=itm)
            create_sale_review(ord_i, reviewer=self.buyer, rating=5, comment="Puas sekali!")

        # Sekarang penjual memiliki 5 penjualan selesai dan rating rata-rata 5.0 -> 'tepercaya'
        self.assertEqual(get_seller_tier(self.seller), 'tepercaya')

    def test_sale_order_review_post_view(self):
        """Endpoint HTTP POST /pesanan/<kode>/ulasan/ menerima ulasan dan redirect ke detail."""
        order = self._create_completed_order()
        client = Client()
        client.force_login(self.buyer)

        response = client.post(
            f"/pesanan/{order.code}/ulasan/",
            {'rating': '5', 'comment': 'Transaksi cepat dan barang mulus.'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(SaleReview.objects.filter(order=order, reviewer=self.buyer, rating=5).exists())

    def test_user_profile_displays_seller_tier(self):
        """Halaman profil publik menyertakan tingkat penjual dalam konteks dan tampilan."""
        client = Client()
        response = client.get(f"/profil/{self.seller.username}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('seller_tier', response.context)
        self.assertContains(response, "Penjual baru")


class SaleItemModerationTest(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name='Institut Teknologi Sumatera', short_name='ITERA')
        self.admin = User.objects.create_superuser(username='admin_mod', email='admin_mod@kampus.id', password='Password123!')
        self.seller = User.objects.create_user(username='penjual_mod', email='penjual_mod@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim='121140081')

        self.reporter = User.objects.create_user(username='pelapor_mod', email='pelapor_mod@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.reporter, campus=self.campus, nim='121140082')

        self.category = Category.objects.create(name='Buku', slug='buku-mod', scope=Category.Scope.JUAL)
        self.item = SaleItem.objects.create(
            owner=self.seller,
            category=self.category,
            title='Buku Kalkulus Purcel Edisi 9 Asli',
            slug='buku-kalkulus-purcel-edisi-9',
            description='Kondisi sangat rapi, tidak ada coretan, original.',
            condition=SaleItem.Condition.BAIK,
            price=95_000,
            pickup_area='Perpustakaan Gedung C',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60),
        )

    def test_report_sale_item_flow(self):
        """Pengguna lain dapat melaporkan listing barang jualan via endpoint dan service."""
        from apps.sales.models import SaleItemReport
        from apps.sales.services import create_sale_item_report, SaleOrderValidationError

        client = Client()
        client.force_login(self.reporter)

        # 1. POST pelaporan listing via view
        resp = client.post(
            f"/jual-beli/{self.item.slug}/lapor/",
            {
                'reason': 'indikasi_penipuan',
                'notes': 'Foto tampak diambil dari marketplace luar dan harga janggal.'
            },
            follow=True
        )
        self.assertEqual(resp.status_code, 200)

        report = SaleItemReport.objects.filter(item=self.item, reporter=self.reporter).first()
        self.assertIsNotNone(report)
        self.assertEqual(report.reason, 'indikasi_penipuan')
        self.assertEqual(report.status, SaleItemReport.Status.MENUNGGU)

        # 2. Pemilik tidak boleh melaporkan barang miliknya sendiri
        client_seller = Client()
        client_seller.force_login(self.seller)
        resp_seller = client_seller.post(
            f"/jual-beli/{self.item.slug}/lapor/",
            {'reason': 'lainnya', 'notes': 'Test sendiri'},
            follow=True
        )
        self.assertEqual(resp_seller.status_code, 200)
        self.assertFalse(SaleItemReport.objects.filter(item=self.item, reporter=self.seller).exists())

        # 3. Validasi service jika alasan tidak valid
        with self.assertRaises(SaleOrderValidationError):
            create_sale_item_report(self.item, self.reporter, reason='alasan_ngawur')

    def test_admin_takedown_sale_item(self):
        """Admin dapat menurunkan listing barang jualan dengan alasan wajib dan notifikasi terkirim."""
        from apps.sales.models import SaleItemReport
        from apps.sales.services import takedown_sale_item
        from apps.core.models import Notification

        # Buat laporan terlebih dahulu
        report = SaleItemReport.objects.create(
            item=self.item,
            reporter=self.reporter,
            reason='barang_terlarang',
            notes='Barang ini mencurigakan.',
            status=SaleItemReport.Status.MENUNGGU
        )

        # Admin melakukan takedown
        takedown_reason = "Melanggar ketentuan barang terlarang kampus."
        takedown_sale_item(self.item, self.admin, takedown_reason)

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, SaleItem.Status.NONAKTIF)
        self.assertEqual(self.item.takedown_reason, takedown_reason)
        self.assertEqual(self.item.takedown_by, self.admin)
        self.assertIsNotNone(self.item.takedown_at)

        # Laporan pending otomatis diselesaikan
        report.refresh_from_db()
        self.assertEqual(report.status, SaleItemReport.Status.DITINDAKLANJUTI)
        self.assertEqual(report.reviewed_by, self.admin)
        self.assertIn("Melanggar ketentuan", report.action_taken)

        # Notifikasi terkirim ke penjual
        notif = Notification.objects.filter(user=self.seller).first()
        self.assertIsNotNone(notif)
        self.assertIn("Diturunkan", notif.title)
        self.assertIn(takedown_reason, notif.message)

    def test_get_staff_operational_stats_includes_reports(self):
        """Statistik operasional staf mencatat jumlah laporan jual beli yang berstatus menunggu."""
        from apps.sales.models import SaleItemReport
        from apps.core.services import get_staff_operational_stats

        # Status awal
        stats_before = get_staff_operational_stats()
        initial_reports = stats_before['sale_report_queue_count']
        initial_total = stats_before['total_queue']

        # Tambahkan satu laporan
        SaleItemReport.objects.create(
            item=self.item,
            reporter=self.reporter,
            reason='deskripsi_palsu',
            notes='Deskripsi tidak sesuai foto.',
            status=SaleItemReport.Status.MENUNGGU
        )

        stats_after = get_staff_operational_stats()
        self.assertEqual(stats_after['sale_report_queue_count'], initial_reports + 1)
        self.assertEqual(stats_after['total_queue'], initial_total + 1)

    def test_prohibited_keywords_rejected_on_edit(self):
        """Penyaringan kata terlarang tetap aktif dan memblokir saat penjual mengubah listing."""
        from apps.sales.forms import SaleItemForm

        form_data = {
            'category': self.category.id,
            'title': 'Buku Kalkulus + Bonus Vape Liquid Pods',
            'description': 'Kondisi mulus dan original.',
            'condition': 'baik',
            'flaws': '',
            'included_items': 'Dus buku',
            'reason_for_sale': 'Sudah lulus kalkulus',
            'price': 95_000,
            'pickup_area': 'Gedung C ITERA',
        }

        form = SaleItemForm(data=form_data, instance=self.item, user=self.seller)
        self.assertFalse(form.is_valid())
        self.assertTrue(any('terlarang' in err for err in form.non_field_errors()))

        # Pastikan data di database tidak berubah
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, 'Buku Kalkulus Purcel Edisi 9 Asli')

        # Edit valid berhasil
        valid_form_data = form_data.copy()
        valid_form_data['title'] = 'Buku Kalkulus Purcel Edisi 9 Edisi Revisi'
        valid_form = SaleItemForm(data=valid_form_data, instance=self.item, user=self.seller)
        self.assertTrue(valid_form.is_valid())
        saved_item = valid_form.save()
        self.assertEqual(saved_item.title, 'Buku Kalkulus Purcel Edisi 9 Edisi Revisi')

    def test_admin_sale_report_actions(self):
        """Aksi admin pada changelist SaleItemReportAdmin berfungsi menandai ditindaklanjuti/diabaikan."""
        from apps.sales.models import SaleItemReport
        from apps.sales.admin import SaleItemReportAdmin
        from django.contrib.admin.sites import AdminSite

        report1 = SaleItemReport.objects.create(
            item=self.item,
            reporter=self.reporter,
            reason='harga_tidak_wajar',
            status=SaleItemReport.Status.MENUNGGU
        )
        report2 = SaleItemReport.objects.create(
            item=self.item,
            reporter=self.reporter,
            reason='lainnya',
            status=SaleItemReport.Status.MENUNGGU
        )

        admin_instance = SaleItemReportAdmin(SaleItemReport, AdminSite())

        # Buat dummy request dengan session & message middleware
        from django.test import RequestFactory
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware
        factory = RequestFactory()
        req = factory.get('/')
        req.user = self.admin
        SessionMiddleware(lambda r: None).process_request(req)
        MessageMiddleware(lambda r: None).process_request(req)

        # Action: tandai ditindaklanjuti
        admin_instance.tandai_ditindaklanjuti(req, SaleItemReport.objects.filter(id=report1.id))
        report1.refresh_from_db()
        self.assertEqual(report1.status, SaleItemReport.Status.DITINDAKLANJUTI)

        # Action: tandai diabaikan
        admin_instance.tandai_diabaikan(req, SaleItemReport.objects.filter(id=report2.id))
        report2.refresh_from_db()
        self.assertEqual(report2.status, SaleItemReport.Status.DIABAIKAN)


class SaleOfferStructuredTests(TestCase):
    """Pengujian sistem tawar harga terstruktur dengan saklar SALE_OFFERS_ENABLED (Butir 5)."""

    def setUp(self):
        self.campus = Campus.objects.create(name='Institut Teknologi Sumatera', short_name='ITERA_OFFER')
        self.category = Category.objects.create(name='Buku', slug='buku-offer', scope=Category.Scope.JUAL)
        self.seller = User.objects.create_user(
            username='seller_offer',
            email='seller_offer@kampus.ac.id',
            password='password123',
            is_active=True,
            is_verified_student=True
        )
        self.buyer = User.objects.create_user(
            username='buyer_offer',
            email='buyer_offer@kampus.ac.id',
            password='password123',
            is_active=True,
            is_verified_student=True
        )
        self.buyer2 = User.objects.create_user(
            username='buyer2_offer',
            email='buyer2_offer@kampus.ac.id',
            password='password123',
            is_active=True,
            is_verified_student=True
        )
        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim='121140091')
        StudentProfile.objects.create(user=self.buyer, campus=self.campus, nim='121140092')
        StudentProfile.objects.create(user=self.buyer2, campus=self.campus, nim='121140093')
        self.item = SaleItem.objects.create(
            owner=self.seller,
            category=self.category,
            title='Kalkulus Purcel Edisi 9',
            description='Buku asli mulus',
            condition=SaleItem.Condition.BAIK,
            price=100_000,
            pickup_area='Perpustakaan Pusat',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60)
        )

    def test_offer_disabled_by_default(self):
        """Saklar SALE_OFFERS_ENABLED bawaannya False; seluruh endpoint & service offer mengembalikan Forbidden / error."""
        from apps.sales.services import create_sale_offer, SaleOrderPermissionError
        from apps.sales.models import SaleOffer

        self.assertFalse(getattr(settings, 'SALE_OFFERS_ENABLED', False))

        # Service raises error
        with self.assertRaises(SaleOrderPermissionError):
            create_sale_offer(self.item, self.buyer, 80_000)

        # HTTP views return 403 Forbidden
        self.client.login(username='buyer_offer', password='password123')
        resp = self.client.post(f'/jual-beli/{self.item.slug}/tawar/', {'offered_price': 80_000})
        self.assertEqual(resp.status_code, 403)

        # Dummy offer for testing accept/reject forbidden
        dummy_offer = SaleOffer.objects.create(
            item=self.item,
            buyer=self.buyer,
            offered_price=80_000,
            expires_at=timezone.now() + timedelta(hours=24)
        )

        self.client.login(username='seller_offer', password='password123')
        resp_acc = self.client.post(f'/jual-beli/tawaran/{dummy_offer.id}/terima/')
        self.assertEqual(resp_acc.status_code, 403)

        resp_rej = self.client.post(f'/jual-beli/tawaran/{dummy_offer.id}/tolak/')
        self.assertEqual(resp_rej.status_code, 403)

    @override_settings(SALE_OFFERS_ENABLED=True)
    def test_offer_validations_when_enabled(self):
        """Validasi tawar harga: tidak bisa menawar barang sendiri, harga harus < listing dan > 0."""
        from apps.sales.services import create_sale_offer, SaleOrderValidationError
        from django.core.exceptions import ValidationError
        from apps.sales.models import SaleOffer

        # Penjual menawar barang sendiri
        with self.assertRaises(SaleOrderValidationError):
            create_sale_offer(self.item, self.seller, 80_000)

        # Harga >= listing
        with self.assertRaises(SaleOrderValidationError):
            create_sale_offer(self.item, self.buyer, 100_000)

        with self.assertRaises(SaleOrderValidationError):
            create_sale_offer(self.item, self.buyer, 120_000)

        # Harga <= 0
        with self.assertRaises(SaleOrderValidationError):
            create_sale_offer(self.item, self.buyer, 0)

        # Model clean validation
        offer_invalid = SaleOffer(item=self.item, buyer=self.buyer, offered_price=100_000, expires_at=timezone.now())
        with self.assertRaises(ValidationError):
            offer_invalid.clean()

    @override_settings(SALE_OFFERS_ENABLED=True)
    def test_create_and_replace_offer_when_enabled(self):
        """Pembeli membuat tawaran aktif; pengajuan tawaran kedua membatalkan tawaran pertama."""
        from apps.sales.services import create_sale_offer
        from apps.sales.models import SaleOffer

        offer1 = create_sale_offer(self.item, self.buyer, 80_000)
        self.assertEqual(offer1.status, SaleOffer.Status.MENUNGGU)
        self.assertEqual(offer1.offered_price, 80_000)
        self.assertTrue(offer1.expires_at > timezone.now())

        # Buat tawaran baru dari pembeli yang sama
        offer2 = create_sale_offer(self.item, self.buyer, 85_000)
        offer1.refresh_from_db()

        self.assertEqual(offer1.status, SaleOffer.Status.DIBATALKAN)
        self.assertEqual(offer2.status, SaleOffer.Status.MENUNGGU)
        self.assertEqual(offer2.offered_price, 85_000)

    @override_settings(SALE_OFFERS_ENABLED=True)
    def test_seller_accept_offer_creates_order_at_agreed_price(self):
        """Penjual menyetujui tawaran: membuat SaleOrder dengan price_snapshot sesuai tawaran dan batas bayar 6 jam."""
        from apps.sales.services import create_sale_offer, accept_sale_offer
        from apps.sales.models import SaleOffer, SaleOrder

        offer1 = create_sale_offer(self.item, self.buyer, 80_000)
        offer_other = create_sale_offer(self.item, self.buyer2, 75_000)

        order = accept_sale_offer(offer1, seller=self.seller)

        offer1.refresh_from_db()
        offer_other.refresh_from_db()
        self.item.refresh_from_db()

        # Tawaran diterima dan terhubung ke order
        self.assertEqual(offer1.status, SaleOffer.Status.DITERIMA)
        self.assertEqual(offer1.order, order)

        # Tawaran saingan otomatis ditolak
        self.assertEqual(offer_other.status, SaleOffer.Status.DITOLAK)

        # Status barang berubah menjadi dipesan
        self.assertEqual(self.item.status, SaleItem.Status.DIPESAN)

        # Pesanan dibuat dengan harga yang disepakati (Rp80.000, bukan Rp100.000)
        self.assertEqual(order.price_snapshot, 80_000)
        self.assertEqual(order.status, SaleOrder.Status.MENUNGGU_PEMBAYARAN)
        # Komisi 5% dari 80.000 = 4.000, net = 76.000
        self.assertEqual(order.commission, 4_000)
        self.assertEqual(order.net_to_seller, 76_000)
        # Batas bayar 6 jam
        self.assertTrue(order.reserved_until > timezone.now() + timedelta(hours=5))

    @override_settings(SALE_OFFERS_ENABLED=True)
    def test_seller_reject_and_buyer_cancel_offer(self):
        """Penjual dapat menolak tawaran, dan pembeli dapat membatalkan tawarannya sendiri."""
        from apps.sales.services import create_sale_offer, reject_sale_offer, cancel_sale_offer
        from apps.sales.models import SaleOffer

        # Test Reject
        offer_rej = create_sale_offer(self.item, self.buyer, 70_000)
        reject_sale_offer(offer_rej, seller=self.seller)
        offer_rej.refresh_from_db()
        self.assertEqual(offer_rej.status, SaleOffer.Status.DITOLAK)

        # Test Cancel by Buyer
        offer_can = create_sale_offer(self.item, self.buyer2, 75_000)
        cancel_sale_offer(offer_can, buyer=self.buyer2)
        offer_can.refresh_from_db()
        self.assertEqual(offer_can.status, SaleOffer.Status.DIBATALKAN)








