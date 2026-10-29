from django.db import models
from django.conf import settings


class TrustScore(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='trust_score', verbose_name="Pengguna"
    )
    score = models.PositiveIntegerField(default=60, verbose_name="Skor Kepercayaan (0-100)")
    risk_probability = models.FloatField(default=0.0, verbose_name="Probabilitas Risiko")
    is_new_user = models.BooleanField(default=True, verbose_name="Pengguna Baru")
    features = models.JSONField(default=dict, blank=True, verbose_name="Fitur ML")
    top_factors = models.JSONField(default=list, blank=True, verbose_name="Faktor Utama")
    model_version = models.CharField(max_length=50, blank=True, default='', verbose_name="Versi Model")
    computed_at = models.DateTimeField(null=True, blank=True, verbose_name="Dihitung Pada")

    # Override manual admin
    override_score = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Skor Override Admin (0-100)"
    )
    override_note = models.TextField(
        blank=True, default='',
        verbose_name="Catatan Wajib Override Admin"
    )
    override_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='trust_overrides', verbose_name="Di-override Oleh"
    )
    override_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Waktu Override"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Skor Kepercayaan"
        verbose_name_plural = "Skor Kepercayaan"

    def __str__(self):
        label = self.get_label()
        effective = self.effective_score
        suffix = " (Override)" if self.override_score is not None else ""
        return f"{self.user} – Skor {effective}{suffix} ({label})"

    @property
    def effective_score(self):
        """Skor yang aktif digunakan (menggunakan override admin jika ada)."""
        if self.override_score is not None:
            return self.override_score
        return self.score

    def get_effective_score(self):
        return self.effective_score

    def get_label(self):
        """Mendapatkan label teks sesuai skor efektif dan status pengguna baru."""
        if self.override_score is not None:
            if self.override_score >= 70:
                return "Tepercaya (Override)"
            elif self.override_score >= 40:
                return "Cukup (Override)"
            return "Perlu hati-hati (Override)"

        if self.is_new_user:
            return "Pengguna baru"
        if self.score >= 70:
            return "Tepercaya"
        if self.score >= 40:
            return "Cukup"
        return "Perlu hati-hati"

    def get_color(self):
        """Warna CSS token sesuai design.md."""
        effective = self.effective_score
        if self.is_new_user and self.override_score is None:
            return "ink-muted"
        if effective >= 70:
            return "success"
        if effective >= 40:
            return "warning"
        return "danger"

    def get_token_color(self):
        """Token warna baru sesuai AGENT.md 5A (pine, amber-text, brick, ink-muted)."""
        effective = self.effective_score
        if self.is_new_user and self.override_score is None:
            return "ink-muted"
        if effective >= 70:
            return "pine"
        if effective >= 40:
            return "amber-text"
        return "brick"


class TrustTrainingExample(models.Model):
    """
    Menyimpan snapshot fitur saat pengajuan sewa dan label masalah setelah sewa selesai.
    Digunakan untuk continuous learning model ML dari data transaksi nyata.
    """
    class Source(models.TextChoices):
        LIVE = 'live', 'Live (Waktu Nyata)'
        BACKFILL = 'backfill', 'Backfill (Data Lama)'

    class ProblemLabel(models.IntegerChoices):
        AMAN = 0, 'Aman / Tepat Waktu'
        BERMASALAH = 1, 'Bermasalah'

    rental = models.OneToOneField(
        'rentals.Rental', on_delete=models.CASCADE,
        related_name='trust_training_example', verbose_name="Pesanan Sewa"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='trust_training_examples', verbose_name="Penyewa"
    )
    features = models.JSONField(default=dict, verbose_name="Snapshot Fitur Saat Pengajuan")
    predicted_risk = models.FloatField(null=True, blank=True, verbose_name="Prediksi Risiko")
    model_version = models.CharField(max_length=100, blank=True, default='', verbose_name="Versi Model")
    label_problem = models.IntegerField(
        null=True, blank=True,
        choices=ProblemLabel.choices,
        verbose_name="Label Kasus Bermasalah"
    )
    labeled_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Pelabelan")
    source = models.CharField(
        max_length=20, choices=Source.choices,
        default=Source.LIVE, db_index=True,
        verbose_name="Sumber Data"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Contoh Pelatihan Skor Kepercayaan"
        verbose_name_plural = "Contoh Pelatihan Skor Kepercayaan"
        ordering = ['-created_at']

    def __str__(self):
        lbl = self.get_label_problem_display() if self.label_problem is not None else "Belum Dilabeli"
        return f"TrainingExample {self.rental.code} – {self.user.username} [{lbl}] ({self.source})"


class TrustModelVersion(models.Model):
    """
    Mencatat silsilah dan metrik versi artefak model ML skor kepercayaan.
    """
    version = models.CharField(max_length=100, unique=True, verbose_name="Versi Model")
    trained_at = models.DateTimeField(auto_now_add=True, verbose_name="Dilatih pada")
    n_real = models.PositiveIntegerField(default=0, verbose_name="Jumlah Data Nyata")
    n_synthetic = models.PositiveIntegerField(default=0, verbose_name="Jumlah Data Sintetis")
    metrics = models.JSONField(default=dict, verbose_name="Metrik Evaluasi")
    is_active = models.BooleanField(default=False, db_index=True, verbose_name="Model Aktif")
    notes = models.TextField(blank=True, default='', verbose_name="Catatan Pelatihan/Promosi")

    class Meta:
        verbose_name = "Versi Model Skor Kepercayaan"
        verbose_name_plural = "Versi Model Skor Kepercayaan"
        ordering = ['-trained_at']

    def __str__(self):
        active_tag = " [AKTIF]" if self.is_active else ""
        return f"ModelVersion {self.version}{active_tag} – {self.trained_at:%d %b %Y %H:%M}"

