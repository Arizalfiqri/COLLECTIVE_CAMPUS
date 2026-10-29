"""
init_platform: Perintah manajemen untuk inisialisasi awal platform KampusRent.

Idempoten dan aman dijalankan berulang kali.
Mengisi:
- 8 Kategori standar barang kampus

TIDAK membuat pengguna fiktif, profil fiktif, barang fiktif, atau transaksi fiktif.
"""
from django.core.management.base import BaseCommand
from apps.catalog.models import Category



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


class Command(BaseCommand):
    help = "Inisialisasi data dasar platform KampusRent (kategori, kampus awal, titik temu) tanpa data fiktif."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Inisialisasi Platform KampusRent ==="))

        # 1. Inisialisasi Kategori
        cat_created_count = 0
        for cat in CATEGORIES:
            obj, created = Category.objects.get_or_create(
                slug=cat['slug'],
                defaults={
                    'name': cat['name'],
                    'icon': cat['icon'],
                    'order': cat['order'],
                }
            )
            if created:
                cat_created_count += 1
            else:
                # Update attributes jika ada penyesuaian order atau icon
                obj.name = cat['name']
                obj.icon = cat['icon']
                obj.order = cat['order']
                obj.save(update_fields=['name', 'icon', 'order'])

        self.stdout.write(self.style.SUCCESS(
            f"[OK] Kategori: {len(CATEGORIES)} kategori siap ({cat_created_count} baru dibuat)."
        ))

        # 2. Inisialisasi Versi Syarat & Ketentuan (TermsVersion v1.0)
        from apps.core.models import TermsVersion
        from django.utils import timezone

        TERMS_DEFAULTS = [
            {
                'term_type': TermsVersion.Type.PENYEWA,
                'version': 'v1.0',
                'content': (
                    "SYARAT DAN KETENTUAN PENYEWAAN BARANG (PENYEWA)\n\n"
                    "1. Kebenaran Identitas: Penyewa menjamin bahwa seluruh data identitas, status kemahasiswaan, NIM, dan dokumen pendukung yang didaftarkan pada akun KampusRent adalah benar, akurat, sah, dan milik pribadi.\n"
                    "2. Pemakaian Wajar & Larangan Pemindahtanganan: Barang sewaan hanya boleh digunakan untuk kebutuhan pribadi/akademik secara wajar dan hati-hati sesuai fungsi semestinya. Penyewa dilarang keras memindahtangankan, meminjamkan, menyewakan ulang (sub-lease), atau menggadaikan barang kepada pihak ketiga mana pun tanpa persetujuan tertulis pemilik.\n"
                    "3. Kewajiban Pengembalian Sesuai Jadwal: Penyewa wajib mengembalikan barang tepat waktu sesuai rentang tanggal dan jadwal serah terima yang telah disepakati kedua belah pihak di platform.\n"
                    "4. Tanggung Jawab Penuh atas Kerusakan dan Kehilangan: Penyewa bertanggung jawab penuh atas segala bentuk kerusakan fisik, penurunan fungsi di luar keausan wajar, atau kehilangan barang selama masa sewa. Dalam hal terjadi kerusakan, penyewa wajib membayar ganti rugi biaya perbaikan yang wajar. Dalam hal barang hilang atau tidak dikembalikan, penyewa wajib membayar ganti rugi sebesar nilai taksiran barang.\n"
                    "5. Denda Keterlambatan: Keterlambatan pengembalian barang dikenakan denda keterlambatan harian (50% dari tarif sewa harian per hari keterlambatan) yang wajib dilunasi oleh penyewa.\n"
                    "6. Tagihan Tambahan dan Konsekuensi Penegakan: Segala bentuk denda keterlambatan, biaya ganti rugi kerusakan, dan kompensasi kehilangan dicatat sebagai Tagihan Tambahan (ExtraCharge) terutang. Penyewa yang memiliki tagihan terutang akan dibatasi hak aksesnya, tidak dapat mengajukan sewa baru, dibekukan akunnya, dimasukkan ke dalam daftar hitam (blacklist) NIM/identitas, serta dapat dilaporkan ke pihak kampus/program studi terkait atau pihak yang berwajib bila terdapat indikasi iktikad buruk atau penggelapan.\n"
                    "7. Persetujuan Dokumentasi Foto Serah Terima: Penyewa menyetujui kewajiban pengambilan dan pengunggahan foto dokumentasi fisik barang sebelum mulai dan sesudah masa sewa sebagai bukti autentik kondisi barang.\n"
                    "8. Pembagian Data Identitas untuk Tindak Lanjut: Penyewa menyetujui bahwa data identitas (nama lengkap, NIM, kampus, nomor kontak) dapat dibagikan kepada pemilik barang dan/atau pihak berwenang guna keperluan koordinasi, penagihan, atau tindak lanjut hukum bila terjadi pelanggaran perjanjian sewa.\n"
                    "9. Penyelesaian Sengketa Melalui Admin Platform: Segala perselisihan mengenai kondisi barang atau biaya diselesaikan melalui mekanisme musyawarah dan peninjauan objektif oleh admin platform KampusRent.\n"
                    "10. Platform Sebagai Perantara: KampusRent bertindak sebagai penyedia platform teknologi perantara yang memfasilitasi transaksi dan pencatatan kesepakatan digital antara pemilik dan penyewa mahasiswa."
                ),
            },
            {
                'term_type': TermsVersion.Type.PEMILIK,
                'version': 'v1.0',
                'content': (
                    "SYARAT DAN KETENTUAN PEMASANGAN BARANG (PEMILIK)\n\n"
                    "1. Kepemilikan Sah: Pemilik menjamin bahwa barang yang dipasang untuk disewakan adalah barang milik sah secara hukum, bukan barang curian, bukan barang sengketa, dan bukan barang milik instansi/kampus yang dilarang untuk disewakan.\n"
                    "2. Kebenaran Deskripsi dan Foto: Pemilik wajib memberikan deskripsi yang akurat, jujur, menyeluruh mengenai fungsi dan kondisi barang, serta melampirkan foto riil terbaru barang tanpa manipulasi yang menyesatkan.\n"
                    "3. Kejujuran Nilai Taksiran: Estimasi nilai barang wajib diisi secara wajar, jujur, dan tidak digelembungkan melebihi harga pasar wajar barang sejenis dalam kondisi bekas saat ini (maksimal batas platform).\n"
                    "4. Larangan Barang Terlarang: Pemilik dilarang menyewakan barang-barang yang melanggar hukum, norma kampus, senjata, zat berbahaya/terlarang, atau barang yang membahayakan keselamatan umum.\n"
                    "5. Kewajiban Pemeriksaan & Serah Terima: Pemilik wajib memeriksa fungsi barang bersama penyewa saat serah terima, mendokumentasikan kondisi awal lewat foto, dan melakukan konfirmasi pengembalian secara objektif dalam batas waktu yang ditentukan."
                ),
            },
            {
                'term_type': TermsVersion.Type.UMUM,
                'version': 'v1.0',
                'content': (
                    "SYARAT DAN KETENTUAN UMUM PLATFORM KAMPUSRENT\n\n"
                    "1. Komunitas Mahasiswa Terverifikasi: KampusRent adalah platform berbagi dan sewa barang antarmahasiswa berbasis verifikasi identitas mahasiswa aktif (KTM).\n"
                    "2. Prinsip Gotong Royong & Saling Menjaga: Setiap pengguna berkomitmen menjaga amanah, merawat barang sesama mahasiswa, dan bersikap jujur dalam setiap tahapan transaksi.\n"
                    "3. Mekanisme Pembayaran Platform: Seluruh pembayaran sewa dan biaya administrasi dilakukan melalui sistem pembayaran terpadu platform KampusRent untuk memastikan ketercatatan dan transparansi kedua belah pihak.\n"
                    "4. Penyelesaian Kendala & Bantuan: Platform menyediakan sarana mediasi sengketa, pengawasan laporan, dan pos Dana Gotong Royong untuk mendukung keberlangsungan ekosistem sewa yang sehat."
                ),
            },
            {
                'term_type': TermsVersion.Type.JUAL_PENJUAL,
                'version': 'v1.0',
                'content': (
                    "SYARAT DAN KETENTUAN PENJUAL (JUAL BELI / THRIFT)\n\n"
                    "1. Kepemilikan Sah: Penjual menjamin bahwa barang yang dipasang untuk dijual adalah barang milik sah secara hukum, bukan barang curian, bukan barang titipan tanpa izin, dan bukan barang milik instansi/kampus yang dilarang untuk diperjualbelikan.\n"
                    "2. Deskripsi dan Foto Jujur: Penjual wajib memberikan deskripsi yang akurat, jujur, menyeluruh mengenai fungsi dan kondisi fisik barang, serta melampirkan foto riil terbaru tanpa manipulasi yang menyesatkan.\n"
                    "3. Pencantuman Cacat dan Minus: Segala bentuk cacat, minus fungsi, keausan, goresan, noda, atau kelengkapan yang hilang wajib dicantumkan secara transparan dalam deskripsi barang.\n"
                    "4. Penetapan Harga Wajar: Penjual wajib mencantumkan harga jual yang wajar dan tidak melebihi batas harga maksimum yang ditentukan oleh platform sesuai tingkat kepercayaan penjual saat ini.\n"
                    "5. Larangan Barang Terlarang: Penjual dilarang keras menjual barang-barang terlarang, termasuk namun tidak terbatas pada: obat resep atau obat keras, minuman beralkohol, rokok dan vape, senjata atau benda tajam berbahaya, hewan atau binatang peliharaan, makanan olahan atau makanan basah, barang palsu atau bajakan, serta akun digital atau akun game.\n"
                    "6. Transaksi dan Titik Temu: Seluruh proses transaksi jual beli wajib diselesaikan melalui mekanisme platform KampusRent dan pertemuan langsung dilakukan di titik temu area kampus yang aman dan disepakati bersama."
                ),
            },
        ]

        terms_count = 0
        for t_def in TERMS_DEFAULTS:
            t_obj, t_created = TermsVersion.objects.get_or_create(
                term_type=t_def['term_type'],
                version=t_def['version'],
                defaults={
                    'content': t_def['content'],
                    'valid_from': timezone.now(),
                    'is_active': True,
                }
            )
            if t_created:
                terms_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"[OK] Syarat & Ketentuan: {len(TERMS_DEFAULTS)} dokumen siap ({terms_count} baru dibuat)."
        ))

        # Platform dasar siap. Kampus tidak lagi bergantung pada berkas daftar awal,
        # melainkan dibuat secara dinamis saat pendaftaran mahasiswa (Fase 7B).
        self.stdout.write(self.style.SUCCESS("[OK] Inisialisasi platform bersih selesai. Tidak ada data fiktif yang dibuat."))


