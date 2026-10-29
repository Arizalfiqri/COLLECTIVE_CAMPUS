import string
import random
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


def generate_rental_code():
    """Kode pendek unik untuk identifikasi sewa."""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = 'KR-' + ''.join(random.choices(chars, k=6))
        if not Rental.objects.filter(code=code).exists():
            return code


class Rental(models.Model):
    class Status(models.TextChoices):
        MENUNGGU_PERSETUJUAN = 'menunggu_persetujuan', 'Menunggu persetujuan'
        MENUNGGU_PEMBAYARAN = 'menunggu_pembayaran', 'Menunggu pembayaran'
        DIBAYAR = 'dibayar', 'Dibayar'
        SEDANG_DISEWA = 'sedang_disewa', 'Sedang disewa'
        MENUNGGU_KONFIRMASI_PENGEMBALIAN = 'menunggu_konfirmasi_pengembalian', 'Menunggu konfirmasi pengembalian'
        SELESAI = 'selesai', 'Selesai'
        SENGKETA = 'sengketa', 'Sengketa'
        DITOLAK = 'ditolak', 'Ditolak'
        DIBATALKAN = 'dibatalkan', 'Dibatalkan'
        KEDALUWARSA = 'kedaluwarsa', 'Kedaluwarsa'

    # Status yang mengunci tanggal (anti double-booking)
    BLOCKING_STATUSES = [
        Status.MENUNGGU_PEMBAYARAN,
        Status.DIBAYAR,
        Status.SEDANG_DISEWA,
        Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN,
        Status.SENGKETA,
    ]

    code = models.CharField(
        max_length=20, unique=True, default=generate_rental_code,
        verbose_name="Kode Sewa", db_index=True
    )
    item = models.ForeignKey(
        'catalog.Item', on_delete=models.CASCADE,
        related_name='rentals', verbose_name="Barang"
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='rentals_as_renter', verbose_name="Penyewa"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='rentals_as_owner', verbose_name="Pemilik"
    )

    start_date = models.DateField(verbose_name="Tanggal Mulai")
    end_date = models.DateField(verbose_name="Tanggal Selesai")

    # Snapshot harga saat pengajuan
    days = models.PositiveIntegerField(default=0, verbose_name="Jumlah Hari")
    price_per_day_snapshot = models.PositiveIntegerField(default=0, verbose_name="Harga/Hari (snapshot)")
    rent_total = models.PositiveIntegerField(default=0, verbose_name="Total Sewa (Rp)")
    deposit_total = models.PositiveIntegerField(default=0, verbose_name="Total Deposit (Rp)")
    protection_fee = models.PositiveIntegerField(default=0, verbose_name="Biaya Proteksi (Rp)")
    grand_total = models.PositiveIntegerField(default=0, verbose_name="Total Bayar (Rp)")
    use_protection = models.BooleanField(default=False, verbose_name="Pakai Proteksi")

    status = models.CharField(
        max_length=40, choices=Status.choices,
        default=Status.MENUNGGU_PERSETUJUAN, verbose_name="Status",
        db_index=True
    )

    # Timestamps siklus sewa
    requested_at = models.DateTimeField(null=True, blank=True, verbose_name="Diajukan Pada")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Disetujui Pada")
    status_changed_at = models.DateTimeField(null=True, blank=True, verbose_name="Status Berubah Pada")
    handed_over_owner_at = models.DateTimeField(null=True, blank=True, verbose_name="Pemilik Serahkan Pada")
    handed_over_renter_at = models.DateTimeField(null=True, blank=True, verbose_name="Penyewa Terima Pada")
    return_requested_at = models.DateTimeField(null=True, blank=True, verbose_name="Pengembalian Diminta Pada")
    returned_date = models.DateField(null=True, blank=True, verbose_name="Tanggal Dikembalikan")

    # Jaminan KTM & Serah Terima SPEC v2
    ktm_held_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="KTM Ditahan Dikonfirmasi")
    ktm_returned_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="KTM Dikembalikan Dikonfirmasi")
    handover_photo_consent_at = models.DateTimeField(null=True, blank=True, verbose_name="Persetujuan Foto Serah Terima")

    # Denda dan kerusakan
    late_days = models.PositiveIntegerField(default=0, verbose_name="Hari Terlambat")
    late_fee = models.PositiveIntegerField(default=0, verbose_name="Denda Keterlambatan (Rp)")
    damage_fee = models.PositiveIntegerField(default=0, verbose_name="Biaya Kerusakan (Rp)")

    # Pembatalan
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cancelled_rentals',
        verbose_name="Dibatalkan Oleh"
    )
    cancel_reason = models.TextField(blank=True, default='', verbose_name="Alasan Pembatalan")
    note = models.TextField(blank=True, default='', verbose_name="Catatan")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Sewa"
        verbose_name_plural = "Sewa"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['item', 'status']),
            models.Index(fields=['renter', 'status']),
            models.Index(fields=['owner', 'status']),
        ]

    def __str__(self):
        return f"{self.code} – {self.item.title}"

    # -------- Method perhitungan sesuai PROJECT_SPEC.md 7.2 --------

    def calc_days(self):
        """days = (end_date - start_date).days + 1"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    def calc_rent_total(self):
        """rent_total = price_per_day * days"""
        return self.price_per_day_snapshot * self.calc_days()

    def calc_grand_total(self):
        """grand_total = rent_total + deposit_total + protection_fee"""
        return self.calc_rent_total() + self.deposit_total + self.protection_fee

    def calc_commission(self):
        """commission = round(rent_total * COMMISSION_PERCENT / 100)"""
        return round(self.rent_total * settings.PLATFORM_COMMISSION_PERCENT / 100)

    def calc_owner_net(self):
        """owner_net = rent_total - commission"""
        return self.rent_total - self.calc_commission()

    def calc_late_days(self):
        """late_days = max(0, (returned_date - end_date).days)"""
        if self.returned_date and self.end_date:
            return max(0, (self.returned_date - self.end_date).days)
        return 0

    def calc_late_fee(self):
        """late_fee = min(round(price_per_day * 0.5 * late_days), deposit_total)"""
        late_d = self.calc_late_days()
        raw_fee = round(self.price_per_day_snapshot * 0.5 * late_d)
        return min(raw_fee, self.deposit_total)

    def calc_deposit_refund(self):
        """deposit_refund = deposit_total - late_fee - damage_fee (min 0)"""
        return max(0, self.deposit_total - self.calc_late_fee() - self.damage_fee)

    def calc_platform_income(self):
        """platform_income = commission + protection_fee"""
        return self.calc_commission() + self.protection_fee

    def snapshot_pricing(self):
        """Ambil snapshot harga dari Item dan hitung total saat pengajuan."""
        self.days = self.calc_days()
        self.price_per_day_snapshot = self.item.price_per_day
        self.deposit_total = self.item.deposit_amount
        prot_fee = settings.PROTECTION_FEE if self.use_protection else 0
        self.protection_fee = prot_fee
        self.rent_total = self.price_per_day_snapshot * self.days
        self.grand_total = self.rent_total + self.deposit_total + self.protection_fee


class ConditionPhoto(models.Model):
    class Phase(models.TextChoices):
        SEBELUM = 'sebelum', 'Sebelum Sewa'
        SERAH_TERIMA = 'serah_terima', 'Saat Serah Terima'
        SESUDAH = 'sesudah', 'Setelah Sewa'

    rental = models.ForeignKey(
        Rental, on_delete=models.CASCADE, related_name='condition_photos',
        verbose_name="Sewa"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        verbose_name="Diunggah Oleh"
    )
    phase = models.CharField(
        max_length=20, choices=Phase.choices, verbose_name="Fase"
    )
    image = models.ImageField(upload_to='conditions/', verbose_name="Foto Kondisi")
    note = models.TextField(blank=True, default='', verbose_name="Catatan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")

    class Meta:
        verbose_name = "Foto Kondisi"
        verbose_name_plural = "Foto Kondisi"
        ordering = ['created_at']

    @property
    def private_file_path(self):
        """Path file fisik di direktori private_media."""
        if not self.image:
            return None
        from pathlib import Path
        name = self.image.name
        if name.startswith('conditions/'):
            name = name[len('conditions/'):]
        return Path(settings.PRIVATE_MEDIA_ROOT) / 'conditions' / name

    @property
    def exists_on_disk(self):
        """Memeriksa apakah berkas fisik ada di private_media."""
        p = self.private_file_path
        return p.exists() if p else False

    def delete_file(self):
        """Menghapus berkas fisik dari private_media."""
        try:
            p = self.private_file_path
            if p and p.exists():
                p.unlink()
        except Exception:
            pass

    def get_serve_url(self):
        """Mendapatkan URL proteksi untuk melayani foto."""
        return f"/sewa/{self.rental.code}/foto/{self.id}/"


class Review(models.Model):
    class AsRole(models.TextChoices):
        PEMILIK = 'pemilik', 'Sebagai Pemilik'
        PENYEWA = 'penyewa', 'Sebagai Penyewa'

    rental = models.ForeignKey(
        Rental, on_delete=models.CASCADE, related_name='reviews',
        verbose_name="Sewa"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='reviews_given', verbose_name="Pengulas"
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='reviews_received', verbose_name="Yang Diulas"
    )
    as_role = models.CharField(
        max_length=10, choices=AsRole.choices, verbose_name="Sebagai Peran"
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Rating"
    )
    comment = models.TextField(blank=True, default='', verbose_name="Komentar")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Ulasan"
        verbose_name_plural = "Ulasan"
        # Unik per (rental, reviewer)
        constraints = [
            models.UniqueConstraint(fields=['rental', 'reviewer'], name='unique_review_per_rental')
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Ulasan {self.reviewer} → {self.reviewee} ({self.rating}★)"


class Dispute(models.Model):
    class Status(models.TextChoices):
        TERBUKA = 'terbuka', 'Terbuka'
        DIPUTUSKAN = 'diputuskan', 'Diputuskan'

    class Decision(models.TextChoices):
        KEMBALIKAN_PENUH = 'kembalikan_penuh', 'Kembalikan Penuh'
        POTONG_SEBAGIAN = 'potong_sebagian', 'Potong Sebagian'
        POTONG_PENUH = 'potong_penuh', 'Potong Penuh'

    rental = models.OneToOneField(
        Rental, on_delete=models.CASCADE, related_name='dispute',
        verbose_name="Sewa"
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='disputes_opened', verbose_name="Dibuka Oleh"
    )
    reason = models.TextField(verbose_name="Alasan")
    evidence_note = models.TextField(blank=True, default='', verbose_name="Catatan Bukti")

    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.TERBUKA, verbose_name="Status"
    )
    decision = models.CharField(
        max_length=20, choices=Decision.choices,
        blank=True, default='', verbose_name="Keputusan"
    )
    deduction_amount = models.PositiveIntegerField(default=0, verbose_name="Jumlah Potongan (Rp)")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='disputes_decided',
        verbose_name="Diputuskan Oleh"
    )
    decision_note = models.TextField(blank=True, default='', verbose_name="Catatan Keputusan")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Sengketa"
        verbose_name_plural = "Sengketa"
        ordering = ['-created_at']

    def __str__(self):
        return f"Sengketa {self.rental.code} – {self.get_status_display()}"


class RentalAgreement(models.Model):
    rental = models.OneToOneField(
        Rental, on_delete=models.CASCADE, related_name='agreement',
        verbose_name="Sewa"
    )
    terms_version = models.ForeignKey(
        'core.TermsVersion', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rental_agreements', verbose_name="Versi S&K"
    )
    terms_version_string = models.CharField(
        max_length=50, blank=True, default='v1.0', verbose_name="Nomor Versi S&K"
    )
    terms_hash = models.CharField(
        max_length=64, blank=True, default='', verbose_name="Hash SHA-256 S&K"
    )
    terms_text_snapshot = models.TextField(
        blank=True, default='', verbose_name="Snapshot Teks Lengkap S&K"
    )
    renter_name = models.CharField(
        max_length=200, blank=True, default='', verbose_name="Nama Lengkap Penyewa"
    )
    renter_nim = models.CharField(
        max_length=50, blank=True, default='', verbose_name="NIM Penyewa"
    )
    renter_campus = models.CharField(
        max_length=200, blank=True, default='', verbose_name="Kampus Penyewa"
    )
    owner_name = models.CharField(
        max_length=200, blank=True, default='', verbose_name="Nama Lengkap Pemilik"
    )
    owner_nim = models.CharField(
        max_length=50, blank=True, default='', verbose_name="NIM Pemilik"
    )
    owner_campus = models.CharField(
        max_length=200, blank=True, default='', verbose_name="Kampus Pemilik"
    )
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="Alamat IP Persetujuan"
    )
    user_agent = models.TextField(
        blank=True, default='', verbose_name="User Agent Persetujuan"
    )
    terms_snapshot = models.JSONField(
        default=dict, verbose_name="Snapshot Syarat & Ketentuan (JSON)"
    )
    accepted_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Waktu Persetujuan"
    )

    class Meta:
        verbose_name = "Perjanjian Sewa"
        verbose_name_plural = "Perjanjian Sewa"

    def __str__(self):
        return f"Perjanjian Sewa {self.rental.code}"


class HandoverSchedule(models.Model):
    class Status(models.TextChoices):
        DIUSULKAN = 'diusulkan', 'Diusulkan'
        DIKONFIRMASI = 'dikonfirmasi', 'Dikonfirmasi'
        DIUBAH = 'diubah', 'Diubah'

    rental = models.ForeignKey(
        Rental, on_delete=models.CASCADE, related_name='handover_schedules',
        verbose_name="Sewa"
    )
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='proposed_schedules', verbose_name="Diusulkan Oleh"
    )
    meet_at = models.DateTimeField(verbose_name="Waktu Pertemuan")
    meeting_point = models.ForeignKey(
        'accounts.MeetingPoint', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='handover_schedules', verbose_name="Titik Temu"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.DIUSULKAN, verbose_name="Status Jadwal"
    )
    note = models.TextField(blank=True, default='', verbose_name="Catatan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Jadwal Serah Terima"
        verbose_name_plural = "Jadwal Serah Terima"
        ordering = ['-created_at']

    def __str__(self):
        return f"Jadwal {self.rental.code} ({self.get_status_display()})"
