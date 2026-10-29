from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.catalog.models import Category, Item
from apps.payments.models import WalletTransaction


class ResponsivePrimitivesUnitTest(TestCase):
    """
    Unit test gerbang kualitas Fase 7H:
    1. Tag <meta name="viewport"> wajib ada dan valid pada setiap template utama.
    2. Komponen pembungkus tabel .table-responsive ada pada halaman bertabel.
    """
    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.user = User.objects.create_user(
            username='mhs_responsive',
            email='mhs_resp@kampus.id',
            password='Password123!',
            full_name='Mahasiswa Responsif'
        )
        self.staff_user = User.objects.create_user(
            username='staff_responsive',
            email='staff_resp@kampus.id',
            password='Password123!',
            full_name='Staf Responsif',
            is_staff=True,
            is_superuser=True
        )
        self.cat = Category.objects.create(name='Elektronik', slug='elektronik')
        self.item = Item.objects.create(
            owner=self.user,
            category=self.cat,
            title='Kamera Mirrorless Sony A6400',
            slug='kamera-mirrorless-sony-a6400',
            description='Kamera untuk dokumentasi kampus',
            price_per_day=50000,
            estimated_value=12000000,
            is_active=True
        )
        # Transaksi dompet agar tabel mutasi dirender dengan pembungkus table-responsive
        WalletTransaction.objects.create(
            user=self.user,
            kind=WalletTransaction.Kind.KREDIT_PAYOUT,
            amount=50000,
            note='Pendapatan sewa kamera'
        )

    def test_meta_viewport_public_pages(self):
        """Halaman publik utama memuat tag meta viewport yang valid."""
        routes = [
            reverse('home'),
            reverse('catalog:item_list'),
            reverse('catalog:item_detail', kwargs={'slug': self.item.slug}),
            reverse('core:tentang'),
            reverse('core:bantuan'),
            reverse('core:kontak'),
            reverse('accounts:login'),
            reverse('accounts:register'),
        ]
        for url in routes:
            with self.subTest(url=url):
                res = self.client.get(url)
                self.assertEqual(res.status_code, 200)
                content = res.content.decode('utf-8')
                self.assertIn('<meta name="viewport"', content)
                self.assertIn('width=device-width', content)
                self.assertIn('initial-scale=1.0', content)

    def test_meta_viewport_authenticated_pages(self):
        """Halaman terautentikasi memuat tag meta viewport yang valid."""
        self.client.force_login(self.user)
        routes = [
            reverse('accounts:dashboard'),
            reverse('payments:wallet'),
            reverse('chat:inbox'),
            reverse('catalog:my_items'),
        ]
        for url in routes:
            with self.subTest(url=url):
                res = self.client.get(url)
                self.assertEqual(res.status_code, 200)
                content = res.content.decode('utf-8')
                self.assertIn('<meta name="viewport"', content)
                self.assertIn('width=device-width', content)

    def test_meta_viewport_admin_staff(self):
        """Kerangka admin staf memuat tag meta viewport yang valid."""
        self.client.force_login(self.staff_user)
        res = self.client.get('/admin/')
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn('<meta name="viewport"', content)
        self.assertIn('width=device-width', content)

    def test_table_responsive_wrapper_wallet(self):
        """Tabel mutasi dompet dibungkus oleh kelas .table-responsive."""
        self.client.force_login(self.user)
        res = self.client.get(reverse('payments:wallet'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        # Harus memuat pembungkus table-responsive
        self.assertIn('table-responsive', content)

    def test_table_responsive_wrapper_admin_changelist(self):
        """Tabel change_list admin dibungkus oleh kelas .table-responsive."""
        self.client.force_login(self.staff_user)
        res = self.client.get('/admin/catalog/item/')
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn('table-responsive', content)
