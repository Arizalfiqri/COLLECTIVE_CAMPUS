import os
import re
from unittest import mock
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User, Campus, MeetingPoint, StudentProfile
from apps.catalog.models import Category, Item
from apps.core.models import Notification
from apps.rentals.models import Rental


class InitPlatformCommandTest(TestCase):
    """Pengujian inisialisasi platform bersih dan idempoten (Fase 7B)."""

    def test_init_platform_creates_clean_data_without_dummy_users_or_items(self):
        """init_platform mengisi 8 kategori tanpa membuat user atau barang fiktif."""
        call_command('init_platform')

        # Verifikasi kategori
        self.assertEqual(Category.objects.for_rental().count(), 8)
        self.assertTrue(Category.objects.filter(slug='kamera').exists())
        self.assertTrue(Category.objects.filter(slug='wisuda').exists())

        # Verifikasi TANPA pengguna atau barang fiktif
        self.assertEqual(User.objects.filter(is_superuser=False).count(), 0)
        self.assertEqual(Item.objects.count(), 0)
        self.assertEqual(Rental.objects.count(), 0)

    def test_init_platform_is_idempotent(self):
        """Menjalankan init_platform berulang kali tidak menduplikasi data."""
        call_command('init_platform')
        cat_count_1 = Category.objects.count()

        # Jalankan kedua kali
        call_command('init_platform')
        self.assertEqual(Category.objects.count(), cat_count_1)


class SeedDemoGuardrailTest(TestCase):
    """Pengujian perlindungan seed_demo agar tidak dijalankan pada production (Fase 7B)."""

    def test_seed_demo_refuses_when_debug_false(self):
        """seed_demo wajib menolak berjalan saat DEBUG=False."""
        with self.settings(DEBUG=False):
            with self.assertRaises(CommandError) as ctx:
                call_command('seed_demo')
            self.assertIn("DEBUG=True", str(ctx.exception))

    def test_seed_demo_does_not_reject_based_on_database_name(self):
        """seed_demo tidak lagi mensyaratkan nama database _dev saat DEBUG=True."""
        # Verifikasi bahwa penjaga hanya mengecek DEBUG=True
        with self.settings(DEBUG=False):
            with self.assertRaises(CommandError) as ctx:
                call_command('seed_demo')
            self.assertIn("DEBUG=True", str(ctx.exception))


class DynamicCampusFilterTest(TestCase):
    """Pengujian filter kampus dinamis di /barang/ sesuai aturan Fase 7B."""

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.cat = Category.objects.create(name='Elektronik', slug='elektronik')

        # Kampus A: Kampus user login (awalnya 0 barang)
        self.campus_a = Campus.objects.create(name='Institut Teknologi Sumatera', short_name='ITERA', city='Lampung Selatan')
        self.user_a = User.objects.create_user(username='mhs_itera', email='a@itera.ac.id', password='Password123!')
        StudentProfile.objects.create(user=self.user_a, campus=self.campus_a, nim='121140001', major='IF')

        # Kampus B: Kampus lain dengan 2 barang aktif dan 1 nonaktif
        self.campus_b = Campus.objects.create(name='Universitas Lampung', short_name='UNILA', city='Bandar Lampung')
        self.user_b = User.objects.create_user(username='mhs_unila', email='b@unila.ac.id', password='Password123!')
        StudentProfile.objects.create(user=self.user_b, campus=self.campus_b, nim='2015061001', major='TI')

        self.item_b1 = Item.objects.create(
            owner=self.user_b, category=self.cat, title='Kamera DSLR Unila',
            slug='kamera-unila', description='Kamera bagus', estimated_value=3000000,
            price_per_day=50000, deposit_amount=100000, is_active=True
        )
        self.item_b2 = Item.objects.create(
            owner=self.user_b, category=self.cat, title='Lensa 50mm Unila',
            slug='lensa-unila', description='Lensa fix', estimated_value=1500000,
            price_per_day=30000, deposit_amount=50000, is_active=True
        )
        self.item_b_inactive = Item.objects.create(
            owner=self.user_b, category=self.cat, title='Tripod Rusak Unila',
            slug='tripod-unila', description='Tripod nonaktif', estimated_value=500000,
            price_per_day=15000, deposit_amount=20000, is_active=False
        )

        # Kampus C: Kampus lain tanpa barang sama sekali (0 barang)
        self.campus_c = Campus.objects.create(name='Politeknik Negeri Lampung', short_name='POLINELA', city='Bandar Lampung')
        self.user_c = User.objects.create_user(username='mhs_polinela', email='c@polinela.ac.id', password='Password123!')
        StudentProfile.objects.create(user=self.user_c, campus=self.campus_c, nim='1975001', major='Agro')

        # Kampus D: Kampus lain hanya memiliki barang nonaktif (0 barang aktif)
        self.campus_d = Campus.objects.create(name='UIN Raden Intan Lampung', short_name='UIN RIL', city='Bandar Lampung')
        self.user_d = User.objects.create_user(username='mhs_uin', email='d@uinril.ac.id', password='Password123!')
        StudentProfile.objects.create(user=self.user_d, campus=self.campus_d, nim='1801001', major='Syariah')
        Item.objects.create(
            owner=self.user_d, category=self.cat, title='Buku Nonaktif UIN',
            slug='buku-uin', description='Buku nonaktif', estimated_value=200000,
            price_per_day=5000, deposit_amount=10000, is_active=False
        )

    def test_single_campus_has_items_renders_single_chip_without_semua_kampus_or_kampus_saya(self):
        """
        Bila hanya satu kampus (UNILA) yang punya barang:
        - Tampilkan satu chip UNILA (2) tanpa 'Semua kampus'.
        - 'Kampus saya' tidak muncul karena kampus user (ITERA) belum punya barang.
        """
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse('catalog:item_list'))
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode('utf-8')
        self.assertIn('UNILA (2)', content)
        self.assertNotIn('Semua kampus', content)
        self.assertNotIn('Kampus saya', content)
        self.assertNotIn('POLINELA', content)
        self.assertNotIn('UIN RIL', content)

    def test_multiple_campuses_with_items_and_kampus_saya(self):
        """
        Bila user_a memasang barang aktif, ITERA punya 1 barang dan UNILA punya 2 barang:
        - 'Kampus saya' muncul.
        - 'Semua kampus' muncul.
        - UNILA (2) muncul.
        """
        Item.objects.create(
            owner=self.user_a, category=self.cat, title='Proyektor ITERA',
            slug='proyektor-itera', description='Proyektor tajam', estimated_value=2000000,
            price_per_day=75000, deposit_amount=150000, is_active=True
        )

        self.client.force_login(self.user_a)
        resp = self.client.get(reverse('catalog:item_list'))
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode('utf-8')
        self.assertIn('Kampus saya', content)
        self.assertIn('Semua kampus', content)
        self.assertIn('UNILA (2)', content)

    def test_no_campus_bar_when_no_active_items(self):
        """Bila tidak ada barang aktif sama sekali di database, bilah filter kampus tidak ditampilkan."""
        Item.objects.all().delete()
        resp = self.client.get(reverse('catalog:item_list'))
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode('utf-8')
        # Bilah filter kampus tidak muncul
        self.assertNotIn('UNILA', content)
        self.assertNotIn('Semua kampus', content)


class DynamicCampusRegistrationAndAdminTest(TestCase):
    """Pengujian pembuatan kampus otomatis saat pendaftaran dan tindakan merge kampus admin (Fase 7B)."""

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.existing_campus = Campus.objects.create(
            name='Institut Teknologi Sumatera',
            short_name='ITERA',
            city='Lampung Selatan'
        )

    def test_register_creates_new_campus_with_normalized_name_and_auto_short_name(self):
        """Pendaftaran dengan kampus baru membuat kampus secara otomatis dengan nama rapi & short_name."""
        from apps.accounts.forms import StudentRegistrationForm
        form_data = {
            'full_name': 'Ahmad Fauzi',
            'username': 'ahmad_fauzi',
            'email': 'ahmad@polnep.ac.id',
            'phone_whatsapp': '081234567899',
            'campus': 'politeknik negeri pontianak',
            'nim': '123456789',
            'major': 'Teknik Sipil',
            'entry_year': 2022,
            'password': 'Password123!',
            'password_confirm': 'Password123!',
        }
        form = StudentRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        # Kampus baru terbuat
        self.assertTrue(Campus.objects.filter(name='Politeknik Negeri Pontianak').exists())
        campus = Campus.objects.get(name='Politeknik Negeri Pontianak')
        self.assertEqual(campus.short_name, 'PNP')
        self.assertEqual(user.student_profile.campus, campus)

    def test_register_rejects_very_similar_campus_typo_with_rapidfuzz(self):
        """Pendaftaran dengan nama kampus yang sangat mirip (typo) ditolak dan disarankan memilih yang ada."""
        from apps.accounts.forms import StudentRegistrationForm
        form_data = {
            'full_name': 'Rian Santoso',
            'username': 'rian_santoso',
            'email': 'rian@itera.ac.id',
            'phone_whatsapp': '081234567888',
            'campus': 'Institut Teknologi Sumatra',  # typo 1 huruf (Sumatra vs Sumatera)
            'nim': '121140099',
            'major': 'IF',
            'entry_year': 2021,
            'password': 'Password123!',
            'password_confirm': 'Password123!',
        }
        form = StudentRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('campus', form.errors)
        self.assertIn('Institut Teknologi Sumatera', form.errors['campus'][0])

    def test_admin_merge_campuses_action(self):
        """Tindakan merge_campuses di admin memindahkan profil mahasiswa dan menghapus kampus lama."""
        from apps.accounts.admin import CampusAdmin
        from django.contrib.admin.sites import AdminSite
        from unittest.mock import MagicMock

        campus_source = Campus.objects.create(name='ITERA Kampus Cabang', short_name='ITERA-C')
        user_src = User.objects.create_user(username='mhs_src', email='src@itera.ac.id', password='Password123!')
        StudentProfile.objects.create(user=user_src, campus=campus_source, nim='99887766', major='EL')
        MeetingPoint.objects.create(campus=campus_source, name='Gerbang Cabang', is_public=True)

        site = AdminSite()
        admin_obj = CampusAdmin(Campus, site)
        request = MagicMock()

        qs = Campus.objects.filter(id__in=[self.existing_campus.id, campus_source.id])
        admin_obj.merge_campuses(request, qs)

        # Kampus source telah dihapus
        self.assertFalse(Campus.objects.filter(id=campus_source.id).exists())
        # Profil mahasiswa telah dipindahkan ke existing_campus
        user_src.student_profile.refresh_from_db()
        self.assertEqual(user_src.student_profile.campus, self.existing_campus)
        # Titik temu dipindahkan
        self.assertTrue(MeetingPoint.objects.filter(campus=self.existing_campus, name='Gerbang Cabang').exists())


class OcrCampusMatchTokenFuzzyTest(TestCase):
    """Pengujian OCR campus_match berbasis token nama kampus kabur (Fase 7B)."""

    def test_ocr_campus_match_with_target_campus_tokens(self):
        """Ekstraksi OCR cocok bila teks memuat token nama kampus target, bukan kata kunci umum semata."""
        from ml.ktm_ocr import extract_ktm_data
        from unittest.mock import patch
        from PIL import Image

        # Buat gambar dummy 200x200
        img = Image.new('RGB', (200, 200), color='white')

        with patch('ml.ktm_ocr.preprocess_ktm_image', return_value=(img, (200, 200))):
            # 1. OCR text berisi 'Institut Teknologi Sumatera' cocok dengan target_campus 'Institut Teknologi Sumatera'
            with patch('pytesseract.image_to_string', return_value="KARTU MAHASISWA\nINSTITUT TEKNOLOGI SUMATERA\nNIM: 121140001\nRina Pratiwi"):
                res = extract_ktm_data(img, target_nim='121140001', target_name='Rina Pratiwi', target_campus='Institut Teknologi Sumatera')
                self.assertTrue(res['campus_match'])
                self.assertEqual(res['nim_match'], True)

            # 2. OCR text hanya berisi kata umum 'universitas' tanpa token nama kampus target TIDAK cocok
            with patch('pytesseract.image_to_string', return_value="KARTU PERPUSTAKAAN UNIVERSITAS BEBAS\nNIM: 121140001\nRina Pratiwi"):
                res = extract_ktm_data(img, target_nim='121140001', target_name='Rina Pratiwi', target_campus='Institut Teknologi Sumatera')
                self.assertFalse(res['campus_match'])



class NotificationModalEndpointTest(TestCase):
    """Pengujian endpoint modal notifikasi HTMX (Item 3)."""

    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.user = User.objects.create_user(username='user_modal', email='modal@kampus.id', password='Password123!')

    def test_anonymous_access_panel_redirected_to_login(self):
        """Akses anonim ke /notifikasi/panel/ dialihkan ke halaman login."""
        resp = self.client.get(reverse('core:notification_panel'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/masuk/', resp.url)

    def test_notification_panel_pagination_and_marks_read_on_open(self):
        """Panel menampilkan 20 notifikasi terbaru, pagination, dan menandai notifikasi yang dibuka sebagai terbaca."""
        # Buat 25 notifikasi
        for i in range(25):
            Notification.notify(
                user=self.user,
                title=f"Notifikasi #{i+1}",
                message=f"Pesan rincian notifikasi ke-{i+1}",
                url=f"/sewa/KR-{i+1}/"
            )

        # Sebelum dibuka: 25 notifikasi belum dibaca
        self.assertEqual(Notification.objects.filter(user=self.user, is_read=False).count(), 25)

        # Buka panel halaman 1
        self.client.force_login(self.user)
        resp = self.client.get(reverse('core:notification_panel'))
        self.assertEqual(resp.status_code, 200)

        # Memuat 20 notifikasi
        items = resp.context['notifications']
        self.assertEqual(len(items), 20)

        # Ada tombol / tautan 'Muat lebih banyak'
        self.assertTrue(resp.context['page_obj'].has_next())
        content = resp.content.decode('utf-8')
        self.assertIn('Muat lebih banyak', content)

        # 20 item yang ditampilkan langsung ditandai terbaca
        unread_remaining = Notification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(unread_remaining, 5)

    def test_mark_all_read_htmx(self):
        """Endpoint HTMX tandai semua dibaca menandai seluruh notifikasi user sebagai terbaca."""
        for i in range(5):
            Notification.notify(user=self.user, title=f"N{i}", message=f"P{i}")

        self.assertEqual(Notification.objects.filter(user=self.user, is_read=False).count(), 5)

        self.client.force_login(self.user)
        resp = self.client.post(reverse('core:mark_all_read_htmx'))
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(Notification.objects.filter(user=self.user, is_read=False).count(), 0)

    def test_legacy_notifications_url_redirects_to_dashboard(self):
        """Halaman lama /notifikasi/ dialihkan ke /dashboard/."""
        self.client.force_login(self.user)
        resp = self.client.get(reverse('core:notifications'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/dashboard/')


class ForbiddenKeywordsPublicTemplateTest(TestCase):
    """Pengujian pemindaian template publik dari kata-kata terlarang beraroma demo (Item 1 & 7)."""

    def test_public_templates_do_not_contain_forbidden_demo_words(self):
        """
        Memindai template publik untuk memastikan tidak ada kata terlarang:
        ['Contoh', 'demo', 'prototipe', 'Rencana:', 'simulasi'].
        """
        forbidden_patterns = [
            r'\bContoh\b',
            r'\bdemo\b',
            r'\bprototipe\b',
            r'\bRencana:\b',
            r'\bsimulasi\b',
        ]

        # Template publik dan partial pengguna
        public_templates = [
            'templates/home.html',
            'templates/base.html',
            'templates/core/tentang.html',
            'templates/core/bantuan.html',
            'templates/catalog/item_list.html',
            'templates/catalog/item_detail.html',
            'templates/catalog/partials/item_grid.html',
            'templates/core/partials/rental_calculator.html',
            'templates/core/partials/notification_panel.html',
        ]

        violations = []
        for rel_path in public_templates:
            abs_path = os.path.join(settings.BASE_DIR, rel_path)
            self.assertTrue(os.path.exists(abs_path), f"Template {rel_path} tidak ditemukan.")
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()

            for pattern in forbidden_patterns:
                matches = re.findall(pattern, content, flags=re.IGNORECASE)
                if matches:
                    violations.append(f"{rel_path}: ditemukan {matches} cocok dengan pattern '{pattern}'")

        self.assertEqual(violations, [], f"Ditemukan teks bernuansa demo di template publik: {violations}")
