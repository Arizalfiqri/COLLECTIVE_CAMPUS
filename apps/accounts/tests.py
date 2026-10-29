from django.test import TestCase, Client
from django.urls import reverse
from django.http import HttpResponse
from django.contrib.messages import get_messages

from apps.accounts.models import User, StudentProfile
from apps.accounts.decorators import verified_student_required, VerifiedStudentRequiredMixin
from apps.accounts.views import dashboard_view


@verified_student_required
def dummy_protected_view(request):
    return HttpResponse("Akses Fitur Terverifikasi Berhasil")


class AccountsAuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('accounts:register')
        self.login_url = reverse('accounts:login')
        self.logout_url = reverse('accounts:logout')
        self.dashboard_url = reverse('accounts:dashboard')

    def test_registration_success(self):
        """Pendaftaran berhasil membuat User (is_email_verified=False), StudentProfile, kirim email aktivasi, dan redirect ke login."""
        data = {
            'full_name': 'Ahmad Fauzi',
            'username': 'ahmad_fauzi',
            'email': 'ahmad@kampus.ac.id',
            'phone_whatsapp': '081234567890',
            'campus_name': 'Universitas Indonesia',
            'nim': '2106789012',
            'major': 'Ilmu Komputer',
            'entry_year': 2021,
            'password': 'PasswordAman123!',
            'password_confirm': 'PasswordAman123!',
        }
        response = self.client.post(self.register_url, data)
        self.assertRedirects(response, reverse('accounts:login'))
        
        user = User.objects.get(username='ahmad_fauzi')
        self.assertEqual(user.email, 'ahmad@kampus.ac.id')
        self.assertFalse(user.is_verified_student)
        self.assertFalse(user.is_email_verified)

        profile = StudentProfile.objects.get(user=user)
        self.assertEqual(profile.nim, '2106789012')
        self.assertEqual(profile.campus_name, 'Universitas Indonesia')

    def test_registration_new_distinct_campus_sinsar(self):
        """Kampus baru dengan nama khas (misal: Institut Teknologi Sinsar) tidak terblokir oleh kampus terdaftar yang mirip awalan (Institut Teknologi Mahasiswa)."""
        from apps.accounts.models import Campus
        Campus.objects.get_or_create(name='Institut Teknologi Mahasiswa', defaults={'short_name': 'ITM', 'city': 'Bandar Lampung'})

        data = {
            'full_name': 'Bambang Sinsar',
            'username': 'bambang_sinsar',
            'email': 'bambang@sinsar.ac.id',
            'phone_whatsapp': '081234567891',
            'campus': 'Institut Teknologi Sinsar',
            'is_new_campus': '1',
            'campus_city': 'Bandar Lampung',
            'campus_short_name': 'ITS',
            'nim': '220110001',
            'major': 'Sistem Informasi',
            'entry_year': 2022,
            'password': 'PasswordAman123!',
            'password_confirm': 'PasswordAman123!',
        }
        response = self.client.post(self.register_url, data)
        self.assertRedirects(response, reverse('accounts:login'))

        # Kampus baru berhasil dibuat
        campus_obj = Campus.objects.filter(name='Institut Teknologi Sinsar').first()
        self.assertIsNotNone(campus_obj)
        self.assertEqual(campus_obj.city, 'Bandar Lampung')
        self.assertEqual(campus_obj.short_name, 'ITS')

        # Profile terhubung ke kampus baru
        user = User.objects.get(username='bambang_sinsar')
        profile = StudentProfile.objects.get(user=user)
        self.assertEqual(profile.campus, campus_obj)

    def test_registration_typo_campus_triggers_conflict(self):
        """Salah ketik nama kampus (typo nyata >= 95%, misal: Sumatra vs Sumatera) memunculkan peringatan konflik."""
        from apps.accounts.models import Campus
        Campus.objects.create(name='Institut Teknologi Sumatera', short_name='ITERA', city='Lampung Selatan')

        data = {
            'full_name': 'Rina Typo',
            'username': 'rina_typo',
            'email': 'rina@typo.ac.id',
            'phone_whatsapp': '081234567892',
            'campus': 'Institut Teknologi Sumatra',  # typo: kurang huruf 'e'
            'nim': '220110002',
            'major': 'Teknik Elektro',
            'entry_year': 2022,
            'password': 'PasswordAman123!',
            'password_confirm': 'PasswordAman123!',
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nama kampus mirip dengan kampus terdaftar &quot;Institut Teknologi Sumatera&quot;')

    def test_registration_validation_errors_bahasa_indonesia(self):
        """Validasi error wajib dalam Bahasa Indonesia."""
        # Uji password tidak cocok
        data = {
            'full_name': 'Ahmad Fauzi',
            'username': 'ahmad_fauzi',
            'email': 'ahmad@kampus.ac.id',
            'phone_whatsapp': '081234567890',
            'campus_name': 'Universitas Indonesia',
            'nim': '2106789012',
            'major': 'Ilmu Komputer',
            'entry_year': 2021,
            'password': 'PasswordAman123!',
            'password_confirm': 'PasswordBeda456!',
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Konfirmasi kata sandi tidak cocok dengan kata sandi.")

    def test_login_with_username_and_email(self):
        """Login dapat menggunakan username atau alamat email."""
        user = User.objects.create_user(
            username='budi_santoso',
            email='budi@kampus.ac.id',
            password='PasswordBudi123!'
        )

        # Login dengan username
        resp_username = self.client.post(self.login_url, {
            'username_or_email': 'budi_santoso',
            'password': 'PasswordBudi123!',
        })
        self.assertRedirects(resp_username, self.dashboard_url)
        self.client.logout()

        # Login dengan email
        resp_email = self.client.post(self.login_url, {
            'username_or_email': 'budi@kampus.ac.id',
            'password': 'PasswordBudi123!',
        })
        self.assertRedirects(resp_email, self.dashboard_url)

    def test_login_invalid_credentials_bahasa_indonesia(self):
        """Pesan error login gagal dalam Bahasa Indonesia."""
        response = self.client.post(self.login_url, {
            'username_or_email': 'user_salah',
            'password': 'PasswordSalah123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Username/email atau kata sandi tidak valid. Silakan coba lagi.")

    def test_logout(self):
        """Logout mengakhiri sesi dan kembali ke halaman utama."""
        user = User.objects.create_user(username='test_user', email='test_user@contoh.id', password='password123')
        self.client.login(username='test_user', password='password123')
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, '/')
        self.assertNotIn('_auth_user_id', self.client.session)


class VerifiedStudentRequiredDecoratorTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.verified_user = User.objects.create_user(
            username='verified_mhs',
            email='verified_mhs@kampus.ac.id',
            password='password123',
            is_verified_student=True
        )
        self.unverified_user = User.objects.create_user(
            username='unverified_mhs',
            email='unverified_mhs@kampus.ac.id',
            password='password123',
            is_verified_student=False
        )

    def test_unauthenticated_user_redirected_to_login(self):
        """Pengguna belum masuk diarahkan ke /masuk/."""
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/fitur-rahasia/')
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()

        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)

        response = dummy_protected_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/masuk/', response.url)

    def test_unverified_student_receives_exact_warning_message(self):
        """
        Pengguna belum terverifikasi KTM dialihkan ke /verifikasi-ktm/
        dengan pesan warning persis: 'Verifikasi KTM dulu untuk memasang barang atau menyewa.'
        """
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/barang/baru/')
        request.user = self.unverified_user

        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)

        response = dummy_protected_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('verification:ktm_stepper'))

        # Cek pesan warning spesifik
        messages_list = list(get_messages(request))
        self.assertTrue(any("Verifikasi KTM dulu untuk memasang barang atau menyewa." in m.message for m in messages_list))

    def test_verified_student_access_granted(self):
        """Mahasiswa terverifikasi dapat mengakses fitur secara penuh."""
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/barang/baru/')
        request.user = self.verified_user

        response = dummy_protected_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Akses Fitur Terverifikasi Berhasil")


class DashboardAndPublicProfileSalesTest(TestCase):
    def setUp(self):
        from apps.accounts.models import Campus
        from apps.catalog.models import Category
        from apps.sales.models import SaleItem, SaleOrder, SaleReview
        from apps.payments.models import WalletTransaction
        from django.utils import timezone
        from datetime import timedelta

        self.campus = Campus.objects.create(name='Institut Teknologi Sumatera', short_name='ITERA')
        self.seller = User.objects.create_user(username='penjual_d4', email='penjual_d4@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim='121140095')

        self.buyer = User.objects.create_user(username='pembeli_d4', email='pembeli_d4@kampus.id', password='Password123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.buyer, campus=self.campus, nim='121140096')

        self.category = Category.objects.create(name='Perabot Kos', slug='perabot-kos-d4', scope=Category.Scope.JUAL)

        # 1. Barang aktif
        self.active_item = SaleItem.objects.create(
            owner=self.seller,
            category=self.category,
            title='Meja Lipat Belajar Lesehan Kayu',
            slug='meja-lipat-belajar-lesehan',
            description='Kondisi mulus, kuat menahan beban laptop.',
            condition=SaleItem.Condition.SEPERTI_BARU,
            price=75_000,
            pickup_area='Asrama TB 1 ITERA',
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60),
        )

        # 2. Barang terjual
        self.sold_item = SaleItem.objects.create(
            owner=self.seller,
            category=self.category,
            title='Kipas Angin Meja Mini USB',
            slug='kipas-angin-meja-mini',
            description='Berfungsi normal, 3 kecepatan.',
            condition=SaleItem.Condition.BAIK,
            price=50_000,
            pickup_area='Kantin B',
            status=SaleItem.Status.TERJUAL,
            expires_at=timezone.now() + timedelta(days=60),
        )

        # 3. Pesanan aktif
        self.order_active = SaleOrder.objects.create(
            code='KJ-ACT001',
            item=self.active_item,
            buyer=self.buyer,
            seller=self.seller,
            status=SaleOrder.Status.DIBAYAR,
            price_snapshot=75_000,
            commission=3_750,
            net_to_seller=71_250,
            reserved_until=timezone.now() + timedelta(hours=6),
        )

        # 4. Transaksi dompet hasil penjualan
        WalletTransaction.objects.create(
            user=self.seller,
            sale_order=self.order_active,
            kind=WalletTransaction.Kind.KREDIT_PENJUALAN,
            amount=71_250,
            note='Kredit hasil penjualan barang'
        )

        # 5. Ulasan jual beli yang diterima
        SaleReview.objects.create(
            order=self.order_active,
            reviewer=self.buyer,
            reviewee=self.seller,
            role=SaleReview.Role.PENJUAL,
            rating=5,
            comment='Penjual sangat ramah dan tepat waktu saat serah terima.'
        )

    def test_dashboard_sales_summary_cards(self):
        """Dasbor menampilkan kartu ringkasan penjualan (terjual, pendapatan, pesanan aktif)."""
        client = Client()
        client.force_login(self.seller)

        response = client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

        # Cek context
        self.assertEqual(response.context['sales_sold_count'], 1)
        self.assertEqual(response.context['sales_revenue_total'], 71_250)
        self.assertEqual(response.context['active_sale_orders_count'], 1)

        # Cek HTML
        content = response.content.decode('utf-8')
        self.assertIn('Penjualan saya', content)
        self.assertIn('Terjual', content)
        self.assertIn('Pendapatan', content)
        self.assertIn('Pesanan aktif', content)
        self.assertIn('Rp71.250', content)

    def test_public_profile_displays_sale_items_and_reviews(self):
        """Profil publik menampilkan daftar barang yang dijual dan ulasan jual beli yang diterima."""
        client = Client()
        response = client.get(f"/profil/{self.seller.username}/")
        self.assertEqual(response.status_code, 200)

        # Cek context
        self.assertIn('active_sale_items', response.context)
        self.assertIn('sale_reviews_received', response.context)
        self.assertEqual(len(response.context['active_sale_items']), 1)
        self.assertEqual(len(response.context['sale_reviews_received']), 1)

        # Cek HTML
        content = response.content.decode('utf-8')
        self.assertIn('Barang yang dijual', content)
        self.assertIn('Meja Lipat Belajar Lesehan Kayu', content)
        self.assertIn('Rp75.000', content)
        self.assertIn('Ulasan jual beli', content)
        self.assertIn('Penjual sangat ramah dan tepat waktu', content)
        self.assertIn('5★', content)

    def test_wallet_page_displays_sale_credit_label_and_code(self):
        """Halaman dompet (/dompet/) menyajikan label jenis transaksi penjualan dan kode referensi pesanan."""
        client = Client()
        client.force_login(self.seller)

        response = client.get('/dompet/')
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn('Kredit Penjualan', content)
        self.assertIn('#KJ-ACT001', content)
        self.assertIn('+Rp71.250', content)

