from django.db import migrations
from django.utils import timezone


SELLER_TERMS_CONTENT = (
    "SYARAT DAN KETENTUAN PENJUAL (JUAL BELI / THRIFT)\n\n"
    "1. Kepemilikan Sah: Penjual menjamin bahwa barang yang dipasang untuk dijual adalah barang milik sah secara hukum, bukan barang curian, bukan barang titipan tanpa izin, dan bukan barang milik instansi/kampus yang dilarang untuk diperjualbelikan.\n"
    "2. Deskripsi dan Foto Jujur: Penjual wajib memberikan deskripsi yang akurat, jujur, menyeluruh mengenai fungsi dan kondisi fisik barang, serta melampirkan foto riil terbaru tanpa manipulasi yang menyesatkan.\n"
    "3. Pencantuman Cacat dan Minus: Segala bentuk cacat, minus fungsi, keausan, goresan, noda, atau kelengkapan yang hilang wajib dicantumkan secara transparan dalam deskripsi barang.\n"
    "4. Penetapan Harga Wajar: Penjual wajib mencantumkan harga jual yang wajar dan tidak melebihi batas harga maksimum yang ditentukan oleh platform sesuai tingkat kepercayaan penjual saat ini.\n"
    "5. Larangan Barang Terlarang: Penjual dilarang keras menjual barang-barang terlarang, termasuk namun tidak terbatas pada: obat resep atau obat keras, minuman beralkohol, rokok dan vape, senjata atau benda tajam berbahaya, hewan atau binatang peliharaan, makanan olahan atau makanan basah, barang palsu atau bajakan, serta akun digital atau akun game.\n"
    "6. Transaksi dan Titik Temu: Seluruh proses transaksi jual beli wajib diselesaikan melalui mekanisme platform KampusRent dan pertemuan langsung dilakukan di titik temu area kampus yang aman dan disepakati bersama."
)


def seed_seller_terms(apps, schema_editor):
    TermsVersion = apps.get_model('core', 'TermsVersion')
    TermsVersion.objects.get_or_create(
        term_type='jual_penjual',
        version='v1.0',
        defaults={
            'content': SELLER_TERMS_CONTENT,
            'is_active': True,
            'valid_from': timezone.now(),
        }
    )


def unseed_seller_terms(apps, schema_editor):
    TermsVersion = apps.get_model('core', 'TermsVersion')
    TermsVersion.objects.filter(term_type='jual_penjual', version='v1.0').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_termsversion_term_type'),
    ]

    operations = [
        migrations.RunPython(seed_seller_terms, reverse_code=unseed_seller_terms),
    ]
