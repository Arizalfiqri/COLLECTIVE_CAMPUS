from django.db import models
from django.conf import settings


class KtmVerification(models.Model):
    class Recommendation(models.TextChoices):
        SETUJU = 'setuju', 'Setuju'
        TINJAU = 'tinjau', 'Tinjau'
        TOLAK = 'tolak', 'Tolak'

    class Status(models.TextChoices):
        MENUNGGU = 'menunggu', 'Menunggu'
        PERLU_TINJAUAN = 'perlu_tinjauan', 'Perlu Tinjauan'
        DISETUJUI = 'disetujui', 'Disetujui'
        DITOLAK = 'ditolak', 'Ditolak'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='ktm_verifications', verbose_name="Pengguna"
    )
    # Gambar KTM disimpan di private_media, BUKAN di media publik
    ktm_image = models.ImageField(
        upload_to='ktm/', verbose_name="Foto KTM",
        help_text="Disimpan di private_media, tidak dilayani publik."
    )

    # Hasil OCR
    ocr_text = models.TextField(blank=True, default='', verbose_name="Teks OCR Mentah")
    ocr_nim = models.CharField(max_length=30, blank=True, default='', verbose_name="NIM dari OCR")
    ocr_name = models.CharField(max_length=150, blank=True, default='', verbose_name="Nama dari OCR")
    ocr_campus = models.CharField(max_length=150, blank=True, default='', verbose_name="Kampus dari OCR")

    # Skor Pencocokan
    nim_match = models.BooleanField(default=False, verbose_name="NIM Cocok")
    name_similarity = models.PositiveIntegerField(default=0, verbose_name="Kemiripan Nama (0-100)")
    campus_match = models.BooleanField(default=False, verbose_name="Kampus Cocok")
    quality_score = models.PositiveIntegerField(default=0, verbose_name="Skor Kualitas (0-100)")
    match_score = models.PositiveIntegerField(default=0, verbose_name="Skor Kecocokan (0-100)")

    # Rekomendasi dan Status
    recommendation = models.CharField(
        max_length=20, choices=Recommendation.choices,
        default=Recommendation.TINJAU, verbose_name="Rekomendasi Sistem"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.MENUNGGU, verbose_name="Status Verifikasi"
    )

    # Review admin
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ktm_reviews',
        verbose_name="Ditinjau Oleh"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Tinjauan")
    admin_note = models.TextField(blank=True, default='', verbose_name="Catatan Admin")

    # Privasi: hapus gambar setelah keputusan
    image_deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Gambar Dihapus Pada")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")


    class Meta:
        verbose_name = "Verifikasi KTM"
        verbose_name_plural = "Verifikasi KTM"
        ordering = ['-created_at']

    def __str__(self):
        return f"KTM {self.user} – {self.get_status_display()}"

    @property
    def private_file_path(self):
        """Path absolut ke file gambar di private_media."""
        if not self.ktm_image:
            return None
        from pathlib import Path
        path = settings.PRIVATE_MEDIA_ROOT / self.ktm_image.name
        if path.exists():
            return path
        # Cek jika tersimpan di subdirektori atau media
        path_media = settings.MEDIA_ROOT / self.ktm_image.name
        if path_media.exists():
            return path_media
        return path

    @property
    def has_image_file(self):
        """Cek apakah file fisik masih ada dan belum dihapus demi privasi."""
        if self.image_deleted_at is not None:
            return False
        p = self.private_file_path
        return p is not None and p.exists()

    def delete_image_file(self):
        """Hapus file gambar KTM dari penyimpanan privat dan catat waktu penghapusan."""
        from django.utils import timezone
        if self.has_image_file:
            try:
                self.private_file_path.unlink(missing_ok=True)
            except Exception:
                pass
        self.image_deleted_at = timezone.now()
        self.save(update_fields=['image_deleted_at'])
