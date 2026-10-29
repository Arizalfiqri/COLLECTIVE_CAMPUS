# Panduan Kode, Arsitektur, dan Sistem Pembelajaran Mesin Collective Campus

Dokumentasi teknis komprehensif untuk pengembang, auditor sistem, dan mahasiswa. Panduan ini menjelaskan struktur repositori, implementasi fitur unik, dan sistem pembelajaran mesin (machine learning) secara transparan dan mudah dipahami tanpa memerlukan latar belakang teknis tingkat lanjut.

Seluruh nama berkas, fungsi, kelas, variabel, dan angka performa di dalam dokumen ini telah diverifikasi langsung dari kode sumber repositori pada commit `8735422`.

---

## Daftar Isi

- [Bagian A: Peta Proyek](#bagian-a-peta-proyek)
  - [Pohon Folder dan Komponen Utama](#pohon-folder-dan-komponen-utama)
  - [Tabel Aplikasi Django](#tabel-aplikasi-django)
  - [Alur Permintaan Aplikasi](#alur-permintaan-aplikasi)
  - [Variabel Lingkungan dan Pengaturan Kunci](#variabel-lingkungan-dan-pengaturan-kunci)
  - [Daftar Perintah Manajemen dan Skrip Otomatisasi](#daftar-perintah-manajemen-dan-skrip-otomatisasi)
  - [Struktur Pengujian dan Alat Audit](#struktur-pengujian-dan-alat-audit)
- [Bagian B: Keunikan Kode](#bagian-b-keunikan-kode)
  - [1. Mesin Status Tunggal untuk Sewa dan Penjualan](#1-mesin-status-tunggal-untuk-sewa-dan-penjualan)
  - [2. Pencegahan Pemesanan Ganda dengan Kunci Baris Database](#2-pencegahan-pemesanan-ganda-dengan-kunci-baris-database)
  - [3. Sinkronisasi Pembayaran Idempoten dan Verifikasi Webhook](#3-sinkronisasi-pembayaran-idempoten-dan-verifikasi-webhook)
  - [4. Buku Besar Berpasangan dan Rekonsiliasi Finansial Independen](#4-buku-besar-berpasangan-dan-rekonsiliasi-finansial-independen)
  - [5. Snapshot Syarat Ketentuan dan Jejak Integritas Kriptografis](#5-snapshot-syarat-ketentuan-dan-jejak-integritas-kriptografis)
  - [6. Tata Kelola Privasi Kartu Tanda Mahasiswa](#6-tata-kelola-privasi-kartu-tanda-mahasiswa)
  - [7. Penyamaran Informasi Kontak Otomatis pada Ruang Percakapan](#7-penyamaran-informasi-kontak-otomatis-pada-ruang-percakapan)
  - [8. Enkripsi Data Rekening Bank dan Pencatatan Log Akses Audit](#8-enkripsi-data-rekening-bank-dan-pencatatan-log-akses-audit)
  - [9. Tangga Reputasi Mahasiswa dan Batas Nilai Transaksi](#9-tangga-reputasi-mahasiswa-dan-batas-nilai-transaksi)
  - [10. Saklar Fitur Arsitektural Fleksibel](#10-saklar-fitur-arsitektural-fleksibel)
  - [11. Audit Otomatis Jarak dan Tata Letak Responsif Perangkat Nyata](#11-audit-otomatis-jarak-dan-tata-letak-responsif-perangkat-nyata)
  - [12. Pemindai Kelas Tailwind CSS dan Kerangka Navigasi Admin Terpadu](#12-pemindai-kelas-tailwind-css-dan-kerangka-navigasi-admin-terpadu)
- [Bagian C: Sistem Pembelajaran Mesin](#bagian-c-sistem-pembelajaran-mesin)
  - [C1 Peta Berkas Pembelajaran Mesin](#c1-peta-berkas-pembelajaran-mesin)
  - [C2 Sistem Pembacaan Dokumen Otomatis Kartu Tanda Mahasiswa](#c2-sistem-pembacaan-dokumen-otomatis-kartu-tanda-mahasiswa)
  - [C3 Pembangkitan Data Sintetis Realistis](#c3-pembangkitan-data-sintetis-realistis)
  - [C4 Spesifikasi Fitur dan Definisi Label Risiko](#c4-spesifikasi-fitur-dan-definisi-label-risiko)
  - [C5 Pelatihan, Evaluasi Komparatif, dan Kalibrasi Probabilitas](#c5-pelatihan-evaluasi-komparatif-dan-kalibrasi-probabilitas)
  - [C6 Operasi Inferensi pada Alur Transaksi](#c6-operasi-inferensi-pada-alur-transaksi)
  - [C7 Mekanisme Pembelajaran Berkelanjutan dari Data Nyata](#c7-mekanisme-pembelajaran-berkelanjutan-dari-data-nyata)
  - [C8 Batasan Etika, Penanganan Bias, dan Kedaulatan Manusia](#c8-batasan-etika-penanganan-bias-dan-kedaulatan-manusia)
  - [C9 Panduan Eksekusi Teknis dan Interpretasi Metrik](#c9-panduan-eksekusi-teknis-dan-interpretasi-metrik)
  - [C10 Glosarium Istilah dan Tanya Jawab Pengujian](#c10-glosarium-istilah-dan-tanya-jawab-pengujian)

---

## Bagian A: Peta Proyek

### Pohon Folder dan Komponen Utama

Pohon folder berikut menampilkan tata letak repositori hingga tingkat kedalaman ketiga beserta peran operasional masing-masing komponen.

```text
SEWA_MAHASISWA/
|-- apps/                          Folder utama modul fungsional aplikasi Django
|   |-- accounts/                  Pengelolaan data pengguna, profil mahasiswa, dan kampus
|   |-- catalog/                   Katalog barang sewa publik, pencarian, dan penayangan
|   |-- chat/                      Sistem pesan langsung antarmahasiswa dengan filter kontak
|   |-- core/                      Navigasi global, halaman statis, kebijakan, dan audit log
|   |-- payments/                  Gerbang pembayaran, buku besar, saldo, dan penarikan
|   |-- rentals/                   Siklus hidup transaksi sewa, serah terima, dan sengketa
|   |-- sales/                     Siklus transaksi jual beli barang bekas antarmahasiswa
|   |-- trust/                     Model reputasi, inferensi skor ML, dan data latih
|   `-- verification/              Alur verifikasi identitas mahasiswa dan OCR KTM
|-- config/                        Konfigurasi utama proyek Django
|   |-- settings.py                Berkas pengaturan aplikasi, basis data, dan saklar fitur
|   |-- urls.py                    Peta rute URL global tingkat proyek
|   `-- wsgi.py                    Antarmuka gateway server web WSGI
|-- dev_tools/                     Alat pengembang dan skrip pengisian data simulasi
|   `-- management/commands/       Perintah pengelolaan data demo dan foto simulasi
|-- docs/                          Dokumentasi teknis, spesifikasi, dan panduan proyek
|   |-- references/                Panduan gaya, token desain, dan aturan penulisan
|   |-- FITUR_PRESENTASI.md        Dokumentasi fitur operasional untuk presentasi tim
|   |-- MODEL_CARD.md              Spesifikasi transparansi tata kelola model ML
|   `-- PANDUAN_KODE.md             Panduan kode arsitektur dan teknis (berkas ini)
|-- ml/                            Modul mandiri rekayasa machine learning
|   |-- artifacts/                 Model biner terkompilasi, scaler, dan metrik JSON
|   |-- data/                      Dataset sintetis CSV untuk pelatihan model
|   |-- demo_retrain.py            Simulasi alur pelatihan ulang dari stream data nyata
|   |-- generate_synthetic_data.py Skrip pembangkit data sintetis berbasis variabel laten
|   |-- ktm_ocr.py                 Pipeline pra-proses gambar dan OCR kartu tanda mahasiswa
|   `-- train_trust_model.py       Pipeline pelatihan, validasi silang, dan kalibrasi
|-- private_media/                 Penyimpanan berkas privat (KTM dan bukti) terisolasi
|-- public_media/                  Penyimpanan berkas media publik (foto barang sewa)
|-- scripts/                       Skrip audit kualitas antarmuka dan otomatisasi
|   |-- check_tailwind_classes.py  Pemeriksa validitas kelas CSS Tailwind pada template
|   |-- responsive_audit.py        Pengujian responsif lintas resolusi perangkat nyata
|   `-- spacing_audit.py           Pengukuran kepatuhan jarak vertikal antarmuka
|-- static/                        Aset statis aplikasi (CSS, JS, gambar, kurva grafik ML)
|   |-- css/                       Berkas gaya kustom dan token palet warna
|   `-- ml/                        Visualisasi grafik metrik evaluasi model machine learning
|-- templates/                     Template antarmuka HTML Django bertingkat
|-- manage.py                      Titik masuk eksekusi perintah manajemen proyek Django
`-- requirements.txt               Daftar pustaka dependensi Python proyek
```

### Tabel Aplikasi Django

Repositori ini terdiri dari 10 aplikasi Django internal yang bekerja sama secara modular. Tabel di bawah merinci isi masing-masing aplikasi:

| Aplikasi | Models (40 Total) | Services | Views Kunci | File URL | Templates | Berkas Pengujian | Perintah Manajemen |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `apps.core` | `Notification`, `TermsVersion` | `get_platform_settings`, `get_staff_operational_stats` | `home_view`, `about_view`, `faq_view`, `terms_view`, `bantuan_view`, `global_search_view` | `apps/core/urls.py` | `templates/core/*.html` | `tests.py`, `tests_phase9_brand.py`, `tests_responsive_clean.py` | `init_platform`, `backup_data`, `cleanup_test_data` |
| `apps.accounts` | `User`, `Campus`, `MeetingPoint`, `BlacklistedNim`, `StudentProfile`, `SuspensionRecord` | `apps/accounts/services.py` | `login_view`, `register_view`, `profile_view`, `campus_select_view` | `apps/accounts/urls.py` | `templates/accounts/*.html` | `apps/accounts/tests.py` | *(tidak ada)* |
| `apps.verification` | `KtmVerification` | `apps/verification/services.py` | `upload_ktm_view`, `ktm_status_view`, `admin_ktm_image_view` | `apps/verification/urls.py` | `templates/verification/*.html` | `apps/verification/tests.py` | *(tidak ada)* |
| `apps.catalog` | `Category`, `Item`, `ItemPhoto` | `apps/catalog/services.py` | `item_list_view`, `item_detail_view`, `item_create_view`, `item_edit_view` | `apps/catalog/urls.py` | `templates/catalog/*.html` | `apps/catalog/tests.py` | *(tidak ada)* |
| `apps.rentals` | `Rental`, `ConditionPhoto`, `Review`, `Dispute`, `RentalAgreement`, `HandoverSchedule` | `apps/rentals/services.py`, `apps/rentals/photos.py` | `rental_request_view`, `rental_detail_view`, `rental_approve_view`, `handover_confirm_view` | `apps/rentals/urls.py` | `templates/rentals/*.html` | `apps/rentals/tests.py` | `process_deadlines` |
| `apps.payments` | `Payment`, `DepositHold`, `Payout`, `LedgerEntry`, `WalletTransaction`, `WithdrawalRequest`, `WithdrawalAccountAccessLog`, `ExtraCharge` | `services.py`, `encryption.py`, `reconciliation.py` | `payment_checkout_view`, `midtrans_notification_webhook`, `wallet_dashboard_view`, `request_withdrawal_view` | `apps/payments/urls.py` | `templates/payments/*.html` | `apps/payments/tests.py` | `reconcile_finances` |
| `apps.trust` | `TrustScore`, `TrustTrainingExample`, `TrustModelVersion` | `apps/trust/services.py` | `trust_profile_view`, `admin_trust_override_view` | `apps/trust/urls.py` | `templates/trust/*.html` | `apps/trust/tests.py` | `train_trust_model`, `retrain_trust_model`, `rollback_trust_model` |
| `apps.chat` | `Conversation`, `Message` | `apps/chat/services.py` | `conversation_list_view`, `conversation_detail_view`, `send_message_view` | `apps/chat/urls.py` | `templates/chat/*.html` | `apps/chat/tests.py` | *(tidak ada)* |
| `apps.sales` | `SaleItem`, `SaleItemPhoto`, `SellerTermsAcceptance`, `SaleOrder`, `SaleAgreement`, `SaleDispute`, `SaleReview`, `SaleItemReport`, `SaleOffer` | `apps/sales/services.py` | `sale_list_view`, `sale_detail_view`, `sale_order_create_view`, `order_confirm_handover_view` | `apps/sales/urls.py` | `templates/sales/*.html` | `apps/sales/tests.py` | *(tidak ada)* |
| `dev_tools` | *(tidak ada model)* | *(tidak ada service)* | `demo_login_view`, `system_status_view` | `dev_tools/urls.py` | `templates/dev_tools/*.html` | `dev_tools/tests.py` | `seed_demo`, `rename_demo_codes`, `replace_demo_photos` |

### Alur Permintaan Aplikasi

Semua interaksi pengguna berjalan melalui lapisan berurutan yang memisahkan tanggung jawab secara tegas: rute URL mengarahkan ke pengendali view, view mendelegasikan logika transaksi bisnis ke service, service berinteraksi dengan database melalui model di dalam transaksi atomik, dan hasilnya disajikan ke pengguna melalui template antarmuka.

```text
[ Browser / Klien Web ]
        |
        |  1. HTTP Request (GET/POST)
        v
[ config/urls.py & apps/*/urls.py ]  --- Mencocokkan rute URL ke fungsi View
        |
        |  2. Panggil fungsi handler
        v
[ apps/*/views.py ]                  --- Validasi input form, cek autentikasi, & otorisasi
        |
        |  3. Panggil fungsi logika bisnis
        v
[ apps/*/services.py ]               --- Mesin status, kalkulasi biaya, verifikasi ML, & lock DB
        |
        |  4. Operasi Database (ORM)
        v
[ apps/*/models.py (Database) ]      --- Penyimpanan baris data, select_for_update, & integritas relasi
        |
        |  5. Kembalikan data objek
        v
[ apps/*/services.py ]
        |
        |  6. Kembalikan konteks data
        v
[ apps/*/views.py ]
        |
        |  7. Render data ke HTML
        v
[ templates/*/*.html ]               --- Template Django (Tailwind CSS, HTMX, Lucide Icons)
        |
        |  8. HTTP Response (HTML)
        v
[ Browser / Klien Web ]
```

### Variabel Lingkungan dan Pengaturan Kunci

Tabel berikut menyajikan variabel lingkungan yang mengatur perilaku aplikasi beserta nilai bawaannya:

| Nama Variabel | Fungsi dan Peran Operasional | Nilai Bawaan (Default) |
| :--- | :--- | :--- |
| `DEBUG` | Mengatur mode penelusuran kesalahan teknis Django | `False` |
| `SECRET_KEY` | Kunci kriptografis penandatangan sesi dan token Django | *(wajib disetel di lingkungan produksi)* |
| `ALLOWED_HOSTS` | Daftar nama domain atau alamat host yang diizinkan melayani permintaan | `localhost,127.0.0.1,testserver` |
| `DATABASE_URL` | Konfigurasi koneksi basis data relasional SQLite atau PostgreSQL | `sqlite:///db.sqlite3` |
| `DEPOSIT_MODE` | Pengatur kebijakan deposit barang sewa (`off`, `optional`, `strict`) | `off` |
| `SALE_OFFERS_ENABLED` | Saklar pengaktif fitur penawaran harga terstruktur pada jual beli | `False` |
| `FIELD_ENCRYPTION_KEY` | Kunci simetris Fernet 32-byte untuk mengenkripsi nomor rekening bank | *(kunci demo berstandar URL-safe base64)* |
| `MIDTRANS_SERVER_KEY` | Kunci server otentikasi transaksi pembayaran gateway Midtrans | `SB-Mid-server-demo` |
| `MIDTRANS_CLIENT_KEY` | Kunci publik antarmuka checkout frontend Midtrans Snap | `SB-Mid-client-demo` |
| `MIDTRANS_IS_PRODUCTION` | Saklar penentu lingkungan gateway Midtrans (sandbox vs live) | `False` |
| `WITHDRAWAL_MIN` | Ambang batas minimal nominal pengajuan penarikan dana saldo pengguna | `20000` (Rp20.000) |
| `TRUST_MIN_REAL_EXAMPLES` | Jumlah sampel data riil minimal sebelum pelatihan ulang ML diizinkan | `200` |
| `TRUST_MIN_POSITIVES` | Jumlah kasus bermasalah riil minimal sebelum pelatihan ulang diizinkan | `20` |
| `PROTECTION_FEE_PERCENT` | Persentase biaya iuran dana gotong royong proteksi kerusakan barang | `5` (5%) |
| `PROTECTION_FEE_MIN` | Nilai minimum nominal biaya proteksi per transaksi sewa | `2000` (Rp2.000) |
| `PROTECTION_MANDATORY_ABOVE` | Batas nilai barang yang mewajibkan proteksi otomatis tanpa opsi batal | `1000000` (Rp1.000.000) |
| `SITE_NAME` | Nama merek platform resmi yang ditampilkan pada header antarmuka | `Collective Campus` |

### Daftar Perintah Manajemen dan Skrip Otomatisasi

Aplikasi dilengkapi dengan 11 perintah manajemen bawaan Django (`python manage.py <perintah>`) dan skrip audit yang dapat dijalankan secara mandiri:

| Nama Perintah / Skrip | Lokasi Berkas | Tujuan dan Fungsi Operasional | Cara Menjalankan |
| :--- | :--- | :--- | :--- |
| `seed_demo` | `dev_tools/management/commands/seed_demo.py` | Membuat 5 kampus demo, pengguna lintas peran, katalog barang, dan riwayat transaksi awal | `python manage.py seed_demo --flush` |
| `train_trust_model` | `apps/trust/management/commands/train_trust_model.py` | Melatih model regresi logistik terkalibrasi dari dataset sintetis 4.000 baris | `python manage.py train_trust_model` |
| `retrain_trust_model` | `apps/trust/management/commands/retrain_trust_model.py` | Melatih ulang model dari data nyata dengan verifikasi ambang data dan gerbang promosi | `python manage.py retrain_trust_model` |
| `rollback_trust_model` | `apps/trust/management/commands/rollback_trust_model.py` | Mengembalikan versi model aktif ke versi stabil sebelumnya jika performa turun | `python manage.py rollback_trust_model` |
| `reconcile_finances` | `apps/payments/management/commands/reconcile_finances.py` | Melakukan audit independen rekonsiliasi kas Midtrans, escrow, saldo, dan buku besar | `python manage.py reconcile_finances` |
| `process_deadlines` | `apps/rentals/management/commands/process_deadlines.py` | Memproses sewa kedaluwarsa, batas waktu bayar, denda keterlambatan, dan pengingat serah terima | `python manage.py process_deadlines` |
| `init_platform` | `apps/core/management/commands/init_platform.py` | Menginisialisasi pengaturan platform bawaan, syarat ketentuan versi 1, dan banner sistem | `python manage.py init_platform` |
| `backup_data` | `apps/core/management/commands/backup_data.py` | Membuat cadangan arsip basis data dan direktori penyimpanan media privat | `python manage.py backup_data` |
| `cleanup_test_data` | `apps/core/management/commands/cleanup_test_data.py` | Menghapus data transaksi sementara hasil pengujian otomatis | `python manage.py cleanup_test_data --dry-run` |
| `rename_demo_codes` | `dev_tools/management/commands/rename_demo_codes.py` | Menyeragamkan format kode sewa demo menjadi format standar `RNT-YYYYMMDD-XXXX` | `python manage.py rename_demo_codes` |
| `replace_demo_photos` | `dev_tools/management/commands/replace_demo_photos.py` | Mengisi ulang foto katalog demo dari generator visual lokal | `python manage.py replace_demo_photos` |
| `spacing_audit.py` | `scripts/spacing_audit.py` | Mengukur kepatuhan margin vertikal halaman web menggunakan Playwright headless | `python scripts/spacing_audit.py` |
| `responsive_audit.py` | `scripts/responsive_audit.py` | Menguji tampilan tanpa luapan horizontal pada 7 profil resolusi perangkat nyata | `python scripts/responsive_audit.py` |
| `check_tailwind_classes.py` | `scripts/check_tailwind_classes.py` | Memindai seluruh template HTML untuk memverifikasi kesesuaian token utilitas CSS | `python scripts/check_tailwind_classes.py` |

### Struktur Pengujian dan Alat Audit

Sistem pengujian perangkat lunak dirancang berlapis untuk menjamin stabilitas fungsionalitas dan konsistensi visual:

1. **Pengujian Unit dan Integrasi Django:**
   Sebanyak 389 uji otomatis mencakup seluruh alur bisnis dari otentikasi, sewa, pembayaran, hingga kalkulasi ML. Pengujian dijalankan dengan perintah:
   ```bash
   python manage.py test
   ```
2. **Audit Jarak Antarmuka (`scripts/spacing_audit.py`):**
   Audit berbasis penjelajah web otomatis (Playwright Chromium) yang menguji:
   - Jarak bilah navigasi ke konten pertama ($\le 48\text{ px}$ di desktop, $\le 32\text{ px}$ di ponsel).
   - Jarak antar-seksi vertikal kontainer utama ($\le 80\text{ px}$ di desktop, $\le 56\text{ px}$ di ponsel).
   - Pencegahan ruang kosong berlebih yang tidak sengaja ($> 120\text{ px}$).
3. **Audit Responsif Lintas Perangkat (`scripts/responsive_audit.py`):**
   Memeriksa 7 viewport (iPhone SE, iPhone 12, Pixel 5, iPad Mini, Mobile 320 px, Desktop 1024 px, dan Desktop 1280 px) untuk menjamin tidak ada luapan scroll horizontal (`scrollWidth <= innerWidth`), ukuran target sentuh tombol minimal $44 \times 44\text{ px}$, dan ukuran teks isi minimal $14\text{ px}$.
4. **Pemindai Sintaks CSS Tailwind (`scripts/check_tailwind_classes.py`):**
   Memeriksa kemurnian kode antarmuka agar tidak menggunakan kelas warna acak di luar palet sistem desain yang ditetapkan.

---

## Bagian B: Keunikan Kode

Bagian ini mendokumentasikan 12 solusi rekayasa perangkat lunak spesifik yang diterapkan dalam repositori Collective Campus. Seluruh cuplikan diverifikasi dari hash commit `8735422`.

### 1. Mesin Status Tunggal untuk Sewa dan Penjualan

- **Apa:** Mesin status terpusat bertipe `models.TextChoices` pada model `Rental` dan `SaleOrder` yang mendefinisikan seluruh kemungkinan fase transaksi secara linier dan eksplisit.
- **Di mana:** `apps/rentals/models.py:18-29` dan `apps/sales/models.py:299-307`.
- **Mengapa penting:** Mencegah perpindahan status ilegal (misalnya barang yang belum dibayar melompat menjadi status diserahkan) dan memberikan satu-satunya sumber kebenaran status transaksi bagi seluruh modul.
- **Cuplikan kode asli:**
  ```python
  # Path: apps/rentals/models.py:18-29 (Commit: 8735422)
      class Status(models.TextChoices):
          MENUNGGU_PERSETUJUAN = 'menunggu_persetujuan', 'Menunggu persetujuan'
          MENUNGGU_PEMBAYARAN = 'menunggu_pembayaran', 'Menunggu pembayaran'
          DIBAYAR = 'dibayar', 'Dibayar'
          SEDANG_DISEWA = 'sedang_disewa', 'Sedang disewa'
          MENUNGGU_KONFIRMASI_PENGEMBALIAN = 'menunggu_konfirmasi_pengembalian', 'Menunggu konfirmasi pengembalian'
          SELESAI = 'selesai', 'Selesai'
          SENGKETA = 'sengketa', 'Sengketa'
          DITOLAK = 'ditolak', 'Ditolak'
          DIBATALKAN = 'dibatalkan', 'Dibatalkan'
          KEDALUWARSA = 'kedaluwarsa', 'Kedaluwarsa'
  ```
- **Bagaimana diuji:** Diuji dalam `apps/rentals/tests.py` melalui fungsi `test_rental_state_transitions` yang memastikan pengecualian `RentalStateError` dilemparkan saat transisi status yang tidak valid dipicu.

Diagram teks di bawah menunjukkan siklus transisi status sewa:

```text
[ Menunggu Persetujuan ]
        |
        +---> Ditolak / Dibatalkan / Kedaluwarsa
        |
        v (Disetujui Pemilik)
[ Menunggu Pembayaran ]
        |
        +---> Kedaluwarsa / Dibatalkan
        |
        v (Pembayaran Terverifikasi Midtrans)
[ Dibayar ]
        |
        v (PIN Serah Terima Cocok)
[ Sedang Disewa ]
        |
        v (Penyewa Mengajukan Pengembalian)
[ Menunggu Konfirmasi Pengembalian ]
        |
        +---> [ Sengketa ] ---> (Diputuskan Admin) ---> [ Selesai ]
        |
        v (Pemilik Konfirmasi Barang Sesuai)
[ Selesai ]
```

### 2. Pencegahan Pemesanan Ganda dengan Kunci Baris Database

- **Apa:** Pemanfaatan klausa penguncian tingkat baris `select_for_update()` di dalam transaksi atomik database (`transaction.atomic()`) sebelum memverifikasi ketersediaan jadwal barang.
- **Di mana:** `apps/rentals/services.py:336-347`.
- **Mengapa penting:** Mencegah kondisi balapan (race condition) ketika dua mahasiswa mengajukan sewa untuk barang dan rentang tanggal yang sama pada milidetik yang identik. Kunci baris memaksa transaksi kedua menunggu hingga transaksi pertama selesai dieksekusi.
- **Cuplikan kode asli:**
  ```python
  # Path: apps/rentals/services.py:336-347 (Commit: 8735422)
      locked_rental = Rental.objects.select_for_update().get(id=rental.id)
      locked_item = Item.objects.select_for_update().get(id=locked_rental.item_id)

      if locked_rental.status != Rental.Status.MENUNGGU_PERSETUJUAN:
          raise RentalStateError(
              f"Permintaan sewa tidak dapat disetujui dari status '{locked_rental.get_status_display()}'."
          )

      # Cek ulang tabrakan dengan sewa yang memblokir
      if check_date_collision(locked_item, locked_rental.start_date, locked_rental.end_date, exclude_rental_id=locked_rental.id):
          raise RentalValidationError("Tanggal sewa bertabrakan dengan pesanan lain yang sudah aktif.")
  ```
- **Bagaimana diuji:** Diuji pada `apps/rentals/tests.py` fungsi `test_concurrent_rental_approval_prevents_double_booking` dengan mensimulasikan dua permintaan persetujuan paralel untuk rentang tanggal tumpang tindih.

### 3. Sinkronisasi Pembayaran Idempoten dan Verifikasi Webhook

- **Apa:** Verifikasi keaslian kriptografis tanda tangan SHA-512 pada webhook Midtrans dan penanganan status pembayaran yang idempoten (menghasilkan status konsisten meskipun dipanggil berkali-kali).
- **Di mana:** `apps/payments/views.py:353-377` dan `apps/payments/services.py:134-147`.
- **Mengapa penting:** Melindungi platform dari pemalsuan notifikasi pembayaran oleh pihak luar, serta mencegah eksekusi ganda penambahan saldo atau pelepasan dana jika Midtrans mengirimkan notifikasi jaringan berulang kali.
- **Cuplikan kode asli:**
  ```python
  # Path: apps/payments/services.py:134-147 (Commit: 8735422)
  def verify_midtrans_signature(order_id, status_code, gross_amount, signature_key):
      """
      Memverifikasi SHA-512 signature key dari notifikasi webhook Midtrans:
      signature_key = SHA512(order_id + status_code + gross_amount + server_key)
      """
      server_key = getattr(settings, 'MIDTRANS_SERVER_KEY', '').strip()
      if not server_key or not signature_key:
          return False

      # Format gross_amount: pastikan string tanpa desimal jika bilangan bulat
      raw_str = f"{order_id}{status_code}{gross_amount}{server_key}"
      calculated = hashlib.sha512(raw_str.encode('utf-8')).hexdigest()
      return hmac.compare_digest(calculated.lower(), signature_key.lower())
  ```
- **Bagaimana diuji:** Diuji di `apps/payments/tests.py` dalam `test_midtrans_webhook_signature_verification` dan `test_idempotent_payment_webhook_processing`.

### 4. Buku Besar Berpasangan dan Rekonsiliasi Finansial Independen

- **Apa:** Sistem pencatatan mutasi keuangan berbasis entri buku besar mutlak (`LedgerEntry`) yang diverifikasi secara matematis terhadap saldo escrow dan mutasi Midtrans oleh mesin audit independen.
- **Di mana:** `apps/payments/reconciliation.py:18-35` dan model `apps/payments/models.py:36-65`.
- **Mengapa penting:** Menjamin tidak ada selisih sepeser pun antara dana riil yang masuk dari rekening bersama Midtrans dengan akumulasi saldo dompet pengguna dan dana cadangan gotong royong platform.
- **Cuplikan kode asli:**
  ```python
  # Path: apps/payments/reconciliation.py:18-33 (Commit: 8735422)
  def run_financial_reconciliation():
      """
      Melakukan rekonsiliasi keuangan menyeluruh:
      1. Total dana masuk dari pembayaran Midtrans (settlement sewa & pesanan jual beli).
      2. Total dana yang sedang ditahan di escrow platform (DepositHold ditahan + sewa berjalan + pesanan jual beli berjalan).
      3. Total saldo dompet pengguna aktif saat ini.
      4. Total penarikan dana aktif (status diminta/diproses) dan yang sudah selesai ditransfer.
      5. Total pendapatan komisi platform dari buku besar (sewa & jual beli).
      6. Total saldo cadangan Dana Gotong Royong platform.
      7. Status seimbang per sewa, per pesanan jual beli, dan secara global.
      """
      # 1. Total Pembayaran Masuk (Inflow dari Midtrans)
      total_payment_settled = (
          Payment.objects.filter(status=Payment.Status.SETTLEMENT)
          .aggregate(total=Sum('gross_amount'))['total'] or 0
      )
  ```
- **Bagaimana diuji:** Diuji melalui perintah manajemen `python manage.py reconcile_finances` dan unit test `test_reconciliation_detects_no_discrepancy` di `apps/payments/tests.py`.

### 5. Snapshot Syarat Ketentuan dan Jejak Integritas Kriptografis

- **Apa:** Penyimpanan salinan permanen dokumen syarat dan ketentuan serta spesifikasi pesanan dalam bentuk dokumen JSON (`terms_snapshot`) lengkap dengan ringkasan hash kriptografis SHA-256 saat transaksi dibuat.
- **Di mana:** `apps/rentals/services.py:234-253` dan `apps/rentals/models.py:362-367`.
- **Mengapa penting:** Melindungi kedua belah pihak dari perselisihan jika pemilik barang mengubah harga, deskripsi barang, atau syarat sewa di kemudian hari setelah transaksi disetujui.
- **Cuplikan kode asli:**
  ```python
  # Path: apps/rentals/services.py:234-249 (Commit: 8735422)
      terms_snapshot = {
          'rental_code': rental.code,
          'item_title': locked_item.title,
          'estimated_value': locked_item.estimated_value,
          'price_per_day': price_per_day,
          'days': days,
          'rent_total': rent_total,
          'deposit_total': deposit_total,
          'protection_fee': protection_fee,
          'grand_total': grand_total,
          'use_protection': use_protection,
          'require_ktm_held': locked_item.require_ktm_held,
          'late_fee_per_day_percent': 50,
          'max_loss_compensation': locked_item.estimated_value,
          'accepted_by': renter.username,
          'accepted_at': now.isoformat(),
  ```
- **Bagaimana diuji:** Diuji pada `apps/rentals/tests.py` melalui `test_rental_agreement_stores_immutable_snapshot`.

### 6. Tata Kelola Privasi Kartu Tanda Mahasiswa

- **Apa:** Berkas gambar Kartu Tanda Mahasiswa (KTM) disimpan di direktori privat yang terisolasi dari URL publik (`PRIVATE_MEDIA_ROOT`), hanya dapat dibuka oleh staf dengan otentikasi ketat, serta dihapus dari media penyimpanan fisik setelah keputusan verifikasi diambil.
- **Di mana:** `config/settings.py:190`, `apps/verification/views.py:141-170`, dan `apps/verification/models.py:97-106`.
- **Mengapa penting:** Menegakkan kepatuhan terhadap Undang-Undang Perlindungan Data Pribadi (UU PDP). Foto identitas mahasiswa tidak boleh tersimpan tanpa batas waktu di server dan tidak boleh memiliki alamat tautan statis yang dapat ditebak.
- **Cuplikan kode asli:**
  ```python
  # Path: apps/verification/models.py:97-106 (Commit: 8735422)
      def delete_image_file(self):
          """Hapus file gambar KTM dari penyimpanan privat dan catat waktu penghapusan."""
          from django.utils import timezone
          if self.has_image_file:
              try:
                  self.private_file_path.unlink(missing_ok=True)
              except Exception:
                  pass
          self.image_deleted_at = timezone.now()
          self.save(update_fields=['image_deleted_at'])
  ```
- **Bagaimana diuji:** Diuji dalam `apps/verification/tests.py` melalui `test_ktm_file_purged_after_decision` dan `test_private_ktm_access_forbidden_for_public`.

### 7. Penyamaran Informasi Kontak Otomatis pada Ruang Percakapan

- **Apa:** Penyaringan otomatis menggunakan ekspresi reguler (regex) yang mendeteksi dan menyamarkan nomor telepon seluler, tautan eksternal (termasuk tautan WhatsApp dan Telegram), serta alamat surel pada pesan percakapan sebelum pembayaran terkonfirmasi.
- **Di mana:** `apps/chat/models.py:140-155`.
- **Mengapa penting:** Mencegah praktik penipuan transaksi di luar sistem (disintermediasi transaksi) yang menghilangkan proteksi dana escrow dan asuransi gotong royong mahasiswa.
- **Cuplikan kode asli:**
  ```python
  # Path: apps/chat/models.py:140-155 (Commit: 8735422)
      def mask_contact_info(cls, text):
          """
          Menyamarkan nomor telepon, tautan, dan email menjadi '[disamarkan sampai pembayaran]'.
          Aturan SPEC v2 bagian E:
          - nomor telepon (pola 08..., +62..., 8 digit berurutan atau lebih)
          - tautan (http, https, www., wa.me, t.me)
          - alamat email
          """
          if not text:
              return text

          masked_notice = "[disamarkan sampai pembayaran]"

          # 1. Mask URL / links (http://, https://, www., wa.me, t.me)
          url_pattern = r'(https?://[^\s]+|www\.[^\s]+|wa\.me/[^\s]+|t\.me/[^\s]+)'
          text = re.sub(url_pattern, masked_notice, text, flags=re.IGNORECASE)
  ```
- **Bagaimana diuji:** Diuji di `apps/chat/tests.py` melalui `test_contact_info_masking_before_payment`.

### 8. Enkripsi Data Rekening Bank dan Pencatatan Log Akses Audit

- **Apa:** Enkripsi simetris Fernet pada string nomor rekening bank atau nomor dompet digital milik pengguna saat disimpan ke database, dipadukan dengan pencatatan audit log setiap kali staf admin mendekripsi data tersebut.
- **Di mana:** `apps/payments/encryption.py:22-33` dan `apps/payments/models.py:304-320`.
- **Mengapa penting:** Mencegah kebocoran data perbankan mahasiswa jika basis data bocor, serta memastikan setiap tindakan pembacaan data finansial oleh staf tercatat pertanggungjawabannya secara transparan.
- **Cuplikan kode asli:**
  ```python
  # Path: apps/payments/encryption.py:22-33 (Commit: 8735422)
  def encrypt_account_number(plain_text: str) -> str:
      """
      Enkripsi nomor rekening atau dompet digital menggunakan Fernet.
      PENTING: Jangan pernah mencetak hasil plain_text ke logging.
      """
      if not plain_text:
          return ""
      clean = plain_text.strip()
      cipher = get_fernet_cipher()
      token = cipher.encrypt(clean.encode('utf-8'))
      return token.decode('utf-8')
  ```
- **Bagaimana diuji:** Diuji dalam `apps/payments/tests.py` pada `test_bank_account_encryption_roundtrip` dan `test_access_log_created_when_decrypted`.

### 9. Tangga Reputasi Mahasiswa dan Batas Nilai Transaksi

- **Apa:** Sistem penjenjangan reputasi otomatis tiga tingkat (`baru`, `tepercaya`, `sangat_tepercaya`) yang membatasi batas estimasi nilai barang maksimum yang boleh disewa atau dijual oleh seorang pengguna.
- **Di mana:** `apps/trust/services.py:81-125` dan `apps/trust/services.py:180-202`.
- **Mengapa penting:** Melindungi mahasiswa dari risiko kerugian besar akibat menyewakan barang bernilai jutaan rupiah (seperti kamera DSLR atau laptop) kepada pengguna yang baru pertama kali bergabung dan belum memiliki rekam jejak.
- **Cuplikan kode asli:**
  ```python
  # Path: apps/trust/services.py:180-195 (Commit: 8735422)
  def is_renter_eligible_for_item(user, item):
      """
      Mengecek apakah penyewa memenuhi syarat pemilik dan batas nilai barang:
      1. Tingkat penyewa >= item.min_renter_tier
      2. Nilai barang item.estimated_value <= limit nilai barang tingkat penyewa
      """
      user_tier = get_renter_tier(user)
      tier_info = get_tier_info(user_tier)

      user_rank = TIER_RANK.get(user_tier, 1)
      required_rank = TIER_RANK.get(item.min_renter_tier, 1)

      if user_rank < required_rank:
          req_label = TIER_LABELS.get(item.min_renter_tier, item.min_renter_tier)
          user_label = TIER_LABELS.get(user_tier, user_tier)
          return False, f"Pemilik mensyaratkan minimal {req_label}. Tingkat Anda saat ini: {user_label}."
  ```
- **Bagaimana diuji:** Diuji dalam `apps/trust/tests.py` melalui `test_renter_eligibility_by_tier_and_item_value`.

### 10. Saklar Fitur Arsitektural Fleksibel

- **Apa:** Pengaturan tingkat aplikasi melalui variabel lingkungan `DEPOSIT_MODE` dan `SALE_OFFERS_ENABLED` yang secara dinamis mengubah perilaku alur checkout tanpa memerlukan perubahan basis kode.
- **Di mana:** `config/settings.py:275` dan `config/settings.py:381`.
- **Mengapa penting:** Memberikan kelincahan bisnis untuk menguji opsi produk (misalnya beralih dari model tanpa deposit ke model deposit opsional, atau menyalakan fitur tawar harga jual beli) sesuai kebutuhan komunitas kampus tertentu.
- **Cuplikan kode asli:**
  ```python
  # Path: config/settings.py:275 dan 381 (Commit: 8735422)
  DEPOSIT_MODE = env('DEPOSIT_MODE', default='off').lower().strip()

  # ==============================================================================
  # KONFIGURASI FASE 8C: JUAL BELI - FITUR TAWAR HARGA TERSTRUKTUR (OPSIONAL)
  # ==============================================================================
  SALE_OFFERS_ENABLED = os.environ.get('SALE_OFFERS_ENABLED', 'False').lower() in ('true', '1', 'yes')
  ```
- **Bagaimana diuji:** Diuji di `apps/rentals/tests.py` dan `apps/sales/tests.py` menggunakan decorator `@override_settings(DEPOSIT_MODE='strict')` dan `@override_settings(SALE_OFFERS_ENABLED=True)`.

### 11. Audit Otomatis Jarak dan Tata Letak Responsif Perangkat Nyata

- **Apa:** Rangkaian skrip pengujian berbasis browser otomatis (Playwright Chromium) yang mengukur jarak vertikal elemen dan mengevaluasi integritas tata letak antarmuka pada berbagai dimensi viewport layar fisik.
- **Di mana:** `scripts/spacing_audit.py:3-13` dan `scripts/responsive_audit.py:8-28`.
- **Mengapa penting:** Memastikan kualitas desain tetap konsisten, tidak berantakan, dan memenuhi kaidah ergonomi sentuhan pada perangkat seluler berlayar kecil tanpa bergantung pada pemeriksaan visual manual.
- **Cuplikan kode asli:**
  ```python
  # Path: scripts/spacing_audit.py:3-13 (Commit: 8735422)
  """
  scripts/spacing_audit.py — Audit Jarak Otomatis (Fase 7I)
  Menggunakan Playwright dengan emulasi perangkat sungguhan (viewport, dpr, touch)
  untuk mengukur:
    (a) Jarak vertikal navbar bottom ke elemen konten pertama (<= 48px desktop, <= 32px mobile)
    (b) Jarak vertikal antar-blok anak langsung dari container utama (<= 80px desktop, <= 56px mobile)
    (c) Ruang kosong vertikal berturut-turut di dalam main (<= 120px)

  Menghasilkan:
    - docs/local/spacing/REPORT.md
    - docs/local/spacing/screenshots/*.png
  """
  ```
- **Bagaimana diuji:** Dijalankan langsung melalui terminal CLI dan diintegrasikan dalam suite pengujian `apps/core/tests_responsive_clean.py`.

### 12. Pemindai Kelas Tailwind CSS dan Kerangka Navigasi Admin Terpadu

- **Apa:** Skrip audit penjamin mutu token antarmuka (`check_tailwind_classes.py`) yang dipadukan dengan kerangka navigasi admin berbasis peran terpadu (`apps/core/admin_nav.py`) yang mengonsolidasikan seluruh panel operasional staf dalam satu dasbor ergonomis.
- **Di mana:** `scripts/check_tailwind_classes.py:10-22` dan `apps/core/admin_nav.py:10-31`.
- **Mengapa penting:** Mencegah pergeseran gaya visual (design drift) dari token warna resmi serta memudahkan petugas operasional kampus memantau antrean verifikasi, sengketa, dan rekonsiliasi dalam satu layar.
- **Cuplikan kode asli:**
  ```python
  # Path: apps/core/admin_nav.py:10-25 (Commit: 8735422)
  MENU_CONFIG = [
      {
          'id': 'ikhtisar',
          'title': 'Ikhtisar',
          'icon': 'layout-dashboard',
          'is_single': True,
          'url_name': 'admin:index',
          'perm': None,
      },
      {
          'id': 'operasional',
          'title': 'Operasional',
          'icon': 'activity',
          'badge_key': 'total_queue',
          'items': [
              {'title': 'Antrean KTM', 'url_name': 'admin:verification_ktmverification_changelist', 'perm': 'verification.view_ktmverification'},
  ```
- **Bagaimana diuji:** Diuji melalui `python scripts/check_tailwind_classes.py` dan uji rendering antarmuka admin di `apps/core/tests.py`.

---

## Bagian C: Sistem Pembelajaran Mesin

### C1 Peta Berkas Pembelajaran Mesin

Arsitektur pembelajaran mesin dalam platform Collective Campus tersusun rapi dalam modul-modul berikut:

```text
Modul Pembelajaran Mesin Collective Campus:
|-- ml/                               Direktori inti algoritma dan data sains
|   |-- data/
|   |   |-- synthetic_rental_trust_data.csv        Dataset sintetis 4.000 baris riwayat sewa
|   |   `-- synthetic_rental_trust_data.csv.sha256 Hash integritas dataset
|   |-- artifacts/                    Model terkompilasi dan catatan performa
|   |   |-- trust_model.joblib        Model Regresi Logistik Terkalibrasi siap pakai
|   |   |-- trust_scaler.joblib       Skaler StandardScaler untuk normalisasi fitur
|   |   |-- trust_pipeline.joblib     Pipeline gabungan skaler dan estimasi
|   |   |-- metrics.json              Laporan komprehensif metrik evaluasi model
|   |   `-- versions/                 Arsip berkas model hasil retraining berkala
|   |-- generate_synthetic_data.py    Pembangkit data sintetis berbasis variabel laten
|   |-- train_trust_model.py          Pipeline pelatihan utama, validasi silang, dan kalibrasi
|   |-- ktm_ocr.py                    Modul pra-proses citra dan pembacaan teks kartu mahasiswa
|   `-- demo_retrain.py               Simulasi pelatihan ulang berkelanjutan dari data riil
|-- apps/trust/                       Integrasi model ke dalam alur web Django
|   |-- models.py                     Model TrustScore, TrustTrainingExample, TrustModelVersion
|   |-- services.py                   Ekstraksi fitur, inferensi skor, dan gerbang promosi
|   `-- management/commands/          Perintah eksekusi pelatihan dan pemulihan model
|-- static/ml/                        Visualisasi grafik metrik evaluasi
|   |-- roc_curve.png                 Kurva karakteristik operasi penerima (ROC)
|   |-- pr_curve.png                  Kurva presisi-recall (PR)
|   |-- calibration_curve.png         Kurva keandalan probabilitas sebelum & sesudah kalibrasi
|   |-- confusion_matrix.png          Matriks konfusi pada data uji independen
|   `-- feature_importance.png        Grafik tingkat pengaruh fitur (koefisien model)
`-- docs/MODEL_CARD.md                Kartu spesifikasi tata kelola etika dan batasan model
```

### C2 Sistem Pembacaan Dokumen Otomatis Kartu Tanda Mahasiswa

Modul `ml/ktm_ocr.py` bertugas membaca data teks dari foto Kartu Tanda Mahasiswa (KTM) yang diunggah pengguna untuk mempercepat proses verifikasi identitas:

1. **Tahap Pra-proses Gambar (`preprocess_ktm_image`):**
   - **Konversi Warna:** Mengubah citra masukan menjadi skala abu-abu (*grayscale* / modus `'L'`) untuk menghilangkan gangguan warna latar belakang kartu.
   - **Penskalaan Ulang Lanczos:** Jika lebar citra kurang dari 1.200 piksel, citra diperbesar secara proporsional menggunakan algoritma interpolasi berkualitas tinggi `Image.Resampling.LANCZOS` agar detail goresan huruf menjadi jelas.
   - **Peningkatan Kontras:** Mempertajam batas antara teks dan latar kartu dengan faktor pengali kontras `1.8` menggunakan `ImageEnhance.Contrast`.
   - **Penyaringan Ketajaman:** Menerapkan filter penajam `ImageFilter.SHARPEN` untuk mempertegas tepian karakter huruf.
2. **Ekstraksi Informasi:**
   - **Ekstraksi NIM:** Menggunakan pola ekspresi reguler kampus untuk mendeteksi deretan 8 sampai 15 digit angka unik mahasiswa.
   - **Ekstraksi Nama:** Membandingkan teks hasil OCR dengan nama lengkap akun pengguna menggunakan algoritma kesamaan string berbobot `rapidfuzz.fuzz.token_sort_ratio`.
   - **Ekstraksi Kampus:** Memeriksa keberadaan kata kunci nama universitas pada teks dokumen.
3. **Rumus Skor Kualitas Gambar (`calculate_quality_score`):**
   Skor kualitas citra (skala 0 sampai 100) dihitung dari kombinasi resolusi fisik dan kelimpahan karakter teks yang berhasil dibaca:
   $$\text{res\_score} = \min\left(100, \frac{\text{lebar} \times \text{tinggi}}{800 \times 500} \times 100\right)$$
   $$\text{text\_score} = \min(100, \text{panjang\_teks\_ocr} \times 2)$$
   $$\text{quality\_score} = \text{round}(0.7 \times \text{res\_score} + 0.3 \times \text{text\_score})$$
4. **Rumus Skor Kecocokan (`calculate_match_score`):**
   Tingkat kecocokan identitas dihitung dengan formula berbobot:
   $$\text{match\_score} = (50 \text{ jika NIM cocok}) + (0.3 \times \text{name\_similarity}) + (10 \text{ jika kampus cocok}) + (0.1 \times \text{quality\_score})$$
   Nilai akhir dibatasi pada rentang $0 \le \text{match\_score} \le 100$.
5. **Rekomendasi Keputusan Sistem:**
   - $\ge 85$: Rekomendasi `setuju` (KTM sangat cocok).
   - $60 - 84$: Rekomendasi `tinjau` (Perlu pengecekan manual oleh staf admin).
   - $< 60$: Rekomendasi `tolak` (Identitas tidak cocok atau gambar tidak terbaca).
6. **Penanganan Cadangan Tanpa Tesseract:**
   Jika pustaka Tesseract OCR belum terpasang di sistem operasi server, fungsi tidak melempar kesalahan sistem (*crash*), melainkan secara anggun mengembalikan status verifikasi `tinjau` dengan catatan penjelasan transparan kepada staf operasional.
7. **Batasan Kritis:**
   Sistem OCR ini **hanya mengekstraksi kesesuaian teks visual**, dan **tidak membuktikan keaslian fisik kartu** (tidak dapat memverifikasi hologram fisik, tanda tangan tinta basah, stempel universitas, atau chip RFID).

### C3 Pembangkitan Data Sintetis Realistis

Karena platform baru belum memiliki ratusan ribu riwayat transaksi, model awal dilatih menggunakan 4.000 baris data sintetis realistis yang dibangkitkan oleh `ml/generate_synthetic_data.py`:

```text
DIAGRAM PEMBANGKITAN DATA SINTETIS:

  Distribusi Normal Baku
        z ~ N(0, 1)
   (Keandalan Laten Mahasiswa)
        |
        +-----------------------------------+
        |                                   |
        v                                   v
Distribusi Fitur Perilaku            Fungsi Logistik Risiko
- umur_akun_hari (Gamma)             Logit = -2.03 - 1.45*z + Noise
- jumlah_sewa_selesai (Poisson)      P = 1 / (1 + exp(-Logit))
- rasio_tepat_waktu (Beta)                  |
- rata_rata_rating (Normal)                 v
- jumlah_sengketa (Poisson)          Label Biner (Ambang 0.50):
- rasio_pembatalan (Beta)            1: Transaksi Bermasalah (~15.4%)
        |                            0: Transaksi Lancar (~84.6%)
        v                                   |
  Matriks 8 Fitur X                         v
        +-----------------------------------+
        |
        v
  Dataset CSV (4.000 Baris)
  Hash SHA-256: 6c071490ca381cfc9413b6a7971e7ed61e9c300ebb6fb3f93affdbe9fc535e5d
```

1. **Variabel Laten Keandalan ($z$):**
   Setiap entitas pengguna diasosiasikan dengan satu nilai variabel laten keandalan $z \sim \mathcal{N}(0, 1)$. Nilai $z$ yang tinggi mencerminkan mahasiswa yang disiplin, komunikatif, dan teliti merawat barang. Nilai $z$ rendah mencerminkan pengguna yang berisiko lalai.
2. **Korelasi Perilaku Realistis:**
   Nilai $z$ dihubungkan ke fitur perilaku melalui distribusi statistik yang relevan:
   - Persentil keandalan $u = \Phi(z)$ menentukan parameter bentuk distribusi Beta untuk `rasio_tepat_waktu` dan `rasio_pembatalan`.
   - Intensitas parameter Poisson untuk sengketa dirumuskan sebagai $\lambda = \exp(-1.4 - 1.1z) \times (\text{total\_transaksi} / 15.0)$.
3. **Pembentukan Label Risiko:**
   Target risiko transaksi berikutnya dihitung menggunakan fungsi probabilitas logistik dengan gangguan stokastik terkalibrasi:
   $$\text{logit} = -2.03 - 1.45 \cdot z + \text{noise}$$
   Di mana $\text{noise} \sim \text{Logistic}(0, 0.75)$. Pengguna diklasifikasikan berisiko ($\text{label} = 1$) jika nilai probabilitas logistik $\ge 0.50$.
4. **Parameter Kunci dan Auditabilitas:**
   - Jumlah sampel total: 4.000 baris.
   - Seed pengacak: `42` (menghasilkan angka yang identik saat dijalankan ulang).
   - Prevalensi target berisiko: 15,4% (616 kasus positif dari 4.000 transaksi).
   - Hash integritas data: `6c071490ca381cfc9413b6a7971e7ed61e9c300ebb6fb3f93affdbe9fc535e5d`.
5. **Keterbatasan:**
   Data sintetis mengasumsikan hubungan matematis yang ideal antara kedisiplinan masa lalu dan masa depan. Pola penipuan terorganisasi yang kompleks di dunia nyata belum sepenuhnya terwakili hingga data riil terkumpul.

### C4 Spesifikasi Fitur dan Definisi Label Risiko

Model machine learning menggunakan 8 fitur perilaku riwayat yang objektif dan bebas dari kebocoran target:

| Nama Fitur | Tipe Data | Definisi Operasional | Arah Pengaruh Risiko |
| :--- | :--- | :--- | :--- |
| `jumlah_sewa_selesai` | Integer ($\ge 3$) | Total akumulasi transaksi sewa yang berhasil diselesaikan | Menurunkan risiko (koefisien: -0.2838) |
| `jumlah_sebagai_pemilik`| Integer ($\ge 0$) | Jumlah transaksi di mana pengguna bertindak sebagai pemilik barang | Menurunkan risiko (koefisien: -0.1051) |
| `rasio_tepat_waktu` | Float (0.0 - 1.0) | Persentase pengembalian barang sewa tanpa keterlambatan hari | Menurunkan risiko paling kuat (koefisien: -0.7643) |
| `rata_rata_rating_diterima`| Float (1.0 - 5.0) | Rata-rata bintang ulasan yang diberikan pihak lain | Menurunkan risiko (koefisien: -0.5057) |
| `jumlah_sengketa` | Integer ($\ge 0$) | Total riwayat klaim sengketa yang pernah terjadi | Menaikkan risiko (koefisien: +0.2501) |
| `rasio_sengketa` | Float (0.0 - 1.0) | Rasio jumlah klaim sengketa terhadap total transaksi | Menaikkan risiko (koefisien: +0.0556) |
| `rasio_pembatalan` | Float (0.0 - 1.0) | Rasio pembatalan sewa yang dipicu sendiri oleh pengguna | Menaikkan risiko (koefisien: +0.1832) |
| `umur_akun_hari` | Integer ($\ge 15$) | Durasi aktif akun pengguna sejak pendaftaran dalam hari | Penyesuaian kecil (koefisien: +0.1653) |

- **Definisi Label Risiko ($Y = 1$):**
  Transaksi diberi label bermasalah jika pada masa sewa terjadi salah satu dari empat kejadian:
  1. Keterlambatan pengembalian barang lebih dari 1 hari kalender (`late_days > 1`).
  2. Terbukti terjadi kerusakan fisik yang memicu pemotongan deposit atau kompensasi (`damage_fee > 0`).
  3. Terjadi persengketaan resmi yang dimenangkan oleh pemilik barang.
  4. Barang tidak dikembalikan sama sekali (kehilangan total).
  Bila transaksi berjalan lancar tanpa pelanggaran di atas, transaksi diberi label $Y = 0$.
- **Pencegahan Kebocoran Data (Data Leakage):**
  Seluruh 8 fitur di atas dihitung **secara eksklusif dari riwayat transaksi masa lalu sebelum transaksi yang sedang dievaluasi**. Informasi yang terjadi selama atau sesudah transaksi yang sedang berjalan sama sekali tidak dimasukkan ke dalam fitur masukan.
- **Fitur Sensitif yang Sengaja Ditiadakan:**
  Sesuai prinsip etika kecerdasan artifisial dan kepatuhan UU PDP, lima kelompok data sensitif di bawah ini **secara ketat dilarang** masuk ke dalam model:
  1. `gender` (Jenis kelamin): Mencegah diskriminasi berbasis gender.
  2. `campus_name` (Nama universitas): Mencegah bias institusional antarkampus.
  3. `major` (Program studi / jurusan): Mencegah prasangka terhadap bidang ilmu tertentu.
  4. `region` (Asal daerah mahasiswa): Mencegah diskriminasi geografis.
  5. `status_ktm` (Status verifikasi identitas): Tidak digunakan karena bersifat konstan (seluruh penyewa aktif wajib terverifikasi).

### C5 Pelatihan, Evaluasi Komparatif, dan Kalibrasi Probabilitas

Pipeline pelatihan dieksekusi melalui `ml/train_trust_model.py` dengan pembagian data 80% data latih (3.200 baris) dan 20% data uji independen (800 baris).

1. **Validasi Silang 5-Fold pada Data Latih:**
   Sebelum menyentuh data uji, model dievaluasi menggunakan validasi silang bertingkat 5-fold:
   - **Regresi Logistik (Logistic Regression):** Rata-rata ROC-AUC = 0.8478, PR-AUC = 0.5107.
   - **Gradient Boosting Classifier:** Rata-rata ROC-AUC = 0.8348, PR-AUC = 0.4845.
2. **Alasan Pemilihan Model Regresi Logistik:**
   Regresi Logistik dipilih sebagai model utama karena unggul pada performa validasi silang dan memberikan **interpretabilitas mutlak**. Bobot koefisien linier dapat dipetakan secara matematis menjadi kalimat penjelasan yang transparan kepada pengguna.
3. **Kalibrasi Probabilitas (Metode Platt Scaling):**
   Model machine learning sering kali menghasilkan estimasi probabilitas mentah yang terlalu percaya diri. Melalui teknik kalibrasi Platt Scaling (`CalibratedClassifierCV` dengan metode sigmoid), kurva keluaran diselaraskan dengan frekuensi kejadian riil:
   - Brier Score Sebelum Kalibrasi: `0.1641`
   - Brier Score Setelah Kalibrasi: `0.1001`
   - **Peningkatan Akurasi Probabilitas:** Kesalahan prediksi probabilitas berhasil ditekan sebesar **39,03%**.
4. **Pemilihan Ambang Keputusan Optimal ($T = 0.2094$):**
   Ambang keputusan standar ($0.50$) tidak cocok untuk masalah keselamatan transaksi karena data kelas berisiko bersifat minoritas (15,4%). Pada data sewa barang berharga, kerugian akibat pengguna berisiko yang lolos (*False Negative*) jauh lebih berbahaya daripada salah memperingatkan pengguna aman (*False Positive*). Dipilih ambang $T = 0.2094$ untuk menjamin tingkat penemuan (*Recall*) kasus berisiko mencapai $\ge 65\%$.

#### Tabel Perbandingan Performa Lengkap pada Data Uji Independen (800 Sampel)

Seluruh angka di bawah ini diambil secara aktual dari berkas artefak `ml/artifacts/metrics.json`:

| Model / Pendekatan | Ambang ($T$) | ROC-AUC | PR-AUC | Akurasi | Presisi | Recall | F1-Score | Brier Score | Matriks Konfusi [TN, FP, FN, TP] |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Dummy (Mayoritas)** | 0.50 | 0.5000 | 0.1538 | 84,62% | 0,00% | 0,00% | 0,00% | 0.1301 | `[[677, 0], [123, 0]]` |
| **Aturan Sederhana (Tepat Waktu < 0.70)** | - | 0.7951 | 0.4197 | 65,50% | 27,83% | 78,05% | 0.4103 | 0.1349 | `[[428, 249], [27, 96]]` |
| **Regresi Logistik Mentah** | 0.50 | 0.8293 | 0.5152 | 76,50% | 37,05% | 75,61% | 0.4973 | 0.1641 | `[[519, 158], [30, 93]]` |
| **Gradient Boosting** | 0.50 | 0.8135 | 0.4494 | 84,88% | 51,61% | 26,02% | 0.3459 | 0.1071 | `[[647, 30], [91, 32]]` |
| **Regresi Logistik Terkalibrasi (Model Terpilih)** | **0.2094** | **0.8292** | **0.5139** | **81,38%** | **43,01%** | **65,04%** | **0.5178** | **0.1001** | `[[571, 106], [43, 80]]` |

*Keterangan Matriks Konfusi Data Uji:* Dari total 123 transaksi berisiko aktual, model berhasil menangkap 80 kasus (*True Positive*), hanya melewatkan 43 kasus (*False Negative*), meloloskan 571 transaksi aman (*True Negative*), dan memberikan peringatan kehati-hatian pada 106 transaksi aman (*False Positive*).

#### Penjelasan Visualisasi Grafik di Direktori `static/ml/`

1. **Kurva ROC (`static/ml/roc_curve.png`):**
   Menampilkan kemampuan model membedakan antara penyewa aman dan berisiko di seluruh variasi ambang. Nilai area di bawah kurva (ROC-AUC) sebesar `0.8292` membuktikan model memiliki daya diskriminasi yang andal jauh di atas tebakan acak ($0.50$).
2. **Kurva PR (`static/ml/pr_curve.png`):**
   Memetakan hubungan presisi terhadap recall pada data kelas minoritas. Nilai PR-AUC sebesar `0.5139` mengonfirmasi keunggulan model lebih dari 3 kali lipat dibandingkan baseline acak ($0.1538$).
3. **Kurva Kalibrasi Probabilitas (`static/ml/calibration_curve.png`):**
   Memperlihatkan perbandingan probabilitas prediksi terhadap proporsi empiris nyata. Garis model terkalibrasi menempel rapat pada garis diagonal ideal $45^\circ$, menandakan nilai probabilitas mencerminkan risiko riil.
4. **Matriks Konfusi (`static/ml/confusion_matrix.png`):**
   Visualisasi sebaran klasifikasi pada ambang operasional $T = 0.2094$, mempertegas minimnya angka *False Negative* untuk keselamatan pemilik barang.
5. **Tingkat Pengaruh Fitur (`static/ml/feature_importance.png`):**
   Grafik batang yang menunjukkan besaran koefisien dan uji permutasi. Fitur `rasio_tepat_waktu` menduduki pengaruh terbesar dalam menurunkan probabilitas risiko transaksi.

### C6 Operasi Inferensi pada Alur Transaksi

Proses inferensi dijalankan secara otomatis saat mahasiswa menyewa barang atau membuka halaman profil kepercayaan:

```text
DIAGRAM INFERENSI DAN PENGHITUNGAN SKOR:

Database Transaksi (ORM)
        |
        v
[ apps/trust/services.py: compute_features(user) ]
  Ekstraksi 8 Fitur Perilaku (Bebas Atribut Sensitif)
        |
        +---> Apakah Pengguna Baru (< 3 Sewa Selesai)?
        |       |
        |       +--- YA ---> Skor Dasar: 60 (Cold Start)
        |                    Status: 'Pengguna baru'
        |                    Faktor: 'Pengguna baru (< 3 sewa selesai)'
        |
        v TIDAK (>= 3 Sewa Selesai)
[ StandardScaler ]  --- Normalisasi nilai fitur: z = (x - mu) / sigma
        |
        v
[ Calibrated Logistic Regression ]  --- Menghitung probabilitas risiko P
        |
        v
[ Transformasi Skor Kepercayaan ]
  Skor Mentah = round((1 - P) * 100)
  Rentang: 0 sampai 100
        |
        v
[ Penghitungan 3 Faktor Penjelas ]
  trust_impact = - (koefisien * z)
  Ambil 3 fitur dengan |trust_impact| terbesar
  Format menjadi kalimat Bahasa Indonesia yang ramah
        |
        v
[ Evaluasi Hak Akses & Batas Nilai ]
  Skor >= 75: Sangat Tepercaya (Maksimal Rp5.000.000)
  Skor >= 60: Tepercaya (Maksimal Rp2.000.000)
  Skor < 60:  Baru / Terbatas (Maksimal Rp750.000)
        |
        v
Apakah ada Penimpaan Admin (override_score)?
  YA   ---> Gunakan override_score + tampilkan alasan staf
  TIDAK ---> Gunakan Skor Model Machine Learning
```

1. **Penanganan Kasus Pengguna Baru (Cold Start):**
   Mahasiswa dengan riwayat sewa kurang dari 3 transaksi (`completed_rentals < 3`) **tidak diproses oleh model regresi logistik** untuk menghindari bias statistik akibat kurangnya sampel. Pengguna baru otomatis menerima skor awal `60`, status `Pengguna baru`, dan batas sewa barang maksimal Rp750.000.
2. **Formula Skor Kepercayaan Mahasiswa:**
   Bagi pengguna dengan $\ge 3$ sewa selesai, model memprediksi probabilitas risiko bermasalah $P \in [0.0, 1.0]$. Skor kepercayaan dihitung secara terbalik:
   $$\text{Skor Kepercayaan} = \text{round}((1.0 - P) \times 100)$$
   Pengguna dengan probabilitas risiko rendah ($P = 0.05$) akan memperoleh skor tinggi `95`. Sebaliknya, pengguna dengan risiko tinggi ($P = 0.40$) akan memperoleh skor `60`.
3. **Rumus Tiga Faktor Penjelas Personal:**
   Pengaruh masing-masing fitur dihitung secara transparan:
   $$z_{\text{val}} = \frac{x_i - \mu_i}{\sigma_i}$$
   $$\text{trust\_impact}_i = - (\text{coef}_i \times z_{\text{val}})$$
   Tiga fitur dengan nilai absolut $|\text{trust\_impact}|$ terbesar disajikan menjadi 3 kalimat bahasa Indonesia (misalnya: *"Rasio tepat waktu 100% menaikkan skor"*, *"Tidak ada catatan sengketa transaksi menaikkan skor"*).
4. **Penimpaan Manual Admin (Human Oversight):**
   Jika staf kampus menemukan bukti khusus di lapangan (misalnya mahasiswa baru saja menyelesaikan sengketa damai), admin dapat menentukan `override_score` melalui dasbor staf. Nilai penimpaan ini otomatis menjadi `effective_score` yang berlaku di seluruh platform, disertai pencatatan alasan operasional di `TrustScoreHistory`.

### C7 Mekanisme Pembelajaran Berkelanjutan dari Data Nyata

Platform dirancang untuk berevolusi secara berkelanjutan dari data transaksi riil tanpa risiko kerusakan performa:

```text
DIAGRAM PEMBELAJARAN BERKELANJUTAN (CONTINUOUS LEARNING):

Checkout Sewa
      |
      v
[ Snapshot Fitur & Prediksi ]
  Disimpan di TrustTrainingExample (source='live', label=None)
      |
      v
Sewa Mencapai Status Terminal (Selesai / Sengketa / Batal)
      |
      v
[ Pelabelan Otomatis ]
  Label = 1 (Jika telat > 1 hari, ada potongan kerusakan, atau sengketa)
  Label = 0 (Jika berjalan lancar)
      |
      v
[ Pemeriksaan Ambang Data Riil ]
  Apakah sampel berlabel >= 200 DAN kasus positif >= 20?
      |
      +--- BELUM ---> Pelatihan ulang ditolak (mencegah overfitting)
      |
      v SUDAH
[ Pembagian Data Berbasis Waktu (Time-based Split 80/20) ]
  80% Data Kronologis Lama -> Data Latih
  20% Data Kronologis Baru -> Data Uji
      |
      v
[ Pelatihan Model Kandidat Baru ]
      |
      v
[ Gerbang Promosi Ketat (Promotion Gate) ]
  1. PR-AUC kandidat >= PR-AUC model aktif - 0.02
  2. Brier Score kandidat <= Brier Score model aktif + 0.01
      |
      +--- GAGAL  ---> Model kandidat ditolak, model aktif dipertahankan
      |
      v LOLOS
[ Promosi Model & Pengarsipan Versi ]
  Simpan artefak ke ml/artifacts/versions/<version>/
  Perbarui TrustModelVersion (is_active=True)
  Kosongkan cache model (clear_model_cache())
```

- **Penyimpanan Snapshot Fitur (`record_training_snapshot`):**
  Saat penyewa mengajukan pesanan, sistem menyimpan snapshot 8 fitur dan prediksi risiko saat itu ke model `TrustTrainingExample` dengan status label kosong (`label_problem = None`). Ini mencegah terjadinya kebocoran target di masa depan.
- **Pelabelan Otomatis Terminal (`label_training_example_for_rental`):**
  Saat pesanan mencapai status terminal (`selesai`, `sengketa`, `dibatalkan`), fungsi pelabelan memeriksa ada tidaknya keterlambatan $> 1$ hari, biaya kerusakan, atau sengketa untuk menetapkan label biner secara objektif.
- **Ambang Perlindungan Data Riil:**
  Pelatihan ulang hanya diizinkan apabila telah terkumpul minimal $200$ contoh riil (`TRUST_MIN_REAL_EXAMPLES`) dan minimal $20$ contoh berlabel positif (`TRUST_MIN_POSITIVES`).
- **Status Basis Data Aktual Saat Ini:**
  Berdasarkan verifikasi perintah langsung pada database produksi:
  - Total `TrustTrainingExample`: **10 baris**
  - Sampel telah berlabel: **7 baris** (1 kasus positif/bermasalah, 6 kasus negatif/lancar)
  - Sampel belum berlabel (transaksi aktif): **3 baris**
  - **Kesimpulan Status Proteksi:** Ambang batas $n_{\text{real}} \ge 200$ dan $n_{\text{pos}} \ge 20$ **belum terpenuhi**. Sistem secara otomatis mengaktifkan gerbang perlindungan dan menolak pelatihan ulang prematur guna mencegah model menghafal segelintir data (*overfitting*). Versi model aktif saat ini adalah `v1.0-logreg-calibrated`.
- **Simulasi Alur Retraining (`ml/demo_retrain.py`):**
  Skrip simulasi mendemonstrasikan aliran 250 data transaksi baru, membaginya secara kronologis 80/20, melatih model kandidat, mengevaluasi gerbang promosi, dan mengarsipkan artefak model baru secara otomatis.
- **Mekanisme Rollback Cepat:**
  Jika model baru menunjukkan anomali di lingkungan produksi, administrator dapat menjalankan perintah tunggal:
  ```bash
  python manage.py rollback_trust_model
  ```
  Sistem akan segera memulihkan versi stabil sebelumnya dan mengosongkan cache memori tanpa waktu henti (*zero downtime*).

### C8 Batasan Etika, Penanganan Bias, dan Kedaulatan Manusia

1. **Ketergantungan Awal pada Data Sintetis:**
   Data sintetis awal digunakan sebagai jembatan *cold start* agar platform memiliki sistem mitigasi risiko sejak hari pertama. Namun, manajemen menyadari bahwa data sintetis tidak mencakup dinamika sosial kampus yang kompleks. Oleh karena itu, sistem dirancang untuk bertransisi ke data riil seiring bertambahnya volume transaksi.
2. **Mitigasi Bias dan Lingkaran Umpan Balik (Feedback Loop):**
   Pengguna dengan skor rendah dapat terjebak dalam lingkaran setan jika tidak diberi kesempatan memperbaiki reputasi. Sistem mengatasi masalah ini dengan:
   - Tetap mengizinkan pengguna baru atau bereputasi rendah menyewa barang berbiaya terjangkau ($\le \text{Rp750.000}$).
   - Setiap transaksi sukses tanpa pelanggaran langsung meningkatkan rasio tepat waktu dan menaikkan skor pada transaksi berikutnya.
3. **Kedaulatan Keputusan Manusia (Human in the Loop):**
   Algoritma machine learning pada platform ini berfungsi sebagai **alat pendukung keputusan (decision support system)**, bukan penentu mutlak nasib pengguna:
   - Rekomendasi penolakan KTM selalu dapat ditinjau ulang oleh staf manusia.
   - Sengketa barang selalu diselesaikan melalui musyawarah dengan mediasi staf admin.
   - Pengguna berhak mengajukan klarifikasi jika merasa skor kepercayaannya tidak sesuai dengan fakta lapangan.

### C9 Panduan Eksekusi Teknis dan Interpretasi Metrik

#### Perintah Operasional Machine Learning

```bash
# 1. Pembangkitan dataset sintetis 4.000 baris
python ml/generate_synthetic_data.py

# 2. Pelatihan model awal, kalibrasi, evaluasi, dan ekspor grafik
python manage.py train_trust_model

# 3. Simulasi alur pelatihan ulang dari stream 250 data nyata
python ml/demo_retrain.py

# 4. Pelatihan ulang resmi dari data transaksi database lokal
python manage.py retrain_trust_model

# 5. Pemulihan model aktif ke versi stabil sebelumnya
python manage.py rollback_trust_model
```

#### Cara Membaca Berkas Artefak `ml/artifacts/metrics.json`

Berkas `metrics.json` menyimpan catatan transparansi performa model:
- `positive_prevalence`: Proporsi kelas berisiko dalam populasi (nilai aktual: `0.154` atau 15,4%).
- `probability_calibration.improvement_percent`: Persentase perbaikan keandalan probabilitas melalui kalibrasi Platt (nilai aktual: `39.03%`).
- `threshold_selection.selected_threshold`: Nilai titik potong probabilitas untuk menandai risiko (nilai aktual: `0.2094`).
- `all_models_test_metrics.logistic_regression_calibrated.recall`: Kemampuan model menangkap kasus berisiko pada data uji (nilai aktual: `0.6504` atau 65,04%).
- `all_models_test_metrics.logistic_regression_calibrated.brier_score`: Rata-rata kuadrat selisih probabilitas terhadap label riil (nilai aktual: `0.1001`, semakin mendekati 0 semakin sempurna).

### C10 Glosarium Istilah dan Tanya Jawab Pengujian

#### Glosarium untuk Mahasiswa Non-ML

- **Machine Learning (Pembelajaran Mesin):** Teknik komputasi di mana program komputer belajar mengenali pola dari data masa lalu tanpa perlu diprogram aturan logikanya satu per satu.
- **Data Sintetis:** Data simulasi yang dibuat oleh algoritma matematika menyerupai karakteristik data asli, digunakan ketika data transaksi riil belum mencukupi.
- **Variabel Laten:** Sifat atau konsep tersembunyi yang tidak dapat diukur secara langsung (misalnya sifat kehati-hatian atau kejujuran seseorang), namun dapat diperkirakan dari perilaku yang terlihat.
- **Data Leakage (Kebocoran Data):** Kesalahan fatal dalam perancangan ML di mana informasi masa depan yang belum terjadi ikut digunakan untuk memprediksi masa lalu, menghasilkan model yang tampak pintar saat diuji tetapi gagal di dunia nyata.
- **ROC-AUC (Receiver Operating Characteristic - Area Under Curve):** Nilai antara 0,5 sampai 1,0 yang menunjukkan kemampuan model membedakan antara dua kelompok (penyewa aman vs berisiko). Nilai 0,8292 tergolong sangat baik.
- **PR-AUC (Precision-Recall Area Under Curve):** Metrik evaluasi yang fokus pada kelas minoritas (kasus berisiko). Menunjukkan seberapa konsisten model mengenali kasus bermasalah tanpa menghasilkan terlalu banyak alarm palsu.
- **Brier Score:** Ukuran ketepatan nilai probabilitas prediksi terhadap kejadian nyata (antara 0 sampai 1). Semakin kecil nilai Brier Score, semakin akurat probabilitas yang dihasilkan model.
- **Kalibrasi Platt (Platt Scaling):** Metode statistik untuk menyelaraskan keluaran model regresi agar angka persentase risiko mencerminkan peluang risiko riil di dunia nyata.
- **Ambang Keputusan (Threshold):** Batas nilai angka probabilitas di mana sistem mulai memutuskan untuk mengambil tindakan pengamanan.
- **Matriks Konfusi (Confusion Matrix):** Tabel 2x2 yang merinci perbandingan antara tebakan model dengan kenyataan sesungguhnya (True Positive, False Positive, True Negative, False Negative).
- **Overfitting:** Kondisi buruk di mana model terlalu menghafal detail data latih hingga kehilangan kemampuan mengenali data baru di masa depan.
- **Model Card:** Dokumen resmi yang mencatat identitas, tujuan penggunaan, batasan etika, dan metrik performa suatu model kecerdasan buatan.

#### Dua Belas Pertanyaan Penguji / Juri dan Jawaban Berbasis Data Aktual

1. **Mengapa memilih model Regresi Logistik terkalibrasi daripada model kompleks seperti Deep Learning atau Gradient Boosting?**  
   *Jawaban:* Pada validasi silang 5-fold, Regresi Logistik menghasilkan ROC-AUC (`0.8478`) dan PR-AUC (`0.5107`) yang lebih tinggi dibandingkan Gradient Boosting (`0.8348` dan `0.4845`). Selain itu, Regresi Logistik memberikan interpretabilitas mutlak di mana koefisien fitur dapat diterjemahkan langsung menjadi tiga kalimat alasan transparan bagi mahasiswa.

2. **Berapa prevalensi kasus bermasalah pada dataset dan bagaimana mengatasinya?**  
   *Jawaban:* Prevalensi kelas berisiko adalah 15,4% (616 dari 4.000 sampel). Ketidakseimbangan ini diatasi dengan mengevaluasi metrik PR-AUC (bukan hanya akurasi semu), serta menurunkan ambang keputusan operasional menjadi `0.2094` untuk memastikan kasus berisiko dapat dijaring secara optimal.

3. **Mengapa ambang keputusan diturunkan dari 0,50 menjadi 0,2094?**  
   *Jawaban:* Pada transaksi sewa barang mahasiswa bernilai jutaan rupiah, biaya *False Negative* (membiarkan pengguna berisiko tinggi merusak atau membawa kabur barang tanpa peringatan) jauh lebih fatal daripada *False Positive* (memberikan edukasi kehati-hatian pada pengguna aman). Ambang `0.2094` menjamin penangkapan 65,04% kasus berisiko pada data uji independen.

4. **Apa bukti bahwa model tidak mengalami overfitting?**  
   *Jawaban:* Selisih performa antara validasi silang pada data latih (ROC-AUC `0.8478`) dan pengujian pada data uji independen yang belum pernah dilihat (ROC-AUC `0.8292`) hanya berjarak 0,0186 (kurang dari 2%). Ini membuktikan model memiliki daya generalisasi yang stabil.

5. **Bagaimana platform membuktikan keadilan algoritma terhadap mahasiswa dari kampus atau daerah minoritas?**  
   *Jawaban:* Atribut nama kampus (`campus_name`), jurusan (`major`), jenis kelamin (`gender`), dan daerah asal (`region`) secara ketat dihapus dari masukan model (diverifikasi melalui fungsi pengecekan `assert sensitive_key not in features` pada `apps/trust/services.py:291-292`). Penilaian murni berbasis rekam jejak perilaku transaksi.

6. **Apa peran kalibrasi Platt Scaling dan berapa peningkatannya?**  
   *Jawaban:* Kalibrasi Platt menyelaraskan probabilitas keluaran dengan proporsi empiris nyata. Nilai Brier Score berhasil diturunkan dari `0.1641` menjadi `0.1001`, yang mencerminkan peningkatan akurasi probabilitas sebesar `39,03%`.

7. **Fitur apa yang paling berpengaruh terhadap penilaian kepercayaan pengguna?**  
   *Jawaban:* Berdasarkan koefisien model, `rasio_tepat_waktu` memiliki dampak proteksi terbesar terhadap penurunan risiko (koefisien `-0.7643`), diikuti oleh `rata_rata_rating_diterima` (koefisien `-0.5057`). Sebaliknya, keberadaan catatan sengketa menjadi faktor pemicu kenaikan risiko terbesar (koefisien `+0.2501`).

8. **Bagaimana sistem memperlakukan mahasiswa baru yang belum pernah bertransaksi?**  
   *Jawaban:* Diterapkan aturan *cold-start rule*. Pengguna dengan $< 3$ transaksi tidak dimasukkan ke dalam model ML, melainkan langsung diberi skor dasar netral `60` dengan batas transaksi maksimal Rp750.000 guna melindungi ekosistem secara proporsional tanpa menutup akses pemula.

9. **Apa yang terjadi jika model machine learning memberikan penilaian yang salah atau merugikan pengguna?**  
   *Jawaban:* Tersedia mekanisme pengawasan manusia (*Human in the Loop*). Staf admin kampus dapat memeriksa riwayat transaksi dan memberikan penimpaan nilai (`override_score`) yang disertai alasan operasional tercatat pada audit log.

10. **Bagaimana sistem mencegah penurunan kualitas saat model dilatih ulang dari data nyata?**  
    *Jawaban:* Diterapkan gerbang promosi otomatis (*promotion gate*) dengan dua syarat mutlak: model kandidat baru harus memiliki PR-AUC tidak boleh turun lebih dari 0,02 ($\text{PR-AUC}_{\text{baru}} \ge \text{PR-AUC}_{\text{aktif}} - 0.02$) dan nilai Brier Score tidak boleh memburuk lebih dari 0,01 ($\text{Brier}_{\text{baru}} \le \text{Brier}_{\text{aktif}} + 0.01$). Jika syarat ini gagal, model baru otomatis dibatalkan.

11. **Mengapa sistem saat ini belum melatih ulang model dengan data transaksi lokal?**  
    *Jawaban:* Berdasarkan pemeriksaan aktual database lokal saat ini, baru terdapat 10 data pelatihan (7 berlabel, dengan hanya 1 kasus positif). Sistem memiliki proteksi batas minimal $n_{\text{real}} \ge 200$ dan $n_{\text{pos}} \ge 20$ untuk mencegah fenomena penghafalan data kecil (*small data overfitting*).

12. **Apakah modul OCR KTM menjamin keaslian kartu mahasiswa?**  
    *Jawaban:* Tidak. Modul `ml/ktm_ocr.py` hanya mengekstraksi teks visual (NIM, nama, dan universitas) dari citra foto. Keaslian fisik (seperti hologram atau validitas status mahasiswa aktif di PDDikti) tetap berada di bawah wewenang konfirmasi administratif staf kampus.
