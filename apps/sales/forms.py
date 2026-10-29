from django import forms
from django.core.exceptions import ValidationError

from apps.catalog.forms import validate_uploaded_photos
from apps.catalog.models import Category
from apps.sales.models import SaleItem
from apps.sales.services import (
    get_seller_tier,
    get_seller_max_price,
    check_prohibited_keywords,
    SELLER_TIER_LABELS,
)


class SaleItemForm(forms.ModelForm):
    agree_terms = forms.BooleanField(
        required=True,
        label="Saya telah membaca dan menyetujui Syarat & Ketentuan Penjual",
        error_messages={
            'required': 'Anda wajib menyetujui Syarat & Ketentuan Penjual untuk memasang barang.'
        }
    )

    class Meta:
        model = SaleItem
        fields = [
            'category',
            'title',
            'description',
            'condition',
            'flaws',
            'included_items',
            'reason_for_sale',
            'price',
            'original_price',
            'pickup_area',
        ]
        widgets = {
            'category': forms.Select(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'title': forms.TextInput(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
                'placeholder': 'Contoh: Buku Kalkulus Edisi 8, Sepatu Converse Chuck Taylor Ori',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
                'rows': 4,
                'placeholder': 'Jelaskan riwayat pemakaian, kondisi fisik, dan alasan dijual secara jujur...',
            }),
            'condition': forms.Select(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
            }),
            'flaws': forms.Textarea(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
                'rows': 2,
                'placeholder': 'Wajib diisi jika kondisi Cukup atau Ada cacat. Contoh: ada goresan tipis di sudut bawah...',
            }),
            'included_items': forms.TextInput(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
                'placeholder': 'Contoh: Dus asli, kabel charger, tas pembungkus',
            }),
            'reason_for_sale': forms.TextInput(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
                'placeholder': 'Contoh: Sudah selesai mata kuliah bersangkutan, ingin upgrade perangkat',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
                'placeholder': 'Contoh: 150000',
            }),
            'original_price': forms.NumberInput(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
                'placeholder': 'Harga baru/asli saat beli (opsional)',
            }),
            'pickup_area': forms.TextInput(attrs={
                'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
                'placeholder': 'Contoh: Gazebo Teknik Untan, Perpustakaan Pusat Polnep',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['category'].queryset = Category.objects.for_sale().order_by('order', 'name')
        self.fields['category'].empty_label = "-- Pilih Kategori Jual --"
        self.fields['flaws'].required = False
        self.fields['included_items'].required = False
        self.fields['reason_for_sale'].required = False
        self.fields['original_price'].required = False

        if self.instance and self.instance.pk:
            # Pada mode ubah barang, agree_terms tidak wajib dicentang ulang
            self.fields['agree_terms'].required = False

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None:
            if price <= 0:
                raise forms.ValidationError("Harga jual harus lebih besar dari Rp0.")
            if self.user:
                tier = get_seller_tier(self.user)
                max_price = get_seller_max_price(tier)
                if price > max_price:
                    tier_label = SELLER_TIER_LABELS.get(tier, tier).lower()
                    raise forms.ValidationError(
                        f"Harga melebihi batas maksimum untuk tingkat {tier_label} (maks. Rp{max_price:,})."
                    )
        return price

    def clean(self):
        cleaned_data = super().clean()
        condition = cleaned_data.get('condition')
        flaws = cleaned_data.get('flaws')
        price = cleaned_data.get('price')
        original_price = cleaned_data.get('original_price')

        # 1. Validasi cacat
        if condition in [SaleItem.Condition.CUKUP, SaleItem.Condition.ADA_CACAT]:
            if not flaws or not flaws.strip():
                self.add_error(
                    'flaws',
                    "Rincian cacat atau minus wajib diisi untuk barang dengan kondisi Cukup atau Ada cacat."
                )

        # 2. Validasi harga asli vs harga jual
        if original_price is not None and price is not None:
            if original_price <= 0:
                self.add_error('original_price', "Harga beli asli harus lebih besar dari Rp0.")

        # 3. Penyaringan kata kunci terlarang
        title = cleaned_data.get('title', '')
        desc = cleaned_data.get('description', '')
        included = cleaned_data.get('included_items', '')
        reason = cleaned_data.get('reason_for_sale', '')
        flaws_text = flaws or ''

        is_prohibited, kw = check_prohibited_keywords(title, desc, included, reason, flaws_text)
        if is_prohibited:
            msg = (
                f"Barang tidak dapat dipasang karena mengandung kata atau jenis barang terlarang: '{kw}'. "
                "Platform melarang penjualan obat resep, miras, rokok/vape, senjata, hewan, makanan olahan, "
                "barang palsu/curian, dan akun digital."
            )
            raise forms.ValidationError(msg)

        return cleaned_data
