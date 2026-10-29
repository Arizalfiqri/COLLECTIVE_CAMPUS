from django.test import TestCase, Client
from django.conf import settings
from apps.accounts.models import User, StudentProfile, Campus
from apps.catalog.models import Category, Item
from apps.sales.models import SaleItem
from django.utils import timezone
from datetime import timedelta


class HomePhase9Tests(TestCase):
    def setUp(self):
        self.client = Client()
        self.campus = Campus.objects.create(name='Institut Teknologi Sumatera', short_name='ITERA')
        self.user = User.objects.create_user(
            username='homeuser',
            email='homeuser@itera.ac.id',
            password='password123',
            full_name='Home Tester'
        )
        StudentProfile.objects.create(
            user=self.user,
            campus=self.campus,
            nim='121140001',
            major='Teknik Informatika'
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
            expires_at=timezone.now() + timedelta(days=30)
        )

    def test_home_renders_both_sections_on_initial_load(self):
        """Memastikan beranda memuat seksi Disewakan terbaru dan Dijual terbaru secara jelas."""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Disewakan terbaru')
        self.assertContains(res, 'Dijual terbaru')
        self.assertContains(res, 'Kamera Canon 700D')
        self.assertContains(res, 'Kalkulus Purcell Edisi 9')

    def test_home_single_tagline_present(self):
        """Memastikan tagline resmi tampil konsisten di beranda."""
        res = self.client.get('/')
        self.assertContains(res, getattr(settings, 'SITE_TAGLINE', 'Saling sewa, saling jual, saling bantu.'))

    def test_search_form_clean_catalog_redirect(self):
        """Memastikan form pencarian bersih dan luas mengarah langsung ke katalog."""
        res = self.client.get('/')
        self.assertContains(res, 'id="hero-search"')
        self.assertContains(res, 'name="q"')
        self.assertContains(res, 'aria-label="Cari barang"')

    def test_calculator_section_has_single_title_and_tabs(self):
        """Memastikan seksi hitung biaya satu judul dan memiliki tiga tab: Biaya sewa, Penghasilan sewa, Penghasilan jual (Fase 10 Butir 5)."""
        res = self.client.get('/')
        self.assertContains(res, 'Hitung biaya sewa &amp; jual')
        self.assertContains(res, 'Biaya sewa')
        self.assertContains(res, 'Penghasilan sewa')
        self.assertContains(res, 'Penghasilan jual')
        # Memastikan opsi tingkat penyewa tidak terpotong
        self.assertContains(res, 'Baru (maks. Rp750.000)')
        self.assertContains(res, 'Tepercaya (maks. Rp1.500.000)')

    def test_security_section_covers_rental_and_sales(self):
        """Memastikan seksi keamanan mencakup sewa dan jual beli."""
        res = self.client.get('/')
        self.assertContains(res, 'Mengapa transaksi di')
        self.assertContains(res, 'Verifikasi identitas mahasiswa (KTM)')
        self.assertContains(res, 'Perjanjian digital &amp; penahanan pembayaran')
        self.assertContains(res, 'Dokumentasi foto serah terima fisik')
        self.assertContains(res, 'Dana Gotong Royong untuk sewa')

    def test_owner_cta_has_two_buttons(self):
        """Memastikan CTA pemilik memiliki dua tombol: Sewakan barang dan Jual barang."""
        res = self.client.get('/')
        self.assertContains(res, 'Sewakan barang')
        self.assertContains(res, 'Jual barang')
        self.assertContains(res, 'Rp207.000')
        self.assertContains(res, 'Rp95.000')
