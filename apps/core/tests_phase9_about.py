from django.test import TestCase, Client, override_settings
from django.conf import settings
from django.urls import reverse


class AboutPhase9Tests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_about_page_covers_sale_problems(self):
        """Memastikan masalah jual beli (barang menumpuk, penipuan grup chat, harga tidak wajar) tampil."""
        res = self.client.get(reverse('core:tentang'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Masalah yang kami lihat')
        self.assertContains(res, 'Masalah jual beli')
        self.assertContains(res, 'menumpuk')
        self.assertContains(res, 'penipuan')
        self.assertContains(res, 'harga tidak wajar')

    def test_about_page_has_two_tab_steps(self):
        """Memastikan cara kerja di tentang memakai komponen 2-tab sewa dan jual beli."""
        res = self.client.get(reverse('core:tentang'))
        self.assertContains(res, 'Cara kerja')
        self.assertContains(res, 'Sewa barang')
        self.assertContains(res, 'Jual beli')
        self.assertContains(res, 'Verifikasi KTM')
        self.assertContains(res, 'Verifikasi dan pasang barang')

    def test_about_page_three_pillars_cover_both(self):
        """Memastikan 3 pilar mencakup sewa dan jual beli serta privasi KTM akurat dengan bukti kode."""
        res = self.client.get(reverse('core:tentang'))
        self.assertContains(res, 'Tiga pilar perlindungan')
        self.assertContains(res, 'Identitas terverifikasi')
        # Pernyataan akurat sesuai kode
        self.assertContains(res, 'foto fisik KTM otomatis dihapus')
        self.assertContains(res, 'delete_image_file()')
        self.assertContains(res, 'apps/verification/models.py')
        self.assertContains(res, 'nama lengkap dan NIM tetap disimpan')
        # Pilar 2 & 3
        self.assertContains(res, 'perjanjian digital')
        self.assertContains(res, 'Bukti dan mediasi')

    def test_about_page_cta_mentions_both(self):
        """Memastikan CTA menyebutkan sewa dan jual beli serta memiliki dua tombol aksi."""
        res = self.client.get(reverse('core:tentang'))
        self.assertContains(res, 'Jelajahi sewa')
        self.assertContains(res, 'Jelajahi jual beli')

    @override_settings(KONFIRMASI_BUDAYA='tidak')
    def test_sakai_sambayan_hidden_when_konfirmasi_budaya_tidak(self):
        """Memastikan kalimat sakai sambayan TIDAK muncul saat KONFIRMASI_BUDAYA=tidak."""
        res = self.client.get(reverse('core:tentang'))
        self.assertNotContains(res, 'sakai sambayan')

    @override_settings(KONFIRMASI_BUDAYA='ya')
    def test_sakai_sambayan_shown_when_konfirmasi_budaya_ya(self):
        """Memastikan kalimat sakai sambayan MUNCUL saat KONFIRMASI_BUDAYA=ya."""
        res = self.client.get(reverse('core:tentang'))
        self.assertContains(res, 'sakai sambayan')
