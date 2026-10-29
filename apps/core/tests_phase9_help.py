from django.test import TestCase, Client
from django.urls import reverse


class Phase9HelpAndFaqTest(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.response = self.client.get(reverse('core:bantuan'))
        self.content = self.response.content.decode('utf-8')

    def test_bantuan_status_and_title(self):
        """Halaman bantuan mengembalikan HTTP 200 dan tidak memiliki pill di atas judul."""
        self.assertEqual(self.response.status_code, 200)
        self.assertIn('<h1 class="text-3xl sm:text-4xl md:text-5xl font-bold text-ink leading-tight tracking-tight">', self.content)
        self.assertIn('Ada yang bisa kami bantu?', self.content)
        # Pastikan pill kecil di atas judul sudah dihapus
        self.assertNotIn('Pusat Bantuan &amp; Panduan</span>', self.content)
        self.assertNotIn('bg-brand-tint text-brand text-xs font-semibold', self.content)

    def test_subtitle_mentions_both_sewa_and_jual_beli(self):
        """Subjudul mencakup sistem sewa dan jual beli mahasiswa."""
        self.assertIn('sistem sewa dan jual beli mahasiswa', self.content)

    def test_chips_are_sentence_case(self):
        """Chip kategori menggunakan kalimat sentence case."""
        expected_chips = [
            'Semua topik',
            'Verifikasi dan akun',
            'Sewa dan escrow',
            'Titik temu dan foto',
            'Denda dan sengketa',
            'Dana Gotong Royong',
            'Dompet dan penarikan',
            'Jual beli',
        ]
        for chip in expected_chips:
            self.assertIn(chip, self.content)

    def test_eleven_code_verified_faq_items_present(self):
        """11 Butir pertanyaan dengan rujukan baris kode dan logika sistem hadir lengkap."""
        # 1. Pembatalan sewa dan pesanan jual beli
        self.assertIn('Bagaimana aturan pembatalan sewa dan jika pemilik barang tidak responsif?', self.content)
        self.assertIn('apps/rentals/views.py', self.content)
        self.assertIn('Bagaimana aturan pembatalan pesanan jual beli dan jika penjual tidak responsif?', self.content)
        self.assertIn('apps/sales/views.py', self.content)

        # 2. Biaya tambahan & transparansi
        self.assertIn('Apakah ada biaya tambahan atau biaya tersembunyi saat bertransaksi?', self.content)
        self.assertIn('5% dari biaya sewa, min. Rp3.000', self.content)
        self.assertIn('0% biaya admin bagi pembeli', self.content)

        # 3. Penyamaran kontak & privasi chat
        self.assertIn('Mengapa nomor WhatsApp atau kontak pribadi saya tidak langsung ditampilkan ke publik?', self.content)
        self.assertIn('apps/chat/models.py', self.content)

        # 4. Privasi foto KTM & durasi simpan foto serah terima
        self.assertIn('Bagaimana privasi foto KTM saya dan berapa lama foto serah terima disimpan?', self.content)
        self.assertIn('delete_image_file()', self.content)
        self.assertIn('apps/verification/models.py', self.content)
        self.assertIn('purge_handover_photos()', self.content)

        # 5. Lupa kata sandi
        self.assertIn('Bagaimana jika saya lupa kata sandi akun?', self.content)
        self.assertIn('RateLimitedPasswordResetView', self.content)
        self.assertIn('apps/accounts/views.py', self.content)

        # 6. Perubahan kampus
        self.assertIn('Apakah saya bisa mengubah kampus atau fakultas setelah akun terverifikasi?', self.content)
        self.assertIn('StudentProfile.campus', self.content)
        self.assertIn('apps/accounts/models.py', self.content)

        # 7. Pemilik / penjual tidak responsif (100% refund)
        self.assertIn('dikembalikan 100% utuh', self.content)

        # 8. Masa periksa barang oleh pembeli (48 jam inspeksi)
        self.assertIn('Berapa lama masa periksa kondisi barang oleh pembeli pada transaksi jual beli?', self.content)
        self.assertIn('Masa inspeksi 48 jam', self.content)
        self.assertIn('SALE_INSPECTION_HOURS = 48', self.content)

        # 9. Biaya bagi pembeli (0% fee)
        self.assertIn('Berapa biaya admin atau komisi yang dibebankan kepada pembeli barang thrift?', self.content)
        self.assertIn('0% fee pembeli', self.content)
        self.assertIn('SaleOrder.total_amount', self.content)

        # 10. Status dipesan mengunci pembelian
        self.assertIn("Apa arti status barang 'Dipesan' dan apakah orang lain masih bisa membelinya?", self.content)
        self.assertIn('SaleItem.Status.DIPESAN', self.content)

        # 11. Kewajiban centang S&K digital
        self.assertIn('Mengapa saya wajib mencentang persetujuan Syarat &amp; Ketentuan (S&amp;K) digital?', self.content)
        self.assertIn('terms_accepted', self.content)
