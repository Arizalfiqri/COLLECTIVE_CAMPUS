import io
import shutil
from pathlib import Path
from PIL import Image

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from apps.accounts.models import User, StudentProfile
from apps.core.models import Notification
from apps.verification.forms import KtmUploadForm
from apps.verification.models import KtmVerification
from apps.verification.admin import KtmVerificationAdmin
from ml.ktm_ocr import calculate_match_score, get_recommendation, calculate_quality_score


class KtmUploadAndFormValidationTests(TestCase):
    def setUp(self):
        self.temp_private_media = Path(settings.BASE_DIR) / 'scratch' / 'test_private_media'
        self.temp_private_media.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.temp_private_media.exists():
            shutil.rmtree(self.temp_private_media, ignore_errors=True)

    def _generate_test_image(self, fmt='JPEG', size=(400, 300)):
        """Buat file image in-memory valid."""
        img = Image.new('RGB', size, color=(200, 220, 240))
        buffer = io.BytesIO()
        img.save(buffer, format=fmt)
        buffer.seek(0)
        ext = 'png' if fmt.upper() == 'PNG' else 'jpg'
        return SimpleUploadedFile(f'test_ktm.{ext}', buffer.read(), content_type=f'image/{ext}')

    def test_upload_valid_jpeg(self):
        """Unggahan JPEG valid di bawah 5 MB harus diterima oleh form."""
        file = self._generate_test_image(fmt='JPEG')
        form = KtmUploadForm(files={'ktm_image': file})
        self.assertTrue(form.is_valid())

    def test_upload_valid_png(self):
        """Unggahan PNG valid di bawah 5 MB harus diterima oleh form."""
        file = self._generate_test_image(fmt='PNG')
        form = KtmUploadForm(files={'ktm_image': file})
        self.assertTrue(form.is_valid())

    def test_upload_invalid_non_image_file(self):
        """Unggahan file teks atau bukan citra harus ditolak Pillow dengan pesan error Bahasa Indonesia."""
        fake_file = SimpleUploadedFile('document.txt', b'Bukan file gambar', content_type='text/plain')
        form = KtmUploadForm(files={'ktm_image': fake_file})
        self.assertFalse(form.is_valid())
        err = form.errors['ktm_image'][0]
        self.assertTrue(
            "Format berkas tidak didukung" in err or "Berkas citra rusak atau tidak dapat dibaca" in err
        )

    def test_upload_corrupt_image(self):
        """Unggahan file dengan ekstensi gambar tapi isi korup harus ditolak."""
        corrupt_file = SimpleUploadedFile('corrupt.jpg', b'\xff\xd8\xff\x00\x01\x02RUSAK', content_type='image/jpeg')
        form = KtmUploadForm(files={'ktm_image': corrupt_file})
        self.assertFalse(form.is_valid())
        self.assertIn("Berkas citra rusak atau tidak dapat dibaca", form.errors['ktm_image'][0])

    def test_upload_exceeds_max_size_5mb(self):
        """Unggahan melebihi 5 MB harus ditolak dengan pesan error Bahasa Indonesia."""
        # Simulasi file 6 MB
        oversized_data = b'x' * (6 * 1024 * 1024)
        oversized_file = SimpleUploadedFile('large.jpg', oversized_data, content_type='image/jpeg')
        form = KtmUploadForm(files={'ktm_image': oversized_file})
        self.assertFalse(form.is_valid())
        self.assertIn("melebihi batas maksimal 5 MB", form.errors['ktm_image'][0])


class KtmOcrScoringAndRecommendationTests(TestCase):
    def test_scoring_formula_exact(self):
        """
        Rumus Skor Kecocokan PROJECT_SPEC.md 9.1:
        match_score = 50 jika nim_match + 0.3 * name_similarity + 10 jika campus_match + 0.1 * quality_score
        """
        # Skenario 1: Semua cocok sempurna
        # 50 + (0.3 * 100) + 10 + (0.1 * 90) = 50 + 30 + 10 + 9 = 99
        score_high = calculate_match_score(nim_match=True, name_similarity=100, campus_match=True, quality_score=90)
        self.assertEqual(score_high, 99)
        self.assertEqual(get_recommendation(score_high), 'setuju')

        # Skenario 2: Nilai rendah (tolak)
        # 0 + (0.3 * 50) + 0 + (0.1 * 60) = 15 + 6 = 21 -> tolak (< 60)
        score_low = calculate_match_score(nim_match=False, name_similarity=50, campus_match=False, quality_score=60)
        self.assertEqual(score_low, 21)
        self.assertEqual(get_recommendation(score_low), 'tolak')

        # Skenario 3: Nilai menengah (tinjau)
        # 50 + (0.3 * 40) + 0 + (0.1 * 70) = 50 + 12 + 0 + 7 = 69 -> tinjau (60-84)
        score_mid = calculate_match_score(nim_match=True, name_similarity=40, campus_match=False, quality_score=70)
        self.assertEqual(score_mid, 69)
        self.assertEqual(get_recommendation(score_mid), 'tinjau')


class KtmPrivacyAndAdminQueueTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff_admin',
            email='staff_admin@kampus.ac.id',
            password='AdminPassword123!',
            is_staff=True
        )
        self.student_user = User.objects.create_user(
            username='student_budi',
            email='student_budi@kampus.ac.id',
            password='StudentPassword123!',
            is_staff=False,
            is_verified_student=False
        )
        self.profile = StudentProfile.objects.create(
            user=self.student_user,
            nim='2021110099',
            campus_name='Universitas KampusRent'
        )

        # Buat file gambar fisik dummy di private_media/ktm/
        import uuid
        ktm_dir = settings.PRIVATE_MEDIA_ROOT / 'ktm'
        ktm_dir.mkdir(parents=True, exist_ok=True)
        self.test_filename = f'test_ktm_{uuid.uuid4().hex}.jpg'
        self.test_filepath = ktm_dir / self.test_filename

        img = Image.new('RGB', (600, 400), color=(240, 240, 240))
        img.save(self.test_filepath, 'JPEG')

        self.verification = KtmVerification.objects.create(
            user=self.student_user,
            ktm_image=f'ktm/{self.test_filename}',
            ocr_nim='2021110099',
            ocr_name='Budi',
            nim_match=True,
            name_similarity=95,
            campus_match=True,
            quality_score=80,
            match_score=94,
            recommendation=KtmVerification.Recommendation.SETUJU,
            status=KtmVerification.Status.MENUNGGU,
        )

    def tearDown(self):
        try:
            if hasattr(self, 'test_filepath') and self.test_filepath.exists():
                self.test_filepath.unlink(missing_ok=True)
        except PermissionError:
            pass

    def test_anonymous_user_cannot_access_ktm_image(self):
        """Pengguna anonim tidak boleh mengakses gambar KTM privat."""
        url = reverse('verification:admin_ktm_image', args=[self.verification.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_regular_student_cannot_access_ktm_image(self):
        """Mahasiswa non-staff tidak boleh mengakses view gambar KTM admin."""
        self.client.login(username='student_budi', password='StudentPassword123!')
        url = reverse('verification:admin_ktm_image', args=[self.verification.pk])
        response = self.client.get(url)
        # Dialihkan ke form login admin karena bukan staf
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_staff_can_view_ktm_image_with_no_store_headers(self):
        """Staf admin dapat melihat gambar KTM dengan header Cache-Control: no-store."""
        # Pastikan file fisik ada untuk test ini
        if not self.test_filepath.exists():
            img = Image.new('RGB', (600, 400), color=(240, 240, 240))
            img.save(self.test_filepath, 'JPEG')

        self.client.login(username='staff_admin', password='AdminPassword123!')
        url = reverse('verification:admin_ktm_image', args=[self.verification.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        response.close()

    @override_settings(KTM_DELETE_AFTER_DECISION=True)
    def test_decision_approval_verifies_student_and_deletes_file(self):
        """
        Saat admin menyetujui KTM:
        1. User.is_verified_student menjadi True
        2. Jika KTM_DELETE_AFTER_DECISION=True, berkas fisik dihapus dan image_deleted_at diisi
        3. Notifikasi dibuat
        4. Akses gambar setelah dihapus mengembalikan 404
        """
        # Pastikan file fisik ada
        if not self.test_filepath.exists():
            img = Image.new('RGB', (600, 400), color=(240, 240, 240))
            img.save(self.test_filepath, 'JPEG')

        self.client.login(username='staff_admin', password='AdminPassword123!')
        
        # Panggil aksi setujui_ktm_action
        from django.contrib.admin.sites import site
        admin_obj = KtmVerificationAdmin(KtmVerification, site)

        from django.test import RequestFactory
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware

        factory = RequestFactory()
        req = factory.post('/admin/verification/ktmverification/')
        req.user = self.staff_user
        SessionMiddleware(lambda r: None).process_request(req)
        req.session.save()
        MessageMiddleware(lambda r: None).process_request(req)

        queryset = KtmVerification.objects.filter(pk=self.verification.pk)
        admin_obj.setujui_ktm_action(req, queryset)

        # Cek status verifikasi & user
        self.verification.refresh_from_db()
        self.student_user.refresh_from_db()

        self.assertEqual(self.verification.status, KtmVerification.Status.DISETUJUI)
        self.assertTrue(self.student_user.is_verified_student)
        self.assertIsNotNone(self.verification.image_deleted_at)
        self.assertFalse(self.test_filepath.exists())  # File fisik terhapus!

        # Cek notifikasi
        notif = Notification.objects.filter(user=self.student_user).first()
        self.assertIsNotNone(notif)
        self.assertIn("disetujui", notif.message)

        # Akses view gambar sekarang harus 404
        url = reverse('verification:admin_ktm_image', args=[self.verification.pk])
        resp_after_delete = self.client.get(url)
        self.assertEqual(resp_after_delete.status_code, 404)
