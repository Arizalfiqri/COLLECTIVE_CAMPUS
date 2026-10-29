from django.db import migrations
from django.utils import timezone


BUYER_TERMS_CONTENT = (
    "SYARAT DAN KETENTUAN PEMBELI (JUAL BELI / THRIFT)\n\n"
    "1. Kondisi Barang Apa Adanya: Pembeli memahami dan menyetujui bahwa barang bekas dijual apa adanya sesuai dengan deskripsi, rincian minus/cacat, dan foto yang dicantumkan oleh penjual.\n"
    "2. Pemeriksaan Saat Serah Terima: Pembeli wajib memeriksa secara teliti kondisi fisik, kelengkapan, dan fungsi barang saat serah terima langsung di titik temu area kampus yang disepakati bersama.\n"
    "3. Pembayaran Melalui Platform: Pembayaran hanya dilakukan secara sah melalui platform KampusRent (rekening bersama) untuk melindungi transaksi kedua belah pihak hingga serah terima selesai.\n"
    "4. Finalitas Transaksi: Tidak ada pengembalian barang atau dana setelah pembeli mengonfirmasi penerimaan barang, kecuali terdapat sengketa yang diajukan dalam masa pemeriksaan dan diputuskan oleh admin.\n"
    "5. Penyelesaian Sengketa: Segala perselisihan atau ketidaksesuaian barang diselesaikan melalui mediasi dan keputusan admin KampusRent secara adil dan mengikat.\n"
    "6. Peran Platform: KampusRent bertindak sebagai perantara penyedia sistem dan rekening bersama yang aman antara mahasiswa penjual dan pembeli."
)


def seed_buyer_terms(apps, schema_editor):
    TermsVersion = apps.get_model('core', 'TermsVersion')
    TermsVersion.objects.get_or_create(
        term_type='jual_pembeli',
        version='v1.0',
        defaults={
            'content': BUYER_TERMS_CONTENT,
            'is_active': True,
            'valid_from': timezone.now(),
        }
    )


def unseed_buyer_terms(apps, schema_editor):
    TermsVersion = apps.get_model('core', 'TermsVersion')
    TermsVersion.objects.filter(term_type='jual_pembeli', version='v1.0').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_alter_termsversion_term_type'),
    ]

    operations = [
        migrations.RunPython(seed_buyer_terms, reverse_code=unseed_buyer_terms),
    ]
