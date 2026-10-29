"""
seed_demo: Perintah manajemen pengembang untuk membuat data demo KampusRent.

HANYA dapat dijalankan jika:
1. DEBUG = True
2. Database berakhiran '_dev' (misal: 'db_dev.sqlite3' atau 'kampusrent_dev')

Aman dijalankan ulang (idempoten) — tidak membuat data ganda.
TIDAK menyentuh superuser yang sudah ada.
"""
import io
import os
import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import User, StudentProfile, Campus
from apps.catalog.models import Category, Item, ItemPhoto
from apps.rentals.models import Rental, Review
from apps.payments.models import Payment, DepositHold, Payout, LedgerEntry
from apps.trust.models import TrustScore
from apps.verification.models import KtmVerification


# ---------- Konstanta data demo (Netral & Token Baru AGENT.md) ----------

CATEGORIES = [
    {'name': 'Kamera & Lensa', 'slug': 'kamera', 'icon': 'camera', 'order': 1},
    {'name': 'Perlengkapan Wisuda', 'slug': 'wisuda', 'icon': 'graduation-cap', 'order': 2},
    {'name': 'Alat Praktikum', 'slug': 'praktikum', 'icon': 'flask-conical', 'order': 3},
    {'name': 'Camping & Outdoor', 'slug': 'camping', 'icon': 'tent', 'order': 4},
    {'name': 'Proyektor & Audio', 'slug': 'proyektor', 'icon': 'projector', 'order': 5},
    {'name': 'Kostum & Busana Acara', 'slug': 'kostum', 'icon': 'shirt', 'order': 6},
    {'name': 'Laptop & Aksesori', 'slug': 'laptop', 'icon': 'laptop', 'order': 7},
    {'name': 'Lain-lain', 'slug': 'lain-lain', 'icon': 'package', 'order': 8},
]

# Pemetaan latar datar ubin per kategori (AGENT.md 5A revisi - Warna Jenuh Datar)
CATEGORY_TILES = {
    'kamera': '#6C8EF5',     # tile-blue
    'wisuda': '#FFC83D',     # tile-saffron
    'praktikum': '#56C596',  # tile-mint
    'camping': '#FF8A6B',    # tile-coral
    'proyektor': '#6C8EF5',  # tile-blue
    'kostum': '#FFC83D',     # tile-saffron
    'laptop': '#56C596',     # tile-mint
    'lain-lain': '#FF8A6B',  # tile-coral
}

DEMO_USERS = [
    # (username, full_name, email, nim, campus, major, entry_year, verified, password)
    ('rina_pratiwi', 'Rina Pratiwi', 'rina@demo.id', '2021110001', 'Universitas KampusRent', 'Teknik Informatika', 2021, True, 'Demo1234!'),
    ('budi_santoso', 'Budi Santoso', 'budi@demo.id', '2020120002', 'Universitas KampusRent', 'Teknik Elektro', 2020, True, 'Demo1234!'),
    ('citra_dewi', 'Citra Dewi', 'citra@demo.id', '2022130003', 'Institut Teknologi Mahasiswa', 'Desain Komunikasi Visual', 2022, True, 'Demo1234!'),
    ('dani_kurniawan', 'Dani Kurniawan', 'dani@demo.id', '2021140004', 'Universitas KampusRent', 'Manajemen', 2021, True, 'Demo1234!'),
    ('eka_wijaya', 'Eka Wijaya', 'eka@demo.id', '2023150005', 'Politeknik Negeri Pelajar', 'Teknik Mesin', 2023, True, 'Demo1234!'),
    ('fitri_handayani', 'Fitri Handayani', 'fitri@demo.id', '2022160006', 'Institut Teknologi Mahasiswa', 'Ilmu Komunikasi', 2022, True, 'Demo1234!'),
    ('gilang_ramadhan', 'Gilang Ramadhan', 'gilang@demo.id', '2024170007', 'Universitas KampusRent', 'Sistem Informasi', 2024, False, 'Demo1234!'),
    ('hana_salsabila', 'Hana Salsabila', 'hana@demo.id', '2024180008', 'Politeknik Negeri Pelajar', 'Teknik Kimia', 2024, False, 'Demo1234!'),
]

DEMO_ADMIN = ('admin_demo', 'Admin Demo', 'admin_demo@demo.id', 'AdminDemo1234!')

ITEMS_DATA = [
    # (owner_idx, cat_slug, title, desc, condition, est_val, price/day, deposit, min, max, area, min_tier, require_ktm_held)
    (0, 'kamera', 'Canon EOS M50 Mark II', 'Kamera mirrorless Canon EOS M50 Mark II, cocok untuk foto dan video kampus. Termasuk lensa kit 15-45mm.', 'sangat_baik', 3000000, 75000, 450000, 1, 7, 'Gedung Sains & Seni', 'tepercaya', False),
    (0, 'kamera', 'Tripod Takara ECO-196A', 'Tripod ringan 1.5m, cocok untuk vlog dan foto studio mahasiswa.', 'baik', 250000, 15000, 40000, 1, 14, 'Gedung Sains & Seni', 'baru', False),
    (1, 'wisuda', 'Set Toga Wisuda S1 (Lengkap)', 'Toga wisuda lengkap (jubah, topi, selempang) ukuran M dan L tersedia. Bersih dan rapi.', 'sangat_baik', 500000, 50000, 100000, 1, 3, 'Area Asrama Barat', 'baru', False),
    (1, 'wisuda', 'Buket Bunga Wisuda Premium', 'Buket bunga artificial premium untuk foto wisuda. Tidak layu, bisa dipakai berulang.', 'sangat_baik', 150000, 35000, 0, 1, 2, 'Area Asrama Barat', 'baru', False), # Boleh tanpa deposit
    (2, 'praktikum', 'Multimeter Digital Sanwa CD800a', 'Multimeter digital untuk praktikum rangkaian listrik dan elektronika. Lengkap kabel probe.', 'baik', 600000, 25000, 100000, 1, 7, 'Gedung Laboratorium', 'baru', False),
    (2, 'praktikum', 'Solder Station Hakko FX-888D', 'Solder station profesional untuk praktikum elektronika dan robotika.', 'baik', 1500000, 40000, 200000, 1, 7, 'Gedung Laboratorium', 'tepercaya', False),
    (3, 'camping', 'Tenda Camping Eiger 4 Orang', 'Tenda dome kapasitas 4 orang, waterproof, cocok untuk camping dan pendakian.', 'baik', 1200000, 60000, 200000, 2, 5, 'Asrama Kampus', 'baru', False),
    (3, 'camping', 'Sleeping Bag Consina Sleep Warmer', 'Sleeping bag nyaman untuk suhu dingin. Compact dan mudah dibawa.', 'cukup', 400000, 20000, 60000, 1, 7, 'Asrama Kampus', 'baru', False),
    (4, 'proyektor', 'Proyektor Epson EB-X500', 'Proyektor 3600 lumens, cocok untuk presentasi kelas atau acara kampus. HDMI dan VGA.', 'sangat_baik', 2800000, 100000, 450000, 1, 3, 'Pusat Komputer', 'tepercaya', True), # Syarat KTM ditahan
    (4, 'proyektor', 'Speaker Portable JBL Flip 6', 'Speaker bluetooth portable, suara jernih dan bass kuat. Waterproof IPX7.', 'sangat_baik', 1500000, 35000, 200000, 1, 5, 'Pusat Komputer', 'tepercaya', False),
    (5, 'kostum', 'Jas Formal Pria (Hitam, L)', 'Jas formal hitam ukuran L untuk seminar, wisuda, atau presentasi. Termasuk dasi.', 'baik', 800000, 45000, 150000, 1, 3, 'Area Kampus Selatan', 'baru', False),
    (5, 'kostum', 'Kebaya Modern Wanita (Biru Navy)', 'Kebaya modern biru navy untuk wisuda atau acara formal kampus. Ukuran M.', 'sangat_baik', 600000, 40000, 100000, 1, 3, 'Area Kampus Selatan', 'baru', False),
    (0, 'laptop', 'Laptop Lenovo ThinkPad X1 Carbon', 'Laptop tipis dan ringan, i7, 16GB RAM, 512GB SSD. Dibatasi pada batas nilai platform.', 'baik', 3000000, 120000, 500000, 1, 7, 'Gedung Sains & Seni', 'sangat_tepercaya', True), # Laptop dibatasi 3jt & KTM ditahan
    (1, 'kamera', 'GoPro Hero 11 Black', 'Action camera waterproof untuk dokumentasi outdoor dan kegiatan kampus. 5.3K video.', 'sangat_baik', 2500000, 80000, 400000, 1, 5, 'Area Asrama Barat', 'tepercaya', True),
    (2, 'praktikum', 'Kit Arduino Uno R3 Lengkap', 'Starter kit Arduino Uno dengan breadboard, sensor, LED, dan kabel jumper. Cocok untuk IoT.', 'baik', 350000, 20000, 55000, 2, 14, 'Gedung Laboratorium', 'baru', False),
    (3, 'camping', 'Kompor Portable & Gas Kaleng (2 pcs)', 'Kompor camping portable plus 2 tabung gas kaleng. Aman dan mudah dipakai.', 'cukup', 150000, 15000, 0, 1, 5, 'Asrama Kampus', 'baru', False), # Boleh tanpa deposit
    (4, 'lain-lain', 'Papan Tulis Portable (Whiteboard 60x90)', 'Whiteboard portable dengan tripod, spidol, dan penghapus. Untuk diskusi kelompok.', 'baik', 300000, 20000, 50000, 1, 7, 'Pusat Komputer', 'baru', False),
    (5, 'kostum', 'Gaun Pesta Wanita (Merah Marun)', 'Gaun pesta elegan warna merah marun untuk acara formal. Ukuran S-M.', 'sangat_baik', 900000, 55000, 150000, 1, 2, 'Area Kampus Selatan', 'baru', False),
    (0, 'kamera', 'Lensa Fix 50mm f/1.8 Canon', 'Lensa fix Canon 50mm f/1.8 STM, bokeh indah untuk portrait wisuda dan acara.', 'sangat_baik', 1800000, 40000, 300000, 1, 7, 'Gedung Sains & Seni', 'tepercaya', False),
    (1, 'lain-lain', 'Ring Light 18" dengan Tripod', 'Ring light 18 inch dengan tripod 2m, 3 mode warna. Cocok untuk foto produk dan vlog.', 'baik', 450000, 25000, 75000, 1, 7, 'Area Asrama Barat', 'baru', True),
]


class Command(BaseCommand):
    help = 'Membuat data demo KampusRent (8 kategori, 9 pengguna, 20 barang, 10 sewa)'

    def handle(self, *args, **options):
        # Guardrail: Wajib DEBUG=True (menolak berjalan bila DEBUG=False)
        if not getattr(settings, 'DEBUG', False):
            raise CommandError("Perintah seed_demo DITOLAK: Hanya dapat dijalankan saat DEBUG=True.")

        self.stdout.write(self.style.NOTICE('[...] Memulai seed_demo di lingkungan pengembangan...'))

        cats = self._create_categories()
        users = self._create_users()
        items = self._create_items(users, cats)
        self._create_rentals(items, users)
        self._create_ktm_verifications(users)
        self._recompute_demo_trust_scores(users)
        self._create_notifications(users)

        self.stdout.write(self.style.SUCCESS('[OK] seed_demo selesai!'))

    def _create_categories(self):
        cats = {}
        for data in CATEGORIES:
            cat, created = Category.objects.get_or_create(
                slug=data['slug'],
                defaults={
                    'name': data['name'],
                    'icon': data['icon'],
                    'order': data['order'],
                }
            )
            # Selalu pastikan icon berisi key Lucide
            if cat.icon != data['icon']:
                cat.icon = data['icon']
                cat.save(update_fields=['icon'])
            cats[data['slug']] = cat
            if created:
                self.stdout.write(f"  + Kategori: {cat.name}")
        return cats

    def _create_users(self):
        users = []

        # Admin demo (tidak mengganggu superuser yang ada)
        admin_u, admin_c = User.objects.get_or_create(
            username=DEMO_ADMIN[0],
            defaults={
                'full_name': DEMO_ADMIN[1],
                'email': DEMO_ADMIN[2],
                'is_staff': True,
                'is_superuser': False,  # Bukan superuser, hanya staff
                'is_verified_student': True,
            }
        )
        if admin_c:
            admin_u.set_password(DEMO_ADMIN[3])
            admin_u.save()
            self.stdout.write(f"  + Admin demo: {admin_u.username}")

        # Berikan semua izin permission agar staf demo bisa mengakses model di Django admin
        from django.contrib.auth.models import Permission
        admin_u.user_permissions.set(Permission.objects.all())

        # Mahasiswa demo
        for udata in DEMO_USERS:
            username, full_name, email, nim, campus, major, entry_year, verified, password = udata
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'full_name': full_name,
                    'email': email,
                    'phone_whatsapp': f'0812{random.randint(10000000, 99999999)}',
                    'is_verified_student': verified,
                }
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(f"  + Pengguna: {user.username} ({'terverifikasi' if verified else 'belum'})")

            from apps.accounts.services import generate_campus_short_name
            # Dapatkan atau buat objek Campus
            campus_obj, _ = Campus.objects.get_or_create(
                name=campus,
                defaults={
                    'short_name': generate_campus_short_name(campus),
                    'city': 'Bandung',
                    'ktm_keywords': [campus.lower()],
                    'is_active': True,
                }
            )

            # Buat atau perbarui StudentProfile
            profile, _ = StudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    'nim': nim,
                    'campus': campus_obj,
                    'major': major,
                    'entry_year': entry_year,
                    'student_status': 'aktif',
                }
            )
            if profile.campus != campus_obj:
                profile.campus = campus_obj
                profile.save(update_fields=['campus'])

            # Buat TrustScore
            if verified:
                score_val = random.choice([62, 68, 72, 78, 85, 90])
                TrustScore.objects.get_or_create(
                    user=user,
                    defaults={
                        'score': score_val,
                        'risk_probability': round(1 - score_val / 100, 2),
                        'is_new_user': random.choice([True, False]),
                        'model_version': 'v0-demo',
                        'computed_at': timezone.now(),
                    }
                )

            users.append(user)

        return users

    def _create_items(self, users, cats):
        items = []
        demo_photos_dir = Path(settings.BASE_DIR) / 'docs' / 'local' / 'demo_photos'

        for idx, idata in enumerate(ITEMS_DATA):
            owner_idx, cat_slug, title, desc, cond, est_val, ppd, deposit, min_d, max_d, area, min_tier, req_ktm = idata
            owner = users[owner_idx]
            cat = cats[cat_slug]

            from django.utils.text import slugify
            base_slug = slugify(title)

            item, created = Item.objects.get_or_create(
                slug=base_slug,
                defaults={
                    'owner': owner,
                    'category': cat,
                    'title': title,
                    'description': desc,
                    'condition': cond,
                    'estimated_value': est_val,
                    'price_per_day': ppd,
                    'deposit_amount': deposit,
                    'min_days': min_d,
                    'max_days': max_d,
                    'pickup_area': area,
                    'min_renter_tier': min_tier,
                    'require_ktm_held': req_ktm,
                    'is_active': True,
                }
            )

            # Perbarui data jika sudah ada sebelumnya
            if not created:
                item.pickup_area = area
                item.category = cat
                item.estimated_value = est_val
                item.price_per_day = ppd
                item.deposit_amount = deposit
                item.min_renter_tier = min_tier
                item.require_ktm_held = req_ktm
                item.save(update_fields=['pickup_area', 'category', 'estimated_value', 'price_per_day', 'deposit_amount', 'min_renter_tier', 'require_ktm_held'])

            # Cek foto lokal di docs/local/demo_photos/ (nama berkas = slug barang)
            local_photo_found = False
            if demo_photos_dir.exists():
                for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    photo_path = demo_photos_dir / f"{base_slug}{ext}"
                    if photo_path.exists():
                        if created or item.photos.count() == 0:
                            with open(photo_path, 'rb') as f:
                                photo = ItemPhoto(item=item, order=0)
                                photo.image.save(f"{base_slug}{ext}", ContentFile(f.read()), save=True)
                            self.stdout.write(f"  + Foto lokal: {item.title} ({photo_path.name})")
                        local_photo_found = True
                        break

            # Bila tidak ada foto di docs/local/demo_photos/, biarkan barang tanpa foto (memakai cadangan template)
            items.append(item)
        return items

    def _create_rentals(self, items, users):
        """Buat sewa dengan status beragam."""
        today = date.today()
        verified_users = [u for u in users if u.is_verified_student]
        if len(verified_users) < 2:
            self.stdout.write(self.style.WARNING('  [!] Tidak cukup pengguna terverifikasi untuk sewa demo.'))
            return

        rental_configs = [
            # (item_idx, renter_idx, status, days_offset_start, days_count, protection)
            (0, 1, Rental.Status.SELESAI, -30, 3, True),
            (0, 2, Rental.Status.DIBAYAR, 2, 4, True),  # Sewa aktif bertabrakan untuk demo filter tanggal
            (2, 0, Rental.Status.SELESAI, -25, 2, False),
            (4, 3, Rental.Status.SELESAI, -20, 3, True),
            (6, 1, Rental.Status.SEDANG_DISEWA, -2, 4, True),
            (9, 2, Rental.Status.DIBAYAR, 1, 2, False),
            (3, 4, Rental.Status.MENUNGGU_PEMBAYARAN, 3, 1, False),
            (7, 0, Rental.Status.MENUNGGU_PERSETUJUAN, 5, 3, True),
            (10, 3, Rental.Status.DITOLAK, -15, 2, False),
            (1, 5, Rental.Status.DIBATALKAN, -10, 1, False),
            (8, 1, Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN, -5, 3, True),
            (14, 0, Rental.Status.SELESAI, -45, 2, False),
            (11, 1, Rental.Status.SELESAI, -40, 2, True),
        ]

        for i, (item_idx, renter_idx, status, start_offset, days_count, use_prot) in enumerate(rental_configs):
            item = items[item_idx]
            renter = verified_users[renter_idx % len(verified_users)]

            # Pastikan penyewa bukan pemilik
            if renter == item.owner:
                renter = verified_users[(renter_idx + 1) % len(verified_users)]
            if renter == item.owner:
                continue

            start = today + timedelta(days=start_offset)
            end = start + timedelta(days=days_count - 1)
            code = f'KR-DEMO{i+1:02d}'
            if Rental.objects.filter(code=code).exists():
                continue

            prot_fee = settings.PROTECTION_FEE if use_prot else 0
            rent_total = item.price_per_day * days_count
            grand = rent_total + item.deposit_amount + prot_fee

            rental = Rental.objects.create(
                code=code,
                item=item,
                renter=renter,
                owner=item.owner,
                start_date=start,
                end_date=end,
                days=days_count,
                price_per_day_snapshot=item.price_per_day,
                rent_total=rent_total,
                deposit_total=item.deposit_amount,
                protection_fee=prot_fee,
                grand_total=grand,
                use_protection=use_prot,
                status=status,
            )
            self.stdout.write(f"  + Sewa: {code} ({rental.get_status_display()})")

            # Buat data pendukung sesuai status
            if status in [Rental.Status.DIBAYAR, Rental.Status.SEDANG_DISEWA,
                          Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN, Rental.Status.SELESAI]:
                # Payment
                Payment.objects.create(
                    rental=rental,
                    order_id=f'KR-{code}-001',
                    gross_amount=grand,
                    status='settlement',
                    payment_type='bank_transfer',
                    paid_at=timezone.now() - timedelta(days=abs(start_offset)),
                )
                # DepositHold
                dep_status = 'dirilis' if status == Rental.Status.SELESAI else 'ditahan'
                DepositHold.objects.create(
                    rental=rental,
                    amount=item.deposit_amount,
                    status=dep_status,
                    released_amount=item.deposit_amount if dep_status == 'dirilis' else 0,
                    released_at=timezone.now() if dep_status == 'dirilis' else None,
                )
                # LedgerEntry masuk
                LedgerEntry.objects.create(rental=rental, kind='masuk_sewa', amount=rent_total)
                LedgerEntry.objects.create(rental=rental, kind='masuk_deposit', amount=item.deposit_amount)
                if use_prot:
                    LedgerEntry.objects.create(rental=rental, kind='masuk_proteksi', amount=prot_fee)

            if status == Rental.Status.SELESAI:
                # Payout & ledger keluar
                commission = round(rent_total * settings.PLATFORM_COMMISSION_PERCENT / 100)
                owner_net = rent_total - commission
                Payout.objects.create(
                    rental=rental,
                    owner=item.owner,
                    gross_rent=rent_total,
                    commission=commission,
                    net_amount=owner_net,
                    status='dicairkan_simulasi',
                    paid_at=timezone.now(),
                )
                LedgerEntry.objects.create(rental=rental, kind='keluar_komisi_platform', amount=commission)
                LedgerEntry.objects.create(rental=rental, kind='keluar_payout_pemilik', amount=owner_net)
                LedgerEntry.objects.create(rental=rental, kind='keluar_deposit_dikembalikan', amount=item.deposit_amount)
                if use_prot:
                    LedgerEntry.objects.create(rental=rental, kind='keluar_proteksi_platform', amount=prot_fee)

                # Review
                Review.objects.create(
                    rental=rental, reviewer=renter, reviewee=item.owner,
                    as_role='penyewa', rating=random.choice([4, 5]),
                    comment=random.choice([
                        'Barang sesuai deskripsi, pemilik ramah!',
                        'Sangat puas, kondisi barang bagus.',
                        'Pengambilan mudah, terima kasih!',
                    ])
                )
                Review.objects.create(
                    rental=rental, reviewer=item.owner, reviewee=renter,
                    as_role='pemilik', rating=random.choice([4, 5]),
                    comment=random.choice([
                        'Penyewa bertanggung jawab, tepat waktu.',
                        'Barang dikembalikan dalam kondisi baik.',
                        'Komunikasi baik, recommended!',
                    ])
                )

    def _create_ktm_verifications(self, users):
        """Buat satu contoh KtmVerification demo berstatus menunggu (Fase 2)."""
        gilang = User.objects.filter(username='gilang_ramadhan').first()
        if not gilang:
            return

        ktm_dir = settings.PRIVATE_MEDIA_ROOT / 'ktm'
        ktm_dir.mkdir(parents=True, exist_ok=True)
        img_name = 'demo_ktm_gilang.jpg'
        img_path = ktm_dir / img_name

        if not img_path.exists():
            # Buat citra kartu KTM demo 800x500 (rasio 1.6 ID card standar)
            w, h = 800, 500
            img = Image.new('RGB', (w, h), (230, 236, 251))  # brand-tint #E6ECFB
            draw = ImageDraw.Draw(img)
            ink = (20, 27, 52)      # #141B34
            brand = (31, 69, 196)   # #1F45C4
            paper = (240, 235, 221) # #F0EBDD

            # Garis tepi kartu
            draw.rounded_rectangle([15, 15, w - 15, h - 15], radius=16, outline=brand, width=3)
            # Bilah atas kartu
            draw.rectangle([18, 18, w - 18, 90], fill=brand)
            # Area foto di kiri
            draw.rounded_rectangle([45, 130, 220, 360], radius=12, fill=paper, outline=ink, width=2)
            # Garis-garis data KTM
            draw.rectangle([260, 140, 680, 165], fill=ink)
            draw.rectangle([260, 190, 580, 210], fill=ink)
            draw.rectangle([260, 235, 520, 255], fill=ink)
            draw.rectangle([260, 280, 480, 300], fill=ink)
            draw.rectangle([260, 325, 420, 345], fill=ink)
            img.save(img_path, 'JPEG', quality=90)

        # Buat entri verifikasi jika belum ada
        ktm_verif, created = KtmVerification.objects.get_or_create(
            user=gilang,
            defaults={
                'ktm_image': f'ktm/{img_name}',
                'ocr_text': "KARTU TANDA MAHASISWA\nUNIVERSITAS KAMPUSRENT\nNIM: 2024170007\nNAMA: Gilang Ramadhan\nSISTEM INFORMASI",
                'ocr_nim': '2024170007',
                'ocr_name': 'Gilang Ramadhan',
                'ocr_campus': 'Universitas KampusRent',
                'nim_match': True,
                'name_similarity': 100,
                'campus_match': True,
                'quality_score': 85,
                'match_score': 98,
                'recommendation': KtmVerification.Recommendation.SETUJU,
                'status': KtmVerification.Status.MENUNGGU,
                'admin_note': 'Unggahan contoh demo. Menunggu peninjauan manual oleh admin.',
            }
        )
        if created:
            self.stdout.write(f"  + KtmVerification demo berstatus menunggu: {gilang.username}")

    def _recompute_demo_trust_scores(self, users):
        """Menghitung skor kepercayaan seluruh pengguna demo dari riwayat sewa secara objektif menggunakan model ML."""
        from apps.trust.services import recompute_trust_score
        self.stdout.write(self.style.NOTICE('  [...] Menghitung skor kepercayaan pengguna demo...'))
        for u in users:
            ts = recompute_trust_score(u)
            if ts:
                self.stdout.write(f"  + Skor Kepercayaan {u.username}: {ts.score} ({ts.get_label()}) - model: {ts.model_version}")

    def _create_notifications(self, users):
        """Membangkitkan contoh notifikasi untuk akun demo."""
        from apps.core.models import Notification
        self.stdout.write(self.style.NOTICE('  [...] Memeriksa dan membuat notifikasi demo...'))
        users_dict = {u.username: u for u in users}
        rina = users_dict.get('rina_pratiwi')
        budi = users_dict.get('budi_santoso')
        dina = users_dict.get('dina_lestari')

        if rina and not Notification.objects.filter(user=rina).exists():
            Notification.notify(
                user=rina,
                title='Pengajuan Sewa Masuk',
                message='Budi Santoso mengajukan sewa untuk Sony Alpha a6400.',
                url='/sewa/'
            )
            Notification.notify(
                user=rina,
                title='Dana Sewa Diteruskan',
                message='Sewa Sony Alpha a6400 selesai. Saldo Rp276.000 telah masuk ke saldo Anda.',
                url='/dashboard/'
            )
            self.stdout.write("  + Notifikasi contoh dibuat untuk rina_pratiwi")

        if budi and not Notification.objects.filter(user=budi).exists():
            Notification.notify(
                user=budi,
                title='Pengajuan Sewa Disetujui',
                message='Rina Pratiwi telah menyetujui pengajuan sewa Anda. Silakan lanjutkan ke pembayaran.',
                url='/sewa/'
            )
            Notification.notify(
                user=budi,
                title='Pengingat Serah Terima',
                message='Jadwal serah terima barang di Gedung Kuliah Bersama besok pukul 10:00 WIB.',
                url='/sewa/'
            )
            self.stdout.write("  + Notifikasi contoh dibuat untuk budi_santoso")

        if dina and not Notification.objects.filter(user=dina).exists():
            Notification.notify(
                user=dina,
                title='Selamat Datang di KampusRent',
                message='Unggah foto Kartu Tanda Mahasiswa (KTM) Anda untuk mulai menyewa barang bernilai lebih tinggi.',
                url='/verifikasi-ktm/'
            )
            self.stdout.write("  + Notifikasi contoh dibuat untuk dina_lestari")
