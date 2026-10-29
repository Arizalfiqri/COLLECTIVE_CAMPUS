import os
import re
from django.test import TestCase, RequestFactory
from django.conf import settings
from django.contrib import admin
from apps.core.context_processors import site_branding
from apps.accounts.emails import send_account_verification_email, send_campus_email_verification
from apps.accounts.models import User
from django.core import mail


class BrandConsistencyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_site_branding_context_processor(self):
        """Uji context processor menyediakan SITE_NAME, SITE_SHORT_NAME, logotype, tagline, dan domain."""
        request = self.factory.get('/')
        ctx = site_branding(request)
        self.assertEqual(ctx['SITE_NAME'], 'Collective Campus')
        self.assertEqual(ctx['SITE_SHORT_NAME'], 'Collective')
        self.assertEqual(ctx['SITE_LOGOTYPE_DARK'], 'Collective')
        self.assertEqual(ctx['SITE_LOGOTYPE_ACCENT'], 'Campus')
        self.assertIn('text-ink', str(ctx['site_logotype']['html']))
        self.assertIn('text-brand', str(ctx['site_logotype']['html']))
        self.assertEqual(ctx['SITE_TAGLINE'], 'Saling sewa, saling jual, saling bantu.')
        self.assertEqual(ctx['SITE_DOMAIN'], '')
        self.assertEqual(ctx['WITHDRAWAL_MIN'], 20000)

    def test_admin_site_headers_configured_with_site_name(self):
        """Uji judul admin memakai variabel SITE_SHORT_NAME ('Collective Admin')."""
        self.assertIn(getattr(settings, 'SITE_SHORT_NAME', 'Collective'), admin.site.site_header)
        self.assertIn(getattr(settings, 'SITE_SHORT_NAME', 'Collective'), admin.site.site_title)

    def test_no_old_brand_literal_in_templates(self):
        """
        Uji tidak ada literal nama lama ('KampusRent' atau 'Sewa Mahasiswa')
        yang tertulis secara hardcoded di seluruh file templates (.html dan .txt).
        """
        templates_dir = os.path.join(settings.BASE_DIR, 'templates')
        pattern = re.compile(r'KampusRent|Sewa\s+Mahasiswa', re.IGNORECASE)

        violations = []
        for root, dirs, files in os.walk(templates_dir):
            for fname in files:
                if not (fname.endswith('.html') or fname.endswith('.txt')):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        matches = pattern.findall(line)
                        if matches:
                            rel_path = os.path.relpath(fpath, templates_dir)
                            violations.append(f"{rel_path}:{line_num} -> {matches} in '{line.strip()}'")

        self.assertEqual(
            len(violations), 0,
            f"Ditemukan {len(violations)} literal nama lama di template:\n" + "\n".join(violations)
        )

    def test_no_old_brand_literal_in_docs(self):
        """
        Uji tidak ada literal nama lama ('KampusRent' atau 'Kampus Rent')
        di seluruh dokumen utama (README.md, docs/, PROJECT_SPEC.md, design.md)
        kecuali pada pengecualian yang tercatat secara sah:
        - Teks ADR historis lama di docs/DECISIONS.md (ADR-001 s.d. ADR-014)
        - Nama database dan instruksi pemulihan cadangan teknis (kampusrent_db_*.sql)
        """
        doc_files = [
            os.path.join(settings.BASE_DIR, 'README.md'),
            os.path.join(settings.BASE_DIR, 'docs', 'references', 'PROJECT_SPEC.md'),
            os.path.join(settings.BASE_DIR, 'docs', 'references', 'design.md'),
        ]
        docs_dir = os.path.join(settings.BASE_DIR, 'docs')
        for root, dirs, files in os.walk(docs_dir):
            if 'local' in root or '.gemini' in root:
                continue
            for fname in files:
                if fname.endswith(('.md', '.txt')):
                    doc_files.append(os.path.join(root, fname))

        pattern = re.compile(r'KampusRent|Kampus\s+Rent', re.IGNORECASE)
        violations = []

        for fpath in doc_files:
            rel = os.path.relpath(fpath, settings.BASE_DIR).replace('\\', '/')
            with open(fpath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # Pengecualian sah sesuai instruksi:
                    # 1. Teks ADR di docs/DECISIONS.md (ADR lama dan pencatatan penggantian nama di ADR-015)
                    if rel == 'docs/DECISIONS.md':
                        continue
                    # 2. Nama berkas cadangan database dan arsip media
                    if 'kampusrent_db_' in line or 'kampusrent_media_' in line:
                        continue
                    # 3. Nama koneksi database teknis dan pengujian
                    if '5432/kampusrent' in line or '-d kampusrent' in line or 'test_kampusrent' in line:
                        continue
                    # 4. Pohon struktur folder teknis
                    if line.strip() == 'kampusrent/':
                        continue
                    matches = pattern.findall(line)
                    if matches:
                        violations.append(f"{rel}:{line_num} -> {matches} in '{line.strip()}'")

        self.assertEqual(
            len(violations), 0,
            f"Ditemukan {len(violations)} literal nama lama di docs:\n" + "\n".join(violations)
        )

    def test_email_subjects_use_dynamic_site_name(self):
        """Uji subjek email menggunakan nama platform dinamis."""
        user = User.objects.create_user(
            username='brandtestuser',
            email='brandtest@kampus.ac.id',
            password='password123',
            full_name='Budi Brand'
        )
        send_account_verification_email(user)
        self.assertTrue(len(mail.outbox) > 0)
        sent = mail.outbox[-1]
        self.assertIn(getattr(settings, 'SITE_NAME', 'Collective Campus'), sent.subject)
        self.assertIn(getattr(settings, 'SITE_NAME', 'Collective Campus'), sent.body)

    def test_forbidden_words_in_public_rendered_pages(self):
        """
        Uji tidak ada kata terlarang yang muncul pada respon HTML halaman publik:
        - 'deposit' (selama DEPOSIT_MODE=off)
        - 'rekening bersama'
        - 'satu almamater'
        - nama lama ('KampusRent', 'Kampus Rent', 'kampusrent')
        """
        public_urls = [
            '/',
            '/tentang/',
            '/bantuan/',
            '/syarat-ketentuan/',
            '/kebijakan-privasi/',
            '/panduan-komunitas/',
            '/barang/',
            '/jual-beli/',
        ]
        forbidden_regexes = [
            (re.compile(r'\bdeposit\b', re.IGNORECASE), "deposit"),
            (re.compile(r'rekening\s+bersama', re.IGNORECASE), "rekening bersama"),
            (re.compile(r'satu\s+almamater', re.IGNORECASE), "satu almamater"),
            (re.compile(r'KampusRent|Kampus\s+Rent', re.IGNORECASE), "nama lama"),
        ]
        violations = []
        for url in public_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"URL {url} harus return 200")
            content = resp.content.decode('utf-8')
            for rgx, label in forbidden_regexes:
                found = rgx.findall(content)
                if found:
                    violations.append(f"URL {url} mengandung kata terlarang '{label}': {found[:3]}")

        self.assertEqual(len(violations), 0, "\n".join(violations))
