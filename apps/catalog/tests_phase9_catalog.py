from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache

from apps.accounts.models import User, Campus, StudentProfile
from apps.catalog.models import Category, Item
from apps.sales.models import SaleItem


class Phase9CatalogTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

        self.campus, _ = Campus.objects.get_or_create(
            name='Institut Teknologi Mahasiswa', defaults={'short_name': 'ITM'}
        )

        self.user = User.objects.create_user(
            username='user_katalog', email='user@katalog.id', password='Password123!',
            full_name='Budi Mahasiswa', is_verified_student=True
        )
        StudentProfile.objects.create(user=self.user, nim='1201', campus=self.campus, major='Informatika')

        self.category = Category.objects.create(name='Peralatan', slug='peralatan', order=1)

        # 1 Barang Sewa Aktif
        self.item = Item.objects.create(
            owner=self.user, category=self.category, title='Proyektor Epson EB-X400',
            estimated_value=4000000, price_per_day=75000, deposit_amount=200000,
            min_days=1, max_days=5, pickup_area='Gedung Kuliah Bersama', is_active=True
        )

        # 1 Barang Jual Aktif
        self.sale_item = SaleItem.objects.create(
            owner=self.user, category=self.category, title='Kalkulus Purcell Edisi 9',
            condition='baik', price=85000, pickup_area='Kantin Fasilkom',
            status=SaleItem.Status.AKTIF
        )

        # Kampus kedua agar terdapat multi-kampus aktif
        self.campus_b = Campus.objects.create(name='Universitas Lampung', short_name='UNILA')
        self.user_b = User.objects.create_user(
            username='user_unila', email='unila@katalog.id', password='Password123!',
            full_name='Siti Mahasiswa', is_verified_student=True
        )
        StudentProfile.objects.create(user=self.user_b, nim='1202', campus=self.campus_b, major='Hukum')
        self.item_b = Item.objects.create(
            owner=self.user_b, category=self.category, title='Kamera DSLR Nikon D3500',
            estimated_value=3500000, price_per_day=80000, deposit_amount=150000,
            min_days=1, max_days=3, is_active=True
        )
        self.sale_item_b = SaleItem.objects.create(
            owner=self.user_b, category=self.category, title='Kemeja Flanel Unila',
            condition='sangat_baik', price=50000, status=SaleItem.Status.AKTIF
        )

    def tearDown(self):
        cache.clear()

    def test_rental_catalog_header_switcher_button_and_pills(self):
        """Uji katalog sewa: tidak ada pill di atas judul, switcher sewa|jual ada, tombol 'Pasang barang'."""
        response = self.client.get(reverse('catalog:item_list'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        # Tidak ada pill 'Katalog terverifikasi'
        self.assertNotIn('Katalog terverifikasi', html)

        # Tombol tunggal Pasang barang
        self.assertIn('Pasang barang', html)

        # Switcher Sewa | Jual beli
        self.assertIn('href="/barang/"', html)
        self.assertIn('href="/jual-beli/"', html)
        self.assertIn('Sewa', html)
        self.assertIn('Jual beli', html)

    def test_rental_catalog_result_count_and_campus_chips(self):
        """Uji katalog sewa: jumlah hasil pencarian 'Menampilkan X barang disewakan' dan format chip kampus."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('catalog:item_list'))
        html = response.content.decode('utf-8')

        # Jumlah hasil
        self.assertIn('Menampilkan', html)
        self.assertIn('barang disewakan', html)
        self.assertIn('1', html)

        # Format chip kampus saya: "Kampus saya (ITM)"
        self.assertIn('Kampus saya (ITM)', html)
        # Semua kampus ada
        self.assertIn('Semua kampus', html)

    def test_sales_catalog_header_switcher_button_and_pills(self):
        """Uji katalog jual beli: tidak ada pill di atas judul, switcher ada, tombol 'Pasang barang'."""
        response = self.client.get(reverse('sales:item_list'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        # Tidak ada pill 'Thrift & jual beli mahasiswa'
        self.assertNotIn('Thrift &amp; jual beli mahasiswa', html)
        self.assertNotIn('Thrift & jual beli mahasiswa', html)

        # Tombol Pasang barang (bukan Pasang barang jualan)
        self.assertIn('Pasang barang', html)
        self.assertNotIn('Pasang barang jualan', html)

        # Switcher Sewa | Jual beli
        self.assertIn('href="/barang/"', html)
        self.assertIn('href="/jual-beli/"', html)

    def test_sales_catalog_result_count_and_campus_chips(self):
        """Uji katalog jual beli: jumlah hasil 'Menampilkan X barang dijual' dan format chip kampus."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('sales:item_list'))
        html = response.content.decode('utf-8')

        # Jumlah hasil
        self.assertIn('Menampilkan', html)
        self.assertIn('barang dijual', html)
        self.assertIn('1', html)

        # Format chip kampus saya: "Kampus saya (ITM)"
        self.assertIn('Kampus saya (ITM)', html)
        self.assertIn('Semua kampus', html)
