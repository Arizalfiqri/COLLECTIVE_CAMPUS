import os
import re
from django.test import TestCase
from django.conf import settings


class Phase7ICssValidationTest(TestCase):
    """
    Fase 7I Butir 1: Validasi Utilitas Tailwind CSS.
    Mengekstrak seluruh kelas utilitas dari template dan memastikan seluruhnya
    telah terkompilasi di static/css/styles.css.
    """

    def test_all_template_tailwind_classes_present_in_built_css(self):
        """Memastikan semua kelas Tailwind utilitas yang dipakai di template ada di styles.css."""
        template_dir = os.path.join(settings.BASE_DIR, 'templates')
        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'styles.css')

        self.assertTrue(os.path.exists(css_path), f"File CSS hasil build tidak ditemukan: {css_path}")
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Regex untuk mengekstrak atribut class (mengecualikan :class atau x-bind:class)
        class_re = re.compile(r'(?<![:@\w])class=["\']([^"\']+)["\']')

        custom_known_classes = {
            'custom-select-wrapper', 'custom-select-trigger', 'custom-select-menu', 'custom-select-option',
            'custom-select-label', 'custom-date-wrapper', 'custom-date-trigger', 'custom-date-popup',
            'custom-date-label', 'custom-scrollbar', 'safe-bottom', 'no-scrollbar', 'table-responsive',
            'tabular-nums', 'htmx-indicator', 'htmx-request', 'toast-item',
            # Spacing tokens (Fase 7I)
            'spacing-navbar-to-content', 'spacing-sections', 'spacing-title-to-content',
            'spacing-breadcrumb', 'spacing-before-footer', 'spacing-hero',
            # Django admin & widget standard classes
            'action-counter', 'actions', 'breadcrumbs', 'button', 'clear', 'collapsed', 'default',
            'paginator', 'paginator-pages', 'question', 'rating', 'unread', 'showall', 'all',
            'admin-sidebar', 'admin-desktop-toggle', 'admin-mobile-toggle', 'admin-date-chip',
        }

        js_syntax_chars = set('{}$%?=<>&|!()[]{}+*^~')
        classes_used = set()

        for root, dirs, files in os.walk(template_dir):
            for file_name in files:
                if file_name.endswith('.html'):
                    file_path = os.path.join(root, file_name)
                    with open(file_path, 'r', encoding='utf-8') as fp:
                        content = fp.read()

                    # Bersihkan template tag Django sebelum ekstraksi
                    clean_content = re.sub(r'\{%.*?%\}', ' ', content, flags=re.DOTALL)
                    clean_content = re.sub(r'\{\{.*?\}\}', ' ', clean_content, flags=re.DOTALL)

                    matches = class_re.findall(clean_content)
                    for m in matches:
                        for c in m.split():
                            c = c.strip('",\'();')
                            if not c or any(ch in c for ch in js_syntax_chars):
                                continue
                            if '.' in c and not re.match(r'^[a-z0-9\-:]+-[0-9]+\.[0-9]+', c):
                                continue
                            if c in custom_known_classes or c.isdigit():
                                continue
                            classes_used.add(c)

        missing = []
        for c in sorted(classes_used):
            escaped = re.sub(r'([:\[\]/\.%\#\(\)])', r'\\\1', c)
            target_selector = '.' + escaped
            if target_selector not in css_content and ('.' + c) not in css_content:
                missing.append(c)

        self.assertEqual(
            missing,
            [],
            f"Ditemukan {len(missing)} kelas Tailwind yang belum terkompilasi di styles.css: {missing}"
        )


class Phase7IForbiddenWordsAndStep3Test(TestCase):
    """
    Fase 7I Butir 5 & 6: Validasi kata terlarang saat DEPOSIT_MODE='off' dan langkah 3 Cara kerja.
    """

    def setUp(self):
        from apps.accounts.models import User, StudentProfile, Campus
        from apps.catalog.models import Category, Item

        self.campus = Campus.objects.create(name='Universitas Lampung', short_name='UNILA', city='Bandar Lampung')
        self.user = User.objects.create_user(
            username='user7i', email='user7i@unila.ac.id', password='Password123!',
            full_name='Mahasiswa Penguji', is_verified_student=True
        )
        StudentProfile.objects.create(user=self.user, campus=self.campus, nim='2015061001')
        self.category = Category.objects.create(name='Kamera & Lensa', slug='kamera', order=1)
        self.item = Item.objects.create(
            owner=self.user,
            category=self.category,
            title='Kamera Mirrorless Uji',
            slug='kamera-mirrorless-uji',
            price_per_day=50000,
            deposit_amount=0,
            estimated_value=1000000,
            min_days=1,
            max_days=5,
            pickup_area='Perpustakaan Pusat',
            require_ktm_held=True,
        )

    def test_step_3_copy_text_matches_spec(self):
        """Langkah 3 'Cara kerja' wajib bertuliskan 'Pembayaran sewa ditahan oleh platform sampai barang kembali'."""
        from django.template.loader import render_to_string
        html = render_to_string('partials/steps.html')
        self.assertIn('Pembayaran sewa ditahan oleh platform sampai barang kembali', html)
        self.assertNotIn('rekening bersama', html.lower())

    def test_no_forbidden_words_in_public_views_when_deposit_off(self):
        """Memastikan tidak ada kata terlarang (deposit, uang jaminan, rekening bersama) pada tampilan publik saat DEPOSIT_MODE='off'."""
        from django.test import override_settings
        from django.urls import reverse

        with override_settings(DEPOSIT_MODE='off'):
            urls = [
                reverse('home'),
                reverse('core:tentang'),
                reverse('core:bantuan'),
                reverse('core:syarat_ketentuan'),
                reverse('core:kebijakan_privasi'),
                reverse('catalog:item_list'),
                reverse('catalog:item_detail', kwargs={'slug': self.item.slug}),
            ]

            forbidden_terms = ['uang jaminan', 'rekening bersama']

            for url in urls:
                res = self.client.get(url)
                self.assertEqual(res.status_code, 200, f"Gagal mengakses {url}")
                content = res.content.decode('utf-8').lower()
                for term in forbidden_terms:
                    self.assertNotIn(
                        term,
                        content,
                        f"Kata terlarang '{term}' ditemukan di {url} saat DEPOSIT_MODE='off'"
                    )

            # Di detail barang dan beranda, kata 'deposit' tidak boleh tampil sama sekali saat mode off
            res_detail = self.client.get(reverse('catalog:item_detail', kwargs={'slug': self.item.slug}))
            self.assertNotIn('deposit', res_detail.content.decode('utf-8').lower())

            res_home = self.client.get(reverse('home'))
            self.assertNotIn('deposit', res_home.content.decode('utf-8').lower())


class Phase7ISentenceCaseTest(TestCase):
    """
    Fase 7I Butir 5 & 6: Standardisasi Sentence Case pada template utama.
    """

    def setUp(self):
        from apps.accounts.models import User, StudentProfile, Campus
        from apps.catalog.models import Category, Item

        self.campus = Campus.objects.create(name='Universitas Lampung', short_name='UNILA', city='Bandar Lampung')
        self.owner = User.objects.create_user(
            username='owner7i', email='owner7i@unila.ac.id', password='Password123!',
            full_name='Pemilik Barang', is_verified_student=True
        )
        StudentProfile.objects.create(user=self.owner, campus=self.campus, nim='2015061002')
        self.category = Category.objects.create(name='Kamera & Lensa', slug='kamera', order=1)
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title='Lensa 50mm Uji',
            slug='lensa-50mm-uji',
            price_per_day=35000,
            deposit_amount=0,
            estimated_value=800000,
            min_days=1,
            max_days=7,
            pickup_area='Gedung A',
            min_renter_tier='baru',
            require_ktm_held=True,
        )

    def test_sentence_case_on_item_detail_and_form(self):
        """Memverifikasi penerapan sentence case seperti 'Barang milik Anda', 'Tingkat penyewa minimal', dll."""
        from django.urls import reverse

        self.client.force_login(self.owner)

        # Detail barang sebagai pemilik
        res = self.client.get(reverse('catalog:item_detail', kwargs={'slug': self.item.slug}))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn('Barang milik Anda', content)
        self.assertIn('Tingkat penyewa minimal:', content)
        self.assertIn('Penyewa baru', content)
        self.assertIn('Mulai sewa', content)
        self.assertIn('Selesai sewa', content)
        self.assertIn('Syarat tambahan: KTM fisik ditahan', content)

        # Form pasang barang
        res_form = self.client.get(reverse('catalog:item_create'))
        self.assertEqual(res_form.status_code, 200)
        content_form = res_form.content.decode('utf-8')

        self.assertIn('Tingkat penyewa minimum', content_form)
        self.assertIn('Penyewa baru', content_form)
        self.assertIn('Syarat fisik KTM ditahan', content_form)
        self.assertIn('Pernyataan &amp; syarat ketentuan pemilik barang', content_form)

