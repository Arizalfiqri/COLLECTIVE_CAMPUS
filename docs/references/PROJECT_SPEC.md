# Collective Campus: Spesifikasi Proyek

> Dokumen ini adalah sumber kebenaran untuk struktur, alur bisnis, dan logika platform **Collective Campus**. Untuk tampilan, baca juga `design.md`.

## 0. Cara membaca dokumen ini

- Dokumen ini ditujukan untuk pengembang dan AI agent. Ikuti stack, struktur folder, nama model, dan aturan bisnis di sini.
- Semua angka (komisi, denda, batas waktu) adalah **nilai awal yang bisa diubah** lewat `.env` atau `settings.py`. Jangan menulisnya langsung (hardcode) di banyak tempat.
- Seluruh teks antarmuka memakai **Bahasa Indonesia**.
- Jika ada hal yang tidak jelas, pilih opsi paling sederhana yang sesuai dokumen ini, lalu catat di `docs/DECISIONS.md`.
- Jangan menambah fitur di luar bagian "Lingkup MVP" tanpa persetujuan.

## 1. Ringkasan produk

**Collective Campus** adalah platform sewa-menyewa dan jual-beli barang antarmahasiswa. Mahasiswa yang punya barang jarang terpakai (kamera, proyektor, toga, perlengkapan camping, alat praktikum, kostum) dapat menyewakannya. Mahasiswa lain bisa menyewa untuk keperluan sesaat dengan harga jauh lebih murah daripada membeli.

**Masalah:** barang untuk keperluan sesaat (acara, wisuda, tugas, pendakian) mahal bila dibeli, dan meminjam ke orang asing berisiko (barang rusak, hilang, telat kembali, penipuan).

**Tiga pembeda utama (harus tampil jelas di demo):**

1. **Verifikasi KTM:** hanya mahasiswa terverifikasi yang boleh memasang barang dan menyewa. Unggahan KTM dibaca otomatis dengan OCR, lalu ditinjau admin.
2. **Deposit dan escrow:** uang sewa dan deposit ditahan platform (disimulasikan), lalu dirilis setelah barang kembali dengan aman.
3. **Bukti kondisi dan skor kepercayaan:** foto kondisi barang sebelum dan sesudah sewa, serta skor kepercayaan pengguna yang dihitung dengan machine learning.

**Model bisnis:** komisi dari biaya sewa, biaya proteksi opsional, dan (rencana lanjutan) listing unggulan serta langganan untuk pemilik dengan banyak barang.

## 2. Konteks lomba dan kriteria sukses

- Lomba web development bertema Technopreneurship, **individu**, waktu pengerjaan **15 hari**, dijalankan di **localhost**.
- Yang dinilai: masalah jelas, model bisnis jelas, prototipe berjalan dari ujung ke ujung, ada keunikan, dan ada integrasi machine learning (juri berlatar ML dengan Python).
- **Kriteria sukses:** satu alur utama berjalan penuh tanpa error: *daftar, verifikasi KTM, pasang barang, cari, ajukan sewa, bayar (Midtrans Sandbox), serah terima dengan foto, pengembalian, deposit dirilis, ulasan, skor kepercayaan diperbarui*.
- Tidak harus 100% lengkap. Prioritaskan alur utama dan tiga pembeda di atas.

## 3. Peran pengguna dan hak akses

Satu akun bisa menjadi **pemilik** (memasang barang) sekaligus **penyewa** (menyewa barang orang lain). Tidak ada akun terpisah.

| Peran | Hak |
|---|---|
| Pengunjung (belum login) | Melihat beranda, katalog, detail barang, profil publik, halaman bantuan |
| Mahasiswa belum terverifikasi | Daftar, login, unggah KTM, lihat dashboard, **tidak bisa** memasang barang atau mengajukan sewa |
| Mahasiswa terverifikasi | Semua hak mahasiswa, ditambah memasang barang, mengajukan sewa, membayar, mengunggah foto kondisi, memberi ulasan |
| Admin | Meninjau KTM, memutuskan sengketa, menonaktifkan barang atau pengguna, melihat ringkasan keuangan platform |

Aturan: setiap view yang mengubah data wajib memeriksa **kepemilikan objek** (cegah akses ke data milik orang lain).

## 4. Stack dan lingkungan

| Bagian | Pilihan |
|---|---|
| Bahasa dan framework | Python 3.11+ dan Django 5.x |
| Database | PostgreSQL lokal (cadangan: SQLite lewat `DATABASE_URL`) |
| Tampilan | Django Templates, Tailwind CSS, HTMX, Alpine.js |
| Pembayaran | Midtrans **Snap Sandbox** lewat library Python `midtransclient` (cek nama paket di dokumentasi resmi Midtrans) |
| OCR KTM | `pytesseract` + Tesseract (bahasa `ind` dan `eng`), cadangan EasyOCR |
| Machine learning | `scikit-learn`, `pandas`, `numpy`, `joblib` |
| Gambar | `Pillow` |
| Konfigurasi | `django-environ` atau `python-decouple`, file `.env` |

Semua berjalan di **localhost**. Webhook Midtrans tidak bisa menjangkau localhost, jadi status pembayaran dicek ke API Midtrans dari server (lihat bagian 9.3).

Contoh `.env.example`:

```
SECRET_KEY=ganti-ini
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=postgresql://postgres:PASSWORD@localhost:5432/kampusrent
MIDTRANS_SERVER_KEY=isi-dari-dashboard-sandbox
MIDTRANS_CLIENT_KEY=isi-dari-dashboard-sandbox
MIDTRANS_IS_PRODUCTION=False
TESSERACT_CMD=
KTM_AUTO_APPROVE=False
KTM_DELETE_AFTER_DECISION=True
PLATFORM_COMMISSION_PERCENT=8
PROTECTION_FEE=3000
LATE_FEE_PERCENT_PER_DAY=50
APPROVAL_DEADLINE_HOURS=24
PAYMENT_DEADLINE_HOURS=6
AUTO_CONFIRM_RETURN_HOURS=48
```

## 5. Struktur proyek

```
kampusrent/
├── manage.py
├── config/                  # settings, urls, wsgi/asgi
├── apps/
│   ├── core/                # beranda, halaman statis, pencarian
│   ├── accounts/            # User, StudentProfile, login/daftar, profil publik
│   ├── verification/        # KtmVerification, OCR, antrean admin
│   ├── catalog/             # Category, Item, ItemPhoto
│   ├── rentals/             # Rental, ConditionPhoto, Review, Dispute, state machine
│   ├── payments/            # Payment, DepositHold, Payout, LedgerEntry, Midtrans
│   └── trust/               # TrustScore, pemuat model ML
├── ml/
│   ├── generate_synthetic_data.py
│   ├── train_trust_model.py
│   ├── ktm_ocr.py
│   ├── data/                # CSV sintetis
│   └── artifacts/           # trust_model.joblib, metrics.json
├── templates/               # base.html, partials/, per aplikasi
├── static/                  # css, js, img (termasuk img/deco/)
├── media/                   # foto barang dan foto kondisi (publik terbatas)
├── private_media/           # gambar KTM (TIDAK pernah dilayani publik)
├── docs/
│   ├── reference/           # gambar referensi desain
│   └── DECISIONS.md
├── tests/
├── requirements.txt
├── .env.example
├── PROJECT_SPEC.md
└── design.md
```

## 6. Model data

Semua nilai uang disimpan sebagai **bilangan bulat rupiah** (tanpa desimal). Semua tabel punya `created_at` dan `updated_at`.

### accounts
- **User** (turunan `AbstractUser`): `email` (unik), `full_name`, `phone_whatsapp`, `avatar`, `is_verified_student` (bool).
- **StudentProfile** (1-1 ke User): `nim`, `campus_name`, `major`, `entry_year`, `student_status` (`aktif`/`lulus`).

### verification
- **KtmVerification**: `user`, `ktm_image` (path privat), `ocr_text`, `ocr_nim`, `ocr_name`, `ocr_campus`, `nim_match` (bool), `name_similarity` (0-100), `campus_match` (bool), `quality_score` (0-100), `match_score` (0-100), `recommendation` (`setuju`/`tinjau`/`tolak`), `status` (`menunggu`/`perlu_tinjauan`/`disetujui`/`ditolak`), `reviewed_by`, `reviewed_at`, `admin_note`, `image_deleted_at`.

### catalog
- **Category**: `name`, `slug`, `icon`, `order`.
- **Item**: `owner`, `category`, `title`, `slug`, `description`, `condition` (`sangat_baik`/`baik`/`cukup`), `estimated_value`, `price_per_day`, `deposit_amount`, `min_days`, `max_days`, `pickup_area` (teks area kampus), `is_active`.
- **ItemPhoto**: `item`, `image`, `order`.

### rentals
- **Rental**: `code` (kode pendek unik), `item`, `renter`, `owner`, `start_date`, `end_date`, `days`, `price_per_day_snapshot`, `rent_total`, `deposit_total`, `protection_fee`, `grand_total`, `use_protection` (bool), `status`, `handed_over_owner_at`, `handed_over_renter_at`, `return_requested_at`, `returned_date`, `late_days`, `late_fee`, `damage_fee`, `cancelled_by`, `cancel_reason`, `note`.
- **ConditionPhoto**: `rental`, `uploaded_by`, `phase` (`sebelum`/`sesudah`), `image`, `note`.
- **Review**: `rental`, `reviewer`, `reviewee`, `as_role` (`pemilik`/`penyewa`), `rating` (1-5), `comment`. Unik per (`rental`, `reviewer`).
- **Dispute**: `rental`, `opened_by`, `reason`, `evidence_note`, `status` (`terbuka`/`diputuskan`), `decision` (`kembalikan_penuh`/`potong_sebagian`/`potong_penuh`), `deduction_amount`, `decided_by`, `decision_note`.

### payments
- **Payment**: `rental`, `order_id` (unik), `gross_amount`, `snap_token`, `status` (`pending`/`settlement`/`expire`/`cancel`/`deny`), `payment_type`, `transaction_id`, `paid_at`, `raw_response` (JSON).
- **DepositHold** (1-1 ke Rental): `amount`, `status` (`ditahan`/`dirilis`/`dipotong_sebagian`/`dipotong_penuh`), `released_amount`, `deducted_amount`, `reason`, `released_at`.
- **Payout** (simulasi, 1-1 ke Rental): `owner`, `gross_rent`, `commission`, `net_amount`, `status` (`menunggu`/`dicairkan_simulasi`), `paid_at`.
- **LedgerEntry**: `rental`, `kind`, `amount`, `note`. Buku besar escrow sebagai bukti audit (lihat 9.4).

### trust
- **TrustScore** (1-1 ke User): `score` (0-100), `risk_probability`, `is_new_user` (bool), `features` (JSON), `top_factors` (JSON), `model_version`, `computed_at`.

### core
- **Notification** (sederhana, opsional): `user`, `message`, `url`, `is_read`.

## 7. Aturan bisnis dan perhitungan

### 7.1 Tarif dan biaya (nilai awal)

| Aturan | Nilai awal |
|---|---|
| Komisi platform | 8% dari `rent_total`, dipotong dari bagian pemilik |
| Biaya proteksi (opsional, dibayar penyewa) | Rp3.000 per sewa, menjadi pendapatan platform |
| Denda keterlambatan | 50% dari harga sewa harian per hari terlambat, diambil dari deposit, diteruskan ke pemilik |
| Batas persetujuan pemilik | 24 jam, lewat itu menjadi `kedaluwarsa` |
| Batas pembayaran penyewa | 6 jam setelah disetujui, lewat itu menjadi `kedaluwarsa` |
| Konfirmasi pengembalian otomatis | 48 jam jika pemilik tidak merespons |
| Deposit minimum | 20% dari `estimated_value` (sistem menyarankan 20-30%) |
| Deposit untuk skor kepercayaan < 40 | Deposit minimum dikalikan 1,5 |

### 7.2 Rumus

```
days            = (end_date - start_date).days + 1          # tanggal akhir ikut dihitung
rent_total      = price_per_day * days
protection_fee  = PROTECTION_FEE jika use_protection, selain itu 0
grand_total     = rent_total + deposit_total + protection_fee
commission      = round(rent_total * 8 / 100)
owner_net       = rent_total - commission
late_days       = max(0, (returned_date - end_date).days)
late_fee        = min(round(price_per_day * 0.5 * late_days), deposit_total)
deposit_refund  = deposit_total - late_fee - damage_fee     # tidak boleh negatif
platform_income = commission + protection_fee
```

**Contoh:** kamera Rp75.000/hari, 3 hari, deposit Rp500.000, dengan proteksi.
`rent_total` Rp225.000, `grand_total` Rp728.000, `commission` Rp18.000, `owner_net` Rp207.000, pendapatan platform Rp21.000.
Jika terlambat 1 hari: `late_fee` Rp37.500, deposit kembali Rp462.500, pemilik menerima tambahan Rp37.500.

### 7.3 Aturan umum

- Hanya akun **terverifikasi KTM** yang boleh memasang barang dan mengajukan sewa.
- Pemilik tidak boleh menyewa barangnya sendiri.
- Durasi sewa harus di antara `min_days` dan `max_days` barang.
- **Anti double-booking:** rentang tanggal tidak boleh bertabrakan dengan sewa lain berstatus `menunggu_pembayaran`, `dibayar`, `sedang_disewa`, `menunggu_konfirmasi_pengembalian`, atau `sengketa`. Cek ulang saat pemilik menyetujui dan saat pembayaran, di dalam `transaction.atomic()` dengan `select_for_update()`.
- **Kontak (WhatsApp) baru terlihat setelah pembayaran berhasil**, agar transaksi tetap lewat platform.
- **Pembatalan:**
  - Sebelum bayar: bebas biaya.
  - Setelah bayar, dibatalkan pemilik: refund penuh (sewa + deposit + proteksi).
  - Setelah bayar, dibatalkan penyewa lebih dari 24 jam sebelum mulai: refund penuh.
  - Setelah bayar, dibatalkan penyewa 24 jam atau kurang sebelum mulai: 20% dari `rent_total` menjadi hak pemilik, sisanya refund.
- Pengguna baru (kurang dari 3 sewa selesai) memakai skor awal 60 dengan label "Pengguna baru".

## 8. Alur bisnis end-to-end

### 8.1 Alur utama (ringkas)

1. Mahasiswa **mendaftar** dan **mengunggah KTM**.
2. Sistem membaca KTM dengan **OCR** dan memberi rekomendasi. **Admin** menyetujui atau menolak.
3. Mahasiswa terverifikasi **memasang barang** (foto, harga per hari, deposit).
4. Penyewa **mencari** barang, memilih tanggal, dan **mengajukan sewa**.
5. Pemilik **menyetujui** (atau menolak).
6. Penyewa **membayar** lewat Midtrans Sandbox. Dana sewa dan deposit **ditahan platform**.
7. Pemilik mengunggah **foto kondisi sebelum**, lalu kedua pihak mengonfirmasi **serah terima**.
8. Setelah masa sewa, penyewa menekan **dikembalikan** dan mengunggah **foto kondisi sesudah**.
9. Pemilik **mengonfirmasi** kondisi baik (atau melaporkan masalah).
10. Platform **merilis deposit** ke penyewa dan **mencairkan bagian pemilik** (simulasi), lalu mencatat komisi.
11. Kedua pihak saling **mengulas**. **Skor kepercayaan** dihitung ulang.

### 8.2 Status sewa (state machine)

| Status | Arti | Dipicu oleh | Status berikutnya |
|---|---|---|---|
| `menunggu_persetujuan` | Permintaan dikirim | Penyewa | `menunggu_pembayaran`, `ditolak`, `dibatalkan`, `kedaluwarsa` |
| `menunggu_pembayaran` | Disetujui, menunggu bayar | Pemilik | `dibayar`, `dibatalkan`, `kedaluwarsa` |
| `dibayar` | Dana masuk dan ditahan | Sistem (setelah cek status Midtrans) | `sedang_disewa`, `dibatalkan` |
| `sedang_disewa` | Serah terima dikonfirmasi kedua pihak | Pemilik dan penyewa | `menunggu_konfirmasi_pengembalian` |
| `menunggu_konfirmasi_pengembalian` | Penyewa melapor barang kembali | Penyewa | `selesai`, `sengketa` |
| `selesai` | Deposit dirilis, payout dicatat | Pemilik atau otomatis 48 jam | (akhir) |
| `sengketa` | Ada klaim kerusakan atau kehilangan | Pemilik | `selesai` (setelah keputusan admin) |
| `ditolak`, `dibatalkan`, `kedaluwarsa` | Berakhir tanpa transaksi atau dengan refund | Pemilik, penyewa, sistem | (akhir) |

Semua perpindahan status dilakukan lewat **satu modul state machine** (`apps/rentals/services.py`) yang memeriksa siapa yang boleh memicu dan dari status mana. Dilarang mengubah `status` langsung dari view.

### 8.3 Syarat serah terima dan pengembalian

- Serah terima baru bisa dikonfirmasi jika sudah ada **minimal 2 foto "sebelum"**.
- Pengembalian baru bisa diajukan jika sudah ada **minimal 2 foto "sesudah"**.
- Halaman detail sewa menampilkan foto sebelum dan sesudah **berdampingan** sebagai bukti.

## 9. Logika inti per modul

### 9.1 Verifikasi KTM (`verification`, `ml/ktm_ocr.py`)

1. **Unggah:** JPG/PNG maksimal 5 MB. Periksa tipe asli dengan Pillow, ganti nama file dengan UUID, simpan di `private_media/`.
2. **Pra-proses:** ubah ke grayscale, ubah ukuran, tingkatkan kontras.
3. **OCR:** `pytesseract` dengan bahasa `ind+eng`.
4. **Ekstraksi dan pencocokan:**
   - NIM: cari angka 8-15 digit dengan regex, bandingkan dengan NIM yang diketik pengguna (`nim_match`).
   - Nama: kemiripan teks (`difflib.SequenceMatcher` atau `rapidfuzz`) terhadap nama yang diketik (`name_similarity`).
   - Kampus: cari kata kunci "universitas", "institut", "politeknik", "sekolah tinggi", dan nama kampus yang diketik (`campus_match`).
   - Kualitas gambar: resolusi minimum dan keterbacaan (`quality_score`).
5. **Skor:** `match_score = 50 jika nim_match + 0,3 * name_similarity + 10 jika campus_match + 0,1 * quality_score`.
6. **Rekomendasi:** `>= 85` setuju, `60-84` tinjau, `< 60` tolak.
7. **Keputusan:** secara bawaan (`KTM_AUTO_APPROVE=False`) **admin yang memutuskan**, dan hasil OCR hanya menjadi rekomendasi untuk mempercepat peninjauan. Jika `KTM_AUTO_APPROVE=True`, rekomendasi "setuju" langsung menyetujui.
8. **Setelah keputusan final:** set `User.is_verified_student`, lalu hapus berkas gambar jika `KTM_DELETE_AFTER_DECISION=True` (catat `image_deleted_at`).
9. **Privasi:** gambar KTM hanya bisa dilihat admin lewat view terproteksi (header `Cache-Control: no-store`), tidak pernah lewat `MEDIA_URL`.

**Keterbatasan yang harus dinyatakan jujur di presentasi:** OCR hanya mencocokkan data yang diketik dengan isi gambar dan **tidak membuktikan keaslian** KTM. Karena itu admin tetap meninjau. Rencana lanjutan: verifikasi email kampus (`.ac.id`) dan validasi ke data resmi kampus.

### 9.2 Pencarian dan katalog (`catalog`, `core`)

- Filter: kata kunci (`icontains` pada judul dan deskripsi), kategori, rentang harga, kondisi, dan **tanggal tersedia** (barang yang tidak bertabrakan dengan sewa aktif).
- Urutan: terbaru, harga terendah, harga tertinggi, skor kepercayaan pemilik tertinggi.
- Hasil dimuat dengan **HTMX** (mengganti partial grid tanpa memuat ulang halaman).
- Detail barang menampilkan: galeri, harga per hari, deposit, kalender ketersediaan, profil pemilik (lencana KTM dan skor), ulasan, dan kartu ringkasan harga.

### 9.3 Pembayaran Midtrans Sandbox (`payments`)

Server key hanya ada di `.env` dan **tidak pernah** dikirim ke browser. Client key boleh ada di template.

**Alur:**

1. `POST /sewa/<kode>/bayar/`: buat `Payment` dengan `order_id` unik (misalnya `KR-<kode>-<nomor>`), lalu minta token Snap dengan `transaction_details` (`order_id`, `gross_amount = grand_total`), `item_details` (sewa, deposit, proteksi), dan `customer_details`. Simpan `snap_token`, kembalikan JSON.
2. Browser memanggil `snap.pay(token, ...)` (popup).
3. Setelah popup selesai (`onSuccess`, `onPending`, atau `onClose`), browser memanggil `POST /sewa/<kode>/sinkron-pembayaran/`.
4. Server **mengecek status transaksi ke API Midtrans** memakai `order_id`. Jika `settlement` (atau `capture` dengan fraud `accept`):
   - set `Payment.status = settlement`, isi `paid_at` dan `raw_response`;
   - ubah sewa menjadi `dibayar`;
   - buat `DepositHold` (`ditahan`) dan `LedgerEntry` masuk (lihat 9.4).
5. Proses ini harus **idempoten**: memanggil dua kali tidak membuat catatan ganda.
6. **Webhook** `/midtrans/notifikasi/` bersifat opsional (hanya berfungsi bila memakai tunnel seperti ngrok atau Cloudflare Tunnel). Jika dibuat, verifikasi `signature_key` = SHA512 dari `order_id + status_code + gross_amount + server_key`.
7. Gunakan masa berlaku transaksi (expiry) sesuai `PAYMENT_DEADLINE_HOURS`.
8. **Jangan pernah** mengubah status pembayaran berdasarkan klik di frontend. Satu-satunya sumber kebenaran adalah hasil cek ke Midtrans.

### 9.4 Escrow dan buku besar (`LedgerEntry`)

Escrow disimulasikan di database. Setiap pergerakan uang dicatat sebagai `LedgerEntry`.

**Saat pembayaran berhasil (contoh grand total Rp728.000):**

| kind | amount |
|---|---|
| `masuk_sewa` | 225.000 |
| `masuk_deposit` | 500.000 |
| `masuk_proteksi` | 3.000 |

**Saat sewa selesai tanpa masalah:**

| kind | amount |
|---|---|
| `keluar_komisi_platform` | 18.000 |
| `keluar_payout_pemilik` | 207.000 |
| `keluar_deposit_dikembalikan` | 500.000 |
| `keluar_proteksi_platform` | 3.000 |

**Invarian wajib (uji dengan unit test):** untuk setiap sewa yang `selesai`, total `masuk_*` sama dengan total `keluar_*`. Jika ada denda atau potongan, tambahkan `keluar_denda_ke_pemilik` dan kurangi `keluar_deposit_dikembalikan` sesuai.

`Payout` berstatus `dicairkan_simulasi` dan tidak memanggil layanan pencairan nyata. Di presentasi, jelaskan bahwa versi produksi memerlukan layanan payout dan ketentuan perizinan yang sesuai (konfirmasi ke penyedia pembayaran).

### 9.5 Pengembalian, kerusakan, dan sengketa (`rentals`)

1. Penyewa menekan **dikembalikan**, mengunggah foto "sesudah", dan sistem mengisi `returned_date`. Hitung `late_days` dan `late_fee`.
2. Pemilik memilih:
   - **Konfirmasi kondisi baik:** sewa menjadi `selesai`, deposit dirilis (dikurangi denda bila ada), payout dicatat.
   - **Laporkan masalah:** pemilik mengisi alasan dan nominal potongan (maksimal sisa deposit). Sewa menjadi `sengketa`.
3. Admin memutuskan sengketa di panel admin: `kembalikan_penuh`, `potong_sebagian` (isi nominal), atau `potong_penuh`. Keputusan menggerakkan `DepositHold` dan `LedgerEntry`, lalu sewa menjadi `selesai`.
4. Jika pemilik tidak merespons dalam `AUTO_CONFIRM_RETURN_HOURS`, sewa dikonfirmasi otomatis (perintah manajemen `process_deadlines`, dijalankan manual atau dengan tombol di panel admin saat demo).

### 9.6 Skor kepercayaan dengan machine learning (`trust`, `ml/`)

**Tujuan:** memperkirakan risiko pengguna bermasalah (telat lebih dari 1 hari, merusak barang, atau terlibat sengketa) pada sewa berikutnya, lalu mengubahnya menjadi skor 0-100 yang mudah dibaca.

**Fitur per pengguna:**

`jumlah_sewa_selesai`, `jumlah_sebagai_pemilik`, `rasio_tepat_waktu`, `rata_rata_rating_diterima`, `jumlah_sengketa`, `rasio_sengketa`, `rasio_pembatalan`, `umur_akun_hari`, `status_ktm` (0/1).

Fitur sensitif (jenis kelamin, kampus, jurusan, asal daerah) **tidak dipakai**.

**Data:** karena belum ada data nyata, buat **data sintetis** dengan `ml/generate_synthetic_data.py` (sekitar 3.000-5.000 baris, `random_state` tetap, proporsi kelas bermasalah sekitar 15%, ada noise). Nyatakan terbuka di presentasi bahwa data bersifat sintetis. Metrik tinggi pada data sintetis **bukan bukti akurasi di dunia nyata**.

**Pelatihan (`ml/train_trust_model.py`):**

1. Bagi data train dan test dengan `stratify`.
2. Bandingkan beberapa model: baseline `DummyClassifier`, baseline aturan sederhana (misalnya `rasio_tepat_waktu < 0,7` berarti berisiko), `LogisticRegression` (`class_weight="balanced"`), dan `GradientBoostingClassifier` (atau `RandomForestClassifier`).
3. Evaluasi: `accuracy`, `precision`, `recall`, `F1`, `ROC-AUC`, `PR-AUC`, dan confusion matrix. Pilih model berdasarkan `recall` dan `ROC-AUC` pada kelas bermasalah.
4. Simpan model terbaik dengan `joblib` ke `ml/artifacts/trust_model.joblib` dan metrik ke `metrics.json`.

**Pemakaian di aplikasi:**

- Muat model **sekali** saat aplikasi mulai (`AppConfig.ready()` atau cache modul).
- `skor = round((1 - probabilitas_bermasalah) * 100)`.
- Pengguna dengan kurang dari 3 sewa selesai: `is_new_user = True`, skor awal 60, tampilkan label "Pengguna baru".
- **Penjelasan:** simpan 3 faktor teratas yang paling memengaruhi skor (dari koefisien model linear atau kontribusi fitur) dan tampilkan dengan kalimat sederhana.
- Hitung ulang skor setelah sewa selesai atau sengketa diputuskan (sinyal Django).
- Pemakaian skor: lencana "Tepercaya" jika skor 70 atau lebih, deposit minimum naik 1,5 kali jika skor di bawah 40, dan urutan "skor tertinggi" di katalog.
- Admin selalu bisa menimpa keputusan manusia atas skor (override dengan catatan).

**Halaman demo ML (disarankan):** `/admin/ringkasan/` atau halaman "Tentang Skor" menampilkan metrik model, perbandingan dengan baseline, dan contoh penjelasan skor. Ini yang paling mungkin ditanyakan juri ML.

## 10. Peta halaman dan URL

**Publik**

| URL | Halaman |
|---|---|
| `/` | Beranda (lihat `design.md`) |
| `/barang/` | Katalog dengan filter |
| `/barang/hasil/` | Partial HTMX hasil pencarian |
| `/barang/<slug>/` | Detail barang |
| `/pengguna/<username>/` | Profil publik (skor, ulasan, barang) |
| `/cara-kerja/`, `/bantuan/` | Halaman statis |
| `/masuk/`, `/daftar/`, `/keluar/` | Autentikasi |

**Mahasiswa (login)**

| URL | Halaman atau aksi |
|---|---|
| `/verifikasi-ktm/` | Stepper unggah KTM dan status |
| `/dashboard/` | Ringkasan: sewa saya, permintaan masuk, barang saya, skor |
| `/barang/baru/`, `/barang/<slug>/ubah/`, `/barang/saya/` | Kelola barang (wajib terverifikasi) |
| `/sewa/ajukan/<slug>/` | Ajukan sewa (POST) |
| `/sewa/<kode>/` | Detail sewa: timeline status, foto kondisi, aksi sesuai peran |
| `/sewa/<kode>/setujui/`, `/tolak/`, `/batal/` | Aksi pemilik atau penyewa |
| `/sewa/<kode>/bayar/`, `/sinkron-pembayaran/` | Pembayaran Midtrans |
| `/sewa/<kode>/foto/` | Unggah foto kondisi |
| `/sewa/<kode>/serah-terima/`, `/kembalikan/`, `/konfirmasi/`, `/laporkan/` | Siklus sewa |
| `/ulasan/<kode>/` | Beri ulasan |
| `/notifikasi/` | Daftar notifikasi (opsional) |

**Admin**

| URL | Fungsi |
|---|---|
| `/admin/` | Django admin yang dikustom: antrean KTM, sengketa, pengguna, barang, kategori, ledger |
| `/admin/ktm/<id>/gambar/` | View privat untuk melihat gambar KTM |
| `/admin/ringkasan/` | Ringkasan platform: jumlah pengguna, sewa, nilai transaksi, komisi, metrik model ML |

## 11. Dashboard dan panel admin

**Dashboard mahasiswa:** status verifikasi KTM, kartu skor kepercayaan beserta 3 faktor penjelasnya, daftar "Sewa saya" (sebagai penyewa), "Permintaan masuk" (sebagai pemilik) dengan tombol aksi, "Barang saya", dan ringkasan pendapatan (simulasi).

**Panel admin (Django admin):**

- Antrean KTM: filter status, tampilkan rekomendasi OCR dan skor, tindakan massal "setujui" dan "tolak" dengan catatan.
- Sengketa: formulir keputusan.
- Ledger: tabel hanya-baca dengan total masuk dan keluar per sewa.
- Barang dan pengguna: nonaktifkan.

## 12. Data demo (seed)

Perintah `python manage.py seed_demo` membuat:

- 8 kategori: Kamera, Perlengkapan Wisuda, Alat Praktikum, Camping dan Outdoor, Proyektor dan Audio, Kostum dan Busana Acara, Laptop dan Aksesori, Lain-lain.
- 1 admin, 6 mahasiswa terverifikasi (nama fiktif), 2 mahasiswa belum terverifikasi.
- 20 barang dengan foto placeholder (jangan memakai foto berhak cipta; gunakan gambar buatan sendiri atau placeholder gradien).
- 10 sewa dalam berbagai status, beberapa ulasan, dan skor kepercayaan.
- Data latih ML sintetis (opsional di perintah terpisah `python ml/generate_synthetic_data.py`).

Akun demo hanya untuk lokal. Cantumkan di README dan jangan dipakai di tempat lain.

## 13. Keamanan dan privasi

- Aktifkan CSRF di semua form dan permintaan POST/HTMX.
- Periksa **kepemilikan objek** di setiap view (cegah IDOR).
- Validasi unggahan: tipe asli, ukuran, nama file diganti UUID, jangan pernah mengeksekusi file unggahan.
- Gambar KTM disimpan di luar `MEDIA_ROOT` publik, hanya bisa dilihat admin, dan dihapus setelah keputusan final (bila diaktifkan).
- Rahasia (secret key, kunci Midtrans) hanya di `.env`. Jangan di-commit.
- Hindari kondisi balapan (race condition) pada booking dan pembayaran dengan transaksi database dan penguncian baris.
- Jangan menampilkan WhatsApp sebelum pembayaran berhasil.
- Skor ML tidak memakai atribut sensitif, dan penjelasannya ditampilkan ke pengguna.
- Data pribadi (NIM, KTM) mengikuti prinsip minimisasi sesuai UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi: kumpulkan seperlunya, batasi akses, hapus bila tidak diperlukan.

## 14. Lingkup MVP dan yang ditunda

**Wajib (MVP):**

- Registrasi, login, profil.
- Unggah KTM, OCR, antrean admin.
- Pasang barang, katalog, pencarian dan filter, detail barang.
- Ajukan sewa, persetujuan, pembayaran Midtrans Sandbox, foto kondisi, serah terima, pengembalian, rilis deposit.
- Escrow dan buku besar (simulasi), ulasan.
- Skor kepercayaan (ML) dengan penjelasan dan halaman metrik.
- Dashboard dan panel admin dasar, data demo.

**Ditunda (tampilkan sebagai peta jalan):**

- Pencairan dana nyata dan escrow produksi.
- Deteksi kerusakan dari foto.
- Notifikasi email atau WhatsApp otomatis dan chat dalam aplikasi.
- Verifikasi ke data resmi kampus, verifikasi email `.ac.id`.
- Asuransi barang, listing unggulan, langganan pemilik, multi-kampus, aplikasi seluler.

## 15. Jadwal 15 hari

| Hari | Fokus | Hasil |
|---|---|---|
| 1 | Setup proyek, database, `.env`, base template + Tailwind | Proyek jalan di localhost, `base.html` sesuai `design.md` |
| 2 | Model data, migrasi, admin dasar, `seed_demo` awal | Semua tabel dan data contoh |
| 3 | Registrasi, login, profil, dashboard kerangka | Autentikasi berfungsi |
| 4 | Unggah KTM, OCR, antrean admin | Verifikasi KTM dengan rekomendasi |
| 5 | Pasang barang (foto, harga, deposit) | CRUD barang |
| 6 | Beranda, katalog, filter, HTMX, detail barang | Tampilan utama selesai |
| 7 | Ajukan sewa, persetujuan, anti double-booking | Alur hingga `menunggu_pembayaran` |
| 8 | Midtrans Sandbox: token, popup, sinkron status | Pembayaran berjalan |
| 9 | Ledger, deposit, foto kondisi, serah terima | Alur hingga `sedang_disewa` |
| 10 | Pengembalian, denda, konfirmasi, rilis deposit, payout | Alur hingga `selesai` |
| 11 | Sengketa, ulasan, pembatalan, `process_deadlines` | Alur lengkap termasuk kasus khusus |
| 12 | ML: data sintetis, pelatihan, metrik, integrasi skor | Skor dan penjelasannya tampil |
| 13 | Dashboard, ringkasan admin, halaman metrik ML | Dashboard dan admin siap |
| 14 | Poles tampilan (dekorasi, responsif), uji alur penuh, perbaikan bug | Demo stabil |
| 15 | Pitch deck, skrip demo, latihan tanya jawab | Siap presentasi |

Jika waktu mepet, korbankan dekorasi 3D, notifikasi, dan pembatalan lanjutan. **Jangan korbankan alur utama dan tiga pembeda.**

## 16. Skenario demo dan antisipasi pertanyaan juri

**Skrip demo (5-7 menit):**

1. Tunjukkan beranda dan masalahnya (singkat).
2. Daftar akun baru, unggah KTM, tunjukkan hasil OCR dan persetujuan admin.
3. Pasang barang dengan foto dan deposit.
4. Dari akun lain: cari, ajukan sewa, pemilik menyetujui.
5. Bayar lewat Midtrans Sandbox, tunjukkan dana ditahan di ledger.
6. Foto kondisi sebelum dan sesudah, kembalikan barang.
7. Deposit dirilis dan payout dicatat, tunjukkan komisi platform.
8. Tampilkan skor kepercayaan dan penjelasannya, lalu halaman metrik model.

**Pertanyaan yang mungkin muncul:**

- *Dari mana data ML-nya?* Sintetis, dinyatakan terbuka, dengan rencana mengumpulkan data nyata (dengan persetujuan pengguna) setelah ada transaksi.
- *Bagaimana dibanding baseline?* Tampilkan tabel metrik model dibanding baseline.
- *Apakah OCR bisa dipalsukan?* Ya, karena itu admin meninjau, dan ada rencana verifikasi email kampus serta data resmi.
- *Bagaimana uangnya benar-benar ditahan?* Disimulasikan di prototipe, versi produksi memerlukan layanan escrow atau payout yang sesuai ketentuan.
- *Apa bedanya dengan marketplace biasa?* Komunitas tertutup terverifikasi, deposit, bukti foto, dan skor kepercayaan.
- *Bagaimana cold start dua sisi?* Mulai dari satu kampus dan satu niche (perlengkapan acara dan wisuda), lalu ekspansi.

## 17. Daftar periksa penerimaan (Definition of Done)

- [ ] Alur utama berjalan dari daftar sampai ulasan tanpa error.
- [ ] Pengguna tanpa verifikasi KTM tidak bisa memasang barang atau menyewa.
- [ ] Tidak ada double-booking pada tanggal yang bertabrakan (ada unit test).
- [ ] Pembayaran Sandbox berhasil dan idempoten, status diperbarui hanya dari cek ke Midtrans.
- [ ] Invarian ledger lolos untuk sewa normal, terlambat, dan sengketa (unit test).
- [ ] Gambar KTM tidak bisa diakses publik.
- [ ] Skor kepercayaan tampil dengan 3 faktor penjelasan, dan halaman metrik model tersedia.
- [ ] Tampilan sesuai `design.md`, responsif di layar ponsel, fokus keyboard terlihat.
- [ ] `seed_demo` membuat data yang cukup untuk demo penuh.
- [ ] README berisi cara menjalankan (instal, `.env`, migrasi, seed, latih model, jalankan server).

## 18. Asumsi yang perlu dikonfirmasi

- Nama produk: **Collective Campus**.
- Persentase komisi, biaya proteksi, denda, dan batas waktu di bagian 7 adalah angka awal dan perlu dibandingkan dengan platform sejenis.
- Metode pembayaran uji di Midtrans Sandbox mengikuti dokumentasi resmi Midtrans.
- Cek ketentuan lomba: apakah demo dari localhost diterima.
