from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image

from apps.catalog.models import Item, Category, ItemPhoto
from apps.catalog.services import calculate_min_deposit, get_suggested_deposit_range


class ItemForm(forms.ModelForm):
    """
    Formulir pasang barang baru (/barang/baru/) dan ubah barang (/barang/<slug>/ubah/).
    """
    class Meta:
        model = Item
        fields = [
            'title', 'category', 'description', 'condition',
            'estimated_value', 'price_per_day', 'deposit_amount',
            'min_renter_tier', 'require_ktm_held',
            'min_days', 'max_days', 'pickup_area',
        ]
        labels = {
            'title': 'Judul Barang',
            'category': 'Kategori Barang',
            'description': 'Deskripsi Lengkap',
            'condition': 'Kondisi Barang',
            'estimated_value': 'Estimasi Nilai Barang (Rp)',
            'price_per_day': 'Harga Sewa per Hari (Rp)',
            'deposit_amount': 'Jumlah Deposit Jaminan (Rp)',
            'min_renter_tier': 'Tingkat Penyewa Minimal',
            'require_ktm_held': 'Syarat Jaminan KTM Fisik Ditahan',
            'min_days': 'Minimum Hari Sewa',
            'max_days': 'Maksimum Hari Sewa',
            'pickup_area': 'Area Pengambilan di Kampus',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'Contoh: Kamera Sony A6400 + Lensa Kit 16-50mm',
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'category': forms.Select(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Jelaskan kelengkapan, fungsi, minus kecil, dan aturan pemakaian barang...',
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'condition': forms.Select(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'estimated_value': forms.NumberInput(attrs={
                'placeholder': 'Maksimal Rp3.000.000',
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'price_per_day': forms.NumberInput(attrs={
                'placeholder': 'Contoh: 75000',
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'deposit_amount': forms.NumberInput(attrs={
                'placeholder': 'Boleh Rp0 jika nilai barang <= Rp150.000',
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'min_renter_tier': forms.Select(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'require_ktm_held': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-brand rounded border-line focus:ring-brand cursor-pointer',
            }),
            'min_days': forms.NumberInput(attrs={
                'min': 1,
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'max_days': forms.NumberInput(attrs={
                'min': 1,
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'pickup_area': forms.TextInput(attrs={
                'placeholder': 'Contoh: Perpustakaan Pusat / Gedung FMIPA',
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['category'].queryset = Category.objects.for_rental().order_by('order', 'name')
        self.fields['category'].empty_label = "-- Pilih Kategori Barang --"
        self.fields['min_renter_tier'].required = False
        self.fields['min_renter_tier'].initial = Item.RenterTier.BARU
        self.fields['require_ktm_held'].required = False

        deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
        if deposit_mode == 'off':
            self.fields['deposit_amount'].widget = forms.HiddenInput()
            self.fields['deposit_amount'].required = False
            self.fields['deposit_amount'].initial = 0
        elif deposit_mode == 'optional':
            self.fields['deposit_amount'].required = False
            self.fields['deposit_amount'].initial = self.instance.deposit_amount if (self.instance and self.instance.pk) else 0

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('min_renter_tier'):
            cleaned_data['min_renter_tier'] = Item.RenterTier.BARU

        est_val = cleaned_data.get('estimated_value')
        deposit = cleaned_data.get('deposit_amount')
        min_d = cleaned_data.get('min_days')
        max_d = cleaned_data.get('max_days')
        price = cleaned_data.get('price_per_day')
        category = cleaned_data.get('category')
        title = cleaned_data.get('title') or ''

        max_allowed_val = getattr(settings, 'MAX_ITEM_VALUE', 3000000)
        no_deposit_below = getattr(settings, 'NO_DEPOSIT_BELOW_VALUE', 150000)

        # 1. Validasi nilai uang positif
        if est_val is not None and est_val <= 0:
            self.add_error('estimated_value', "Estimasi nilai barang harus lebih dari Rp0.")
        if price is not None and price <= 0:
            self.add_error('price_per_day', "Harga sewa per hari harus lebih dari Rp0.")

        # 2. Batas nilai maksimum barang (SPEC v2 Bagian A.2: ditolak jika > MAX_ITEM_VALUE)
        if est_val is not None and est_val > max_allowed_val:
            val_str = f"Rp{max_allowed_val:,}".replace(',', '.')
            self.add_error(
                'estimated_value',
                f"Estimasi nilai barang tidak boleh melebihi {val_str}. "
                f"Barang di atas batas ini belum dapat dipasang di KampusRent demi mitigasi risiko."
            )

        # 3. Kategori Laptop (SPEC v2 Bagian A.2: dibatasi maksimal MAX_ITEM_VALUE)
        is_laptop = (category and category.slug == 'laptop') or ('laptop' in title.lower())
        if is_laptop and est_val is not None and est_val > max_allowed_val:
            val_str = f"Rp{max_allowed_val:,}".replace(',', '.')
            self.add_error(
                'estimated_value',
                f"Kategori Laptop dibatasi maksimal estimasi nilai {val_str}."
            )

        # 4. Validasi deposit sesuai DEPOSIT_MODE
        deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
        if deposit_mode == 'off':
            cleaned_data['deposit_amount'] = 0
        elif deposit_mode == 'optional':
            if cleaned_data.get('deposit_amount') is None:
                cleaned_data['deposit_amount'] = 0
            elif cleaned_data['deposit_amount'] < 0:
                self.add_error('deposit_amount', "Jaminan tidak boleh negatif.")
        else:
            if est_val is not None and deposit is not None:
                if est_val <= no_deposit_below:
                    # Barang di bawah atau sama dengan Rp150.000 boleh tanpa deposit (>= 0)
                    if deposit < 0:
                        self.add_error('deposit_amount', "Deposit tidak boleh negatif.")
                else:
                    min_required = calculate_min_deposit(est_val, self.user)
                    if deposit < min_required:
                        formatted_min = f"Rp{min_required:,}".replace(',', '.')
                        no_dep_str = f"Rp{no_deposit_below:,}".replace(',', '.')
                        self.add_error(
                            'deposit_amount',
                            f"Deposit minimum untuk barang ini adalah {formatted_min} "
                            f"(berdasarkan tangga jaminan platform). Nilai barang di atas {no_dep_str} tidak boleh tanpa deposit."
                        )

        # 5. Validasi batas hari sewa
        if min_d and max_d:
            if min_d < 1:
                self.add_error('min_days', "Minimum hari sewa minimal 1 hari.")
            if max_d < min_d:
                self.add_error('max_days', "Maksimum hari sewa tidak boleh lebih kecil dari minimum hari sewa.")

        return cleaned_data


def validate_uploaded_photos(files, existing_count=0):
    """
    Validasi berkas foto yang diunggah:
    - Jumlah foto: 1-6 foto
    - Format asli: JPG atau PNG via Pillow
    - Ukuran: maks 5 MB per foto
    """
    errors = []
    valid_photos = []

    total_count = existing_count + len(files)
    if total_count < 1:
        errors.append("Wajib mengunggah minimal 1 foto barang.")
    elif total_count > 6:
        errors.append(f"Maksimal 6 foto per barang. Anda mengunggah {total_count} foto.")

    for f in files:
        # Cek ukuran maks 5 MB
        if f.size > 5 * 1024 * 1024:
            size_mb = round(f.size / (1024 * 1024), 2)
            errors.append(f"Berkas '{f.name}' ({size_mb} MB) melebihi batas maksimal 5 MB.")
            continue

        # Cek keaslian citra via Pillow
        try:
            img = Image.open(f)
            if not img.format or img.format.upper() not in ['JPEG', 'PNG']:
                errors.append(f"Format berkas '{f.name}' tidak didukung. Harap unggah format JPG atau PNG.")
                continue
            img.verify()
            if hasattr(f, 'seek'):
                f.seek(0)
            valid_photos.append(f)
        except Exception:
            errors.append(f"Berkas '{f.name}' rusak atau bukan citra yang valid.")

    return valid_photos, errors
