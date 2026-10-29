import re
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import Campus, StudentProfile
from apps.payments.models import WalletTransaction
from apps.catalog.models import Category, Item
from apps.sales.models import SaleItem

User = get_user_model()


class Phase9ComprehensiveVerificationTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(
            name='Institut Teknologi Metro',
            short_name='ITM',
            city='Metro',
            is_active=True,
        )
        self.user = User.objects.create_user(
            username='user_verify',
            email='verify@itm.ac.id',
            password='Password123!',
            is_verified_student=True,
        )
        self.profile = StudentProfile.objects.create(
            user=self.user,
            campus=self.campus,
            nim='20261026',
            major='Teknik Sipil',
        )
        self.cat_rental = Category.objects.create(name='Kamera & Foto', slug='kamera-foto', scope=Category.Scope.SEWA)
        self.cat_sale = Category.objects.create(name='Buku Kuliah', slug='buku-kuliah', scope=Category.Scope.JUAL)
        self.rental_item = Item.objects.create(
            owner=self.user,
            title='Kamera Canon 700D',
            category=self.cat_rental,
            price_per_day=50000,
            estimated_value=3000000,
            is_active=True
        )
        self.sale_item = SaleItem.objects.create(
            owner=self.user,
            title='Kalkulus Purcell Edisi 9',
            category=self.cat_sale,
            price=120000,
            condition=SaleItem.Condition.SEPERTI_BARU,
            status=SaleItem.Status.AKTIF,
        )
        # Tambahkan transaksi dompet untuk pengujian dompet
        WalletTransaction.objects.create(
            user=self.user,
            kind=WalletTransaction.Kind.KREDIT_PAYOUT,
            amount=150000,
            note='Pencairan pokok sewa unit kamera',
        )

    @override_settings(SITE_NAME="PlatformMahasiswaX")
    def test_dynamic_site_name_everywhere(self):
        """Nilai SITE_NAME harus dinamis di title, footer, meta tag."""
        pages = [
            reverse('home'),
            reverse('core:tentang'),
            reverse('core:bantuan'),
            reverse('catalog:item_list'),
        ]
        for url in pages:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            content = response.content.decode('utf-8')
            self.assertIn("PlatformMahasiswaX", content, f"SITE_NAME tidak ditemukan pada {url}")
            # Verifikasi ada di meta og:site_name
            self.assertIn('content="PlatformMahasiswaX"', content, f"Meta og:site_name tidak memakai SITE_NAME pada {url}")

    def test_beranda_sewa_dan_beli_modes(self):
        """Beranda mode sewa dan beli menampilkan konten, kalkulator, dan katalog yang sesuai."""
        # Mode Sewa
        res_sewa = self.client.get(reverse('home') + '?mode=sewa')
        self.assertEqual(res_sewa.status_code, 200)
        c_sewa = res_sewa.content.decode('utf-8')
        self.assertIn('Biaya sewa', c_sewa)
        self.assertIn('Penghasilan sewa', c_sewa)
        self.assertIn('Disewakan terbaru', c_sewa)

        # Mode Beli
        res_beli = self.client.get(reverse('home') + '?mode=beli')
        self.assertEqual(res_beli.status_code, 200)
        c_beli = res_beli.content.decode('utf-8')
        self.assertIn('Penghasilan jual', c_beli)
        self.assertIn('Dijual terbaru', c_beli)

    def test_no_prohibited_words_in_rendered_public_pages(self):
        """Halaman publik tidak boleh memuat kata terlarang (Contoh, demo, prototipe, Rencana:)."""
        prohibited_patterns = [r'\bdemo\b', r'\bprototipe\b', r'\brencana:\b']
        pages = [
            reverse('home'),
            reverse('core:tentang'),
            reverse('core:bantuan'),
            reverse('catalog:item_list'),
            reverse('core:kontak'),
        ]
        for url in pages:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            content = response.content.decode('utf-8').lower()
            for pattern in prohibited_patterns:
                self.assertFalse(
                    bool(re.search(pattern, content)),
                    f"Pola terlarang '{pattern}' ditemukan pada {url}"
                )

    def test_wallet_nominal_visibility_and_classes(self):
        """Tabel dan kartu mutasi dompet harus selalu memuat nominal yang terlihat."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('payments:wallet'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Nominal Rp150.000 harus ada di desktop dan kartu mobile
        self.assertIn('150.000', content)
        self.assertIn('Saldo dompet aktif', content)
        # Tidak boleh ada class 'uppercase' pada label saldo dompet aktif
        self.assertNotRegex(
            content,
            r'class="[^"]*uppercase[^"]*">\s*Saldo dompet aktif\s*<',
            "Ditemukan class uppercase pada label Saldo dompet aktif"
        )
