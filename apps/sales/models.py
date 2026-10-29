import datetime
import io
import random
import string
from PIL import Image

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import Category


class SaleItemQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=SaleItem.Status.AKTIF, expires_at__gt=timezone.now())


class SaleItem(models.Model):
    class Condition(models.TextChoices):
        BARU_SEGEL = 'baru_segel', 'Baru (segel)'
        SEPERTI_BARU = 'seperti_baru', 'Seperti baru'
        BAIK = 'baik', 'Baik'
        CUKUP = 'cukup', 'Cukup'
        ADA_CACAT = 'ada_cacat', 'Ada cacat'

    class Status(models.TextChoices):
        AKTIF = 'aktif', 'Aktif'
        DIPESAN = 'dipesan', 'Dipesan'
        TERJUAL = 'terjual', 'Terjual'
        NONAKTIF = 'nonaktif', 'Nonaktif'
        KEDALUWARSA = 'kedaluwarsa', 'Kedaluwarsa'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sale_items',
        verbose_name="Penjual"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_items',
        verbose_name="Kategori"
    )
    title = models.CharField(max_length=200, verbose_name="Judul Barang")
    slug = models.SlugField(max_length=220, unique=True, verbose_name="Slug")
    description = models.TextField(verbose_name="Deskripsi")
    condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        default=Condition.BAIK,
        verbose_name="Kondisi"
    )
    flaws = models.TextField(
        blank=True,
        default='',
        verbose_name="Cacat atau minus"
    )
    included_items = models.TextField(
        blank=True,
        default='',
        verbose_name="Kelengkapan"
    )
    reason_for_sale = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Alasan dijual"
    )
    price = models.PositiveIntegerField(verbose_name="Harga (Rp)")
    original_price = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Harga beli asli (Rp)"
    )
    pickup_area = models.CharField(max_length=200, verbose_name="Area titik temu")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AKTIF,
        verbose_name="Status"
    )
    takedown_reason = models.TextField(blank=True, default='', verbose_name="Alasan Penurunan Listing")
    takedown_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_items_taken_down',
        verbose_name="Diturunkan oleh"
    )
    takedown_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Penurunan Listing")
    expires_at = models.DateTimeField(verbose_name="Kedaluwarsa pada")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    objects = SaleItemQuerySet.as_manager()

    class Meta:
        verbose_name = "Barang Jualan"
        verbose_name_plural = "Barang Jualan"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['expires_at', 'status']),
        ]

    def __str__(self):
        return f"{self.title} (Rp{self.price:,})"

    def clean(self):
        super().clean()
        if self.condition in [self.Condition.CUKUP, self.Condition.ADA_CACAT]:
            if not self.flaws or not self.flaws.strip():
                raise ValidationError({
                    'flaws': 'Rincian cacat atau minus wajib diisi untuk barang dengan kondisi Cukup atau Ada cacat.'
                })
        if self.owner_id:
            from apps.sales.services import get_seller_tier, get_seller_max_price, SELLER_TIER_LABELS
            tier = get_seller_tier(self.owner)
            max_price = get_seller_max_price(tier)
            if self.price and self.price > max_price:
                tier_label = SELLER_TIER_LABELS.get(tier, tier).lower()
                raise ValidationError({
                    'price': f"Harga melebihi batas maksimum untuk tingkat {tier_label} (maks. Rp{max_price:,})."
                })

        from apps.sales.services import check_prohibited_keywords
        is_proh, kw = check_prohibited_keywords(
            self.title, self.description, self.included_items, self.reason_for_sale, self.flaws
        )
        if is_proh:
            raise ValidationError(
                f"Barang tidak dapat dipasang atau disimpan karena mengandung kata terlarang: '{kw}'."
            )

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + datetime.timedelta(days=60)

        if not self.slug:
            base_slug = slugify(self.title) or 'barang-jual'
            unique_slug = base_slug
            counter = 1
            while SaleItem.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug

        super().save(*args, **kwargs)

    @property
    def primary_photo(self):
        return self.photos.first()

    @property
    def savings_percent(self):
        if self.original_price and self.original_price > self.price:
            diff = self.original_price - self.price
            return round((diff / self.original_price) * 100)
        return None

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def seller_tier(self):
        from apps.sales.services import get_seller_tier
        return get_seller_tier(self.owner)

    @property
    def seller_tier_label(self):
        from apps.sales.services import SELLER_TIER_LABELS
        return SELLER_TIER_LABELS.get(self.seller_tier, 'Penjual baru')

    @property
    def tile_bg(self):
        if self.category:
            return self.category.tile_bg
        return 'bg-tile-blue'

    @property
    def fallback_illustration_url(self):
        title_lower = self.title.lower() if self.title else ''
        if 'ring light' in title_lower:
            return '/static/illustrations/ring-light.svg'
        if 'papan tulis' in title_lower or 'whiteboard' in title_lower:
            return '/static/illustrations/whiteboard.svg'
        if 'laptop' in title_lower or 'thinkpad' in title_lower:
            return '/static/illustrations/laptop.svg'
        if 'gaun' in title_lower or 'jas' in title_lower or 'kebaya' in title_lower:
            return '/static/illustrations/kostum.svg'

        cat_slug = self.category.slug if self.category else 'lainnya-jual'
        # fallback mapping to standard svg illustration
        if cat_slug in ('pakaian-thrift', 'kostum'):
            return '/static/illustrations/kostum.svg'
        if cat_slug in ('buku-alat-kuliah', 'wisuda'):
            return '/static/illustrations/wisuda.svg'
        if cat_slug in ('elektronik-jual', 'laptop'):
            return '/static/illustrations/laptop.svg'
        if cat_slug in ('hobi-olahraga', 'camping'):
            return '/static/illustrations/camping.svg'
        return '/static/illustrations/lain-lain.svg'


class SaleItemPhoto(models.Model):
    sale_item = models.ForeignKey(
        SaleItem,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name="Barang jualan"
    )
    image = models.ImageField(upload_to='sales/', verbose_name="Foto")
    order = models.PositiveIntegerField(default=0, verbose_name="Urutan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")

    class Meta:
        verbose_name = "Foto Barang Jualan"
        verbose_name_plural = "Foto Barang Jualan"
        ordering = ['order', 'id']

    def __str__(self):
        return f"Foto {self.order} - {self.sale_item.title}"

    def save(self, *args, **kwargs):
        if self.image:
            try:
                if hasattr(self.image, 'file'):
                    img = Image.open(self.image)
                    max_side = 1280
                    w, h = img.size
                    should_resize = w > max_side or h > max_side

                    if should_resize or img.format != 'JPEG':
                        if should_resize:
                            ratio = min(max_side / w, max_side / h)
                            new_size = (int(w * ratio), int(h * ratio))
                            img = img.resize(new_size, Image.Resampling.LANCZOS)
                        if img.mode in ('RGBA', 'P'):
                            img = img.convert('RGB')
                        output = io.BytesIO()
                        img.save(output, format='JPEG', quality=80, optimize=True)
                        output.seek(0)
                        base_name = self.image.name.rsplit('.', 1)[0]
                        new_name = f"{base_name}.jpg"
                        self.image.save(new_name, ContentFile(output.read()), save=False)
            except Exception:
                pass
        super().save(*args, **kwargs)


class SellerTermsAcceptance(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_terms_acceptances',
        verbose_name="Penjual"
    )
    terms_version = models.ForeignKey(
        'core.TermsVersion',
        on_delete=models.PROTECT,
        verbose_name="Versi S&K"
    )
    terms_hash = models.CharField(max_length=64, verbose_name="Hash SHA-256")
    text_snapshot = models.TextField(verbose_name="Snapshot teks S&K")
    accepted_at = models.DateTimeField(auto_now_add=True, verbose_name="Waktu persetujuan")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Alamat IP")
    user_agent = models.CharField(max_length=500, blank=True, default='', verbose_name="User agent")

    class Meta:
        verbose_name = "Persetujuan S&K Penjual"
        verbose_name_plural = "Persetujuan S&K Penjual"
        ordering = ['-accepted_at']

    def __str__(self):
        return f"{self.user.username} - S&K {self.terms_version.version} ({self.accepted_at.strftime('%Y-%m-%d %H:%M')})"


def generate_sale_order_code():
    """Kode pendek unik untuk identifikasi pesanan jual beli (KJ-XXXXXX)."""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = 'KJ-' + ''.join(random.choices(chars, k=6))
        if not SaleOrder.objects.filter(code=code).exists():
            return code


class SaleOrder(models.Model):
    class Status(models.TextChoices):
        MENUNGGU_PEMBAYARAN = 'menunggu_pembayaran', 'Menunggu pembayaran'
        DIBAYAR = 'dibayar', 'Dibayar'
        DISERAHKAN = 'diserahkan', 'Diserahkan'
        SELESAI = 'selesai', 'Selesai'
        DIBATALKAN = 'dibatalkan', 'Dibatalkan'
        KEDALUWARSA = 'kedaluwarsa', 'Kedaluwarsa'
        SENGKETA = 'sengketa', 'Sengketa'

    code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        default=generate_sale_order_code,
        verbose_name="Kode Pesanan"
    )
    item = models.ForeignKey(
        SaleItem,
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name="Barang Jualan"
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sale_orders_bought',
        verbose_name="Pembeli"
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sale_orders_sold',
        verbose_name="Penjual"
    )
    price_snapshot = models.PositiveIntegerField(verbose_name="Snapshot Harga (Rp)")
    listing_snapshot = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Snapshot Listing"
    )
    commission = models.PositiveIntegerField(
        default=0,
        verbose_name="Komisi Platform (Rp)"
    )
    net_to_seller = models.PositiveIntegerField(
        default=0,
        verbose_name="Jumlah Bersih Penjual (Rp)"
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.MENUNGGU_PEMBAYARAN,
        verbose_name="Status Pesanan"
    )
    reserved_until = models.DateTimeField(verbose_name="Batas Waktu Pembayaran")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Bayar")
    meetup_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Pertemuan")
    meeting_point = models.ForeignKey(
        'accounts.MeetingPoint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_orders',
        verbose_name="Titik Temu"
    )
    handed_over_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Diserahkan")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Selesai")
    cancel_reason = models.TextField(blank=True, default='', verbose_name="Alasan Pembatalan")
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_sale_orders',
        verbose_name="Dibatalkan Oleh"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Pesanan Jual Beli"
        verbose_name_plural = "Pesanan Jual Beli"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['buyer', 'status']),
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['reserved_until', 'status']),
        ]

    def __str__(self):
        return f"{self.code} - {self.item.title} (Rp{self.price_snapshot:,})"

    @property
    def total_amount(self):
        return self.price_snapshot

    @property
    def is_paid(self):
        return self.status in [
            self.Status.DIBAYAR,
            self.Status.DISERAHKAN,
            self.Status.SELESAI,
            self.Status.SENGKETA,
        ] or bool(self.paid_at)


class SaleAgreement(models.Model):
    order = models.OneToOneField(
        SaleOrder,
        on_delete=models.CASCADE,
        related_name='agreement',
        verbose_name="Pesanan Jual Beli"
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sale_agreements',
        verbose_name="Pembeli"
    )
    terms_version = models.ForeignKey(
        'core.TermsVersion',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Versi S&K"
    )
    terms_hash = models.CharField(max_length=64, verbose_name="Hash SHA-256 S&K")
    text_snapshot = models.TextField(verbose_name="Snapshot Teks S&K")
    agreed_at = models.DateTimeField(auto_now_add=True, verbose_name="Waktu Persetujuan")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Alamat IP")
    user_agent = models.CharField(max_length=500, blank=True, default='', verbose_name="User Agent")

    class Meta:
        verbose_name = "Perjanjian Pembelian"
        verbose_name_plural = "Perjanjian Pembelian"
        ordering = ['-agreed_at']

    def __str__(self):
        return f"Perjanjian {self.order.code} - {self.buyer.username}"


class SaleDispute(models.Model):
    class Type(models.TextChoices):
        TIDAK_SESUAI_DESKRIPSI = 'tidak_sesuai_deskripsi', 'Tidak sesuai deskripsi'
        PENJUAL_TIDAK_HADIR = 'penjual_tidak_hadir', 'Penjual tidak hadir'
        RUSAK_SAAT_SERAH_TERIMA = 'rusak_saat_serah_terima', 'Rusak saat serah terima'
        PALSU = 'palsu', 'Palsu / Tidak asli'
        LAINNYA = 'lainnya', 'Lainnya'

    class Status(models.TextChoices):
        TERBUKA = 'terbuka', 'Terbuka'
        DIPROSES = 'diproses', 'Sedang Ditinjau'
        SELESAI = 'selesai', 'Selesai Diputuskan'
        DITOLAK = 'ditolak', 'Ditolak'

    class Decision(models.TextChoices):
        REFUND_PEMBELI = 'refund_pembeli', 'Pengembalian Dana ke Pembeli (Refund Penuh)'
        LEPAS_KE_PENJUAL = 'lepas_ke_penjual', 'Pencairan Dana ke Penjual (Lepas Penuh)'
        SEBAGIAN = 'sebagian', 'Penyelesaian Sebagian (Split Nominal)'

    order = models.OneToOneField(
        SaleOrder,
        on_delete=models.CASCADE,
        related_name='dispute',
        verbose_name="Pesanan Jual Beli"
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sale_disputes_opened',
        verbose_name="Pembuka Sengketa"
    )
    dispute_type = models.CharField(
        max_length=40,
        choices=Type.choices,
        default=Type.LAINNYA,
        verbose_name="Jenis Sengketa"
    )
    reason = models.TextField(verbose_name="Uraian Sengketa")
    evidence_photos = models.JSONField(default=list, blank=True, verbose_name="Bukti Foto Privat")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TERBUKA,
        verbose_name="Status Sengketa"
    )
    decision = models.CharField(
        max_length=30,
        choices=Decision.choices,
        blank=True,
        default='',
        verbose_name="Keputusan"
    )
    nominal = models.PositiveIntegerField(default=0, verbose_name="Nominal Putusan (Rp)")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_disputes_decided',
        verbose_name="Pemutus (Staf Admin)"
    )
    notes = models.TextField(blank=True, default='', verbose_name="Catatan Putusan Admin")
    seller_violation_recorded = models.BooleanField(default=False, verbose_name="Pelanggaran Penjual Dicatat")
    seller_violation_notes = models.CharField(max_length=255, blank=True, default='', verbose_name="Catatan Pelanggaran Penjual")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Diselesaikan pada")

    class Meta:
        verbose_name = "Sengketa Jual Beli"
        verbose_name_plural = "Sengketa Jual Beli"
        ordering = ['-created_at']

    def __str__(self):
        return f"Sengketa {self.order.code} - {self.get_dispute_type_display()} ({self.get_status_display()})"

    @property
    def sale_order(self):
        return self.order


class SaleReview(models.Model):
    class Role(models.TextChoices):
        PEMBELI = 'pembeli', 'Sebagai Pembeli'
        PENJUAL = 'penjual', 'Sebagai Penjual'

    order = models.ForeignKey(
        'sales.SaleOrder',
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name="Pesanan Jual Beli"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sale_reviews_given',
        verbose_name="Pengulas"
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sale_reviews_received',
        verbose_name="Yang Diulas"
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        verbose_name="Sebagai Peran"
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Rating (1-5)"
    )
    comment = models.CharField(
        max_length=300,
        blank=True,
        default='',
        verbose_name="Komentar (maks. 300 karakter)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Ulasan Jual Beli"
        verbose_name_plural = "Ulasan Jual Beli"
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'reviewer'],
                name='unique_sale_review_per_reviewer_order'
            )
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Ulasan {self.reviewer} → {self.reviewee} ({self.rating}★)"


class SaleItemReport(models.Model):
    class Reason(models.TextChoices):
        BARANG_TERLARANG = 'barang_terlarang', 'Barang terlarang atau ilegal'
        INDIKASI_PENIPUAN = 'indikasi_penipuan', 'Indikasi penipuan atau spam'
        DESKRIPSI_PALSU = 'deskripsi_palsu', 'Deskripsi, kondisi, atau foto palsu'
        HARGA_TIDAK_WAJAR = 'harga_tidak_wajar', 'Harga tidak wajar atau manipulatif'
        KONTAK_LUAR = 'kontak_luar', 'Mengarahkan transaksi di luar platform'
        LAINNYA = 'lainnya', 'Lainnya'

    class Status(models.TextChoices):
        MENUNGGU = 'menunggu', 'Menunggu'
        DITINDAKLANJUTI = 'ditindaklanjuti', 'Ditindaklanjuti'
        DIABAIKAN = 'diabaikan', 'Diabaikan'

    item = models.ForeignKey(
        SaleItem,
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name="Barang Jualan"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sale_reports_filed',
        verbose_name="Pelapor"
    )
    reason = models.CharField(
        max_length=40,
        choices=Reason.choices,
        default=Reason.LAINNYA,
        verbose_name="Alasan Laporan"
    )
    notes = models.TextField(blank=True, default='', verbose_name="Catatan atau Penjelasan")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.MENUNGGU,
        verbose_name="Status Laporan"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_reports_reviewed',
        verbose_name="Ditinjau oleh"
    )
    action_taken = models.CharField(max_length=255, blank=True, default='', verbose_name="Tindakan yang Diambil")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dilaporkan pada")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Diselesaikan pada")

    class Meta:
        verbose_name = "Laporan Barang Jualan"
        verbose_name_plural = "Laporan Barang Jualan"
        ordering = ['-created_at']

    def __str__(self):
        return f"Laporan {self.item.title} oleh {self.reporter.username} ({self.get_status_display()})"


class SaleOffer(models.Model):
    class Status(models.TextChoices):
        MENUNGGU = 'menunggu', 'Menunggu tanggapan'
        DITERIMA = 'diterima', 'Diterima'
        DITOLAK = 'ditolak', 'Ditolak'
        KEDALUWARSA = 'kedaluwarsa', 'Kedaluwarsa'
        DIBATALKAN = 'dibatalkan', 'Dibatalkan'

    item = models.ForeignKey(
        SaleItem,
        on_delete=models.CASCADE,
        related_name='offers',
        verbose_name="Barang Jualan"
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sale_offers_made',
        verbose_name="Calon Pembeli"
    )
    offered_price = models.PositiveIntegerField(verbose_name="Harga Tawaran (Rp)")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.MENUNGGU,
        verbose_name="Status Tawaran"
    )
    order = models.ForeignKey(
        'SaleOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_offer_source',
        verbose_name="Pesanan Terkait"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    expires_at = models.DateTimeField(verbose_name="Kedaluwarsa pada")

    class Meta:
        verbose_name = "Tawaran Harga Jual Beli"
        verbose_name_plural = "Tawaran Harga Jual Beli"
        ordering = ['-created_at']

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at and self.status == self.Status.MENUNGGU

    def clean(self):
        super().clean()
        if self.offered_price and self.item_id and self.offered_price >= self.item.price:
            raise ValidationError({'offered_price': "Harga tawaran harus lebih rendah dari harga listing."})
        if self.item_id and self.buyer_id and self.item.owner_id == self.buyer_id:
            raise ValidationError({'buyer': "Penjual tidak dapat menawar barang miliknya sendiri."})

    def __str__(self):
        return f"Tawaran Rp{self.offered_price:,} untuk {self.item.title} oleh {self.buyer.username}"




