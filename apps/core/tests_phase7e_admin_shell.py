import re
from pathlib import Path
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import Permission

from apps.accounts.models import User
from apps.core.admin_nav import MENU_CONFIG, get_admin_navigation, resolve_url


class Phase7EAdminShellTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='admin_boss',
            email='admin@kampusrent.id',
            password='PasswordSuper123',
            full_name='Budi Superadmin'
        )
        cls.regular_staff = User.objects.create_user(
            username='staff_biasa',
            email='staff@kampusrent.id',
            password='PasswordStaff123',
            is_staff=True,
            full_name='Staff Biasa'
        )
        cls.normal_user = User.objects.create_user(
            username='mahasiswa_biasa',
            email='mhs@kampusrent.id',
            password='PasswordMhs123',
            is_staff=False,
            full_name='Mahasiswa Biasa'
        )

    def setUp(self):
        self.client = Client()

    def test_admin_shell_present_and_no_public_footer_on_all_staff_pages(self):
        """
        1. Kerangka Tunggal:
        Semua halaman staf memuat penanda data-admin-shell dan tidak memuat footer situs publik.
        """
        self.client.force_login(self.superuser)

        staff_urls = [
            '/admin/',
            '/admin/penarikan/',
            '/admin/rekonsiliasi/',
            '/admin/model-skor/',
            '/admin/ringkasan/',
            '/admin/pengumuman/',
            '/admin/verification/ktmverification/',
            '/admin/rentals/rental/',
            '/admin/catalog/item/',
        ]

        for url in staff_urls:
            with self.subTest(url=url):
                res = self.client.get(url)
                self.assertEqual(res.status_code, 200, f"URL {url} harus mengembalikan 200 OK")
                content = res.content.decode('utf-8')
                self.assertIn('data-admin-shell', content, f"URL {url} wajib memuat penanda data-admin-shell")
                self.assertNotIn('Kain Tapis Lampung', content, f"URL {url} tidak boleh memuat footer kain border situs publik")
                self.assertNotIn('Saling sewa perlengkapan kuliah antarmahasiswa', content, f"URL {url} tidak boleh memuat footer deskripsi publik")

    def test_all_menu_links_reverse_and_return_200_for_superuser(self):
        """
        Seluruh tautan konfigurasi menu di apps/core/admin_nav.py ter-reverse dan mengembalikan 200 untuk superuser.
        """
        self.client.force_login(self.superuser)

        for group in MENU_CONFIG:
            if group.get('is_single'):
                url_name = group['url_name']
                url = resolve_url(url_name)
                res = self.client.get(url)
                self.assertEqual(res.status_code, 200, f"Single menu {url_name} ({url}) harus mengembalikan 200 OK")
            else:
                for item in group.get('items', []):
                    url_name = item['url_name']
                    url = resolve_url(url_name)
                    res = self.client.get(url)
                    self.assertEqual(res.status_code, 200, f"Menu item {item['title']} ({url_name} -> {url}) harus mengembalikan 200 OK")

    def test_menu_items_hidden_when_permission_missing(self):
        """
        Item menu navigasi tersembunyi bila staf tidak memiliki izin terkait.
        """
        rf = RequestFactory()
        req = rf.get('/admin/')
        req.user = self.regular_staff  # Belum memiliki izin apapun kecuali is_staff

        nav = get_admin_navigation(req)
        visible_titles = []
        for g in nav:
            for it in g.get('items', []):
                visible_titles.append(it['title'])

        # Karena regular_staff belum punya perm 'verification.view_ktmverification', item itu harusnya tidak muncul
        self.assertNotIn('Antrean KTM', visible_titles)
        self.assertNotIn('Sengketa', visible_titles)

        # Berikan izin khusus view_ktmverification
        perm = Permission.objects.get(codename='view_ktmverification')
        self.regular_staff.user_permissions.add(perm)

        # Segarkan user dari database agar cache permission dibersihkan
        self.regular_staff = User.objects.get(pk=self.regular_staff.pk)
        req2 = rf.get('/admin/')
        req2.user = self.regular_staff

        nav2 = get_admin_navigation(req2)
        visible_titles2 = []
        for g in nav2:
            for it in g.get('items', []):
                visible_titles2.append(it['title'])

        self.assertIn('Antrean KTM', visible_titles2)
        self.assertNotIn('Sengketa', visible_titles2)

    def test_only_one_group_active_and_open_on_load(self):
        """
        Saat halaman dimuat, hanya satu grup yang is_open=True dan itu adalah grup halaman aktif.
        """
        rf = RequestFactory()

        # Kasus 1: URL di dalam grup Operasional
        req1 = rf.get('/admin/verification/ktmverification/')
        req1.user = self.superuser
        nav1 = get_admin_navigation(req1)
        open_groups1 = [g['id'] for g in nav1 if g.get('is_open') and not g.get('is_single')]
        self.assertEqual(open_groups1, ['operasional'], "Hanya grup operasional yang boleh is_open=True")

        # Kasus 2: URL di dalam grup Katalog
        req2 = rf.get('/admin/catalog/item/')
        req2.user = self.superuser
        nav2 = get_admin_navigation(req2)
        open_groups2 = [g['id'] for g in nav2 if g.get('is_open') and not g.get('is_single')]
        self.assertEqual(open_groups2, ['katalog'], "Hanya grup katalog yang boleh is_open=True")

        # Kasus 3: URL root /admin/
        req3 = rf.get('/admin/')
        req3.user = self.superuser
        nav3 = get_admin_navigation(req3)
        open_groups3 = [g['id'] for g in nav3 if g.get('is_open') and not g.get('is_single')]
        self.assertEqual(open_groups3, [], "Di root /admin/, tidak ada sub-akordeon yang terbuka (Ikhtisar aktif)")

    def test_no_emoji_in_admin_templates(self):
        """
        Memastikan tidak ada karakter emoji di seluruh template admin KampusRent.
        """
        template_dirs = [
            Path(settings.BASE_DIR) / 'templates' / 'admin',
            Path(settings.BASE_DIR) / 'templates' / 'payments' / 'admin_withdrawals.html',
            Path(settings.BASE_DIR) / 'templates' / 'payments' / 'admin_reconciliation.html',
            Path(settings.BASE_DIR) / 'templates' / 'trust' / 'admin_model_score.html',
            Path(settings.BASE_DIR) / 'templates' / 'trust' / 'admin_summary.html',
        ]

        # Pola regex Unicode emoji umum
        emoji_pattern = re.compile(
            r'[\U0001F300-\U0001F64F]|[\U0001F680-\U0001F6FF]|[\U0001F900-\U0001F9FF]|[\U0001FA00-\U0001FAFF]|[\u2600-\u26FF]|[\u2700-\u27BF]'
        )

        files_to_check = []
        for p in template_dirs:
            if p.is_dir():
                files_to_check.extend(p.rglob('*.html'))
            elif p.is_file():
                files_to_check.append(p)

        for filepath in files_to_check:
            content = filepath.read_text(encoding='utf-8')
            matches = emoji_pattern.findall(content)
            self.assertEqual(
                len(matches), 0,
                f"File {filepath.name} tidak boleh mengandung emoji! Ditemukan: {matches}"
            )

    def test_no_uppercase_small_caps_in_admin_templates(self):
        """
        Memastikan tidak ada kelas 'uppercase tracking-wider' di template admin.
        """
        templates = [
            Path(settings.BASE_DIR) / 'templates' / 'admin' / 'index.html',
            Path(settings.BASE_DIR) / 'templates' / 'admin' / 'broadcast_announcement.html',
            Path(settings.BASE_DIR) / 'templates' / 'payments' / 'admin_reconciliation.html',
            Path(settings.BASE_DIR) / 'templates' / 'payments' / 'admin_withdrawals.html',
        ]

        for p in templates:
            content = p.read_text(encoding='utf-8')
            self.assertNotIn(
                'uppercase tracking-', content,
                f"File {p.name} tidak boleh menggunakan uppercase tracking!"
            )

    def test_commission_label_reads_from_settings(self):
        """
        Label persentase komisi harus membaca PLATFORM_COMMISSION_PERCENT (8%).
        """
        self.client.force_login(self.superuser)

        # Cek di /admin/rekonsiliasi/
        res_recon = self.client.get('/admin/rekonsiliasi/')
        content_recon = res_recon.content.decode('utf-8')
        self.assertIn('Komisi platform (8%)', content_recon)
        self.assertNotIn('Komisi platform (5%)', content_recon)

        # Cek di /admin/
        res_index = self.client.get('/admin/')
        content_index = res_index.content.decode('utf-8')
        self.assertIn('Komisi platform (8%)', content_index)

    def test_htmx_chart_and_recent_transactions_endpoints(self):
        """
        Uji endpoint partial HTMX untuk grafik dan transaksi terbaru.
        """
        self.client.force_login(self.superuser)

        # 1. HTMX Chart: 7, 30, 90 hari
        for days in [7, 30, 90]:
            chart_url = reverse('admin_rental_chart_root') + f"?days={days}"
            res = self.client.get(chart_url, HTTP_HX_REQUEST='true')
            self.assertEqual(res.status_code, 200)
            content = res.content.decode('utf-8')
            self.assertIn(f'{days} hari', content)
            self.assertIn('<svg', content)

        # 2. HTMX Recent Transactions: search
        tx_url = reverse('admin_recent_transactions_root') + "?q=KR"
        res_tx = self.client.get(tx_url, HTTP_HX_REQUEST='true')
        self.assertEqual(res_tx.status_code, 200)

    def test_security_staff_only_access(self):
        """
        Hanya pengguna berstatus staf yang dapat mengakses halaman staf.
        """
        protected_urls = [
            '/admin/',
            '/admin/penarikan/',
            '/admin/rekonsiliasi/',
            '/admin/model-skor/',
            '/admin/ringkasan/',
            '/admin/pengumuman/',
        ]

        # 1. Pengguna anonim dialihkan ke login
        self.client.logout()
        for url in protected_urls:
            res = self.client.get(url)
            self.assertIn(res.status_code, [302, 403], f"Anonim pada {url} harus ditolak/dialihkan")

        # 2. Pengguna reguler (bukan staf) ditolak atau dialihkan
        self.client.force_login(self.normal_user)
        for url in protected_urls:
            res = self.client.get(url)
            self.assertIn(res.status_code, [302, 403], f"Non-staf pada {url} harus ditolak/dialihkan")
