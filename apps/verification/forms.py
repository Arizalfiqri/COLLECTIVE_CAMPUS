import os
from django import forms
from django.core.exceptions import ValidationError
from PIL import Image


class KtmUploadForm(forms.Form):
    """
    Formulir unggah berkas foto KTM mahasiswa.
    Memeriksa batas ukuran (maks 5 MB) dan keaslian tipe citra (JPG/PNG) via Pillow.
    """
    ktm_image = forms.FileField(
        label="Foto Kartu Tanda Mahasiswa (KTM)",
        help_text="Format JPG atau PNG. Ukuran berkas maksimal 5 MB.",
        widget=forms.FileInput(attrs={
            'accept': 'image/jpeg,image/png,image/jpg',
            'class': 'sr-only',
            'id': 'ktm_file_input',
        }),
        error_messages={
            'required': 'Silakan pilih foto KTM Anda untuk diunggah.',
        }
    )

    def clean_ktm_image(self):
        image = self.cleaned_data.get('ktm_image')
        if not image:
            raise ValidationError("Berkas foto KTM wajib diunggah.")

        # 1. Batas ukuran berkas 5 MB (5 * 1024 * 1024 bytes)
        max_size = 5 * 1024 * 1024
        if image.size > max_size:
            size_mb = round(image.size / (1024 * 1024), 2)
            raise ValidationError(
                f"Ukuran berkas ({size_mb} MB) melebihi batas maksimal 5 MB. "
                "Silakan kompres atau pilih foto dengan ukuran lebih kecil."
            )

        # 2. Verifikasi tipe asli berkas menggunakan Pillow
        try:
            image_copy = Image.open(image)
            image_format = image_copy.format
            if not image_format or image_format.upper() not in ['JPEG', 'PNG']:
                raise ValidationError(
                    "Format berkas tidak didukung. Harap unggah foto dalam format JPG atau PNG."
                )
            # Pastikan berkas gambar tidak korup
            image_copy.verify()
        except ValidationError:
            raise
        except Exception:
            raise ValidationError(
                "Berkas citra rusak atau tidak dapat dibaca. Silakan pilih foto lain."
            )
        finally:
            # Kembalikan pointer berkas ke awal agar Django dapat menyimpannya
            if hasattr(image, 'seek'):
                image.seek(0)

        return image
