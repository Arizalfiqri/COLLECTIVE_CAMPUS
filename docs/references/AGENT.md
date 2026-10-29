# AGENT.md: Aturan Kerja dan Standar Desain Collective Campus (v2)

> Baca file ini **pertama** di setiap sesi, lalu `PROJECT_SPEC.md` (bisnis dan logika) dan `design.md` (tampilan dasar).
> Untuk hal **visual dan cara kerja**, urutan prioritas: `AGENT.md` > `design.md`. Untuk **aturan bisnis**, `PROJECT_SPEC.md` tetap yang utama.
> Bagian `design.md` yang digantikan file ini: bilah atas (2), strip kategori kaca (5.3), tata letak beranda (6.1), dekorasi 3D (7), tipografi (4.2), **warna (4.1), bayangan dan panel kaca (4.3)**, dan lencana KTM di setiap kartu (5.4). Bagian lain tetap berlaku.

## 1. Mengapa file ini ada

Hasil Fase 1 sudah berfungsi, tetapi tampilannya terasa seperti **template buatan AI**: ikon emoji, tiga kartu sama rata, ruang kosong besar, dan kartu barang tanpa foto. Tujuan v2: tampilan dengan **identitas sendiri**, yang **memperlihatkan produk nyata** (foto, harga, kuitansi, skor), dan terlihat dibuat oleh orang yang peduli detail.

Yang tetap dipertahankan dari referensi awal: kolom pencarian berbentuk pil dengan tombol kuning, serta kesan lega dan ramah. Yang diganti: palet warna (bagian 5A, tanpa gradien), cara menyusun halaman, dan semua hiasan yang tidak punya makna.

## 2. Bug yang wajib diperbaiki lebih dulu (dari tangkapan layar beranda)

| Masalah | Perbaikan |
|---|---|
| Foto kartu barang tidak tampil, teks alt bocor dan menimpa lencana | Selidiki penyebabnya: apakah file gambar benar-benar dibuat oleh `seed_demo`, apakah `MEDIA_URL` dan `MEDIA_ROOT` dilayani saat `DEBUG=True` (cek `config/urls.py`), dan apakah path di database benar. Kartu wajib punya cadangan ilustrasi bila gambar gagal dimuat |
| Harga tanpa pemisah ribuan ("Rp25000") | Buat filter template `rupiah` yang menghasilkan "Rp25.000" (titik sebagai pemisah ribuan) dan pakai di semua tempat yang menampilkan uang |
| Label kategori terpotong dengan "..." | Jangan memotong. Pakai satu baris yang bisa digeser, dengan nama kategori yang lebih pendek |
| Dua baris kategori yang sama (chip di hero dan strip kaca) | Pertahankan satu saja |
| Ruang kosong besar sesudah hero | Rapatkan, gunakan ritme jarak yang konsisten |
| Avatar pemilik berisi "..." | Pakai inisial nama pada lingkaran berwarna |
| Angka skor tanpa konteks (72, 78, 85) | Tampilkan sebagai cincin kecil dengan kata ("Tepercaya") atau hapus dari kartu |
| Bilah atas "Kampus Indonesia" dan "IDR (Rp)" | Hapus. Tidak berfungsi dan tidak berguna |
| Teks pengembang di footer ("Dibangun dengan Django 5 dan Tailwind") | Hapus dari tampilan publik |
| Klaim "Sesuai UU Pelindungan Data Pribadi" | Ganti dengan pernyataan yang benar-benar bisa dipertanggungjawabkan, misalnya "Foto KTM hanya dilihat admin dan dihapus setelah verifikasi" (hanya jika memang diimplementasikan) |
| Nama kampus lain pada data demo | Pakai area netral atau fiktif ("Gedung A", "Perpustakaan", "Kantin utara") |

## 3. Daftar larangan: ciri tampilan template AI

Jangan lakukan hal-hal ini:

1. **Emoji sebagai ikon antarmuka.** Tidak boleh ada emoji di UI sama sekali.
2. **Tiga kartu sama rata** dengan ikon di tengah, atau **empat kolom** ikon + judul + satu kalimat.
3. Lencana pil kecil di atas judul hero ("Komunitas Mahasiswa Terverifikasi").
4. Label kecil huruf kapital semua di atas judul ("LANGKAH 1").
5. Semua elemen rata tengah.
6. **Gradien dalam bentuk apa pun** (latar, tombol, kartu, teks, ikon), efek cahaya (glow), gumpalan blur, panel kaca (`backdrop-blur`), bayangan berwarna, dan bentuk 3D acak tanpa makna.
7. Lencana yang sama di setiap kartu, sampai tidak lagi bermakna.
8. Teks pengisi tanpa fungsi (pemilih bahasa atau mata uang palsu).
9. Tanda hubung panjang (—) dan frasa klise ("aman dan transparan dari awal hingga akhir", "solusi terbaik").
10. Terlalu banyak warna, atau pastel di atas pastel. Ikuti palet dan aturan pemakaian di bagian 5A.

## 4. Identitas visual Collective Campus

Hiasan harus berasal dari **produknya**, bukan bentuk acak.

1. **Motif kartu KTM.** Persegi panjang bersudut membulat dengan rasio sekitar 1,586 (ukuran kartu ID standar), berisi foto kecil, garis teks, dan centang "Terverifikasi". Dipakai di hero dan halaman verifikasi.
2. **Bahasa kuitansi.** Ringkasan harga, detail sewa, dan buku besar memakai garis putus-putus (seperti perforasi struk), angka bergaya `tabular-nums`, dan nomor referensi seperti `KR-2X9F`. Uang yang ditahan diberi stempel kecil "Ditahan".
3. **Segel verifikasi.** Satu bentuk perisai-centang, dipakai di **profil dan detail barang**, tidak di setiap kartu.
4. **Foto nyata lebih berharga daripada dekorasi.** Ruang di halaman dipakai untuk barang, bukan hiasan.
5. **Sentuhan identitas lokal (Identitas Lampung-Nusantara — Fase 7B & 7F).** Prinsip: ornamen jarang tetapi bermakna, bukan garis pembatas berulang. Warna ornamen: kunyit (`#F2A900`) di atas tinta (`#141B34`) atau marun-tapis (`#5B1A24`). Tanpa gradien, blur, atau bayangan berwarna. Ornamen tidak pernah berada di belakang teks. Menggunakan keterangan resmi: "terinspirasi kain tapis dan siger Lampung, digambar ulang secara geometris" (tidak mengklaim "motif asli").
   - **Pembersihan ornamen (Fase 7B):**
     1. Pita di bawah navbar dihapus di semua halaman; navbar bersih dengan hanya border 1 px (`border-b border-line`).
     2. Penanda 5 tumpal di bawah judul H2 dihapus di semua halaman.
   - **Pita Ornamen (Hanya 3 Tempat, Semuanya Kunyit di Atas Tinta `#141B34`):**
     1. Tepi atas blok "Bukti / Keamanan Transaksi" (`kain_border` variant="ink" size="lg").
     2. Tepi bawah blok "Bukti / Keamanan Transaksi" (`kain_border` variant="ink" size="lg").
     3. Tepat di atas footer (`kain_border` variant="ink" size="responsive": tinggi 24 px desktop, 16 px mobile).
   - **Aset Geometris Utama:**
     1. `static/img/tapis-tile.svg`: Pola ubin belah ketupat tapis kunyit di atas latar tinta 56x56 px.
     2. `static/img/tapis-tile-marun.svg`: Pola ubin belah ketupat tapis kunyit di atas latar marun `#5B1A24` 56x56 px (Fase 7F).
     3. `static/img/siger.svg`: Mahkota siger Lampung stilir geometris kunyit.
     4. `static/img/kapal.svg`: Perahu Lampung stilir geometris kunyit dan kertas.
     5. `static/img/kapal-tinta.svg`: Perahu Lampung stilir geometris kunyit dengan tiang dan layar tinta `#141B34` untuk plat kertas (Fase 7F).
     6. `static/img/logo-mark.svg`: Logo perisai biru dengan siger kunyit 32x32 px.
   - **Aturan Marun-Tapis dan Penempatan Momen Budaya (Fase 7F):**
     - Token `marun-tapis` (`#5B1A24`) HANYA boleh dipakai sebagai latar panel ornamen (momen budaya), BUKAN untuk teks, tombol, atau latar bagian halaman lain.
     - Nilai bawaan `[LATAR_PANEL] = marun`; jika ditulis "tinta", memakai `#141B34`. Tanpa gradien.
     - Penempatan momen budaya DIBATASI KETAT HANYA pada 3 lokasi:
       1. **Seksi Gotong Royong (Beranda):** Panel kain marun `[LATAR_PANEL]` dengan satu plat kertas (`#F8F5EE`, rounded) di tengah berisi ilustrasi kapal (lambung kunyit, layar & tiang tinta) dan siger kecil di bawahnya. Teks HANYA di dalam plat, tidak pernah di atas pola.
       2. **Header Halaman Tentang (`/tentang/`):** Panel sisi kanan desktop berlatar `tapis-tile.svg` dengan `siger.svg`.
       3. **Halaman Galat Sistem (404/403/500/CSRF):** Panel berlatar `tapis-tile.svg` dengan ilustrasi `kapal.svg` di tengah. Teks di luar pola.
     - Seluruh ornamen dan panel ornamen wajib diberi atribut `aria-hidden="true"`. Teks tidak pernah berada di atas pola berulang.
   - **Dana Gotong Royong:** Rekening cadangan gotong royong internal untuk menanggung sengketa dan barang yang tidak dikembalikan. Slogan merek: "Saling sewa, saling bantu."

## 5. Ikon

- Pakai satu set ikon garis, **Lucide**, sebagai **SVG inline**. Garis 1,75 px, ukuran 20 atau 24 px, warna `currentColor` dari token.
- Simpan sebagai sprite atau file di `static/icons/` dan panggil lewat komponen `templates/partials/icon.html`. Jangan memuat pustaka JS besar hanya untuk ikon.
- Pemetaan awal: Kamera → `camera`, Wisuda → `graduation-cap`, Alat praktikum → `flask-conical`, Camping → `tent`, Proyektor → `projector`, Kostum → `shirt`, Laptop → `laptop`, Lain-lain → `package`, Verifikasi → `shield-check`, Pembayaran → `wallet`, Foto → `camera`, Cari → `search`.

## 5A. Warna dan permukaan (menggantikan design.md 4.1 dan 4.3)

**Konsep: "kertas dan tinta".** Latar kertas hangat, teks tinta navy gelap, satu biru tegas untuk aksi, dan kunyit sebagai sorotan kecil. Semua warna **datar**. Tidak ada gradien sama sekali. Rasanya seperti kartu mahasiswa dan kuitansi cetak, bukan situs template.

### Token warna

| Token | Hex | Pemakaian |
|---|---|---|
| `paper` | `#F8F5EE` | Latar halaman |
| `paper-deep` | `#F0EBDD` | Pita seksi selang-seling, latar placeholder foto |
| `card` | `#FFFFFF` | Kartu, kolom pencarian, kuitansi |
| `line` | `#E4DECF` | Garis pemisah dan border kartu |
| `ink` | `#141B34` | Teks utama, blok gelap |
| `ink-muted` | `#566074` | Teks sekunder |
| `brand` | `#1F45C4` | Tombol utama, tautan, cincin fokus |
| `brand-hover` | `#17369F` | Hover dan saat ditekan |
| `brand-tint` | `#E6ECFB` | Chip, latar ikon, kartu KTM di hero |
| `saffron` | `#F2A900` | Tombol cari, satu sorotan kecil per layar, bintang rating |
| `pine` | `#0E7C5A` | Terverifikasi, berhasil |
| `pine-dark` | `#0A5C43` | Teks di atas `pine-tint` |
| `pine-tint` | `#DDF1E8` | Latar status berhasil |
| `amber-text` | `#9A5B00` | Teks status menunggu atau ditahan |
| `amber-tint` | `#FFF0D1` | Latar status menunggu atau ditahan |
| `brick` | `#B42318` | Error, tolak, bahaya |
| `brick-tint` | `#FDE7E4` | Latar error |
| `tile-blue` | `#8EA8F7` | Khusus ubin ilustrasi placeholder (Kamera, Laptop) |
| `tile-saffron` | `#FFD66B` | Khusus ubin ilustrasi placeholder (Wisuda, Kostum) |
| `tile-mint` | `#7ACFAC` | Khusus ubin ilustrasi placeholder (Praktikum, Proyektor) |
| `tile-coral` | `#FFA68C` | Khusus ubin ilustrasi placeholder (Camping, Lain-lain) |
| `marun-tapis` | `#5B1A24` | HANYA sebagai latar panel ornamen (momen budaya), bukan untuk teks, tombol, atau latar bagian halaman lain. Motif kunyit di atas marun memakai `tapis-tile-marun.svg`. Nilai [LATAR_PANEL] = marun (bawaan); jika "tinta", pakai `#141B34`. Tanpa gradien. |

### Pasangan yang dipakai (kontras perkiraan, tetap uji dengan alat kontras)

| Teks atau elemen | Latar | Kontras |
|---|---|---|
| `ink` | `paper` | sekitar 15:1 |
| `ink-muted` | `paper` | sekitar 5,8:1 |
| putih | `brand` | sekitar 7,7:1 |
| `brand` (tautan) | `paper` | sekitar 7:1 |
| `ink` | `saffron` | sekitar 8,5:1 |
| putih | `pine` | sekitar 5,2:1 |
| `pine-dark` | `pine-tint` | sekitar 6,8:1 |
| `amber-text` | `amber-tint` | sekitar 4,8:1 |
| `brick` | `brick-tint` | sekitar 5,5:1 |
| putih | `ink` | sekitar 17:1 |

Jangan menaruh teks putih di atas `saffron`. Jangan menaruh teks `pine` langsung di atas `pine-tint` (pakai `pine-dark`).

### Aturan pemakaian

1. **Dilarang:** gradien (latar, tombol, kartu, teks, ikon), efek cahaya (glow), gumpalan blur, panel kaca (`backdrop-blur`), dan bayangan berwarna.
2. **Pemisah dengan garis dan blok datar.** Kartu memakai border 1 px `line`, bukan bayangan. Satu-satunya bayangan yang boleh: `0 1px 2px rgba(20,27,52,0.08)` untuk elemen melayang (dropdown, modal, kolom pencarian).
3. **Proporsi:** sekitar 60% `paper` dan `card`, 25% `ink`, 10% `brand`, paling banyak 3% `saffron`, sisanya warna status.
4. **`saffron` hanya** untuk tombol cari bulat, bintang rating, dan satu sorotan kecil per layar (misalnya stempel atau harga).
5. **Satu blok gelap (`ink`) per halaman** paling banyak, misalnya seksi Bukti, dengan teks putih dan aksen `saffron`.
6. **Warna status selalu disertai teks atau ikon.** Jangan mengandalkan warna saja.
7. **Placeholder foto dan ubin ilustrasi kategori** memakai warna datar nada lebih lembut (tanpa gradien): biru `#8EA8F7` (`tile-blue`), kunyit `#FFD66B` (`tile-saffron`), mint `#7ACFAC` (`tile-mint`), koral `#FFA68C` (`tile-coral`), satu warna tetap per kategori. Ilustrasi berisi putih dengan garis `ink` `#141B34` setebal 2 px, mengisi sekitar 55-60% lebar ubin dengan rasio 4:3, dengan satu detail isi `ink` (misalnya lensa atau layar). Warna koral hanya dipakai di ubin ilustrasi. Dilarang memakai `paper-deep` sebagai latar ubin.
8. **Tautan** berwarna `brand` dengan garis bawah. **Fokus keyboard:** cincin `brand` 3 px dengan jarak 2 px.
9. **Tombol:** utama `brand` (teks putih), sekunder putih dengan border `line` dan teks `ink`, aksen cari `saffron` dengan ikon `ink`.

### Konfigurasi Tailwind (ganti token lama, jangan di-`extend`)

Hapus token lama (`bg`, `blue`, `teal`, `sun`, `coral`, `star`, `footer-bg`), lalu cari dan ganti semua pemakaiannya di template.

```js
// tailwind.config.js (potongan)
theme: {
  colors: {
    transparent: 'transparent', current: 'currentColor', white: '#FFFFFF',
    paper: { DEFAULT: '#F8F5EE', deep: '#F0EBDD' },
    card: '#FFFFFF',
    line: '#E4DECF',
    ink: { DEFAULT: '#141B34', muted: '#566074' },
    brand: { DEFAULT: '#1F45C4', hover: '#17369F', tint: '#E6ECFB' },
    saffron: '#F2A900',
    pine: { DEFAULT: '#0E7C5A', dark: '#0A5C43', tint: '#DDF1E8' },
    amber: { text: '#9A5B00', tint: '#FFF0D1' },
    brick: { DEFAULT: '#B42318', tint: '#FDE7E4' },
    tile: { blue: '#8EA8F7', saffron: '#FFD66B', mint: '#7ACFAC', coral: '#FFA68C' },
    'marun-tapis': '#5B1A24',
  },
}
```

## 6. Tipografi (menggantikan design.md 4.2)

- Judul: **Bricolage Grotesque** (bobot 700, jarak huruf sedikit rapat). Isi: **Plus Jakarta Sans** (400 dan 500). Dua-duanya dari Google Fonts, dengan cadangan `system-ui, sans-serif`.
- Angka uang memakai `font-variant-numeric: tabular-nums`.
- Skala ukuran tetap seperti `design.md` 4.2.

## 7. Beranda v2

Susunan dari atas ke bawah (tanpa bilah atas):

```
[navbar: logo | Jelajahi, Cara kerja, Bantuan | Masuk, Pasang barang]

HERO (rata kiri, dua kolom)
┌────────────────────────────┬─────────────────────────┐
│ Sewa kamera, toga, atau    │  [kartu KTM + centang]  │
│ proyektor dari sesama      │     [kartu barang nyata │
│ mahasiswa.                 │      foto + Rp/hari]    │
│ Pemilik terverifikasi KTM. │        [kartu kuitansi: │
│ Uang ditahan sampai barang │   Deposit Rp500.000     │
│ kembali.                   │   Ditahan]              │
│ (ikon cari | kolom cari |  │                         │
│  kategori | (cari))        │                         │
│ Pencarian populer: Kamera, │                         │
│ Toga, Proyektor            │                         │
└────────────────────────────┴─────────────────────────┘

[Baris kategori: SATU baris, ikon Lucide, bisa digeser, tidak terpotong]

Barang populer ..................................... Lihat semua
[grid 4 kolom, kartu lebih besar, foto nyata]

Cara kerja (alur 5 langkah, garis penghubung, potongan UI mini)
Verifikasi KTM > Ajukan sewa > Bayar (dana ditahan) > Serah terima + foto > Kembali, deposit cair

Bukti, bukan janji (dua kolom)
[kuitansi contoh sewa kamera 3 hari]   [foto sebelum/sesudah + cincin skor + 3 faktor]

Punya barang yang jarang dipakai? (ajakan pemilik)
Contoh: Rp75.000 x 3 hari = Rp207.000 untukmu setelah komisi 8%.   [Pasang barang]

[footer ringkas 3 kolom]
```

Aturan tiap bagian:

- **Hero:** judul rata kiri, satu kalimat pendukung, kolom pencarian pil dengan tombol kuning bulat. Sisi kanan berisi **tiga elemen produk** yang bertumpuk sedikit: kartu KTM, kartu barang (foto nyata), dan kartu kuitansi kecil. Semuanya data contoh yang jelas diberi tanda "Contoh". Di mobile tampilkan satu kartu barang di bawah teks.
- **Pencarian populer** berisi kata kunci nyata, bukan kategori.
- **Cara kerja** adalah satu alur berurutan (boleh bernomor karena urutan nyata), bukan tiga kartu kembar. Tiap langkah punya potongan UI mini yang dibuat dengan CSS.
- **Bukti:** kuitansi memakai contoh hitungan di `PROJECT_SPEC.md` 7.2 (sewa Rp225.000, deposit Rp500.000 ditahan, proteksi Rp3.000, total Rp728.000). Skor kepercayaan ditampilkan bersama 3 faktor penjelasnya.
- Hapus seksi "Mengapa Collective Campus aman?" empat kolom. Isinya sudah tercakup oleh seksi Bukti.

## 8. Kartu barang v2

1. Foto 4:5 (wajib ada gambar, lihat bagian 9).
2. Nama barang (maks. 2 baris).
3. **Rp75.000 / hari** (angka tebal, "/ hari" redup).
4. Baris kecil: area pengambilan dan status ("Tersedia hari ini" atau tanggal kosong terdekat).
5. Pemilik: avatar inisial, nama, dan **cincin skor kecil dengan kata** ("Tepercaya", "Cukup", "Pengguna baru").
6. **Tanpa lencana KTM di kartu.** Semua pemilik sudah wajib terverifikasi, jadi lencananya tidak lagi membedakan. Tulis sekali di dekat pencarian: "Semua pemilik terverifikasi KTM". Segel verifikasi tampil di profil dan detail barang.

## 9. Foto dan data demo

- Kartu wajib punya gambar. Urutan pilihan:
  1. **Foto buatan sendiri** (kamera ponsel) untuk 10-20 barang. Ini paling meyakinkan.
  2. **Foto bebas lisensi** (misalnya Unsplash atau Pexels) dengan sumber dan lisensi dicatat di `docs/CREDITS.md`.
  3. Cadangan: **ilustrasi SVG per kategori** dengan gaya seragam (garis dan dua warna dari token). Bukan kotak kosong, bukan emoji.
- Foto diubah ukurannya saat diunggah (maks. 1280 px sisi terpanjang, kualitas JPEG sekitar 80).
- Nama pengguna dan area di data demo bersifat fiktif atau netral.

## 10. Cara kerja agen dan verifikasi visual

1. Kerjakan perubahan dalam bagian kecil. Jangan mengubah logika bisnis saat merevisi desain.
2. Setelah setiap perubahan tampilan: jalankan server, buka halaman pada lebar **1280 px** dan **390 px**, dan ambil tangkapan layar (pakai browser bawaan bila tersedia, jika tidak minta saya mengirim tangkapan layar).
3. Periksa sebelum melapor: tidak ada gambar rusak atau teks alt bocor, tidak ada teks terpotong atau tumpang tindih, tidak ada emoji, harga berformat "Rp25.000", konsol browser bersih, kontras teks memadai, dan fokus keyboard terlihat.
4. **Jangan menyatakan selesai sebelum melihat hasilnya sendiri.**
5. Jika ada keputusan desain yang ambigu, pilih yang paling sesuai file ini dan catat di `docs/DECISIONS.md`.
6. Commit per bagian dengan pesan yang jelas.

## 11. Daftar periksa desain

- [ ] Semua bug di bagian 2 sudah diperbaiki.
- [ ] Tidak ada emoji di antarmuka, semua ikon memakai Lucide inline.
- [ ] Hero asimetris dengan elemen produk (kartu KTM, kartu barang, kartu kuitansi).
- [ ] Tidak ada tiga kartu kembar atau empat kolom ikon + judul + satu kalimat.
- [ ] Semua kartu barang punya foto atau ilustrasi, harga berformat benar.
- [ ] Lencana KTM hanya di profil dan detail, bukan di setiap kartu.
- [ ] Teks bebas dari tanda hubung panjang, frasa klise, dan label huruf kapital semua.
- [ ] Palet sesuai bagian 5A. Tidak ada gradien, glow, blur, panel kaca, atau bayangan berwarna di mana pun (cek juga CSS bawaan dan komponen lama).
- [ ] Token warna lama sudah dihapus dan tidak ada sisa pemakaiannya di template.
- [ ] Pola tapis geometris abstrak hanya di maksimal tiga tempat (pita pembatas, blok Bukti, tepi kuitansi) dan <=10% area halaman.
- [ ] Istilah Dana Gotong Royong menggantikan dana proteksi di antarmuka publik dan dokumen.
- [ ] Halaman /tentang/ dan seksi beranda Gotong Royong bebas dari tanda hubung panjang dan frasa klise.
- [ ] Rapi di lebar 390 px dan 1280 px.
