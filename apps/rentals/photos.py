import base64
import io
import logging
import uuid
from datetime import timedelta
from pathlib import Path
from PIL import Image, ImageOps

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.rentals.models import Rental, ConditionPhoto

logger = logging.getLogger(__name__)


def resize_and_compress_image(image_input, max_dim=1280, quality=80):
    """
    Mengecilkan gambar ke maksimal 1280 px (proporsional),
    memperbaiki orientasi EXIF kamera ponsel, mengonversi ke RGB,
    dan mengompresi ke JPEG dengan quality=80.
    Menerima File object, bytes, atau base64 data string.
    Mengembalikan bytes JPEG.
    """
    if isinstance(image_input, str):
        # Kemungkinan base64 data URL dari canvas getUserMedia (data:image/jpeg;base64,...)
        if ',' in image_input:
            image_input = image_input.split(',', 1)[1]
        raw_bytes = base64.b64decode(image_input)
        in_stream = io.BytesIO(raw_bytes)
    elif hasattr(image_input, 'read'):
        in_stream = io.BytesIO(image_input.read())
    elif isinstance(image_input, (bytes, bytearray)):
        in_stream = io.BytesIO(image_input)
    else:
        raise ValueError("Format masukan gambar tidak dikenali.")

    in_stream.seek(0)
    image = Image.open(in_stream)

    # 1. Perbaiki orientasi EXIF (misal hasil jepretan kamera smartphone)
    try:
        image = ImageOps.exif_transpose(image)
    except Exception as e:
        logger.debug(f"Gagal exif_transpose: {e}")

    # 2. Konversi ke mode RGB (menangani RGBA, P, grayscale, dsb)
    if image.mode != 'RGB':
        image = image.convert('RGB')

    # 3. Resize proporsional jika sisi terpanjang melebihi max_dim (1280 px)
    width, height = image.size
    if width > max_dim or height > max_dim:
        image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

    # 4. Simpan ke JPEG dengan quality 80
    out_stream = io.BytesIO()
    image.save(out_stream, format='JPEG', quality=quality, optimize=True)
    out_stream.seek(0)
    return out_stream.getvalue()


def save_condition_photo(rental, user, phase, image_input, note=""):
    """
    Memproses dan menyimpan foto kondisi secara privat di private_media/conditions/.
    - Mengecilkan ke maks 1280 px, JPEG quality 80
    - Menyimpan fisik file di private_media/conditions/
    - Membuat record ConditionPhoto
    """
    if phase not in ConditionPhoto.Phase.values:
        raise ValueError(f"Fase foto '{phase}' tidak valid.")

    is_participant = (
        user.id in [rental.renter_id, rental.owner_id] or
        user.is_staff or user.is_superuser
    )
    if not is_participant:
        raise PermissionError("Hanya peserta sewa atau admin yang dapat mengunggah foto kondisi.")

    # Pastikan direktori private_media/conditions ada
    target_dir = Path(settings.PRIVATE_MEDIA_ROOT) / 'conditions'
    target_dir.mkdir(parents=True, exist_ok=True)

    # Kompresi dan resize
    compressed_bytes = resize_and_compress_image(image_input, max_dim=1280, quality=80)

    # Beri nama file unik
    unique_suffix = uuid.uuid4().hex[:8]
    filename = f"{rental.code}_{phase}_{unique_suffix}.jpg"
    full_path = target_dir / filename

    # Tulis berkas fisik ke direktori privat
    with open(full_path, 'wb') as f:
        f.write(compressed_bytes)

    # Buat record ConditionPhoto (image field menyimpan path relatif 'conditions/<filename>')
    photo = ConditionPhoto.objects.create(
        rental=rental,
        uploaded_by=user,
        phase=phase,
        image=f"conditions/{filename}",
        note=note.strip() if note else "",
    )
    logger.info(f"ConditionPhoto #{photo.id} ({phase}) saved privately for {rental.code} by {user.username}")
    return photo


def purge_handover_photos():
    """
    Menghapus foto serah terima (phase='serah_terima') yang sewanya telah berstatus 'selesai'
    lebih dari HANDOVER_PHOTO_RETENTION_DAYS (bawaan 30 hari).
    - Idempoten
    - TIDAK menghapus foto jika sewa memiliki sengketa (Dispute)
    - Mengembalikan jumlah foto yang dihapus
    """
    retention_days = int(getattr(settings, 'HANDOVER_PHOTO_RETENTION_DAYS', 30))
    cutoff = timezone.now() - timedelta(days=retention_days)

    # Cari sewa selesai yang melewati masa retensi dan TIDAK memiliki sengketa
    eligible_rentals = Rental.objects.filter(
        status=Rental.Status.SELESAI,
        status_changed_at__lte=cutoff,
    ).exclude(
        status=Rental.Status.SENGKETA
    ).exclude(
        dispute__isnull=False
    )

    photos_to_purge = ConditionPhoto.objects.filter(
        rental__in=eligible_rentals,
        phase=ConditionPhoto.Phase.SERAH_TERIMA
    )

    purged_count = 0
    for photo in photos_to_purge:
        try:
            photo.delete_file()
            photo.delete()
            purged_count += 1
        except Exception as e:
            logger.error(f"Gagal menghapus foto serah terima #{photo.id}: {e}")

    logger.info(f"Purge handover photos completed: {purged_count} foto dihapus.")
    return purged_count
