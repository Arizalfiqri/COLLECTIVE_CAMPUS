from django.db import models
from django.conf import settings
from django.utils.text import slugify


class CategoryQuerySet(models.QuerySet):
    def for_rental(self):
        """Kategori yang tampil di modul sewa (scope sewa atau keduanya)."""
        return self.filter(scope__in=[Category.Scope.SEWA, Category.Scope.KEDUANYA])

    def for_sale(self):
        """Kategori yang tampil di modul jual beli (scope jual atau keduanya)."""
        return self.filter(scope__in=[Category.Scope.JUAL, Category.Scope.KEDUANYA])


class Category(models.Model):
    class Scope(models.TextChoices):
        SEWA = 'sewa', 'Sewa'
        JUAL = 'jual', 'Jual'
        KEDUANYA = 'keduanya', 'Keduanya'

    name = models.CharField(max_length=100, verbose_name="Nama Kategori")
    slug = models.SlugField(max_length=120, unique=True, verbose_name="Slug")
    scope = models.CharField(
        max_length=10, choices=Scope.choices, default=Scope.SEWA,
        verbose_name="Cakupan"
    )
    icon = models.CharField(max_length=50, blank=True, default='📦', verbose_name="Ikon")
    order = models.PositiveIntegerField(default=0, verbose_name="Urutan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")

    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    objects = CategoryQuerySet.as_manager()

    class Meta:
        verbose_name = "Kategori"
        verbose_name_plural = "Kategori"
        ordering = ['order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['name', 'scope'], name='uniq_category_name_scope'),
        ]

    def __str__(self):
        return self.name

    @property
    def icon_name(self):
        """Nama ikon Lucide untuk kategori ini (AGENT.md 5)."""
        slug_to_icon = {
            'kamera': 'camera',
            'wisuda': 'graduation-cap',
            'praktikum': 'flask-conical',
            'camping': 'tent',
            'proyektor': 'projector',
            'kostum': 'shirt',
            'laptop': 'laptop',
            'lain-lain': 'package',
            'pakaian-thrift': 'shirt',
            'buku-alat-kuliah': 'graduation-cap',
            'elektronik-jual': 'laptop',
            'perabot-kos': 'package',
            'hobi-olahraga': 'tent',
            'lainnya-jual': 'package',
        }
        return slug_to_icon.get(self.slug, 'package')

    @property
    def short_name(self):
        """Nama pendek kategori agar tidak terpotong (AGENT.md 2)."""
        slug_to_short = {
            'kamera': 'Kamera & Lensa',
            'wisuda': 'Wisuda',
            'praktikum': 'Praktikum',
            'camping': 'Camping',
            'proyektor': 'Proyektor',
            'kostum': 'Kostum',
            'laptop': 'Laptop',
            'lain-lain': 'Lainnya',
            'pakaian-thrift': 'Pakaian',
            'buku-alat-kuliah': 'Buku dan alat',
            'elektronik-jual': 'Elektronik',
            'perabot-kos': 'Perabot kos',
            'hobi-olahraga': 'Hobi',
            'lainnya-jual': 'Lainnya',
        }
        return slug_to_short.get(self.slug, self.name)

    @property
    def tint_bg(self):
        """Warna latar datar placeholder (backward compatibility)."""
        return self.tile_bg

    @property
    def tile_bg(self):
        """Warna latar datar ubin ilustrasi (AGENT.md 5A revisi: biru, kunyit, mint, koral)."""
        slug_to_tile = {
            'kamera': 'bg-tile-blue',
            'wisuda': 'bg-tile-saffron',
            'praktikum': 'bg-tile-mint',
            'camping': 'bg-tile-coral',
            'proyektor': 'bg-tile-blue',
            'kostum': 'bg-tile-saffron',
            'laptop': 'bg-tile-mint',
            'lain-lain': 'bg-tile-coral',
            'pakaian-thrift': 'bg-tile-saffron',
            'buku-alat-kuliah': 'bg-tile-blue',
            'elektronik-jual': 'bg-tile-mint',
            'perabot-kos': 'bg-tile-coral',
            'hobi-olahraga': 'bg-tile-blue',
            'lainnya-jual': 'bg-tile-coral',
        }
        return slug_to_tile.get(self.slug, 'bg-tile-blue')


    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Item(models.Model):
    class Condition(models.TextChoices):
        SANGAT_BAIK = 'sangat_baik', 'Sangat Baik'
        BAIK = 'baik', 'Baik'
        CUKUP = 'cukup', 'Cukup'

    class RenterTier(models.TextChoices):
        BARU = 'baru', 'Penyewa baru'
        TEPERCAYA = 'tepercaya', 'Penyewa tepercaya'
        SANGAT_TEPERCAYA = 'sangat_tepercaya', 'Penyewa sangat tepercaya'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='items', verbose_name="Pemilik"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='items', verbose_name="Kategori"
    )
    title = models.CharField(max_length=200, verbose_name="Judul Barang")
    slug = models.SlugField(max_length=220, unique=True, verbose_name="Slug")
    description = models.TextField(verbose_name="Deskripsi")
    condition = models.CharField(
        max_length=20, choices=Condition.choices,
        default=Condition.BAIK, verbose_name="Kondisi"
    )
    # Semua nilai uang: bilangan bulat rupiah
    estimated_value = models.PositiveIntegerField(verbose_name="Estimasi Nilai (Rp)")
    price_per_day = models.PositiveIntegerField(verbose_name="Harga Sewa per Hari (Rp)")
    deposit_amount = models.PositiveIntegerField(default=0, verbose_name="Jumlah Deposit (Rp)")
    min_days = models.PositiveIntegerField(default=1, verbose_name="Minimum Hari Sewa")
    max_days = models.PositiveIntegerField(default=30, verbose_name="Maksimum Hari Sewa")
    pickup_area = models.CharField(max_length=200, verbose_name="Area Pengambilan")
    min_renter_tier = models.CharField(
        max_length=20, choices=RenterTier.choices,
        default=RenterTier.BARU, verbose_name="Tingkat Penyewa Minimum"
    )
    require_ktm_held = models.BooleanField(
        default=False, verbose_name="Syarat Jaminan KTM Fisik Ditahan"
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")


    class Meta:
        verbose_name = "Barang"
        verbose_name_plural = "Barang"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', '-created_at']),
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Item.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def primary_photo(self):
        """Ambil foto utama (urutan pertama), memanfaatkan cache prefetch jika ada untuk mencegah query N+1."""
        if hasattr(self, '_prefetched_objects_cache') and 'photos' in self._prefetched_objects_cache:
            photos = sorted(self._prefetched_objects_cache['photos'], key=lambda p: p.order)
            return photos[0] if photos else None
        return self.photos.order_by('order').first()

    @property
    def tile_bg(self):
        """Warna latar datar ubin kartu barang ini."""
        if self.category:
            return self.category.tile_bg
        return 'bg-tile-blue'

    @property
    def fallback_illustration_url(self):
        """URL ilustrasi SVG datar cadangan sesuai kategori atau spesifik barang (AGENT.md revisi)."""
        title_lower = self.title.lower() if self.title else ''
        if 'ring light' in title_lower:
            return '/static/illustrations/ring-light.svg'
        if 'papan tulis' in title_lower or 'whiteboard' in title_lower:
            return '/static/illustrations/whiteboard.svg'
        if 'laptop' in title_lower or 'thinkpad' in title_lower:
            return '/static/illustrations/laptop.svg'
        if 'gaun' in title_lower or 'jas' in title_lower or 'kebaya' in title_lower:
            return '/static/illustrations/kostum.svg'

        cat_slug = self.category.slug if self.category else 'lain-lain'
        return f"/static/illustrations/{cat_slug}.svg"


    @property
    def average_rating(self):
        """Rating rata-rata dari ulasan sewa barang ini."""
        from apps.rentals.models import Review
        reviews = Review.objects.filter(rental__item=self, as_role='penyewa')
        if not reviews.exists():
            return None
        return round(reviews.aggregate(avg=models.Avg('rating'))['avg'], 1)

    @property
    def review_count(self):
        from apps.rentals.models import Review
        return Review.objects.filter(rental__item=self, as_role='penyewa').count()


class ItemPhoto(models.Model):
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name='photos',
        verbose_name="Barang"
    )
    image = models.ImageField(upload_to='items/', verbose_name="Foto")
    order = models.PositiveIntegerField(default=0, verbose_name="Urutan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")

    class Meta:
        verbose_name = "Foto Barang"
        verbose_name_plural = "Foto Barang"
        ordering = ['order']

    def __str__(self):
        return f"Foto {self.order} - {self.item.title}"

    def save(self, *args, **kwargs):
        # Optimasi dan pengecilan gambar: maks 1280px sisi terpanjang, kualitas JPEG 80 (AGENT.md 9)
        if self.image:
            try:
                from PIL import Image
                import io
                from django.core.files.base import ContentFile

                # Hanya proses jika file baru diunggah / memiliki atribut file
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
