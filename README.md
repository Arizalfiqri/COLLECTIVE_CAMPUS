# Collective Campus

Platform sewa-menyewa dan jual-beli (thrift) perlengkapan kuliah antarmahasiswa berbasis Django 5 dan Machine Learning terkalibrasi untuk lingkungan kampus Indonesia. Mengusung arsitektur aman dengan verifikasi identitas mahasiswa (KTM), sistem pembayaran ditahan platform sampai barang kembali atau diterima, pembukuan berimbang (double-entry ledger), masa inspeksi 48 jam, serta model Machine Learning untuk skor kepercayaan pengguna.

---

## Fitur Utama & Keunggulan Platform
1. **Verifikasi KTM & Sinyal Email Kampus (.ac.id):** Akses transaksi aman yang terisolasi khusus mahasiswa aktif. Berkas fisik foto KTM terisolasi di direktori privat dan otomatis dihapus permanen dari server segera setelah ditinjau demi perlindungan privasi (UU No. 27/2022 PDP). Sinyal domain email resmi `.ac.id` yang terverifikasi menjadi penguat kepercayaan.
2. **Pembayaran Ditahan & Perlindungan Transaksi:** Pembayaran sewa dan jual beli ditahan oleh platform sampai barang kembali atau diterima via Midtrans Snap. Dana sewa baru dicairkan ke pemilik setelah barang dikembalikan dalam kondisi baik; dan pada jual beli, dana ditahan selama masa inspeksi 48 jam sebelum dicairkan ke penjual.
3. **Dokumentasi Kondisi Sebelum-Sesudah Pakai & Serah Terima:** Foto kondisi fisik barang saat serah terima awal dan saat pengembalian (sewa) atau saat penyerahan tatap muka di titik temu kampus ramai (jual beli) menjadi bukti objektif bebas bias jika terjadi sengketa.
4. **Machine Learning Trust Score:** Model probabilistik terkalibrasi (Logistic Regression + Platt Scaling) untuk memprediksi risiko sewa tanpa menggunakan atribut sensitif/demografis (bebas bias gender, kampus, atau jurusan).
5. **Modul Jual-Beli (Thrift Mahasiswa):** Wadah transaksi barang perlengkapan kuliah bekas dengan batas plafon harga berbasis reputasi penjual, penyaringan kata kunci barang terlarang, snapshot listing beku (data + hash SHA-256 foto), hak inspeksi 48 jam pembeli, sistem sengketa admin, ulasan dua arah, serta tawar harga terstruktur.

Katalog lengkap seluruh fitur dapat dibaca pada [docs/FEATURES.md](file:///c:/Mata%20Kuliah/Pekan%20Cangget/SEWA_MAHASISWA/docs/FEATURES.md).

---

## Prasyarat Sistem
- **Python:** Versi 3.11 atau lebih baru
- **Database:** PostgreSQL 14, 15, 16, 17, atau 18 (direkomendasikan) atau SQLite (pengujian cepat)
- **Node.js & npm:** Versi 18+ (untuk kompilasi Tailwind CSS)
- **OCR Engine (Opsional):** Tesseract OCR (untuk ekstraksi otomatis teks pada KTM)
- **Git**

---

## Panduan Instalasi & Menjalankan Proyek

### 1. Kloning & Virtual Environment
```bash
git clone <url-repositori>
cd SEWA_MAHASISWA

# Buat virtual environment baru
python -m venv .venv

# Aktifkan virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# Atau Windows Command Prompt:
# .venv\Scripts\activate.bat
```

### 2. Instal Dependensi Python
```bash
pip install -r requirements.txt
```

### 3. Konfigurasi Lingkungan (.env)
Salin berkas template lingkungan:
```bash
copy .env.example .env
```
Sesuaikan konfigurasi di `.env` (atur koneksi database PostgreSQL, kunci Midtrans Sandbox, dan parameter platform).

> **PENTING — KEAMANAN KREDENSIAL:**
> Jangan pernah menuliskan akun atau kata sandi di repositori publik atau commit git. Folder `docs/local/` telah disiapkan dan otomatis diabaikan oleh `.gitignore` untuk catatan akun lokal pengembang. Sebelum hosting publik: hapus atau nonaktifkan semua akun demo dan ganti seluruh kata sandi admin.

### 4. Build Aset CSS (Tailwind CSS)
Satu perintah untuk mengompilasi seluruh kelas CSS (Tailwind CSS) ke `static/css/styles.css`:
```bash
npm run build:css
```
Untuk mode pengembangan aktif (otomatis kompilasi saat template HTML diubah):
```bash
npm run watch:css
```
*(Wajib dijalankan setiap kali ada kelas Tailwind baru yang ditambahkan di berkas template HTML).*

### 5. Migrasi Database
```bash
python manage.py migrate
```

### 6. Inisialisasi Data Awal Platform (Idempoten & Bersih)
Perintah ini mengisi 8 kategori barang resmi dan konfigurasi dasar platform tanpa membuat akun atau barang palsu:
```bash
python manage.py init_platform
```

### 7. Membuat Akun Superuser (Admin)
```bash
python manage.py createsuperuser
```

### 8. Data Demo untuk Pengembangan Lokal (Opsional)
Hanya dapat dijalankan di lingkungan lokal saat `DEBUG=True`:
```bash
python manage.py seed_demo
```
*Catatan: Perintah ini idempoten dan tidak akan pernah menghapus data nyata yang sudah ada di database.*

### 9. Menjalankan Server Pengembangan (Dev Server)
Untuk mengompilasi CSS terbaru secara otomatis dan langsung menjalankan server pengembangan:
```powershell
.\run.ps1
```
Atau secara manual:
```bash
npm run build:css
python manage.py runserver
```
Akses platform melalui browser:
- **Halaman Utama:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Katalog Barang:** [http://127.0.0.1:8000/barang/](http://127.0.0.1:8000/barang/)
- **Panel Admin:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) (atau sesuai `ADMIN_URL` di `.env`)

---

## Menjalankan Mode Produksi Lokal (Waitress & WhiteNoise)

Collective Campus dirancang siap produksi. Anda dapat menguji performa produksi di lingkungan lokal Windows menggunakan WSGI server **Waitress** dengan `DEBUG=False` dan kompresi aset statis **WhiteNoise**:

### 1. Kumpulkan Berkas Statis (Collectstatic)
```bash
python manage.py collectstatic --noinput
```

### 2. Jalankan Server Waitress
```bash
waitress-serve --port=8000 config.wsgi:application
```
- Berkas statis (`/static/`) dilayani efisien dan terkompresi oleh **WhiteNoise**.
- Berkas media publik (foto barang di `/media/`) dilayani aman via Django saat `SERVE_MEDIA_LOCAL=True`.
- **Privasi Terjamin:** Berkas privat (`private_media/` seperti foto KTM) **TIDAK PERNAH** memiliki URL publik dan tidak dapat diakses secara langsung dari browser.
- *Catatan Hosting Publik:* Pada server hosting publik sebenarnya (Nginx/Caddy/Cloudflare R2/Amazon S3), direktori media publik diarahkan langsung ke reverse proxy atau object storage.

---

## Tabel Variabel Lingkungan (.env)

| Variabel | Tipe Data | Nilai Bawaan (Default) | Deskripsi & Rekomendasi |
| :--- | :--- | :--- | :--- |
| `DEBUG` | Boolean | `False` | Wajib `False` di produksi. `True` hanya untuk dev lokal. |
| `SECRET_KEY` | String | *(Wajib saat DEBUG=False)* | Kunci kriptografi Django. Minimal 50 karakter acak unik. |
| `ALLOWED_HOSTS` | List | `127.0.0.1,localhost` | Daftar domain/IP yang diizinkan mengakses aplikasi. |
| `CSRF_TRUSTED_ORIGINS` | List | `http://127.0.0.1:8000,...` | Asal domain tepercaya untuk validasi token CSRF formulir. |
| `ADMIN_URL` | String | `admin/` | Path URL kustom panel admin (contoh: `kelola-collective/`). |
| `DATABASE_URL` | String | `sqlite:///db.sqlite3` | URI koneksi DB (`postgres://user:pass@host:5432/dbname`). |
| `SERVE_MEDIA_LOCAL` | Boolean | `True` | Mengizinkan penyajian media publik saat uji produksi lokal. |
| `USE_HTTPS` | Boolean | `False` | Aktifkan (`True`) saat situs telah terpasang sertifikat SSL/TLS. |
| `SECURE_SSL_REDIRECT` | Boolean | `False` | Mengalihkan otomatis seluruh traffic HTTP ke HTTPS. |
| `SESSION_COOKIE_SECURE`| Boolean | `False` | Hanya mengirim cookie sesi melalui koneksi HTTPS yang aman. |
| `CSRF_COOKIE_SECURE` | Boolean | `False` | Hanya mengirim cookie CSRF melalui koneksi HTTPS yang aman. |
| `SECURE_HSTS_SECONDS` | Integer | `31536000` | Header HTTP Strict Transport Security (1 tahun). |
| `EMAIL_BACKEND` | String | `console.EmailBackend` | Backend pengiriman email (console saat dev, smtp saat live). |
| `EMAIL_HOST` | String | `smtp.gmail.com` | Host server SMTP email. |
| `EMAIL_PORT` | Integer | `587` | Port server SMTP (587 untuk TLS). |
| `EMAIL_USE_TLS` | Boolean | `True` | Mengaktifkan enkripsi TLS pada komunikasi email. |
| `EMAIL_HOST_USER` | String | `""` | Alamat email / username akun SMTP. |
| `EMAIL_HOST_PASSWORD` | String | `""` | Kata sandi aplikasi (App Password) akun SMTP. |
| `DEFAULT_FROM_EMAIL` | String | `Collective Campus <no-reply@...>` | Nama pengirim email otomatis platform. |
| `SUPPORT_EMAIL` | String | `bantuan@collectivecampus.id` | Alamat email layanan bantuan yang tampil di halaman Kontak. |
| `MIDTRANS_SERVER_KEY` | String | `""` | Kunci server rahasia dari Midtrans Dashboard. |
| `MIDTRANS_CLIENT_KEY` | String | `""` | Kunci klien publik untuk Midtrans Snap SDK di frontend. |
| `MIDTRANS_IS_PRODUCTION`| Boolean | `False` | `False` untuk Sandbox simulator, `True` untuk transaksi nyata. |
| `MIDTRANS_ENABLED_PAYMENTS`| List | `dana,seabank_va,...` | Metode bayar aktif (DANA, SeaBank VA, Mandiri, QRIS). |
| `MIDTRANS_SNAP_MODE` | String | `popup` | Tampilan checkout Midtrans: `popup` atau `embed`. |
| `WHATSAPP_HANDOVER_ENABLED`| Boolean| `True` | Tampilkan kontak WhatsApp lawan bicara saat jendela serah terima. |
| `TESSERACT_CMD` | String | `""` | Path absolut ke biner `tesseract.exe` (jika tidak ada di PATH). |
| `KTM_DELETE_AFTER_DECISION`| Boolean | `True` | Otomatis hapus berkas fisik KTM setelah disetujui/ditolak (PDP). |
| `SITE_NAME` | String | `Collective Campus` | Nama merek platform yang tampil di seluruh template, email, dan metadata. |
| `SITE_SHORT_NAME` | String | `Collective` | Nama singkat platform untuk navbar dan admin header. |
| `SITE_LOGOTYPE_DARK` | String | `Collective` | Bagian teks gelap pada logotype merek. |
| `SITE_LOGOTYPE_ACCENT` | String | `Campus` | Bagian teks biru pada logotype merek. |
| `SITE_TAGLINE` | String | `Saling sewa, saling jual, saling bantu.` | Slogan resmi platform. |
| `SITE_DOMAIN` | String | `""` | Domain publik platform (kosong bawaan, tidak ditampilkan bila kosong). |
| `KONFIRMASI_BUDAYA` | String | `tidak` | Menampilkan kalimat budaya daerah Lampung jika disetel `ya`. |
| `SALE_COMMISSION_PERCENT`| Integer | `5` | Persentase komisi platform untuk transaksi jual beli. |
| `SALE_COMMISSION_MIN` | Integer | `2000` | Nilai komisi minimal platform untuk jual beli (Rp). |
| `PLATFORM_COMMISSION_PERCENT`| Integer | `8` | Persentase komisi operasional platform dari pokok sewa. |
| `PROTECTION_FEE_MIN` | Integer | `3000` | Iuran minimal Dana Gotong Royong perlindungan barang. |
| `FIELD_ENCRYPTION_KEY`| String | `""` | Kunci enkripsi Fernet (AES-128 URL-safe base64 32-byte) untuk nomor rekening. |
| `WITHDRAWAL_MIN` | Integer | `20000` | Batas minimal penarikan saldo dompet (dalam rupiah). |
| `TRUST_MIN_REAL_EXAMPLES`| Integer | `200` | Ambang minimal data transaksi nyata sebelum retrain model ML diizinkan. |
| `TRUST_MIN_POSITIVES`| Integer | `20` | Ambang minimal kasus bermasalah nyata sebelum retrain model ML diizinkan. |

---

## Sistem Dompet & Penarikan Dana (Payout)

> [!CAUTION]
> **Peringatan Kritis Keamanan — Pencadangan Kunci Enkripsi (`FIELD_ENCRYPTION_KEY`):**
> Kunci simetris `FIELD_ENCRYPTION_KEY` digunakan untuk mengenkripsi dan mendekripsi seluruh nomor rekening bank dan akun dompet digital mahasiswa di database. Kunci ini **WAJIB dicadangkan secara aman** di tempat penyimpanan rahasia terpisah (seperti password vault atau secret manager). **JANGAN PERNAH** menghapus atau mengganti kunci ini tanpa migrasi dekripsi database terlebih dahulu. Jika kunci ini hilang atau berganti secara tidak sengaja, seluruh nomor rekening yang tersimpan di database **TIDAK AKAN BISA DIDEKRIPSI KEMBALI** secara permanen.

Sistem dompet mahasiswa (`/dompet/`) mencatat seluruh mutasi saldo secara aman dan terhubung langsung ke buku besar akuntansi ganda (*double-entry ledger*):
- **Sumber Saldo Masuk:** Payout sewa barang pemilik (setelah komisi 8%), pengembalian saldo penyewa, denda kerusakan, dan kompensasi Dana Gotong Royong.
- **Pencairan Dana (Withdrawal):** Batas minimal penarikan diatur via `WITHDRAWAL_MIN` (bawaan Rp20.000). Pada rilis versi saat ini, pencairan diproses manual oleh staf admin ke rekening bank/dompet digital terdaftar (DANA, SeaBank, Mandiri, BCA, BRI, BNI).
- **Kesiapan Produksi:** Untuk lingkungan produksi penuh, alur penarikan ini dapat langsung dihubungkan ke API payout penyedia pembayaran (seperti Midtrans Iris) tanpa mengubah struktur buku besar.
- **Keamanan Data Perbankan:** Nomor rekening/dompet dienkripsi menggunakan kunci Fernet (`FIELD_ENCRYPTION_KEY`), tidak pernah ditulis ke log aplikasi, ditampilkan terselubung (*masked* `•••• 1234`), dan setiap akses pengungkapan nomor oleh staf admin dicatat secara ketat (*audited access log*).


---

## Machine Learning & Continuous Learning (Fase 7C)

Collective Campus menerapkan model probabilistik terkalibrasi (*Calibrated Logistic Regression* via Platt Scaling) untuk mengestimasi risiko transaksi dan skor kepercayaan pengguna (TrustScore) tanpa menggunakan atribut sensitif/demografis (bebas bias gender, kampus, jurusan, atau IPK).

### 1. Siklus Pembelajaran dari Data Nyata
- **Snapshot Otomatis:** Saat penyewa mengajukan sewa (`ajukan_sewa`), sistem menyimpan snapshot 8 fitur objektif pengguna ke model `TrustTrainingExample` (`source='live'`).
- **Pelabelan Idempoten Terminal State:** Saat transaksi sewa mencapai status akhir (lancar -> label 0; terlambat > 1 hari / denda kerusakan / sengketa / barang tidak kembali -> label 1), sistem melabeli data secara otomatis dan idempoten.
- **Pemisahan Data Backfill:** Data historis lampau diberi penanda `source='backfill'` dan secara bawaan dikecualikan dari set evaluasi retraining demi mencegah kebocoran data (*data leakage*).

### 2. Perintah Manajemen Retraining & Rollback
- **Retraining dengan Guardrail Ketat:**
  ```bash
  python manage.py retrain_trust_model
  ```
  *Guardrail:* Membatalkan retraining jika data nyata berlabel `< 200` (`TRUST_MIN_REAL_EXAMPLES`) atau kasus bermasalah `< 20` (`TRUST_MIN_POSITIVES`). Menggunakan time-based split 80/20. Model kandidat **HANYA** dipromosikan jika PR-AUC naik $\ge +0.01$ dan Brier score tidak memburuk.
  *Pilihan Argumen:*
  - `--force`: Mengabaikan batas data minimal (untuk pengujian/evaluasi cepat).
  - `--include-backfill`: Menyertakan data historis backfill.
  - `--dry-run`: Simulasi evaluasi tanpa menyimpan artefak atau mengubah status model di database.
- **Rollback Versi Model:**
  ```bash
  python manage.py rollback_trust_model --version=v1.0-logreg-calibrated
  ```
  Mengaktifkan kembali artefak model versi sebelumnya dan membersihkan cache in-memory seketika.
- **Demo Simulasi In-Memory (Untuk Penguji/Juri):**
  ```bash
  python ml/demo_retrain.py
  ```
  Mensimulasikan 250 transaksi sewa berlabel, alur time-split 80/20, evaluasi metrik PR-AUC/Brier, dan keputusan promosi secara in-memory tanpa memodifikasi database produksi.
- **Dashboard Staf:** Pantau metrik data nyata, riwayat versi artefak, serta pemicu evaluasi dan rollback di `/admin/model-skor/`.

---

## Panduan Beralih ke Kunci Midtrans Produksi

Saat platform siap dipublikasikan dan menerima transaksi nyata antarmahasiswa:

1. **Aktivasi Akun Produksi Midtrans:**
   - Masuk ke [Dashboard Midtrans](https://dashboard.midtrans.com/).
   - Pastikan proses verifikasi legalitas / KYC pedagang telah disetujui oleh Midtrans.
2. **Ubah Mode Environment ke Production:**
   - Di pojok kiri atas Dashboard Midtrans, alihkan switch dari **SANDBOX** ke **PRODUCTION**.
3. **Salin Kunci Produksi:**
   - Buka menu **Settings** > **Access Keys**.
   - Salin **Server Key** produksi (berawalan `Mid-server-...`).
   - Salin **Client Key** produksi (berawalan `Mid-client-...`).
4. **Perbarui Variabel di `.env` Server Produksi:**
   ```env
   MIDTRANS_IS_PRODUCTION=True
   MIDTRANS_SERVER_KEY=Mid-server-xxxxxxxxxxxxxxxxxxxx
   MIDTRANS_CLIENT_KEY=Mid-client-xxxxxxxxxxxxxxxxxxxx
   ```
5. **Konfigurasi Payment Notification URL (Webhook):**
   - Di Dashboard Midtrans, buka **Settings** > **Configuration**.
   - Isi **Payment Notification URL** dengan:
     `https://domain-resmi-anda.com/midtrans/webhook/`
   - Pastikan URL tersebut dapat diakses publik dengan respon HTTP 200 OK.

---

## Pencadangan & Pemulihan Data (Backup & Restore)

Platform menyediakan perintah manajemen khusus untuk mencadangkan database PostgreSQL dan seluruh berkas media tanpa mengekspos kata sandi atau kredensial rahasia:

### 1. Menjalankan Pencadangan Lengkap
```bash
python manage.py backup_data
```
Keluaran akan tersimpan di folder `backups/` (otomatis masuk `.gitignore`):
- Berkas SQL database: `backups/kampusrent_db_YYYYMMDD_HHMMSS.sql`
- Arsip berkas media: `backups/kampusrent_media_YYYYMMDD_HHMMSS.tar.gz`

### 2. Memulihkan Database (Restore)
Gunakan `psql` atau `pg_restore`:
```bash
# Untuk format dump SQL:
psql -h 127.0.0.1 -U <db_user> -d <db_name> -f backups/kampusrent_db_YYYYMMDD_HHMMSS.sql
```

### 3. Memulihkan Berkas Media
Ekstrak arsip tar.gz ke direktori proyek:
```bash
tar -xzf backups/kampusrent_media_YYYYMMDD_HHMMSS.tar.gz
```

---

## Menjalankan Suite Tes (Automated Testing)

Untuk memvalidasi integritas platform, jalankan seluruh suite tes unit:
```bash
python manage.py test
```
*Catatan Performa:* Pada konfigurasi pengujian, sistem otomatis menggunakan `MD5PasswordHasher` berkecepatan tinggi sehingga seluruh suite tes (~338+ pengujian menyeluruh) dapat selesai dalam hitungan detik.

---

## Audit Responsif Perangkat Nyata (Playwright Emulation — Fase 7H)

Platform menyediakan alat audit responsif otomatis menggunakan Playwright Chromium untuk menguji seluruh rute pada emulasi perangkat nyata:
- **Perangkat Teruji:** iPhone SE, iPhone 12, Pixel 5, iPad Mini (portrait), Viewport 320 px, Desktop 1024 px, dan Desktop 1280 px.
- **Pemeriksaan Standar:**
  - (a) Bebas scroll horizontal halaman (`scrollWidth <= innerWidth`)
  - (b) Keberadaan meta viewport
  - (c) Tipografi isi min. 14 px & input min. 16 px (mencegah auto-zoom iOS)
  - (d) Target sentuh tombol & aksi utama min. 44×44 px
  - (e) Batas gambar (tidak meluap kontainer)
  - (f) Teks bebas clipping/overlap
  - (g) Tabel menggulir internal (`overflow-x-auto`)
  - (h) Bebas obstruksi elemen fixed/sticky
  - (i) Modal & laci responsif serta dapat ditutup

### Menjalankan Audit Responsif:
```bash
# 1. Pastikan Playwright dan browser Chromium terpasang
pip install playwright
playwright install chromium

# 2. Jalankan audit menyeluruh (pastikan dev server aktif di http://127.0.0.1:8000)
# Opsional: Atur variabel AUDIT_USERNAME dan AUDIT_ADMIN_USERNAME jika menggunakan akun khusus
python scripts/responsive_audit.py

# Opsi parameter:
# Menjalankan tanpa screenshot untuk pengujian cepat:
python scripts/responsive_audit.py --no-screenshots

# Menjalankan untuk perangkat tertentu:
python scripts/responsive_audit.py --devices iphone_se,pixel_5
```
Laporan lengkap dan tangkapan layar akan tersimpan di `docs/local/responsive/REPORT.md` dan `docs/local/responsive/<rute>/<perangkat>.png`.

---

## Pemberitahuan Hukum & Perlindungan Data Pribadi
- Seluruh teks hukum (Syarat & Ketentuan, Kebijakan Privasi, dan Panduan Komunitas) telah diselaraskan dengan Undang-Undang Republik Indonesia Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi (UU PDP).
- **Pemberitahuan:** Sebelum publikasi komersial sungguhan, teks dokumen hukum disarankan ditinjau lebih lanjut oleh penasihat hukum berkualifikasi (lihat rujukan di [docs/LEGAL_DISCLAIMER.md](file:///c:/Mata%20Kuliah/Pekan%20Cangget/SEWA_MAHASISWA/docs/LEGAL_DISCLAIMER.md)).
