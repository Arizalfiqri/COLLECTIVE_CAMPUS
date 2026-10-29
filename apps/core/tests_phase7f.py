import os
import re
from django.test import TestCase
from django.conf import settings
from django.urls import reverse
from apps.catalog.management.commands.replace_demo_photos import get_category_tile_color, STROKE_WIDTH, WIDTH, HEIGHT


class Phase7FFinalPolishTest(TestCase):
    """Pengujian aturan Fase 7F: Poles Akhir Beranda & Halaman Publik, Pembekuan Desain."""

    def test_marun_tapis_asset_and_strict_placement(self):
        """1. Token marun-tapis dan aset tapis-tile-marun.svg tersedia dan aria-hidden."""
        marun_tile_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'tapis-tile-marun.svg')
        self.assertTrue(os.path.exists(marun_tile_path), "Aset static/img/tapis-tile-marun.svg harus ada.")
        with open(marun_tile_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        self.assertIn("#5B1A24", svg_content, "tapis-tile-marun.svg harus menggunakan latar #5B1A24")
        self.assertIn("#F2A900", svg_content, "tapis-tile-marun.svg harus menggunakan motif kunyit #F2A900")

        # Periksa beranda: panel marun tapis ada, aria-hidden, teks HANYA dalam plat
        res = self.client.get(reverse('home'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn("tapis-tile-marun.svg", content, "Beranda harus menggunakan tapis-tile-marun.svg di seksi gotong royong")
        self.assertIn("#5B1A24", content, "Panel kain beranda harus berlatar #5B1A24")

        # Cek aria-hidden pada panel kain marun
        self.assertIn('aria-hidden="true"', content)

        # Cek bahwa #5B1A24 TIDAK digunakan untuk tombol umum (misal btn bg-marun-tapis tidak boleh ada)
        self.assertNotIn("text-marun", content, "Token marun tidak boleh dipakai sebagai warna teks")
        self.assertNotIn("bg-marun-tapis text-", content, "Token marun tidak boleh dipakai sebagai tombol")

    def test_gotong_royong_section_cultural_anchor(self):
        """2. Seksi Gotong Royong dua kolom dengan kutipan, 3 prinsip berikon, dan kartu dana."""
        res = self.client.get(reverse('home'))
        content = res.content.decode('utf-8')

        # Kutipan
        self.assertIn("Saling sewa, saling bantu.", content)
        # 3 Prinsip
        self.assertIn("Saling bantu (Dana Gotong Royong)", content)
        self.assertIn("Ramah (serah terima di titik temu kampus)", content)
        self.assertIn("Terbuka antarkampus", content)
        # Plat kertas kapal dan siger
        self.assertIn("kapal-tinta.svg", content)
        self.assertIn("siger.svg", content)
        self.assertIn("Gotong Royong Mahasiswa", content)

    def test_item_card_aspect_ratio_and_typography(self):
        """3. Kartu barang menggunakan aspek 4:3, tipografi terstandar, dan generator ubin lembut."""
        card_path = os.path.join(settings.BASE_DIR, 'templates', 'partials', 'item_card.html')
        with open(card_path, 'r', encoding='utf-8') as f:
            card_content = f.read()

        self.assertIn("aspect-[4/3]", card_content, "Kartu barang harus menggunakan aspect-[4/3]")
        self.assertNotIn("aspect-[4/5]", card_content, "Rasio lama 4:5 tidak boleh ada lagi")

        # Periksa konstanta generator replace_demo_photos
        self.assertEqual(STROKE_WIDTH, 2, "Garis ikon ilustrasi generator harus 2px")
        self.assertEqual(WIDTH, 400)
        self.assertEqual(HEIGHT, 300)

        # Warna nada lembut
        self.assertEqual(get_category_tile_color("kamera"), "#8EA8F7")
        self.assertEqual(get_category_tile_color("wisuda"), "#FFD66B")
        self.assertEqual(get_category_tile_color("praktikum"), "#7ACFAC")
        self.assertEqual(get_category_tile_color("camping"), "#FFA68C")

    def test_standalone_calculator_and_streamlined_proof_block(self):
        """4. Kalkulator sewa dipisahkan mandiri dan blok gelap dirampingkan."""
        res = self.client.get(reverse('home'))
        content = res.content.decode('utf-8')

        # Seksi kalkulator mandiri
        self.assertIn("Hitung biaya sewa", content)
        self.assertIn("id=\"kalkulator-hasil\"", content)

        # Blok gelap Bukti / Keamanan
        self.assertIn("Mengapa transaksi di Collective Campus aman?", content)
        self.assertIn("Verifikasi identitas mahasiswa (KTM)", content)
        self.assertTrue("Penahanan dana escrow &amp; deposit" in content or "Perjanjian digital &amp; penahanan pembayaran" in content)
        self.assertIn("Dokumentasi foto serah terima fisik", content)
        self.assertIn("Dana Gotong Royong", content)

        # Posisi: Hitung biaya sewa harus muncul SEBELUM blok gelap
        idx_calc = content.find("Hitung biaya sewa")
        idx_dark = content.find("Mengapa transaksi di Collective Campus aman?")
        self.assertTrue(idx_calc < idx_dark, "Seksi kalkulator harus berada tepat di atas blok gelap")

    def test_hero_alignment_and_three_guarantees(self):
        """5. Hero menampilkan 3 jaminan berikon dan pencarian populer tetap."""
        res = self.client.get(reverse('home'))
        content = res.content.decode('utf-8')

        self.assertIn("Pemilik terverifikasi KTM", content)
        self.assertIn("Pembayaran ditahan platform", content)
        self.assertIn("Perjanjian digital", content)

    def test_section_spacing_consistency(self):
        """Standarisasi jarak seksi Phase 7I: 64px desktop (lg:mt-16), 48px tablet (sm:mt-12), 40px mobile (mt-10)."""
        home_path = os.path.join(settings.BASE_DIR, 'templates', 'home.html')
        with open(home_path, 'r', encoding='utf-8') as f:
            home_content = f.read()

        # Phase 7I melarang py-16 md:py-24 dan menggantinya dengan sistem jarak tunggal mt-10 sm:mt-12 lg:mt-16 / spacing-sections
        self.assertNotIn("py-16 md:py-24", home_content, "Phase 7I melarang py-* besar bertumpuk pada seksi")
        occurrences = home_content.count("mt-10 sm:mt-12 lg:mt-16")
        self.assertGreaterEqual(occurrences, 4, "Beranda harus memakai mt-10 sm:mt-12 lg:mt-16 pada seksi utama")

