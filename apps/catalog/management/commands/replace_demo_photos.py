import os
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
from PIL import Image, ImageDraw

from apps.catalog.models import Item, ItemPhoto

DEMO_USERNAMES = {
    'rina_pratiwi',
    'budi_santoso',
    'citra_dewi',
    'dani_kurniawan',
    'eka_wijaya',
    'fitri_handayani',
    'gilang_ramadhan',
    'hana_salsabila',
    'admin_demo',
}

INK = '#141B34'
WHITE = '#FFFFFF'
STROKE_WIDTH = 2
WIDTH = 400
HEIGHT = 300


class OffsetDraw:
    """Helper untuk mentranslasi koordinat ikon ke kanvas rasio 4:3 (400x300, offset Y -50)."""
    def __init__(self, draw, dx=0, dy=0):
        self._draw = draw
        self._dx = dx
        self._dy = dy

    def _pt(self, pt):
        return (pt[0] + self._dx, pt[1] + self._dy)

    def _box(self, box):
        if isinstance(box, (list, tuple)) and len(box) == 2 and isinstance(box[0], (list, tuple)):
            return [self._pt(box[0]), self._pt(box[1])]
        elif isinstance(box, (list, tuple)) and len(box) == 4:
            return [box[0] + self._dx, box[1] + self._dy, box[2] + self._dx, box[3] + self._dy]
        return box

    def _pts(self, coords):
        if not coords:
            return coords
        if isinstance(coords[0], (list, tuple)):
            return [self._pt(p) for p in coords]
        return [self._pt(coords[0]), self._pt(coords[1])]

    def polygon(self, xy, **kwargs):
        return self._draw.polygon(self._pts(xy), **kwargs)

    def rectangle(self, xy, **kwargs):
        return self._draw.rectangle(self._box(xy), **kwargs)

    def rounded_rectangle(self, xy, **kwargs):
        return self._draw.rounded_rectangle(self._box(xy), **kwargs)

    def ellipse(self, xy, **kwargs):
        return self._draw.ellipse(self._box(xy), **kwargs)

    def line(self, xy, **kwargs):
        return self._draw.line(self._pts(xy), **kwargs)

    def arc(self, xy, start, end, **kwargs):
        return self._draw.arc(self._box(xy), start, end, **kwargs)

    def __getattr__(self, name):
        return getattr(self._draw, name)


def get_category_tile_color(category_slug="", category_name=""):
    """
    Menentukan warna latar ubin sesuai ketetapan AGENT.md Fase 7F (nada lembut):
    - Kamera dan Laptop: biru #8EA8F7
    - Praktikum dan Proyektor: mint #7ACFAC
    - Camping dan Lainnya: koral #FFA68C
    - Wisuda dan Kostum: kunyit #FFD66B
    """
    s = (category_slug or "").lower()
    n = (category_name or "").lower()
    combined = f"{s} {n}"

    if any(k in combined for k in ['kamera', 'camera', 'laptop']):
        return '#8EA8F7'
    if any(k in combined for k in ['praktikum', 'proyektor', 'projector', 'audio']):
        return '#7ACFAC'
    if any(k in combined for k in ['camping', 'outdoor', 'lain']):
        return '#FFA68C'
    if any(k in combined for k in ['wisuda', 'kostum']):
        return '#FFD66B'
    return '#8EA8F7'


def determine_icon_type(title, category_name="", category_slug=""):
    """
    Menentukan jenis ikon datar geometris berdasarkan kata kunci judul barang.
    Mendukung ikon spesifik: gaun, jas, tas_tidur, speaker, kamera, tripod,
    laptop, proyektor, api, tenda, topi_toga, bunga, alat_ukur, papan_sirkuit, kotak.
    """
    t_title = (title or "").lower()
    t_cat = f"{category_name} {category_slug}".lower()

    # 1. Cek kata kunci pada judul barang
    if any(k in t_title for k in ['tripod', 'ring light', 'ringlight']):
        return 'tripod'
    if any(k in t_title for k in ['kamera', 'camera', 'lensa', 'gopro', 'canon', 'eos', 'nikon', 'sony']):
        return 'kamera'
    if any(k in t_title for k in ['laptop', 'notebook', 'thinkpad']):
        return 'laptop'
    if any(k in t_title for k in ['proyektor', 'projector']):
        return 'proyektor'
    if any(k in t_title for k in ['speaker', 'audio', 'sound']):
        return 'speaker'
    if any(k in t_title for k in ['kompor', 'gas kaleng', 'stove']):
        return 'api'
    if any(k in t_title for k in ['sleeping bag', 'sleepingbag', 'tas tidur']):
        return 'tas_tidur'
    if any(k in t_title for k in ['tenda', 'tent']):
        return 'tenda'
    if 'toga' in t_title:
        return 'topi_toga'
    if 'jas' in t_title:
        return 'jas'
    if any(k in t_title for k in ['kebaya', 'gaun']):
        return 'gaun'
    if any(k in t_title for k in ['buket', 'bunga']):
        return 'bunga'
    if any(k in t_title for k in ['multimeter', 'solder', 'avometer', 'sanwa', 'hakko']):
        return 'alat_ukur'
    if any(k in t_title for k in ['arduino', 'raspberry', 'sirkuit']):
        return 'papan_sirkuit'

    # 2. Cadangan dari kategori bila pada judul belum terdeteksi
    if 'kamera' in t_cat:
        return 'kamera'
    if 'laptop' in t_cat:
        return 'laptop'
    if 'proyektor' in t_cat:
        return 'proyektor'
    if 'wisuda' in t_cat:
        return 'topi_toga'
    if 'camping' in t_cat:
        return 'tenda'
    if 'kostum' in t_cat:
        return 'gaun'
    if 'praktikum' in t_cat:
        return 'alat_ukur'

    return 'kotak'


def draw_flat_icon(draw, icon_type):
    """
    Menggambar ikon datar bergaris tinta 3px dengan isi putih.
    Ukuran ikon sekitar 60% lebar ubin (sekitar 240 px di dalam ubin 400x400),
    tanpa teks, tanpa label, tanpa bingkai dalam semu.
    """
    ink = INK
    white = WHITE
    w = STROKE_WIDTH

    if icon_type == 'kamera':
        # Lebar ~230 px (85-315)
        draw.polygon([(155, 140), (175, 110), (225, 110), (245, 140)], fill=white, outline=ink, width=w)
        draw.rectangle([(100, 120), (130, 140)], fill=white, outline=ink, width=w)
        draw.rounded_rectangle([(85, 140), (315, 285)], radius=12, fill=white, outline=ink, width=w)
        draw.ellipse([(150, 155), (250, 255)], fill=white, outline=ink, width=w)
        draw.ellipse([(175, 180), (225, 230)], fill=white, outline=ink, width=w)

    elif icon_type == 'tripod':
        # Lebar ~210 px (95-305)
        draw.ellipse([(155, 80), (245, 170)], fill=white, outline=ink, width=w)
        draw.ellipse([(175, 100), (225, 150)], fill=white, outline=ink, width=w)
        draw.rectangle([(196, 170), (204, 225)], fill=white, outline=ink, width=w)
        draw.ellipse([(192, 220), (208, 236)], fill=white, outline=ink, width=w)
        draw.line([(195, 232), (95, 320)], fill=ink, width=w+1)
        draw.line([(200, 232), (200, 325)], fill=ink, width=w+1)
        draw.line([(205, 232), (305, 320)], fill=ink, width=w+1)

    elif icon_type == 'laptop':
        # Lebar ~240 px (80-320)
        draw.rounded_rectangle([(95, 100), (305, 235)], radius=8, fill=white, outline=ink, width=w)
        draw.rectangle([(115, 118), (285, 218)], fill=white, outline=ink, width=w)
        draw.polygon([(80, 240), (320, 240), (330, 275), (70, 275)], fill=white, outline=ink, width=w)
        draw.rectangle([(175, 250), (225, 268)], fill=white, outline=ink, width=w)

    elif icon_type == 'proyektor':
        # Lebar ~240 px (80-320)
        draw.rounded_rectangle([(80, 145), (320, 245)], radius=12, fill=white, outline=ink, width=w)
        draw.ellipse([(235, 160), (295, 220)], fill=white, outline=ink, width=w)
        draw.ellipse([(250, 175), (280, 205)], fill=white, outline=ink, width=w)
        for y in [172, 186, 200, 214]:
            draw.line([(105, y), (175, y)], fill=ink, width=w)
        draw.rectangle([(105, 245), (130, 260)], fill=white, outline=ink, width=w)
        draw.rectangle([(270, 245), (295, 260)], fill=white, outline=ink, width=w)

    elif icon_type == 'speaker':
        # Bodi kabinet speaker dengan tweeter dan woofer (lebar ~160 px, 120-280)
        draw.rounded_rectangle([(120, 85), (280, 315)], radius=14, fill=white, outline=ink, width=w)
        draw.ellipse([(170, 110), (230, 170)], fill=white, outline=ink, width=w)
        draw.ellipse([(188, 128), (212, 152)], fill=white, outline=ink, width=w)
        draw.ellipse([(150, 195), (250, 295)], fill=white, outline=ink, width=w)
        draw.ellipse([(180, 225), (220, 265)], fill=white, outline=ink, width=w)

    elif icon_type == 'api':
        # Kompor dan lidah api (lebar ~170 px)
        draw.rectangle([(120, 265), (280, 295)], fill=white, outline=ink, width=w)
        draw.line([(100, 295), (135, 295)], fill=ink, width=w+1)
        draw.line([(265, 295), (300, 295)], fill=ink, width=w+1)
        draw.polygon([(200, 85), (245, 145), (225, 180), (255, 215), (200, 260), (145, 215), (175, 180), (155, 145)], fill=white, outline=ink, width=w)
        draw.polygon([(200, 140), (225, 180), (210, 210), (200, 250), (190, 210), (175, 180)], fill=white, outline=ink, width=w)

    elif icon_type == 'tenda':
        # Tenda camping segitiga (lebar ~240 px, 80-320)
        draw.polygon([(200, 95), (320, 295), (80, 295)], fill=white, outline=ink, width=w)
        draw.polygon([(200, 155), (245, 295), (155, 295)], fill=white, outline=ink, width=w)
        draw.line([(200, 95), (200, 295)], fill=ink, width=w)
        draw.line([(200, 95), (60, 305)], fill=ink, width=w)
        draw.line([(200, 95), (340, 305)], fill=ink, width=w)

    elif icon_type == 'tas_tidur':
        # Gulungan tidur / sleeping bag silinder dengan 2 sabuk pengikat (lebar ~230 px)
        draw.rounded_rectangle([(120, 135), (315, 265)], radius=20, fill=white, outline=ink, width=w)
        draw.ellipse([(85, 135), (145, 265)], fill=white, outline=ink, width=w)
        draw.arc([(100, 155), (130, 245)], start=30, end=330, fill=ink, width=w)
        # 2 sabuk penahan dengan gesper
        draw.rectangle([(180, 133), (196, 267)], fill=white, outline=ink, width=w)
        draw.rectangle([(176, 188), (200, 212)], fill=white, outline=ink, width=w)
        draw.rectangle([(245, 133), (261, 267)], fill=white, outline=ink, width=w)
        draw.rectangle([(241, 188), (265, 212)], fill=white, outline=ink, width=w)
        # Pegangan jinjing atas
        draw.arc([(185, 105), (255, 145)], start=180, end=360, fill=ink, width=w+1)

    elif icon_type == 'topi_toga':
        # Topi toga wisuda (lebar ~240 px, 80-320)
        draw.polygon([(150, 180), (250, 180), (235, 250), (165, 250)], fill=white, outline=ink, width=w)
        draw.polygon([(200, 90), (320, 150), (200, 210), (80, 150)], fill=white, outline=ink, width=w)
        draw.ellipse([(193, 143), (207, 157)], fill=white, outline=ink, width=w)
        draw.line([(200, 150), (280, 195)], fill=ink, width=w)
        draw.polygon([(275, 195), (290, 195), (295, 245), (270, 245)], fill=white, outline=ink, width=w)

    elif icon_type == 'gaun':
        # Gaun / kebaya wanita dengan siluet rok mekar (lebar ~210 px, 95-305)
        draw.polygon([
            (160, 95), (135, 125), (160, 135), (165, 185),
            (95, 305), (305, 305),
            (235, 185), (240, 135), (265, 125), (240, 95)
        ], fill=white, outline=ink, width=w)
        # Garis leher V-neck
        draw.polygon([(160, 95), (240, 95), (200, 135)], fill=white, outline=ink, width=w)
        # Sabuk pinggang
        draw.line([(165, 185), (235, 185)], fill=ink, width=w)

    elif icon_type == 'jas':
        # Jas pria berdasi formal (lebar ~250 px, 75-325)
        draw.polygon([
            (145, 115), (75, 145), (105, 175), (120, 160),
            (120, 310), (280, 310),
            (280, 160), (295, 175), (325, 145), (255, 115)
        ], fill=white, outline=ink, width=w)
        # Kerah kemeja putih di dalam jas
        draw.polygon([(165, 115), (235, 115), (200, 240)], fill=white, outline=ink, width=w)
        # Dasi tinta di tengah
        draw.polygon([(193, 125), (207, 125), (204, 140), (196, 140)], fill=ink)
        draw.polygon([(195, 140), (205, 140), (210, 215), (200, 235), (190, 215)], fill=ink)
        # Kancing jas
        draw.ellipse([(196, 255), (204, 263)], fill=ink)
        draw.ellipse([(196, 278), (204, 286)], fill=ink)

    elif icon_type == 'bunga':
        # Buket bunga wisuda (lebar ~140 px)
        draw.polygon([(160, 205), (240, 205), (215, 315), (185, 315)], fill=white, outline=ink, width=w)
        draw.polygon([(175, 230), (225, 230), (210, 255), (190, 255)], fill=white, outline=ink, width=w)
        petals = [
            (200, 120, 28),
            (160, 155, 25),
            (240, 155, 25),
            (175, 190, 24),
            (225, 190, 24),
        ]
        for cx, cy, r in petals:
            draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=white, outline=ink, width=w)

    elif icon_type == 'alat_ukur':
        # Multimeter alat praktikum (lebar ~180 px, 110-290)
        draw.rounded_rectangle([(110, 85), (290, 315)], radius=14, fill=white, outline=ink, width=w)
        draw.rectangle([(135, 110), (265, 165)], fill=white, outline=ink, width=w)
        draw.ellipse([(160, 185), (240, 265)], fill=white, outline=ink, width=w)
        draw.line([(200, 225), (200, 195)], fill=ink, width=w+1)
        draw.ellipse([(135, 280), (155, 300)], fill=white, outline=ink, width=w)
        draw.ellipse([(190, 280), (210, 300)], fill=white, outline=ink, width=w)
        draw.ellipse([(245, 280), (265, 300)], fill=white, outline=ink, width=w)

    elif icon_type == 'papan_sirkuit':
        # Modul mikrokontroler / Arduino (lebar ~230 px, 85-315)
        draw.rounded_rectangle([(85, 105), (315, 295)], radius=8, fill=white, outline=ink, width=w)
        draw.rectangle([(160, 165), (240, 245)], fill=white, outline=ink, width=w)
        draw.rectangle([(75, 125), (100, 165)], fill=white, outline=ink, width=w)
        draw.rectangle([(75, 225), (100, 265)], fill=white, outline=ink, width=w)
        for x in range(125, 285, 20):
            draw.rectangle([(x, 115), (x+10, 128)], fill=white, outline=ink, width=w-1)
            draw.rectangle([(x, 272), (x+10, 285)], fill=white, outline=ink, width=w-1)

    else:  # 'kotak'
        # Kotak paket 3D isometrik (lebar ~220 px, 90-310)
        draw.polygon([(200, 95), (310, 150), (200, 205), (90, 150)], fill=white, outline=ink, width=w)
        draw.polygon([(90, 150), (200, 205), (200, 305), (90, 250)], fill=white, outline=ink, width=w)
        draw.polygon([(200, 205), (310, 150), (310, 250), (200, 305)], fill=white, outline=ink, width=w)


class Command(BaseCommand):
    help = (
        "Mengganti foto demo bertulisan dengan ilustrasi datar ubin warna tetap per kategori: "
        "Kamera dan Laptop (#6C8EF5), Praktikum dan Proyektor (#56C596), "
        "Camping dan Lainnya (#FF8A6B), Wisuda dan Kostum (#FFC83D). "
        "Ikon sekitar 60% lebar ubin tanpa teks/label. "
        "Mendukung docs/local/demo_photos/<slug>.jpg sebagai sumber foto asli bila ada. "
        "Gunakan --apply untuk mengeksekusi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help="Eksekusi penggantian ItemPhoto hasil seed_demo setelah pg_dump. Hanya jika disetujui pengguna."
        )

    def handle(self, *args, **options):
        apply_mode = options.get('apply', False)

        # Identifikasi Item milik akun seed_demo (jangan ubah foto non-seed seperti laptop Acer milik Arfi)
        demo_items = Item.objects.filter(
            owner__username__in=DEMO_USERNAMES
        ).select_related('owner', 'category').order_by('id')

        count = demo_items.count()

        if not apply_mode:
            self.stdout.write(self.style.NOTICE(f"=== DRY-RUN: Rencana Penggantian Foto Demo ({count} barang ditemukan) ==="))
            if count == 0:
                self.stdout.write("Tidak ada barang demo yang ditemukan.")
                return

            self.stdout.write(f"{'ID':<6} | {'Kategori':<20} | {'Judul Barang':<32} | {'Warna':<8} | {'Ikon'}")
            self.stdout.write("-" * 85)
            for item in demo_items:
                cat_slug = item.category.slug if item.category else ""
                cat_name = item.category.name if item.category else ""
                color = get_category_tile_color(cat_slug, cat_name)
                icon = determine_icon_type(item.title, cat_name, cat_slug)
                self.stdout.write(
                    f"{item.id:<6} | {cat_name[:18]:<20} | {item.title[:30]:<32} | {color:<8} | {icon}"
                )

            self.stdout.write("-" * 85)
            self.stdout.write(self.style.WARNING(
                f"[DRY-RUN] Ditemukan {count} barang demo.\n"
                "PERINGATAN: Tidak ada berkas yang diubah dalam mode bawaan DRY-RUN.\n"
                "Gunakan --apply untuk mengeksekusi penggantian setelah cadangan dibuat."
            ))
            return

        # MODE --APPLY
        self.stdout.write(self.style.WARNING("=== MENJALANKAN MODE --APPLY ==="))
        # 1. Jalankan backup_data (pg_dump)
        self.stdout.write("[1/3] Menjalankan cadangan database (pg_dump)...")
        call_command('backup_data', skip_media=True)

        # 2. Generator foto datar baru
        self.stdout.write(f"[2/3] Menghasilkan ilustrasi datar baru untuk {count} barang demo...")
        media_items_dir = Path(settings.MEDIA_ROOT) / 'items'
        media_items_dir.mkdir(parents=True, exist_ok=True)
        local_photos_dir = Path(settings.BASE_DIR) / 'docs' / 'local' / 'demo_photos'

        updated_count = 0
        for item in demo_items:
            cat_slug = item.category.slug if item.category else ""
            cat_name = item.category.name if item.category else ""
            color = get_category_tile_color(cat_slug, cat_name)
            icon = determine_icon_type(item.title, cat_name, cat_slug)
            target_filename = f"flat_{item.slug}.jpg"
            target_path = media_items_dir / target_filename
            relative_name = f"items/{target_filename}"

            local_candidate = local_photos_dir / f"{item.slug}.jpg"
            if local_candidate.exists():
                shutil.copyfile(local_candidate, target_path)
                self.stdout.write(f"  [Item {item.id}] Menggunakan berkas foto lokal: {local_candidate.name}")
            else:
                img = Image.new('RGB', (WIDTH, HEIGHT), color)
                draw = ImageDraw.Draw(img)
                draw_flat_icon(OffsetDraw(draw, dx=0, dy=-50), icon)
                img.save(target_path, format='JPEG', quality=95)
                self.stdout.write(f"  [Item {item.id}] Dihasilkan ilustrasi 4:3 60%: {icon} ({color}) -> {target_filename}")

            # Perbarui atau buat ItemPhoto untuk barang ini
            existing_photos = list(item.photos.all())
            if existing_photos:
                primary = existing_photos[0]
                if primary.image.name != relative_name:
                    try:
                        if primary.image.storage.exists(primary.image.name):
                            primary.image.storage.delete(primary.image.name)
                    except Exception as e:
                        self.stderr.write(f"    Gagal hapus berkas lama {primary.image.name}: {e}")
                primary.image.name = relative_name
                primary.is_primary = True
                primary.save()

                # Hapus foto ekstra demo jika ada
                for extra in existing_photos[1:]:
                    try:
                        if extra.image.storage.exists(extra.image.name):
                            extra.image.storage.delete(extra.image.name)
                    except Exception:
                        pass
                    extra.delete()
            else:
                ItemPhoto.objects.create(
                    item=item,
                    image=relative_name,
                    is_primary=True
                )

            updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"[3/3] Selesai! Berhasil memperbarui {updated_count} ItemPhoto demo dengan ilustrasi datar 60% per kategori tanpa teks. "
            "Barang tetap ada dan foto pengguna non-demo (mis. Acer laptop) tidak diubah."
        ))
