# Kredit dan Atribusi Aset (CREDITS)

Dokumen ini mencatat sumber inspirasi, lisensi aset pihak ketiga, dan atribusi desain yang digunakan dalam platform Collective Campus.

---

## 1. Inspirasi Motif Nusantara (Poles Nusantara)

- **Aset:** `static/patterns/tapis_geom.svg`
- **Inspirasi Budaya:** Ritme geometris berulang (segitiga dan zigzag) yang terinspirasi dari kain tenun tradisional **Tapis Lampung**, Sumatra.
- **Karakteristik Desain:**
  - Stilasi geometris abstrak murni, menggunakan satu warna datar dari token palet platform (`brand` `#1F45C4`).
  - Dibuat secara orisinal dalam format SVG tanpa efek gradien atau bayangan.
  - **Prinsip Penghormatan Budaya:** Motif ini bukan merupakan salinan atau replika motif sakral/upacara adat tertentu dari kebudayaan Lampung, melainkan apresiasi estetika geometris Nusantara yang diselaraskan dengan identitas modern "kertas dan tinta" Collective Campus.
- **Pemakaian Terbatas:**
  1. Pita pembatas antarseksi pada beranda (`templates/home.html`).
  2. Tekstur latar tipis dengan opasitas rendah (4%) pada blok gelap seksi Bukti (`templates/home.html`).
  3. Aksen tepi kartu kuitansi transaksi (`templates/rentals/rental_detail.html`, `templates/catalog/partials/receipt_summary.html`, dan kartu kuitansi contoh beranda).

---

## 2. Tipografi

- **Bricolage Grotesque** (Judul & Heading)
  - Desainer: Mathieu Triay
  - Sumber: [Google Fonts](https://fonts.google.com/specimen/Bricolage+Grotesque)
  - Lisensi: SIL Open Font License, 1.1

- **Plus Jakarta Sans** (Teks Isi & UI)
  - Desainer: Gumpita Rahayu, Tokotype
  - Sumber: [Google Fonts](https://fonts.google.com/specimen/Plus+Jakarta+Sans)
  - Lisensi: SIL Open Font License, 1.1

---

## 3. Ikonografi

- **Lucide Icons**
  - Komponen inline SVG berbasis pustaka Lucide (`static/icons/` dan `templates/partials/icon.html`).
  - Sumber: [Lucide.dev](https://lucide.dev)
  - Lisensi: ISC License

---

## 4. Ilustrasi & Foto Demo

- **Ilustrasi Kategori:**
  - Ilustrasi vektor datar per kategori (`apps/catalog/models.py`) dibuat khusus untuk sistem cadangan placeholder gambar sesuai standar `AGENT.md`.
- **Foto Demo Prototipe:**
  - Dihasilkan melalui command pengisian data demo (`apps/core/management/commands/seed_demo.py`) untuk kebutuhan simulasi dan evaluasi transaksi prototipe mahasiswa.
