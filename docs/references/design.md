# design.md: Panduan Desain Collective Campus

> Dokumen ini untuk AI agent dan pengembang. Baca bersama `PROJECT_SPEC.md`. Semua teks antarmuka memakai **Bahasa Indonesia**.

## 1. Cara memakai referensi

Gambar referensi ada di `docs/reference/` (file bernama `Rentify...`, format `.jfif` yang sebenarnya JPEG; ganti ekstensi menjadi `.jpg` jika alat tidak bisa membukanya). Jika gambar tidak bisa dilihat, pakai **deskripsi tertulis di bagian 2** sebagai gantinya.

**Aturan keras:**

1. **Ikuti** susunan, nuansa, dan hierarki visual referensi.
2. **Jangan menyalin** aset, ilustrasi, foto, logo, atau teks dari referensi. Referensi berasal dari tema WordPress komersial, dan teks di dalam gambarnya rusak atau acak (misalnya "Classified Ads Hornee Ad:"). Buat semua aset dan teks sendiri.
3. Ganti isi dari "iklan baris, mobil, fashion" menjadi **sewa barang antarmahasiswa** (kamera, toga, proyektor, perlengkapan camping, alat praktikum).
4. Hasil akhir harus terlihat sebagai produk dengan identitas sendiri, bukan tiruan.

## 2. Deskripsi tertulis referensi (dari atas ke bawah)

1. **Bilah atas tipis:** latar abu-abu muda, teks kecil di kiri dan pilihan kecil (bahasa/mata uang) di kanan.
2. **Navbar putih:** logo kecil di kiri, menu di tengah (5-6 tautan teks), ikon pencarian dan **tombol pil berwarna tosca** di kanan.
3. **Hero:** latar sangat terang dengan semburat biru. Judul besar, tebal, dua baris, rata tengah, berwarna navy gelap. Di bawahnya **kolom pencarian berbentuk pil putih yang lebar** dengan bayangan lembut, dan **tombol bulat kuning** berikon kaca pembesar di ujung kanan. Di bawah kolom pencarian ada **4 ikon kategori bergaya garis tipis** berwarna biru dengan label kecil.
4. **Dekorasi 3D pastel:** bentuk lengkung biru besar di kiri atas dan kanan, bentuk melengkung tertutup (seperti gerbang) berwarna biru di kanan, **tumpukan balok warna** (kuning, biru, koral) di kiri bawah, bintang biru kecil, serta partikel oranye kecil. Sebagian bentuk **dikaburkan (blur)** untuk memberi kedalaman.
5. **Strip kategori kaca:** panel putih tembus pandang berisi 5 ikon kategori dengan label. Satu ikon 3D di tengah lebih besar dan menonjol.
6. **Judul seksi** rata tengah dengan subjudul kecil di bawahnya.
7. **Seksi "Barang unggulan":** judul tebal rata kiri, tombol kecil berbingkai tipis di kanan.
8. **Grid kartu 5 kolom x 2 baris:** gambar bersudut membulat dengan latar warna pastel berbeda (biru, kuning, abu, tosca), lalu nama, harga, **bintang kuning**, dan baris kecil berisi info tambahan.
9. **Footer:** latar abu-abu terang, 4 kolom tautan dengan teks kecil.

Kesan keseluruhan: **bersih, lega, ramah, modern, pastel biru, dengan satu aksen hangat (kuning)**.

## 3. Pemetaan ke Collective Campus

| Referensi | Collective Campus |
|---|---|
| Logo "ClassiAd" | Logo Collective Campus (buat sendiri, sederhana) |
| Menu tengah | Beranda, Jelajahi, Cara kerja, Bantuan |
| Tombol pil tosca | **Pasang barang** (jika belum login: **Masuk**) |
| Judul hero | "Sewa barang kampus, aman dan terverifikasi" (boleh disempurnakan) |
| Kolom pencarian | "Cari kamera, toga, proyektor..." + pilihan kategori |
| 4-5 ikon kategori | Kamera, Wisuda, Alat praktikum, Camping, Proyektor, Kostum |
| "Featured Ads" | **Barang populer** |
| Kartu foto orang/mobil | Kartu **foto barang** (rasio 4:5), harga **per hari**, rating, **lencana Terverifikasi KTM** |
| Footer 4 kolom | Collective Campus, Jelajahi, Bantuan, Legal |

## 4. Token desain

### 4.1 Warna

| Token | Hex | Pemakaian |
|---|---|---|
| `bg` | `#F4F7FB` | Latar halaman dan hero |
| `surface` | `#FFFFFF` | Kartu, navbar, kolom pencarian |
| `ink` | `#1E2347` | Judul dan teks utama (navy gelap) |
| `ink-muted` | `#5F6788` | Teks sekunder (kontras cukup di atas putih) |
| `blue-100` | `#E3EDFB` | Latar ikon, chip, panel kaca |
| `blue-300` | `#B7CDF2` | Bentuk dekorasi terang, garis |
| `blue-500` | `#7FA6E8` | Bentuk dekorasi utama |
| `blue-700` | `#3F67B8` | Tautan, ikon garis, fokus |
| `teal-400` | `#3DBDB5` | Dekorasi dan latar ikon (bukan latar teks putih) |
| `teal-600` | `#0F7D76` | **Tombol utama** dengan teks putih |
| `sun-400` | `#F6B73C` | Tombol pencarian bulat (ikon navy di dalamnya) |
| `coral-400` | `#F2877B` | Dekorasi dan aksen kecil |
| `star` | `#F5B301` | Bintang rating |
| `success` | `#1F9D61` | Terverifikasi, berhasil |
| `warning` | `#C98A0B` | Menunggu, perhatian |
| `danger` | `#D64545` | Error, tolak |
| `footer-bg` | `#EEF1F6` | Latar footer |

Kontras teks normal minimal **4,5:1**. Teks putih hanya di atas `teal-600`, `blue-700`, atau `ink`. Jangan menaruh teks putih di atas `teal-400` atau `sun-400`.

### 4.2 Tipografi

- **Satu keluarga huruf: Poppins** (sesuai karakter geometris di referensi). Muat dari Google Fonts dengan `display=swap`, dan sediakan cadangan `system-ui, sans-serif` agar tetap terbaca saat offline.
- Bobot: 400 (isi), 500 (label dan tombol), 600 (subjudul), 700 (judul).

| Peran | Desktop | Mobile |
|---|---|---|
| Judul hero | 56/64, bobot 700 | 34/42 |
| H2 (judul seksi) | 32/40, bobot 700 | 26/34 |
| H3 (judul kartu atau panel) | 20/28, bobot 600 | 18/26 |
| Isi | 16/26, bobot 400 | 16/26 |
| Kecil | 14/22 | 14/22 |
| Keterangan | 12/18 | 12/18 |

Panjang baris isi kurang dari 80 karakter. Gunakan **sentence case** (huruf besar hanya di awal kalimat dan nama diri). Jangan memakai label HURUF KAPITAL semua.

### 4.3 Bentuk, bayangan, jarak

- Radius: pil `9999px` (tombol, kolom pencarian, chip), kartu `20px`, gambar di dalam kartu `16px`, input `14px`.
- Bayangan lembut berwarna biru, bukan abu-abu pekat:
  - kartu: `0 8px 24px rgba(63, 103, 184, 0.10)`
  - kolom pencarian dan panel kaca: `0 12px 40px rgba(63, 103, 184, 0.16)`
- Jarak berbasis kelipatan 4 px. Jarak antarseksi besar (`96px` desktop, `64px` mobile).
- Lebar konten maksimum `1200px`, rata tengah.
- Panel kaca: `background: rgba(255,255,255,0.65)`, `backdrop-filter: blur(12px)`, border putih `1px` transparan 60%.

### 4.4 Cuplikan konfigurasi Tailwind

```js
// tailwind.config.js (potongan)
theme: {
  extend: {
    fontFamily: { sans: ['Poppins', 'system-ui', 'sans-serif'] },
    colors: {
      bg: '#F4F7FB', ink: '#1E2347', 'ink-muted': '#5F6788',
      blue: { 100: '#E3EDFB', 300: '#B7CDF2', 500: '#7FA6E8', 700: '#3F67B8' },
      teal: { 400: '#3DBDB5', 600: '#0F7D76' },
      sun: { 400: '#F6B73C' }, coral: { 400: '#F2877B' },
      star: '#F5B301', success: '#1F9D61', warning: '#C98A0B', danger: '#D64545',
    },
    borderRadius: { card: '20px', media: '16px', field: '14px' },
    boxShadow: {
      card: '0 8px 24px rgba(63,103,184,0.10)',
      float: '0 12px 40px rgba(63,103,184,0.16)',
    },
  },
}
```

## 5. Komponen

### 5.1 Navbar
Putih, tinggi 72px, menempel di atas (sticky) dengan bayangan sangat tipis saat digulir. Kiri logo, tengah menu, kanan ikon cari dan satu tombol utama. Di mobile menu menjadi panel geser dengan tombol buka dan tutup yang jelas.

### 5.2 Hero dengan kolom pencarian
- Judul 2 baris rata tengah, di bawahnya satu kalimat pendukung pendek.
- **Kolom pencarian pil** lebar (maks. 720px): ikon di kiri, input, pemilih kategori (dropdown kecil), dan **tombol bulat kuning 52px** berikon pencarian (dengan `aria-label="Cari"`).
- Di bawahnya baris **ikon kategori** (garis tipis, `blue-700`, di dalam lingkaran `blue-100`).
- Di mobile kolom pencarian tetap pil satu baris, pemilih kategori pindah ke bawah.

### 5.3 Strip kategori kaca
Panel kaca berisi 5-6 kategori. Satu kategori yang sedang dipilih diberi latar `blue-100` dan garis bawah `blue-700`. Di mobile berubah menjadi baris yang bisa digeser horizontal.

### 5.4 Kartu barang (komponen utama)

Anatomi dari atas ke bawah:

1. Gambar foto barang, rasio 4:5, sudut `media`, latar pastel bergantian bila foto transparan.
2. **Lencana kiri atas pada gambar:** "Terverifikasi KTM" (lihat 5.5), muncul hanya jika pemilik terverifikasi.
3. Nama barang (maks. 2 baris), bobot 600.
4. Harga: **"Rp75.000 / hari"** (angka bobot 700, "/ hari" lebih redup).
5. Baris meta: bintang kuning + rating + jumlah ulasan, serta area pengambilan (misalnya "Gedung A").
6. Pemilik kecil: avatar 24px, nama, dan **skor kepercayaan** (angka kecil).

Grid: 2 kolom (mobile), 3 (tablet), 4-5 (desktop). Jarak antarkartu 20px. Kartu seluruhnya bisa diklik, dengan fokus keyboard yang jelas.

### 5.5 Lencana khas Collective Campus (elemen yang harus paling diingat)

- **Lencana "Terverifikasi KTM":** pil kecil, ikon perisai-centang, latar `teal-600`, teks putih 12px bobot 600. Konsisten di kartu, detail barang, profil, dan dashboard. Ini ciri utama produk, jadi perlakuannya harus identik di mana pun.
- **Cincin skor kepercayaan:** lingkaran progres 0-100 dengan angka di tengah. Warna: `success` (70+), `warning` (40-69), `danger` (di bawah 40). Label teks selalu menyertai warna ("Tepercaya", "Cukup", "Perlu hati-hati"), jangan mengandalkan warna saja. Pengguna baru: label "Pengguna baru" berwarna `ink-muted`.

### 5.6 Tombol
- **Utama:** latar `teal-600`, teks putih, pil, tinggi 44-48px, bobot 500.
- **Aksen (pencarian):** bulat, `sun-400`, ikon `ink`.
- **Sekunder:** putih, border `blue-300`, teks `ink`.
- **Bahaya:** latar `danger` hanya untuk tindakan seperti batalkan atau tolak.
- Teks tombol menyebutkan hasilnya: "Ajukan sewa", "Bayar sekarang", "Konfirmasi barang diterima", "Unggah KTM". Hindari "Submit" dan "OK".

### 5.7 Formulir
Label di atas input, input tinggi 48px, sudut `field`, border `blue-300`, fokus `blue-700` dengan cincin 3px. Pesan error di bawah input, berwarna `danger`, menjelaskan masalah dan cara memperbaikinya. Unggah file memakai area tarik-dan-lepas dengan pratinjau gambar.

### 5.8 Stepper verifikasi KTM
Tiga langkah (urutan nyata, jadi penomoran layak dipakai): **1 Data diri, 2 Unggah KTM, 3 Menunggu tinjauan.** Tampilkan petunjuk foto: "Foto tegak, terang, tulisan terbaca, tanpa pantulan cahaya." Setelah unggah, tampilkan status dan hasil bacaan otomatis (NIM dan nama terbaca) agar pengguna bisa memperbaiki bila salah.

### 5.9 Timeline status sewa
Garis vertikal (mobile) atau horizontal (desktop) dengan titik status: Diajukan, Disetujui, Dibayar, Diserahkan, Dikembalikan, Selesai. Langkah selesai berwarna `success`, langkah aktif `blue-700`, langkah berikutnya abu-abu. Di bawah timeline ada **kartu aksi** yang hanya memuat tombol yang boleh ditekan pengguna saat ini.

### 5.10 Kartu ringkasan harga (detail barang dan pembayaran)
Baris: Sewa (harga x hari), Deposit (dikembalikan setelah barang aman), Proteksi (opsional, saklar), **Total bayar**. Tulis catatan singkat: "Deposit ditahan platform dan dikembalikan setelah barang kembali dengan aman."

### 5.11 Foto kondisi sebelum dan sesudah
Dua kolom berdampingan dengan keterangan "Sebelum sewa" dan "Setelah sewa", masing-masing galeri kecil. Jika belum ada foto, tampilkan keadaan kosong yang menyuruh mengunggah.

### 5.12 Kalender ketersediaan
Pemilih rentang tanggal. Tanggal tidak tersedia berwarna abu-abu dan dicoret, rentang terpilih memakai `blue-100` dengan ujung `blue-700`.

### 5.13 Lainnya
Toast konfirmasi (muncul sebagai respons tindakan, hilang sendiri), tabel dashboard dengan baris yang padat tapi terbaca, chip filter, paginasi sederhana, dan modal konfirmasi untuk tindakan yang tidak bisa dibatalkan.

## 6. Tata letak halaman

### 6.1 Beranda

```
[bilah atas tipis]
[navbar: logo | menu | cari | Pasang barang]
┌──────────────────────────────────────────────┐
│   (bentuk 3D kiri)    JUDUL HERO    (bentuk  │
│                       2 baris        3D kanan)│
│         ( ikon cari | kolom pencarian | (cari) )│
│            ikon kategori x4-6 (garis tipis)  │
│  (balok warna kiri bawah)                    │
└──────────────────────────────────────────────┘
[strip kategori kaca: 5-6 ikon]
[judul seksi "Cara kerja": 3 langkah ringkas dengan ikon]
[Barang populer ........................ Lihat semua]
[grid kartu 5 x 2]
[seksi kepercayaan: lencana KTM, deposit, foto kondisi, skor]
[footer 4 kolom]
```

Seksi "Cara kerja" dan seksi kepercayaan menonjolkan **tiga pembeda produk** (verifikasi KTM, deposit, foto kondisi dan skor). Gunakan penomoran hanya di "Cara kerja" karena itu memang urutan langkah.

### 6.2 Detail barang
Galeri besar di kiri, kolom kanan berisi judul, harga, lencana, pemilih tanggal, kartu ringkasan harga, dan tombol "Ajukan sewa" (lengket di bawah pada mobile). Di bawahnya: deskripsi, kondisi, area pengambilan, profil pemilik (lencana KTM dan cincin skor), dan ulasan.

### 6.3 Detail sewa
Timeline status di atas, kartu aksi, ringkasan biaya, foto kondisi sebelum dan sesudah berdampingan, serta kontak WhatsApp **hanya setelah pembayaran berhasil**.

### 6.4 Dashboard
Kartu ringkas di atas (status KTM, skor kepercayaan + 3 faktor penjelasnya, pendapatan simulasi), lalu tab "Sewa saya", "Permintaan masuk", dan "Barang saya".

### 6.5 Verifikasi KTM
Stepper di atas, area unggah, petunjuk foto, dan status.

### 6.6 Admin
Pakai Django admin dengan tema bawaan yang dirapikan (judul "Collective Admin", warna `blue-700`). Tidak perlu meniru hero. Pastikan antrean KTM mudah dipindai.

## 7. Dekorasi 3D (aksen, bukan fondasi)

Dekorasi 3D adalah **gambar atau bentuk CSS/SVG**, bukan kode inti. Kerjakan **setelah** halaman berfungsi.

- Buat 3-5 bentuk: lengkung biru, bentuk gerbang, bintang kecil, tumpukan balok warna. Gunakan **gradien dan blur CSS/SVG** atau ilustrasi 3D gratis dengan lisensi yang jelas (catat sumber dan lisensinya di `docs/DECISIONS.md`).
- Simpan di `static/img/deco/`, format WebP atau SVG, masing-masing di bawah 150 KB.
- Pasang dengan `position: absolute`, `aria-hidden="true"`, `pointer-events: none`, dan `loading="lazy"` untuk yang di luar layar pertama.
- Di mobile tampilkan paling banyak **2 bentuk**, dan jangan pernah menutupi teks atau kolom pencarian.
- Jangan menyalin ilustrasi dari gambar referensi.

## 8. Gerak (motion)

- Satu momen gerak: **dua bentuk dekorasi hero mengapung sangat pelan** (amplitudo kecil, siklus lama). Sisanya diam.
- Respons terhadap tindakan diperbolehkan: toast muncul, panel dibuka, hasil pencarian diganti (HTMX) dengan transisi singkat.
- Hover kartu: bayangan sedikit menguat. Jangan memberi animasi muncul (fade/slide) pada setiap seksi.
- Hormati `prefers-reduced-motion`: matikan gerak dekorasi sepenuhnya.

## 9. Responsif dan aksesibilitas

- **Mobile dulu.** Titik henti: `sm 640`, `md 768`, `lg 1024`, `xl 1280`.
- Target sentuh minimal **44x44 px**.
- Fokus keyboard selalu terlihat (cincin `blue-700` 3px dengan offset).
- Semua gambar punya `alt` bermakna (foto barang: nama barang). Dekorasi memakai `aria-hidden`.
- Status tidak boleh hanya berupa warna: sertakan teks atau ikon.
- Gunakan elemen HTML semantik (`header`, `nav`, `main`, `section`, `footer`, `button`, `a`).
- Form punya label yang terhubung dan pesan error yang dibacakan (`aria-live`).

## 10. Gaya bahasa (microcopy)

Nada: ramah, jelas, singkat, kalimat aktif, sentence case, pakai kata sehari-hari. Beri nama hal menurut cara pengguna memahaminya, bukan menurut cara sistem dibuat.

| Konteks | Contoh |
|---|---|
| Judul hero | Sewa barang kampus, aman dan terverifikasi |
| Placeholder pencarian | Cari kamera, toga, atau proyektor |
| Tombol | Ajukan sewa / Bayar sekarang / Unggah KTM |
| Keadaan kosong (katalog) | Belum ada barang yang cocok. Coba ubah kata kunci atau kategori. |
| Keadaan kosong (dashboard) | Belum ada sewa. Jelajahi barang untuk memulai. |
| Error unggah | Foto KTM belum terbaca. Coba foto lebih terang dan pastikan tulisan tidak terpantul cahaya. |
| Error akses | Verifikasi KTM dulu untuk memasang barang atau menyewa. |
| Toast sukses | Permintaan sewa terkirim. Pemilik akan menjawab dalam 24 jam. |
| Penjelasan deposit | Deposit ditahan platform dan dikembalikan setelah barang kembali dengan aman. |

Hindari: label huruf kapital semua, titik tengah sebagai pemisah metadata, tanda panah pada tombol, kalimat promosi berlebihan, dan permintaan maaf pada pesan error.

## 11. Catatan implementasi (Django)

- Tampilan: **Django Templates + Tailwind**. Struktur: `templates/base.html` (navbar, footer, slot konten) dan komponen di `templates/partials/` (`item_card.html`, `trust_ring.html`, `ktm_badge.html`, `status_timeline.html`, `price_summary.html`, `toast.html`).
- Pencarian dan filter memakai **HTMX**: formulir mengirim `hx-get` ke `/barang/hasil/` dan mengganti `#hasil-grid` dengan partial `item_grid.html`.
- Interaksi kecil (menu mobile, dropdown, saklar proteksi) memakai **Alpine.js**.
- Jalankan Tailwind dengan CLI atau `django-tailwind`. Jangan memuat CDN Tailwind di versi akhir.
- Font dan ikon: Poppins, dan satu set ikon garis (misalnya Lucide) yang dipakai konsisten.

## 12. Daftar periksa sebelum selesai

- [ ] Beranda terlihat sepaham dengan referensi: hero + kolom pencarian pil, ikon kategori, strip kaca, grid kartu, footer 4 kolom.
- [ ] Tidak ada aset, teks, atau ilustrasi yang disalin dari referensi.
- [ ] Lencana Terverifikasi KTM dan cincin skor tampil konsisten di semua tempat.
- [ ] Semua teks dalam Bahasa Indonesia dan mengikuti gaya bahasa di bagian 10.
- [ ] Kontras teks lolos 4,5:1, fokus keyboard terlihat, `prefers-reduced-motion` dihormati.
- [ ] Tampilan rapi di lebar 360px dan 1280px.
- [ ] Dekorasi tidak menutupi teks atau mengganggu pencarian, dan ukuran gambar dioptimalkan.
