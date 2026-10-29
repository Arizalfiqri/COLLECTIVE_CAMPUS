from django.db import models
from django.conf import settings
from django.utils import timezone
import hashlib


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications', verbose_name="Pengguna"
    )
    title = models.CharField(max_length=200, blank=True, default='', verbose_name="Judul")
    message = models.CharField(max_length=500, verbose_name="Pesan")
    url = models.CharField(max_length=300, blank=True, default='', verbose_name="URL Tujuan")
    is_read = models.BooleanField(default=False, verbose_name="Sudah Dibaca")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")


    class Meta:
        verbose_name = "Notifikasi"
        verbose_name_plural = "Notifikasi"
        ordering = ['-created_at']

    def __str__(self):
        status = "Dibaca" if self.is_read else "Belum dibaca"
        return f"{self.user} – {self.title or self.message[:30]} ({status})"

    @classmethod
    def notify(cls, user, title, message, url=''):
        """Helper untuk membuat notifikasi baru."""
        return cls.objects.create(
            user=user,
            title=title,
            message=message,
            url=url
        )


class TermsVersion(models.Model):
    class Type(models.TextChoices):
        PENYEWA = 'penyewa', 'Syarat & Ketentuan Penyewa'
        PEMILIK = 'pemilik', 'Syarat & Ketentuan Pemilik'
        UMUM = 'umum', 'Syarat & Ketentuan Umum'
        JUAL_PENJUAL = 'jual_penjual', 'Syarat & Ketentuan Penjual'
        JUAL_PEMBELI = 'jual_pembeli', 'Syarat & Ketentuan Pembeli'

    TermType = Type

    term_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.PENYEWA,
        verbose_name="Jenis S&K"
    )
    version = models.CharField(
        max_length=50,
        default='v1.0',
        verbose_name="Versi S&K"
    )
    content = models.TextField(
        verbose_name="Isi Syarat & Ketentuan"
    )
    valid_from = models.DateTimeField(
        default=timezone.now,
        verbose_name="Berlaku Sejak"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Versi Syarat & Ketentuan"
        verbose_name_plural = "Versi Syarat & Ketentuan"
        ordering = ['term_type', '-valid_from', '-created_at']

    def __str__(self):
        status = "Aktif" if self.is_active else "Tidak Aktif"
        return f"{self.get_term_type_display()} {self.version} ({status})"

    def calculate_sha256(self):
        return hashlib.sha256(self.content.strip().encode('utf-8')).hexdigest()

    @classmethod
    def get_active_terms(cls, term_type='penyewa'):
        """Mengambil versi aktif terbaru untuk jenis S&K tertentu."""
        active = cls.objects.filter(
            term_type=term_type,
            is_active=True,
            valid_from__lte=timezone.now()
        ).order_by('-valid_from', '-created_at').first()
        return active

