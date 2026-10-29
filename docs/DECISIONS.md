# Catatan Keputusan Teknis (Architectural Decisions) - KampusRent

Dokumen ini mencatat keputusan arsitektural dan teknis yang diambil selama pengembangan platform KampusRent sesuai panduan `PROJECT_SPEC.md`.

---

### [ADR-001] Pemilihan Database Cadangan (SQLite) untuk Fase 0
- **Status:** Diterima (Cadangan Sementara)
- **Konteks:** PostgreSQL belum terpasang/berjalan di lingkungan lokal host saat inisialisasi awal. Spesifikasi (`PROJECT_SPEC.md` Bagian 4) mengizinkan SQLite sebagai cadangan melalui `DATABASE_URL`.
- **Keputusan:** Menggunakan SQLite (`DATABASE_URL=sqlite:///db.sqlite3`) untuk memungkinkan eksekusi dan pengujian cepat di localhost tanpa memblokir pengembangan. Pengaturan menggunakan `django-environ` sehingga dapat langsung beralih ke PostgreSQL kapan saja dengan mengubah nilai `DATABASE_URL` di `.env` tanpa perubahan kode.

---

### [ADR-002] Metode Kompilasi Tailwind CSS
- **Status:** Diterima
- **Konteks:** Diperlukan kompilasi utilitas Tailwind CSS dengan token khusus dari `design.md` Bagian 4.
- **Keputusan:** Menggunakan `npm` dan Tailwind CSS CLI mandiri (`npm run build:css`). File input `static/css/input.css` dikompilasi menjadi `static/css/styles.css` (terminifikasi, ~14 KB), menghindari CDN untuk performa dan kestabilan offline.

---

### [ADR-003] Inisialisasi Custom User Model
- **Status:** Diterima
- **Konteks:** Django mewajibkan model User kustom diatur sebelum migrasi pertama dijalankan untuk mencegah konflik relasi auth.
- **Keputusan:** Membuat model `User(AbstractUser)` di `apps/accounts/models.py` dengan tambahan field `full_name`, `phone_whatsapp`, `avatar`, dan `is_verified_student`, serta model `StudentProfile` (1-1 ke User). Mendaftarkan `AUTH_USER_MODEL = 'accounts.User'` di `config/settings.py` sebelum mengeksekusi migrasi awal.

---

### [ADR-004] Penanganan Privasi Dokumen KTM (`private_media`)
- **Status:** Diterima
- **Konteks:** KTM mengandung data pribadi mahasiswa (NIM, nama, foto) yang dilindungi UU PDP No. 27 Tahun 2022.
- **Keputusan:** Menetapkan direktori `private_media/` yang sepenuhnya terpisah dari `MEDIA_ROOT`. File di folder ini tidak didaftarkan pada routing `urls.py` publik dan hanya dapat diakses melalui view terproteksi untuk admin di Fase 2.

---

### [ADR-005] Penundaan Pemasangan Tesseract OCR ke Fase 2
- **Status:** Diterima
- **Konteks:** Biner `tesseract` belum tersedia di sistem host saat inisialisasi Fase 0.
- **Keputusan:** Menyiapkan variabel `TESSERACT_CMD` di `.env` dan `config/settings.py`, serta pustaka `pytesseract` di virtual environment. Pemasangan biner engine dan pengetesan OCR akan dilakukan pada Fase 2 ketika fitur verifikasi KTM dibangun.

---

### [ADR-006] Revisi Desain v2 (Fase 1.5): Konsep Kertas dan Tinta (AGENT.md)
- **Status:** Diterima
- **Konteks:** Tampilan awal Fase 1 terkesan seperti template generik AI (emoji berlebihan, gradien, glassmorphism blur, kartu kembar, bug foto kartu, harga tanpa pemisah ribuan).
- **Keputusan:**
  1. Menerapkan konsep visual "kertas dan tinta" (`paper` `#F8F5EE`, `ink` `#141B34`, `brand` `#1F45C4`, `saffron` `#F2A900`) sepenuhnya datar (flat), tanpa gradien, glow, blur, maupun bayangan berwarna.
  2. Mengganti semua emoji dengan ikon Lucide SVG inline (`templates/partials/icon.html`).
  3. Mengganti tipografi dengan Bricolage Grotesque (Heading) dan Plus Jakarta Sans (Body), serta angka uang menggunakan tabular-nums.
  4. Menghapus lencana KTM dari kartu barang beranda (semua pemilik wajib terverifikasi, lencana hanya ditampilkan pada profil dan detail).
  5. Memperbaiki bug foto kartu dengan ilustrasi vektor SVG datar per kategori dan fallback otomatis bila gambar gagal dimuat.
  6. Menambahkan filter template `rupiah` (`Rp25.000`) dan helper avatar inisial tunggal bersih.
  7. Menata ulang beranda dengan hero asimetris 3 kartu produk, 1 baris kategori scrollable tanpa terpotong, grid 4 kolom, alur 5 langkah transaksi, dan seksi bukti blok gelap tunggal.

---

### [ADR-007] Anti Double-Booking: Recheck Transaksional dan Penolakan Otomatis Permintaan Bertabrakan (Fase 4)
- **Status:** Diterima
- **Konteks:** Pada platform rental bersama, banyak penyewa dapat mengajukan sewa pada rentang tanggal yang saling bertabrakan saat status masih `menunggu_persetujuan`. Jika pemilik menyetujui satu permintaan, permintaan lain pada tanggal yang sama tidak boleh dibiarkan menggantung atau memicu bentrokan ganda (double-booking).
- **Keputusan:**
  1. Seluruh transisi status sewa dipusatkan dalam satu modul state machine (`apps/rentals/services.py`) dengan decorator `@transaction.atomic`.
  2. Saat pemilik menyetujui sewa (`setujui_sewa`), sistem mengunci baris `Rental` dan `Item` menggunakan `select_for_update()`, lalu memeriksa ulang tabrakan terhadap status pemblokir (`menunggu_pembayaran`, `dibayar`, `sedang_disewa`, `menunggu_konfirmasi_pengembalian`, `sengketa`).
  3. Setelah sewa disetujui berpindah ke `menunggu_pembayaran`, semua permintaan lain untuk barang yang sama yang masih berstatus `menunggu_persetujuan` dan rentang tanggalnya bertabrakan otomatis diubah menjadi `ditolak` dengan alasan resmi: `"Tanggal sudah dipesan"`.
  4. Penyewa dari permintaan yang ditolak otomatis menerima notifikasi dalam aplikasi seketika.

---

### [ADR-008] Integrasi Midtrans Sandbox, Escrow, dan Pembukuan Berimbang Buku Besar (Fase 5A)
- **Status:** Diterima
- **Konteks:** Pembayaran sewa mahasiswa harus aman, terpercaya, dan kebal dari manipulasi frontend (client-side status tampering). Selain itu, seluruh pergerakan dana sewa, penahanan deposit jaminan, dan iuran dana proteksi harus diaudit dengan pembukuan ganda (double-entry ledger) yang memenuhi invarian ketat: $\sum \text{Masuk} = \sum \text{Keluar}$.
- **Keputusan:**
  1. **Sumber Kebenaran Tunggal:** Status pembayaran diverifikasi langsung ke API Midtrans (`CoreApi.transactions.status`) menggunakan `order_id` unik (`KR-<kode>-<nomor>`), atau melalui webhook resmi yang tervalidasi signature key SHA-512. Frontend tidak pernah dipercaya untuk mengubah status pembayaran.
  2. **Idempotensi & Kunci Transaksi:** Transisi ke status `dibayar`, pembuatan `DepositHold`, dan pencatatan `LedgerEntry` mutasi masuk dijalankan di dalam `@transaction.atomic` dengan `select_for_update()`. Pemanggilan berulang (misal dari webhook ganda atau klik berkali-kali) aman dan tidak menduplikasi data.
  3. **Pemisahan Escrow & Model Komisi:** Pendapatan platform murni berasal dari komisi `PLATFORM_COMMISSION_PERCENT` (8%) dari sewa pokok yang dipotong dari bagian pemilik. Iuran proteksi kerusakan ringan (`masuk_dana_proteksi`) dialokasikan terpisah ke cadangan dana bersama dan tidak dihitung sebagai keuntungan langsung platform.
  4. **Invarian Wajib Buku Besar:** Untuk setiap sewa yang diselesaikan (`settle_rental_funds`) maupun dibatalkan setelah bayar (`process_cancellation_after_payment`), total `masuk_*` dipastikan persis seimbang dengan total `keluar_*`. Panel admin Django memvalidasi dan menampilkan badge audit status invarian ("Seimbang").
  5. **Aturan Pembatalan Pasca-Bayar:**
     - Dibatalkan oleh pemilik: refund penuh (100% sewa + deposit + proteksi) ke penyewa.
     - Dibatalkan oleh penyewa > 24 jam sebelum `start_date`: refund penuh (100%) ke penyewa.
     - Dibatalkan oleh penyewa $\le$ 24 jam sebelum `start_date`: 20% dari sewa pokok dialokasikan ke pemilik sebagai kompensasi pembatalan mendadak, sisanya di-refund ke penyewa.
  6. **Privasi Kontak Bertahap:** Nomor telepon/WhatsApp kedua pihak disamarkan penuh sebelum pembayaran berhasil dan baru dibuka dengan tautan langsung `wa.me` setelah transaksi berstatus `dibayar`.


---

### [ADR-009] Alur Serah Terima, Pengembalian, Sengketa, dan Penegakan Invarian Buku Besar (Fase 5B)
- **Status:** Diterima
- **Konteks:** Fase 5B mengimplementasikan siklus transaksi fisik barang antarmahasiswa: penjadwalan temu kampus, dokumentasi kondisi visual (sebelum, serah terima, sesudah), perlindungan privasi foto dan masa retensi (GDPR/UU PDP), konfirmasi jaminan fisik KTM, perhitungan keterlambatan dan denda, alur pengembalian dan arbitrase sengketa, otomasi penanganan barang tidak dikembalikan (sita deposit, suspend akun, blacklist NIM, dan klaim dana proteksi simulasi), serta ulasan dan skor kepercayaan berbasis performa nyata.
- **Keputusan:**
  1. **Jadwal & Titik Temu Kampus:**
     - Pemilik dan penyewa dapat saling mengusulkan jadwal serah terima pada status dibayar.
     - Validasi titik temu: Jika penyewa dan pemilik berasal dari kampus berbeda (lintas kampus), sistem mewajibkan pemilihan titik temu publik (is_public=True) yang ramai demi keamanan kedua pihak.
     - Pengingat serah terima dikirim otomatis pada H-1 waktu temu melalui command process_deadlines.
  2. **Dokumentasi Kondisi & Privasi Foto:**
     - Foto kondisi sebelum (sebelum): Pemilik wajib mengunggah minimal 2 foto sebelum serah terima dapat dikonfirmasi.
     - Foto serah terima (serah_terima): Diambil langsung di dalam aplikasi (WebRTC getUserMedia dengan akses kamera ponsel dan fallback unggah file standar di desktop/mobile).
     - Persetujuan foto (handover_photo_consent_at): Pengambilan foto serah terima diblokir jika penyewa belum menyetujui klausa persetujuan foto pada perjanjian digital sewa.
     - Penyimpanan privat & proteksi IDOR: Seluruh foto kondisi disimpan di luar MEDIA_URL pada direktori privat (condition_photos/private/), dikompresi maksimal 1280 px (JPEG 80%), dan hanya dilayani melalui view terproteksi (rental_photo_serve_view) dengan header Cache-Control: no-store, private yang memvalidasi otorisasi peserta sewa atau admin.
     - Retensi & Pembersihan Otomatis: Command berkala purge_handover_photos menghapus file fisik dan record foto serah terima setelah HANDOVER_PHOTO_RETENTION_DAYS (30 hari) sejak sewa selesai. Pembersihan bersifat idempoten dan dikecualikan jika sewa memiliki sengketa aktif/tercatat.
  3. **Penahanan KTM (Identitas Fisik):**
     - Jika barang mensyaratkan jaminan KTM (item.require_ktm_held = True), kedua pihak wajib mengonfirmasi penyerahan fisik KTM (ktm_held_confirmed_at) sebelum status berpindah ke sedang_disewa.
     - Saat pengembalian kondisi baik disetujui, konfirmasi pengembalian KTM (ktm_returned_confirmed_at) wajib tercatat.
  4. **Pengembalian & Penyelesaian Escrow:**
     - Penyewa mengajukan pengembalian dengan minimal 2 foto kondisi sesudah (sesudah).
     - Keterlambatan dihitung otomatis per hari penuh (late_days) dengan tarif denda 50% dari harga sewa harian (late_fee = late_days * round(price_per_day * 0.5)), dibatasi maksimal sebesar sisa deposit.
     - Pemilik dapat mengonfirmasi pengembalian kondisi baik (menyelesaikan sewa dan mencairkan escrow via settle_rental_funds) atau melaporkan masalah/kerusakan dengan mengusulkan nominal potongan deposit (maksimal sisa deposit).
     - Penyewa dapat langsung menyetujui potongan untuk menyelesaikan transaksi seketika tanpa eskalasi admin.
     - Konfirmasi pengembalian otomatis terjadi setelah AUTO_CONFIRM_RETURN_HOURS (48 jam) jika pemilik tidak memberikan respons.
  5. **Penanganan Kasus Barang Tidak Dikembalikan (Non-Return):**
     - Pada status sedang_disewa, jika end_date + NON_RETURN_GRACE_HOURS (48 jam) terlewati tanpa pengembalian, command process_deadlines otomatis:
       a. Membuka Dispute kategori barang tidak dikembalikan.
       b. Menyita seluruh deposit jaminan untuk dialihkan ke saldo pemilik (keluar_deposit_ke_pemilik).
       c. Membekukan akun penyewa (User.is_suspended = True).
       d. Memasukkan NIM mahasiswa penyewa ke BlacklistedNim untuk mencegah pendaftaran ulang di masa depan.
       e. Mengirim notifikasi darurat kepada kedua belah pihak.
     - Admin dapat menyetujui klaim dana proteksi simulasi (maksimal 50% estimasi nilai barang dikurangi deposit yang telah disita) dengan entri buku besar berimbang (masuk_klaim_proteksi dan keluar_kompensasi_pemilik), mempertahankan invarian total Masuk = total Keluar.
  6. **Ulasan & Skor Kepercayaan Dinamis:**
     - Setelah sewa berstatus selesai, kedua pihak dapat memberikan 1 kali ulasan (rating 1-5, catatan maksimal 300 karakter). Ulasan bersifat permanen setelah dikirim dan tampil di halaman profil publik dan detail barang.
     - Fungsi recompute_trust_score(user) memperbarui metrik riwayat sewa (total selesai, rasio tepat waktu, frekuensi sengketa) secara objektif pada tabel TrustScore.

---

### [ADR-010] Model Machine Learning Skor Kepercayaan, Kalibrasi Probabilitas, dan Kepatuhan Etika Algoritmik (Fase 6)
- **Status:** Diterima
- **Konteks:** Fase 6 mengimplementasikan sistem penaksiran risiko sewa dan perhitungan skor kepercayaan pengguna (*AI Trust Score*). Ekosistem awal belum memiliki puluhan ribu data riwayat sewa nyata dengan label sengketa/kerusakan/keterlambatan, sehingga diperlukan metodologi data sintetis berbasis variabel laten keandalan yang jujur, transparan, dan tidak bocor target (*target leakage*). Sistem harus dapat dipertanggungjawabkan di hadapan juri teknis ML, menjunjung privasi mahasiswa (UU No. 27/2022 tentang Perlindungan Data Pribadi), serta mengutamakan interpretabilitas (*explainability*) daripada *black-box* yang rumit.
- **Keputusan:**
  1. **Pembangkitan Data Sintetis & Penghapusan Fitur Konstan:**
     - Data sintetis (4.000 sampel, *random state* 42) dibangkitkan dari distribusi laten keandalan $z \sim \mathcal{N}(0, 1)$ yang memetakan perilaku historis dan label target `bermasalah_berikutnya` (proporsi ~15,4%) dengan *noise* logistik terkalibrasi sehingga terdapat *overlap* realistis antarkelas tanpa pemisahan sempurna (*no perfect separation*).
     - **Penghapusan `status_ktm`:** Fitur status verifikasi KTM dihapus dari model karena pada populasi mahasiswa aktif yang bertransaksi, nilai fitur ini hampir konstan (variansi mendekati nol, >98% berstatus terverifikasi). Memasukkan fitur nyaris konstan berisiko menimbulkan *spurious correlation* dan membingungkan pembobotan fitur linear.
     - **Pencegahan Target Leakage:** Seluruh 8 fitur prediktif hanya dihitung dari riwayat sebelum transaksi sewa yang dievaluasi.
  2. **Pemilihan Model & Kriteria Evaluasi:**
     - Menguji 4 model dengan 80/20 *stratified split* dan 5-fold *stratified cross-validation*: `DummyClassifier` (prior), `RuleBaseline` (rasio tepat waktu < 0,7), `LogisticRegression`, dan `GradientBoostingClassifier`.
     - `LogisticRegression` dipilih sebagai model produksi karena mencatatkan performa CV ROC-AUC tertinggi (0,8478 ± 0,0169 vs Gradient Boosting 0,8348 ± 0,0178) serta PR-AUC 0,5139 (vs Gradient Boosting 0,4494), dengan keunggulan mutlak berupa transparansi matematis (*closed-form linear weights*) yang memungkinkan *feature attribution* langsung tanpa aproksimasi SHAP/LIME yang lambat.
  3. **Kalibrasi Probabilitas (Platt Scaling):**
     - Model mentah dikalibrasi menggunakan `CalibratedClassifierCV(method='sigmoid', cv='prefit')` pada data validasi.
     - Kalibrasi berhasil menurunkan Brier score dari 0,1641 ke 0,1001 (penurunan kesalahan probabilitas sebesar 39,0%), menjamin bahwa probabilitas risiko $P(\text{bermasalah})$ memiliki interpretasi frekuentis yang akurat dan dapat ditransformasikan secara linier menjadi skor kepercayaan $0 - 100$.
  4. **Ambang Batas Keputusan (*Decision Threshold*):**
     - Ambang batas probabilitas diturunkan dari 0,50 ke **0,209** pada data validasi demi memastikan *safety margin* dengan target *recall* kelas berisiko minimal 0,70.
     - Pada data uji independen, ambang ini menghasilkan *recall* 0,6504 dan *precision* 0,4301. Trade-off ini diterima secara sadar: sistem lebih memilih mendeteksi potensi risiko lebih awal daripada meloloskan akun berisiko tinggi.
  5. **Anti-Bias, Privasi Data, dan Penolakan Atribut Sensitif:**
     - Model secara tegas **TIDAK MENGGUNAKAN** atribut sensitif demografis seperti jenis kelamin, agama, suku/asal daerah, kampus, fakultas, maupun program studi.
     - Penilaian murni berbasis performa transaksi objektif: riwayat ketepatan waktu, ulasan dari rekan mahasiswa, frekuensi sengketa, dan rasio pembatalan sepihak.
  6. **Penanganan Pengguna Baru (*Cold-Start Protection*):**
     - Pengguna dengan kurang dari 3 transaksi selesai diklasifikasikan sebagai `is_new_user=True`.
     - Model ML dilewati (*bypassed*) dan sistem memberikan skor default netral **60** dengan label informatif *"Pengguna baru"*, mencegah penalti atau bias probabilitas akibat riwayat yang belum konvergen.
  7. **Interpretabilitas & Human-in-the-Loop Override:**
     - Setiap inferensi menghasilkan 3 kalimat penjelas faktor teratas (*top factors*) dalam Bahasa Indonesia sederhana berbasis kontribusi $w_i \times x_{\text{standardized}}$, memberikan transparansi penuh kepada mahasiswa mengenai alasan di balik skor mereka.
     - Admin platform memiliki hak intervensi manual (*admin override*) dengan kewajiban mengisi catatan alasan (`override_note`) dan jejak audit staf (`override_by`), menjamin prinsip akuntabilitas manusia atas keputusan algoritmik.

---

### [ADR-011] Identitas Visual Nusantara, Dana Gotong Royong, dan Halaman Edukasi Nilai (Fase Poles Nusantara)
- **Status:** Diterima
- **Konteks:** Menghadirkan sentuhan identitas lokal Indonesia (Nusantara) pada platform KampusRent tanpa mengorbankan fungsionalitas, keterbacaan, atau prinsip "kertas dan tinta" yang telah dibangun pada v2. Menyelaraskan istilah perlindungan risiko agar mencerminkan semangat kebersamaan mahasiswa Indonesia ("Dana Gotong Royong" menggantikan "dana proteksi"), serta menyediakan sarana edukasi masalah, cara kerja, dan transparansi gotong royong melalui seksi beranda dan halaman `/tentang/`.
- **Keputusan:**
  1. **Pola Geometris Abstrak Tapis Lampung:**
     - Dibuat pola SVG geometris berulang (`static/patterns/tapis_geom.svg`) yang terinspirasi dari ritme segitiga dan zigzag kain tapis khas Lampung.
     - Pola dibuat murni geometris datar, satu warna (`brand` `#1F45C4`), tanpa gradien, dan tidak menyalin motif adat sakral tertentu demi menghormati warisan budaya.
     - Dibatasi secara ketat maksimal pada tiga lokasi: (a) pita pembatas antarseksi beranda, (b) tekstur tipis opasitas rendah (4%) pada latar blok gelap Bukti, dan (c) tepi kartu kuitansi (kuitansi sewa & ringkasan perkiraan sewa).
     - Dilarang dipasang pada tombol, teks, kartu barang, atau melebihi 10% luas halaman untuk menjaga fokus pengguna pada konten dan barang.
  2. **Penggantian Istilah Menjadi "Dana Gotong Royong":**
     - Istilah "dana proteksi" diubah menjadi "Dana Gotong Royong" pada seluruh lapisan antarmuka pengguna, kuitansi transaksi, pesan notifikasi, formulir pengajuan sewa, aksi admin, pengujian unit, serta dokumentasi publik.
     - Nama field database internal (seperti `protection_fee`, `is_protection_selected`) dan jenis entri buku besar (`masuk_dana_proteksi`, `keluar_ke_dana_proteksi`) dipertahankan demi menjaga kompatibilitas basis data dan stabilitas logika pembukuan ganda.
     - Penjelasan singkat ditambahkan pada detail sewa dan beranda untuk mengedukasi bahwa iuran ini adalah urunan bersama untuk menanggung risiko kerusakan ringan wajar saat pemakaian normal, bukan produk asuransi komersial.
  3. **Halaman /tentang/ dan Seksi Beranda:**
     - Menambahkan rute `/tentang/` dan template `templates/core/tentang.html` yang merinci masalah sewa informal antarmahasiswa, cara kerja 5 langkah aman platform, serta 3 pilar proteksi (KTM, escrow, foto kondisi).
     - Menambahkan seksi "Gotong royong, versi kampus" pada beranda dengan narasi singkat, bersih, tanpa tanda hubung panjang (—), dan tanpa frasa klise.
  4. **Pencegahan Kategori Budaya/Adat Sembarangan:**
     - Memastikan tidak ada penambahan kategori busana adat atau budaya buatan yang tidak relevan dengan kebutuhan sewa harian mahasiswa kampus.

---

### [ADR-012] Mode Produk, Transisi Data Bersih, Notifikasi Modal, dan Relokasi Fitur Machine Learning (Fase 7A)
- **Status:** Diterima
- **Konteks:** Menyiapkan platform KampusRent agar terasa 100% siap publik (mode produk, bukan demo). Menghapus seluruh residu konten bernuansa demo/prototipe/simulasi dari template publik, menyajikan data bersih awal via command idempoten `init_platform`, mengamankan `seed_demo` agar tidak dapat dijalankan di non-dev database atau production, mengganti kuitansi statis dengan kalkulator biaya sewa interaktif berbasis HTMX dan aturan bisnis nyata, mengubah notifikasi menjadi panel modal/dropdown HTMX yang dinamis dan terintegrasi, menerapkan filter kampus dinamis di katalog `/barang/`, serta merelokasi tampilan teknis machine learning ke panel staf `/admin/model-skor/` sambil mengarahkan edukasi publik ke `/bantuan/#skor-kepercayaan`.
- **Keputusan:**
  1. **Audit & Pembersihan Konten Demo:**
     - Menghapus teks "Contoh", "Tampilan contoh", "Rencana:", "demo", "simulasi", "prototipe" dari template publik (`home.html`, `base.html`, `tentang.html`, `bantuan.html`, `item_list.html`, `rental_detail.html`, dll).
     - Hero sisi kanan beranda: menampilkan 3 barang terbaru yang nyata dari database jika ada; bila database masih kosong, menampilkan ilustrasi alur 3 langkah transaksi yang bersih tanpa nama atau harga fiktif.
     - Seksi "Bukti, bukan janji": kuitansi statis fiktif diganti dengan kalkulator biaya sewa interaktif (`/kalkulator-sewa/`, HTMX) yang menghitung secara dinamis sewa pokok, komisi 8%, deposit berdasarkan tangga kepercayaan, dan iuran Dana Gotong Royong.
     - Cincin skor fiktif di beranda dihapus dan diganti dengan 4 pilar keamanan transaksi nyata.
     - Spanduk uji pembayaran: hanya ditampilkan pada langkah pembayaran jika `MIDTRANS_IS_PRODUCTION=False` ("Mode uji pembayaran: tidak ada uang sungguhan").
  2. **Inisialisasi Data Bersih (`init_platform`):**
     - Perintah `python manage.py init_platform` dibuat idempoten dan bersih: mengisi 8 kategori resmi, kampus awal (dari berkas konfigurasi `config/initial_campuses.json`, diawali kampus ITERA), dan titik temu publik awal, tanpa membuat pengguna atau barang fiktif.
     - Perintah `seed_demo` dipindahkan ke modul `dev_tools/` dan diproteksi dengan guardrail ketat: menolak berjalan jika `DEBUG=False` atau nama database tidak berakhiran `_dev`.
     - Dokumentasi `README.md` diperbarui dengan alur setup produksi bersih: buat database baru, konfigurasi `DATABASE_URL`, migrate, `init_platform`, `createsuperuser`. Seluruh kredensial akun demo fiktif dihapus dari panduan publik.
  3. **Notifikasi Interaktif Sebagai Panel Modal/Dropdown (HTMX):**
     - Ikon lonceng di navbar kini memicu panel notifikasi HTMX (`/notifikasi/panel/`): dropdown pada desktop dan modal layar penuh pada ponsel, dengan fokus terjebak (focus trap Alpine.js `@alpinejs/focus`), tombol Esc untuk menutup, dan atribut aksesibilitas `aria-label`.
     - Memuat 20 notifikasi terbaru dengan tombol pagination "Muat lebih banyak", otomatis menandai notifikasi yang dibuka sebagai terbaca, tombol "Tandai semua dibaca" via HTMX, tautan langsung ke sewa terkait, serta sinkronisasi penanda unread badge secara real-time via OOB swap.
     - Halaman standalone `/notifikasi/` dihapus dan dialihkan (redirect 302) ke dashboard pengguna.
  4. **Filter Kampus Dinamis di Katalog (`/barang/`):**
     - Filter cakupan kampus di `/barang/` menampilkan "Kampus saya" (selalu ada), "Semua kampus", serta hanya kampus lain yang memiliki barang aktif yang dipasang oleh mahasiswa dari kampus tersebut.
     - Kampus lain diurutkan berdasarkan jumlah barang aktif terbanyak (`active_items_count`), disajikan dengan nama pendek dan jumlah (misal: `ITERA (12)`), dalam baris horizontal yang dapat digeser (`overflow-x-auto no-scrollbar whitespace-nowrap`) tanpa pemotongan teks.
     - Formulir pendaftaran tetap memuat seluruh kampus aktif di database. Query dioptimalkan dengan agregasi `Count(..., filter=Q(is_active=True))` untuk menghindari problem N+1.
  5. **Relokasi Fitur Machine Learning (Edukasi Publik vs Panel Staf):**
     - Tautan publik "Skor Kepercayaan" di navbar dan halaman `/skor-kepercayaan/` dihapus dari konsumsi publik (dialihkan ke `/bantuan/#skor-kepercayaan`).
     - Pusat Bantuan (`/bantuan/`) dilengkapi bagian khusus "Bagaimana Skor Kepercayaan dihitung?" dengan bahasa awam: 4 faktor yang dinilai, faktor demografis sensitif yang tidak dipakai, arti skor 60 untuk "Pengguna baru", dan kiat menaikkan skor.
     - Seluruh metrik teknis, grafik kurva evaluasi, dan simulator interaktif dipindahkan ke rute khusus staf `/admin/model-skor/` yang diproteksi decorator `@staff_member_required`.
     - Tooltip cincin skor di dashboard dan profil diperbarui dari "data sintetis" menjadi "Skor dihitung dari riwayat sewamu. Pelajari di Bantuan."

---

### [ADR-013] Poles Akhir Beranda dan Halaman Publik serta Pembekuan Desain (Fase 7F)
- **Status:** Diterima (Desain Dibekukan)
- **Konteks:** Melakukan penyempurnaan menyeluruh pada halaman publik (Beranda, Katalog, Detail Barang, dan Tentang) sebelum desain dibekukan (Design Freeze). Fokus meliputi penambahan token ornamen budaya marun-tapis yang dibatasi ketat, pembentukan jangkar budaya seksi Gotong Royong 2 kolom dengan panel kain marun dan plat kertas, pembaruan rasio kartu barang 4:3 dengan warna ubin lembut dan generator foto demo baru, pemisahan kalkulator sewa mandiri dari blok bukti gelap yang dirampingkan, penyelarasan vertikal hero dengan 3 jaminan berikon, serta standarisasi sistem jarak (96 px desktop / 64 px mobile) dan tipografi isi minimal 15 px.
- **Keputusan:**
  1. **Token Ornamen Baru `marun-tapis` (`#5B1A24`):**
     - Ditambahkan pada `AGENT.md` dan `tailwind.config.js` dengan batasan ketat: HANYA digunakan sebagai latar panel ornamen (momen budaya), bukan untuk teks, tombol, kartu, atau latar bagian halaman lain.
     - Varian SVG `static/img/tapis-tile-marun.svg` dibuat dengan latar `#5B1A24` dan geometri belah ketupat kunyit `#F2A900` identik dengan `tapis-tile.svg`. Seluruh ornamen datar tanpa gradien.
     - Penempatan momen budaya dibatasi ketat hanya pada 3 lokasi: (1) seksi Gotong Royong beranda, (2) header Tentang, dan (3) halaman galat sistem (404/403/500/CSRF).
  2. **Jangkar Budaya Seksi "Gotong royong, versi kampus":**
     - Dikonfigurasi dalam tata letak dua kolom asimetris:
       - Kolom kiri: teks ringkas (maks. 2 paragraf), satu kutipan besar `"[KUTIPAN]"` ("Saling sewa, saling bantu."), tiga prinsip singkat berikon Lucide (Saling bantu, Ramah, Terbuka antarkampus), dan kartu penjelasan Dana Gotong Royong yang dipindahkan ke bawah kolom kiri.
       - Kolom kanan: panel kain `[LATAR_PANEL]` marun tinggi 300 px (desktop) dan 200 px (mobile) dengan pola penuh, memuat satu plat kertas (`#F8F5EE`, sudut membulat) di tengah berisi ilustrasi kapal (`kapal-tinta.svg`: lambung kunyit, tiang dan layar tinta) serta siger kecil di bawahnya.
       - Teks hanya di dalam plat kertas, tidak pernah di atas pola tapis. Seluruh elemen ornamen berstatus `aria-hidden="true"`.
  3. **Kartu Barang Rasio 4:3 dan Generator Ilustrasi Demo:**
     - Rasio wadah gambar kartu barang diubah dari 4:5 menjadi 4:3 (`aspect-[4/3]`).
     - Tipografi kartu distandarkan: judul barang 15-16 px semibold (`text-[15px] sm:text-base`, maks. 2 baris), harga 17-18 px bold (`text-[17px] sm:text-[18px]`), dan seluruh metadata 13 px (`text-[13px]`).
     - Warna ubin per kategori diperbarui dengan nada lebih lembut: biru `#8EA8F7` (Kamera & Laptop), kunyit `#FFD66B` (Wisuda & Kostum), mint `#7ACFAC` (Praktikum & Proyektor), koral `#FFA68C` (Camping & Lain-lain).
     - Generator foto demo `replace_demo_photos` diperbarui menghasilkan kanvas 400x300 (4:3) dengan `STROKE_WIDTH = 2`, ikon mengisi 55-60% lebar ubin, dan dieksekusi dengan `--apply` hanya pada barang demo (`DEMO_USERNAMES`), tanpa menyentuh foto buatan pengguna.
  4. **Pemisahan Kalkulator Sewa dan Perampingan Blok Bukti:**
     - Kalkulator sewa interaktif dipisahkan dari blok gelap menjadi seksi mandiri "Hitung biaya sewa" berlatar paper dengan kartu putih 2 kolom (formulir di kiri, kuitansi hasil di kanan) tepat di atas blok gelap.
     - Blok gelap `bg-ink` dirampingkan khusus untuk "Mengapa transaksi di KampusRent aman?" berisi 4 pilar berikon dengan teks minimal 15 px, kontras tinggi > 4,5:1, pita kunyit atas-bawah tetap utuh, dan paragraf penutup yang redundan dihapus.
  5. **Hero Penyelarasan Vertikal dan Tiga Jaminan:**
     - Grid hero disejajarkan vertikal secara presisi (`items-center`).
     - Tautan kecil lama diganti dengan baris 3 jaminan singkat berikon (Pemilik terverifikasi KTM, Uang ditahan platform, Foto bukti kondisi) di bawah kolom pencarian, dengan tetap mempertahankan tautan pencarian populer.
  6. **Standarisasi Sistem Jarak dan Tipografi Halaman Publik:**
     - Jarak antarseksi di beranda, katalog, detail barang, dan Tentang distandarkan menjadi 96 px pada desktop (`md:py-24` / `md:mt-24`) dan 64 px pada ponsel (`py-16` / `mt-16`).
     - Jarak judul seksi ke isi ditetapkan 24 px (`mb-6`).
     - Teks isi di seluruh halaman publik ditetapkan minimal 15 px (`text-[15px]`), menggantikan nilai ad hoc lama.
  7. **Pembekuan Desain (Design Freeze):**
     - Seluruh token warna, tata letak, komponen publik, rasio kartu, dan ornamen budaya dinyatakan final dan dibekukan. Tidak ada penambahan fitur visual di luar spesifikasi.

---

### [ADR-014] Arsitektur Modul Jual Beli Barang Bekas (Thrift Kampus) dan Perlindungan Transaksi (Fase 8)
- **Status:** Diterima
- **Konteks:** Mahasiswa sering membutuhkan buku kuliah, alat laboratorium, kalkulator ilmiah, dan perangkat pendukung studi dengan harga terjangkau, serta membutuhkan saluran terpercaya untuk melepas perlengkapan studi yang sudah tidak terpakai tanpa risiko penipuan COD liar atau marketplace umum tanpa verifikasi identitas.
- **Keputusan:**
  1. **Pemisahan Domain dan Model Data:** Modul jual beli diisolasi dalam aplikasi `apps/sales/` dengan model tersendiri (`SaleItem`, `SaleOrder`, `SaleAgreement`, `SaleDispute`, `SaleReview`, `SaleItemReport`, `SaleOffer`) untuk menjaga keterpisahan tanggung jawab dan mencegah regresi pada modul sewa (`apps/rentals/`).
  2. **Batas Harga Bertingkat Berbasis Reputasi Penjual:** Menerapkan plafon harga maksimum bertingkat (`SALE_MAX_PRICE_NEW` Rp1.000.000, `SALE_MAX_PRICE_TRUSTED` Rp3.000.000, `SALE_MAX_PRICE_TOP` Rp8.000.000) untuk membatasi paparan risiko sebelum penjual membuktikan keandalannya.
  3. **Penyaringan Kata Kunci Barang Terlarang:** Validasi daftar kata terlarang (`SALE_PROHIBITED_KEYWORDS`) diterapkan secara ketat pada pembersihan model (`clean()`) dan formulir (`forms.py`) guna memblokir penjualan obat keras, alkohol, rokok/vape, senjata tajam, satwa, dan akun digital.
  4. **Snapshot Listing Beku:** Saat pesanan dibuat, snapshot detail barang (judul, deskripsi, kondisi, kelengkapan, harga, dan hash SHA-256 seluruh foto) dibekukan di `SaleOrder.listing_snapshot`. Penjual dilarang mengubah informasi listing setelah pesanan masuk.
  5. **Perjanjian Pembelian Digital (SaleAgreement):** Mencatat persetujuan S&K pembeli secara atomik dengan hash SHA-256 dokumen S&K aktif, alamat IP, dan user-agent peramban.
  6. **Escrow, Komisi Platform, dan Buku Besar Berimbang:** Pembayaran pembeli ditampung di escrow Midtrans. Platform mengenakan komisi 5% (minimum Rp2.000) dan mencatat transaksi ke `LedgerEntry` (`MASUK_PENJUALAN`, `PENDAPATAN_KOMISI_PENJUALAN`, `KELUAR_PENJUALAN`, `KELUAR_REFUND_PENYEWA`). Invarian buku besar dijaga seimbang: Nilai Transaksi = Payout Penjual + Komisi Platform.
  7. **Alur Serah Terima Tatap Muka & Masa Inspeksi 48 Jam:** Serah terima wajib dilakukan di titik temu kampus ramai dengan bukti foto fisik. Dana ditahan selama masa inspeksi 48 jam untuk memberi kesempatan pembeli memeriksa kesesuaian barang sebelum dilepaskan otomatis ke dompet penjual.
  8. **Sistem Sengketa Jual Beli (`SaleDispute`):** Fasilitas mediasi sengketa admin dilengkapi perbandingan snapshot listing vs foto sengketa, jejak pesan chat, serta opsi keputusan adil (lepas ke penjual, pengembalian dana penuh pembeli, atau bagi sebagian). Pelanggaran penjual memicu penalti reputasi otomatis.
  9. **Ulasan Dua Arah & Reputasi Terpadu:** Ulasan timbal balik (`SaleReview`) antara pembeli dan penjual terintegrasi dengan perhitungan tingkat penjual (`get_seller_tier`) yang menggabungkan rekam jejak sewa dan jual beli.
  10. **Moderasi Listing & Aksi Penurunan:** Pelaporan listing oleh komunitas (`SaleItemReport`) dan tindakan penurunan barang (*takedown*) oleh moderator dengan alasan tertulis wajib yang otomatis ternotifikasi ke penjual.
  11. **Saklar Tawar Harga Terstruktur (`SALE_OFFERS_ENABLED`):** Fitur tawar harga dikendalikan oleh saklar konfigurasi (bawaan: dinonaktifkan/False). Jika diaktifkan, tawaran berlaku 24 jam dan penerimaan oleh penjual otomatis membentuk pesanan dengan batas bayar 6 jam pada harga kesepakatan.

---

### [ADR-015] Penggantian Nama Merek Platform Menjadi "Collective Campus" dan Penyelarasan Identitas (Fase 10)
- **Status:** Diterima
- **Konteks:** Nama awal "KampusRent" bersifat sementara dan berorientasi sempit hanya pada persewaan. Dengan hadirnya modul jual beli perlengkapan kuliah (thrift), platform berkembang menjadi ekosistem gotong royong terpadu antarmahasiswa lintas kampus. Dibutuhkan nama merek baru yang inklusif, modern, dan merefleksikan semangat kolektif saling bantu mahasiswa tanpa kehilangan kejelasan fungsi intinya.
- **Keputusan:**
  1. **Nama Merek & Tagline:** Menetapkan nama resmi platform menjadi **Collective Campus** (`SITE_NAME="Collective Campus"`), dengan nama singkat **Collective** (`SITE_SHORT_NAME="Collective"`), slogan resmi **"Saling sewa, saling jual, saling bantu."** (`SITE_TAGLINE`), dan `SITE_DOMAIN=""` (bawaan kosong; tidak ditampilkan jika belum diisi).
  2. **Hierarki Logotipe Visual:**
     - Navbar: Menampilkan tanda visual siger (`logo-mark.svg`) dan `SITE_SHORT_NAME` ("Collective", semibold, warna tinta `text-ink`).
     - Footer dan Judul: Menampilkan `SITE_NAME` dengan komposisi dua warna ("Collective" dalam warna tinta `text-ink` dan "Campus" dalam warna biru `text-brand`). Seluruh teks logotipe dan judul ditulis dalam sentence/title case tanpa huruf kapital semua (all-caps).
     - Favicon dan atribut alt: Menggunakan representasi tanda resmi dan teks alternatif nama baru.
     - Judul tab peramban: Diformat menjadi `"Collective Campus: sewa dan jual beli barang antarmahasiswa"`.
     - Panel Admin: Menampilkan header dan judul `"Collective Admin"`.
  3. **Penyelarasan Seluruh Antarmuka & Dokumen:** Mengganti kemunculan nama lama di template, static, meta/OG, subjek dan pengirim email, dokumentasi, dokumen hukum (S&K, Kebijakan Privasi, Panduan Komunitas), serta halaman bantuan dan Tentang.
  4. **Pengecualian yang Dipertahankan:**
     - Nama database PostgreSQL (`kampusrent`) dan database pengujian (`test_kampusrent`) dipertahankan demi stabilitas koneksi lingkungan lokal dan hosting yang telah terpasang.
     - Jalur direktori repositori (`SEWA_MAHASISWA`) dan berkas cadangan lampau (`backups/kampusrent_db_*.sql`).
     - Riwayat komit git dan awalan kode transaksi yang telah beredar di database (`KR-` untuk sewa dan `KJ-` untuk jual beli).
     - Teks ADR terdahulu (ADR-001 hingga ADR-014) dipertahankan sebagai catatan sejarah arsitektur asli.





