from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    email = models.EmailField(unique=True, verbose_name="Alamat Email")
    full_name = models.CharField(max_length=150, blank=True, verbose_name="Nama Lengkap")
    phone_whatsapp = models.CharField(max_length=20, blank=True, verbose_name="Nomor WhatsApp")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True, verbose_name="Foto Profil")
    is_verified_student = models.BooleanField(default=False, verbose_name="Terverifikasi Mahasiswa")
    is_email_verified = models.BooleanField(default=True, verbose_name="Email Terverifikasi")
    is_suspended = models.BooleanField(default=False, verbose_name="Akun Dibekukan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")

    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Pengguna"
        verbose_name_plural = "Pengguna"

    def __str__(self):

        return self.full_name or self.username

    def save(self, *args, **kwargs):
        if not self.full_name and (self.first_name or self.last_name):
            self.full_name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)


class Campus(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Nama Kampus")
    short_name = models.CharField(max_length=50, verbose_name="Nama Singkat / Inisial")
    city = models.CharField(max_length=100, verbose_name="Kota")
    ktm_keywords = models.JSONField(default=list, blank=True, verbose_name="Kata Kunci KTM")
    nim_pattern = models.CharField(max_length=100, blank=True, default='', verbose_name="Pola Regex NIM (opsional)")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Kampus"
        verbose_name_plural = "Kampus"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.short_name})"


class MeetingPoint(models.Model):
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='meeting_points', verbose_name="Kampus")
    name = models.CharField(max_length=150, verbose_name="Nama Titik Temu")
    is_public = models.BooleanField(default=True, verbose_name="Titik Publik / Ramai")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")

    class Meta:
        verbose_name = "Titik Temu"
        verbose_name_plural = "Titik Temu"
        ordering = ['campus', 'name']

    def __str__(self):
        pub_str = "Publik" if self.is_public else "Khusus"
        return f"{self.name} – {self.campus.short_name} ({pub_str})"


class BlacklistedNim(models.Model):
    nim = models.CharField(max_length=30, unique=True, verbose_name="NIM")
    reason = models.TextField(blank=True, default='', verbose_name="Alasan")
    blacklisted_at = models.DateTimeField(auto_now_add=True, verbose_name="Waktu Masuk Daftar Hitam")

    class Meta:
        verbose_name = "NIM Diblokir"
        verbose_name_plural = "NIM Diblokir"
        ordering = ['-blacklisted_at']

    def __str__(self):
        return f"{self.nim} (Daftar Hitam)"


class StudentProfile(models.Model):
    class StudentStatus(models.TextChoices):
        AKTIF = 'aktif', 'Aktif'
        LULUS = 'lulus', 'Lulus'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    nim = models.CharField(max_length=30, verbose_name="NIM")
    campus = models.ForeignKey(
        Campus, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='student_profiles', verbose_name="Kampus"
    )
    major = models.CharField(max_length=100, verbose_name="Jurusan / Program Studi")
    entry_year = models.PositiveIntegerField(verbose_name="Tahun Masuk", null=True, blank=True)
    student_status = models.CharField(
        max_length=20,
        choices=StudentStatus.choices,
        default=StudentStatus.AKTIF,
        verbose_name="Status Mahasiswa"
    )
    campus_email = models.EmailField(blank=True, default='', verbose_name="Email Kampus (.ac.id)")
    is_campus_email_verified = models.BooleanField(default=False, verbose_name="Email Kampus Terverifikasi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Profil mahasiswa"
        verbose_name_plural = "Profil mahasiswa"


    def __init__(self, *args, **kwargs):
        c_name = kwargs.pop('campus_name', None)
        super().__init__(*args, **kwargs)
        if c_name and not self.campus_id:
            try:
                campus, _ = Campus.objects.get_or_create(
                    name=c_name.strip(),
                    defaults={'short_name': c_name[:10].strip(), 'city': 'Bandung'}
                )
                self.campus = campus
            except Exception:
                pass

    @property
    def campus_name(self):
        """Kembalikan nama kampus dari relasi FK campus demi kompatibilitas."""
        return self.campus.name if self.campus else ""

    def __str__(self):
        c_name = self.campus_name or "Tanpa Kampus"
        return f"{self.nim} - {self.user.get_full_name() or self.user.username} ({c_name})"


class SuspensionRecord(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='suspension_records',
        verbose_name="Pengguna"
    )
    reason = models.TextField(verbose_name="Alasan Pembekuan")
    suspended_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='issued_suspensions',
        verbose_name="Dibekukan oleh"
    )
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Mulai Dibekukan")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Berakhir pada")
    is_permanent = models.BooleanField(default=True, verbose_name="Permanen")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")

    class Meta:
        verbose_name = "Riwayat Pembekuan Akun"
        verbose_name_plural = "Riwayat Pembekuan Akun"
        ordering = ['-started_at']

    def __str__(self):
        status = "Permanen" if self.is_permanent else f"s.d. {self.ended_at}"
        return f"Pembekuan {self.user.username} ({status}) - {self.reason[:30]}"
