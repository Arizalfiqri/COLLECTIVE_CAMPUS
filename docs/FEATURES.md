# Katalog Fitur Lengkap Collective Campus (v2.0)

Dokumen ini memuat katalog komprehensif seluruh fitur yang tersedia pada platform **Collective Campus**, mencakup **Modul Sewa-Menyewa (Rental)** dan **Modul Jual-Beli (Thrift)** antarmahasiswa berbasis Django 5 dan Machine Learning terkalibrasi.

---

## 1. Modul Inti & Autentikasi Pengguna

| Fitur | Deskripsi | Status |
|---|---|---|
| **Pendaftaran & Autentikasi** | Akun mahasiswa terisolasi dengan pembatasan domain kampus resmi (`.ac.id`), verifikasi kode OTP/email, dan reset kata sandi mandiri. | Aktif |
| **Verifikasi KTM Digital** | Pengunggahan foto Kartu Tanda Mahasiswa (KTM) yang disimpan di direktori privat (`private_media/`), ditinjau oleh staf kampus, dan berkas foto otomatis dibersihkan permanen setelah diverifikasi demi kepatuhan UU PDP No. 27/2022. | Aktif |
| **Profil Mahasiswa** | Profil publik menampilkan inisial nama, nama universitas, status verifikasi KTM, tingkat reputasi penjual/penyewa, skor kepercayaan (TrustScore), barang sewa aktif, barang jualan aktif, serta rekapitulasi ulasan yang diterima. | Aktif |
| **Dasbor Pengguna** | Dasbor terpadu 4 kartu ringkasan: Sewa aktif, Penyewaan barang saya, Saldo dompet, dan Ringkasan penjualan saya (total terjual, pendapatan bersih, pesanan aktif). Dilengkapi tab filter riwayat transaksi. | Aktif |
| **Dompet Internal (Wallet)** | Pencatatan saldo internal pengguna dengan prinsip buku besar berimbang (*double-entry ledger*). Mendukung penarikan dana ke rekening bank mahasiswa dengan enkripsi rekening. | Aktif |
| **Pesan Langsung (Chat)** | Komunikasi internal antarmahasiswa per barang sewa maupun barang jualan tanpa membocorkan nomor telepon pribadi sebelum kesepakatan jadwal temu. | Aktif |
| **Notifikasi Real-Time** | Notifikasi dalam aplikasi (*in-app notification*) untuk setiap pembaruan status transaksi, batas waktu pembayaran, persetujuan jadwal temu, hasil sengketa, dan ulasan. | Aktif |

---

## 2. Modul Sewa-Menyewa (Rental)

| Fitur | Deskripsi | Status |
|---|---|---|
| **Katalog Sewa Multi-Kampus** | Pencarian teks instan, filter kategori (Kamera, Praktikum, Wisuda, Camping, Proyektor, Kostum, Laptop, Lain-lain), filter kampus mahasiswa, dan pengurutan harga/reputasi. | Aktif |
| **Kalender Ketersediaan & Booking** | Pemilihan rentang tanggal sewa dengan kalkulator biaya transparan dan pencegahan bentrok sewa ganda (*anti double-booking*) berbasis transaksi atomik database (`select_for_update`). | Aktif |
| **Perjanjian Sewa Digital (S&K)** | Penandatanganan digital syarat & ketentuan sewa dengan pencatatan nomor versi, hash SHA-256 teks perjanjian, alamat IP, dan user-agent peramban pada database. | Aktif |
| **Escrow & Pembayaran Midtrans** | Penahanan dana sewa pada rekening escrow platform via Midtrans Snap. Dana baru dicairkan ke pemilik setelah barang dikembalikan dan diverifikasi. | Aktif |
| **Dokumentasi Serah Terima** | Pengunggahan foto kondisi fisik barang sebelum dipakai (saat serah terima awal) dan sesudah dipakai (saat pengembalian) di titik temu kampus yang ramai. Berkas foto privat dihapus berkala pascatransaksi selesai. | Aktif |
| **Penyelesaian & Pencairan Dana** | Pemilik memverifikasi pengembalian barang, saldo sewa diteruskan otomatis ke dompet pemilik. | Aktif |
| **Tagihan Tambahan (ExtraCharge)** | Penagihan resmi denda keterlambatan pengembalian harian, ganti rugi kerusakan fisik, atau kehilangan barang tanpa memotong saldo sepihak. Pengguna dengan tagihan terutang dibatasi dari transaksi baru. | Aktif |
| **Sengketa Sewa (Dispute)** | Mediasi sengketa oleh admin kampus dengan telaah foto kondisi sebelum-sesudah dan jejak pesan. | Aktif |
| **Ulasan Sewa** | Penilaian bintang 1–5 dan ulasan tekstual antara penyewa dan pemilik setelah transaksi selesai. | Aktif |
| **Dana Gotong Royong** | Rekening cadangan internal platform untuk menanggung risiko sengketa dan melindungi pemilik barang dari kerugian tak terduga. | Aktif |
| **Machine Learning TrustScore** | Model probabilistik terkalibrasi (*Logistic Regression + Platt Scaling*) untuk menilai risiko perilaku sewa mahasiswa tanpa menggunakan atribut demografis sensitif. Dilengkapi dasbor pemantauan dan simulator staf di `/admin/model-skor/`. | Aktif |

---

## 3. Modul Jual-Beli Barang Bekas Kampus (Thrift)

| Fitur | Deskripsi | Status |
|---|---|---|
| **Listing Barang Jual Beli** | Pemasangan iklan barang perlengkapan kuliah bekas (buku teks, alat praktikum, kalkulator, elektronik, dll.) lengkap dengan kondisi fisik (*baru segel, seperti baru, baik, cukup, ada cacat*), minus/cacat, kelengkapan bawaan, alasan dijual, harga beli asli, dan titik temu kampus. | Aktif |
| **Batas Harga Berbasis Reputasi** | Batas maksimal harga barang yang boleh dijual disesuaikan dengan tingkat reputasi penjual: Penjual Baru (Rp1.000.000), Penjual Tepercaya (Rp3.000.000), dan Penjual Sangat Tepercaya (Rp8.000.000) guna memitigasi penipuan bernilai tinggi. | Aktif |
| **Penyaringan Barang Terlarang** | Filter kata kunci otomatis (*prohibited keywords*) pada tingkat form dan model untuk mencegah penjualan obat keras, alkohol, rokok/vape, senjata tajam/api, satwa, makanan basah, barang bajakan/curian, dan akun digital. | Aktif |
| **Masa Tayang & Perpanjangan Listing** | Masa tayang listing ditetapkan 60 hari. Penjual dapat memperpanjang masa tayang 60 hari tambahan atau mengubah status menjadi nonaktif kapan saja. | Aktif |
| **Katalog Jual Beli Mandiri** | Antarmuka khusus `/jual-beli/` dengan filter kampus, kategori, kondisi fisik, rentang harga, dan pengurutan dinamis (*terbaru, harga termurah, harga termahal, paling hemat*). | Aktif |
| **Snapshot Listing Beku** | Saat pembeli membuat pesanan, sistem secara otomatis membekukan snapshot seluruh rincian barang (judul, deskripsi, kondisi, harga, kelengkapan, foto beserta hash SHA-256) sehingga penjual tidak dapat mengubah rincian barang pascapemesanan. | Aktif |
| **Persetujuan S&K Pembeli Digital** | Pembeli wajib menyetujui Syarat & Ketentuan Jual Beli digital sebelum pembayaran. Hash SHA-256, stempel waktu, IP address, dan user agent tersimpan pada model `SaleAgreement`. | Aktif |
| **Escrow Jual Beli & Komisi Platform** | Pembayaran ditampung di escrow Midtrans dengan batas waktu bayar 6 jam. Platform memotong komisi 5% (minimum Rp2.000) untuk operasional dan Dana Gotong Royong; sisa dana (*net to seller*) ditahan hingga transaksi tuntas. | Aktif |
| **Jadwal & Titik Temu Kampus** | Penjual dan pembeli menyepakati titik temu aman di area kampus ramai dan tanggal pertemuan dalam batas waktu maksimal 7 hari. | Aktif |
| **Serah Terima Fisik Langsung** | Serah terima dilakukan langsung secara tatap muka dengan pengunggahan foto fisik barang saat diserahkan sebagai bukti valid serah terima. | Aktif |
| **Masa Inspeksi 48 Jam** | Pembeli memiliki waktu 48 jam sejak serah terima untuk memeriksa kesesuaian barang. Pembeli dapat mengonfirmasi terima secara manual untuk langsung mencairkan dana ke penjual, atau sistem akan melepaskan dana otomatis setelah 48 jam jika tidak ada sanggahan. | Aktif |
| **Pembatalan & Pengembalian Dana** | Pesanan yang belum diserahterimakan dapat dibatalkan oleh pembeli atau penjual dengan pengembalian saldo 100% secara instan ke dompet pembeli. | Aktif |
| **Sistem Sengketa Jual Beli (`SaleDispute`)** | Pembeli dapat mengajukan sengketa selama masa inspeksi 48 jam jika barang rusak atau tidak sesuai deskripsi. Panel admin dilengkapi perbandingan snapshot vs foto sengketa, transkrip chat, dan opsi putusan: lepas ke penjual, refund penuh ke pembeli, atau split/potongan sebagian. | Aktif |
| **Penalti Reputasi Penjual** | Sengketa yang diputuskan merugikan pembeli atau tercatat pelanggaran penjual akan menurunkan tingkat reputasi penjual kembali ke status 'baru' dan membatasi harga jual maksimal. | Aktif |
| **Ulasan Dua Arah (`SaleReview`)** | Pembeli dan penjual dapat saling memberikan rating 1–5 bintang dan komentar maksimal 300 karakter setelah pesanan selesai. | Aktif |
| **Reputasi Penjual Terpadu (`get_seller_tier`)** | Evaluasi otomatis reputasi penjual menggabungkan penjualan selesai, rekam jejak tanpa sengketa, dan rata-rata rating ulasan dari modul sewa dan jual beli. Lencana reputasi tampil konsisten pada kartu, detail barang, dan profil publik. | Aktif |
| **Moderasi & Pelaporan Listing (`SaleItemReport`)** | Tombol "Laporkan listing" pada halaman detail barang dengan 6 kategori alasan. Moderator platform dapat meninjau antrean laporan dan menurunkan barang (*takedown*) dengan alasan wajib yang ternotifikasi ke penjual. | Aktif |
| **Tawar Harga Terstruktur (`SaleOffer`)** | Fitur penawaran harga terstruktur yang dikendalikan saklar `SALE_OFFERS_ENABLED` (bawaan: dinonaktifkan). Jika diaktifkan, calon pembeli dapat mengajukan tawaran berlaku 24 jam; jika diterima penjual, pesanan langsung terbentuk pada harga yang disepakati dengan batas bayar 6 jam. | Aktif (Opsional Saklar) |

---

## 4. Administrasi & Keamanan Operasional

| Fitur | Deskripsi | Status |
|---|---|---|
| **Antrean Operasional Admin Terpadu** | Widget operasional pada dashboard admin menampilkan jumlah antrean verifikasi KTM pending, antrean penarikan dana pending, sengketa sewa pending, sengketa jual beli pending, dan laporan listing pending. | Aktif |
| **Rekonsiliasi Buku Besar** | Audit periodik kesesuaian saldo dompet seluruh pengguna dengan arus kas masuk-keluar di buku besar (*double-entry ledger*). | Aktif |
| **Audit Jejak Keamanan & Log** | Pencatatan log autentikasi, akses media privat, perubahan status pesanan, dan putusan sengketa untuk transparansi audit internal. | Aktif |
| **Pembersihan Berkas Privat Otomatis** | Command berkala `purge_handover_photos` untuk menghapus foto fisik serah terima dan foto KTM yang masa retensinya telah lewat demi meminimalkan paparan data pribadi. | Aktif |
