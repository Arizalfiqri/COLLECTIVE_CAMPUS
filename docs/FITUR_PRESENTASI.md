# Fitur Presentasi Collective Campus

Dokumen resmi presentasi fitur platform Collective Campus untuk sesi penilaian, demo produk, dan tanya jawab juri. Disusun berdasarkan implementasi kode nyata pada Django 5 dan pustaka Machine Learning terkalibrasi.

---

## 0. Ringkasan Satu Halaman

### Apa Itu Collective Campus
Collective Campus adalah platform lokapasar sewa-menyewa perlengkapan kuliah dan jual beli barang bekas terkurasi khusus mahasiswa aktif berbasis web Django 5.

### Untuk Siapa
Mahasiswa perguruan tinggi di Indonesia yang membutuhkan perlengkapan kuliah berbiaya hemat (kamera, alat praktikum, jas wisuda, proyektor, laptop), serta mahasiswa yang ingin memperoleh pendapatan tambahan dari barang yang jarang terpakai.

### Masalah
1. Risiko penipuan transaksi antarmahasiswa di media sosial tanpa jaminan identitas dan tanpa penahanan dana.
2. Tingginya biaya pembelian perlengkapan kuliah penunjang yang hanya digunakan beberapa hari dalam satu semester.
3. Kerusakan atau kehilangan barang pinjaman tanpa kejelasan dokumentasi awal dan tanpa saluran ganti rugi resmi.
4. Barang perlengkapan bekas menumpuk di kamar indekos tanpa saluran penjualan lokal yang terpercaya.

### Solusi
1. Ekosistem tertutup khusus mahasiswa dengan verifikasi Kartu Tanda Mahasiswa dan sinyal email kampus resmi.
2. Penahanan dana transaksi pada rekening bersama platform via Midtrans hingga barang kembali atau masa periksa 48 jam berakhir.
3. Dokumentasi foto fisik kondisi barang sebelum dan sesudah transaksi di titik temu kampus yang disepakati.
4. Model Machine Learning skor kepercayaan untuk memprediksi risiko transaksi secara objektif tanpa bias demografis.

### Lima Keunikan Utama
1. Penahanan dana sewa dan jual beli dengan pelepasan berbasis bukti fisik dan masa periksa.
2. Pembukuan saldo dompet internal menggunakan sistem buku besar berpasangan yang setara perbankan.
3. Model Machine Learning terkalibrasi yang memberikan skor risiko dan tiga faktor penjelas transparan.
4. Kepatuhan privasi data mahasiswa sesuai Undang-Undang Perlindungan Data Pribadi dengan pembersihan berkas otomatis.
5. Sentuhan identitas visual lokal Lampung-Nusantara geometris yang elegan tanpa gradien dan ramah aksesibilitas.

### Angka Kunci Proyek
- 10 aplikasi Django terintegrasi.
- 40 model database terstruktur.
- 50 berkas migrasi skema database.
- 11 perintah manajemen operasional mandiri.
- 79 berkas template antarmuka terstandarisasi.
- 389 tes otomatis dengan tingkat kelulusan seratus persen.
- 35.525 baris kode Python produksi dan pengujian.
- 17.682 baris kode antarmuka HTML.
- 723 baris kode JavaScript utilitas.
- 0 kelas CSS hilang pada kompilasi Tailwind CSS.

---

## 1. Peta Fitur

| Kelompok | Fitur | Status |
|---|---|---|
| Akun dan Verifikasi | Pendaftaran akun mahasiswa dan validasi domain kampus | [Berjalan] |
| Akun dan Verifikasi | Verifikasi Kartu Tanda Mahasiswa dengan bantuan OCR | [Berjalan] |
| Akun dan Verifikasi | Verifikasi email dan sinyal kampus resmi | [Berjalan] |
| Akun dan Verifikasi | Atur ulang kata sandi mandiri | [Berjalan] |
| Sewa | Katalog multi-kategori dan pencarian instan | [Berjalan] |
| Sewa | Penyaringan berbasis kampus dan lokasi | [Berjalan] |
| Sewa | Pemasangan iklan barang sewa dan kalender ketersediaan | [Berjalan] |
| Sewa | Pengajuan sewa dengan penandatanganan digital syarat dan ketentuan | [Berjalan] |
| Sewa | Persetujuan pemilik dan pencegahan bentrok jadwal otomatis | [Berjalan] |
| Sewa | Pembayaran sewa melalui Midtrans Snap sandbox | [Berjalan] |
| Sewa | Kesepakatan jadwal dan titik temu kampus | [Berjalan] |
| Sewa | Dokumentasi foto kondisi fisik sebelum dan sesudah pakai | [Berjalan] |
| Sewa | Konfirmasi serah terima fisik langsung | [Berjalan] |
| Sewa | Pengembalian barang dan pelepasan dana sewa | [Berjalan] |
| Sewa | Penagihan denda keterlambatan dan biaya tambahan | [Berjalan] |
| Sewa | Pengajuan sengketa sewa dan mediasi admin | [Berjalan] |
| Sewa | Ulasan dua arah penyewaan | [Berjalan] |
| Jual Beli | Pemasangan iklan barang jualan dengan batas harga reputasi | [Berjalan] |
| Jual Beli | Penyaringan kata kunci barang terlarang kampus | [Berjalan] |
| Jual Beli | Masa tayang listing enam puluh hari dan perpanjangan | [Berjalan] |
| Jual Beli | Katalog jual beli mandiri dan filter kondisi fisik | [Berjalan] |
| Jual Beli | Pembekuan snapshot spesifikasi dan foto barang saat pemesanan | [Berjalan] |
| Jual Beli | Persetujuan syarat dan ketentuan jual beli digital | [Berjalan] |
| Jual Beli | Pembayaran pesanan ditahan dengan komisi platform | [Berjalan] |
| Jual Beli | Kesepakatan jadwal temu dan serah terima fisik langsung | [Berjalan] |
| Jual Beli | Masa pemeriksaan empat puluh delapan jam pembeli | [Berjalan] |
| Jual Beli | Pembatalan pesanan dan pengembalian saldo instan | [Berjalan] |
| Jual Beli | Sengketa jual beli dengan perbandingan snapshot | [Berjalan] |
| Jual Beli | Ulasan dua arah jual beli | [Berjalan] |
| Jual Beli | Evaluasi tingkat reputasi penjual otomatis | [Berjalan] |
| Jual Beli | Pelaporan barang jualan dan moderasi penurunan iklan | [Berjalan] |
| Jual Beli | Penawaran harga terstruktur | [Saklar] |
| Uang | Penahanan pembayaran sewa dan pesanan platform | [Berjalan] |
| Uang | Buku besar berpasangan untuk seluruh mutasi dana | [Berjalan] |
| Uang | Dompet internal pengguna untuk penampungan hasil transaksi | [Berjalan] |
| Uang | Permohonan penarikan dana dengan enkripsi nomor rekening | [Berjalan] |
| Uang | Rekonsiliasi otomatis saldo dompet terhadap buku besar | [Berjalan] |
| Uang | Pemotongan komisi platform dan alokasi dana cadangan | [Berjalan] |
| Kepercayaan | Tingkat reputasi penyewa dan penjual berbasis rekam jejak | [Berjalan] |
| Kepercayaan | Model Machine Learning skor kepercayaan terkalibrasi | [Berjalan] |
| Kepercayaan | Penjelasan transparan faktor penentu skor pengguna | [Berjalan] |
| Kepercayaan | Pembelajaran ulang model dari data transaksi nyata | [Berjalan] |
| Komunikasi | Percakapan langsung antarpengguna dalam platform | [Berjalan] |
| Komunikasi | Penyamaran nomor kontak dan tautan luar sebelum kesepakatan | [Berjalan] |
| Komunikasi | Panel notifikasi dalam aplikasi berbasis pembaruan instan | [Berjalan] |
| Keamanan dan Privasi | Isolasi berkas identitas pribadi pada direktori privat | [Berjalan] |
| Keamanan dan Privasi | Pembersihan berkas foto identitas dan serah terima berkala | [Berjalan] |
| Keamanan dan Privasi | Pencatatan log akses data rekening bank pengguna | [Berjalan] |
| Keamanan dan Privasi | Pembatasan akses pengguna yang ditangguhkan | [Berjalan] |
| Admin | Pusat kendali operasional staf terpadu | [Berjalan] |
| Admin | Antrean verifikasi identitas, penarikan dana, dan sengketa | [Berjalan] |
| Admin | Dasbor pemantauan kinerja model Machine Learning | [Berjalan] |
| Admin | Pengumuman siaran massal berjadwal | [Berjalan] |
| Identitas dan Desain | Penerapan bahasa desain kertas dan tinta tanpa gradien | [Berjalan] |
| Identitas dan Desain | Ornamen geometris Tapis dan Siger Lampung terukur | [Berjalan] |
| Identitas dan Desain | Antarmuka responsif penuh pada layar ponsel dan desktop | [Berjalan] |
| Kualitas Teknis | Otomatisasi pengujian regresi tiga ratus delapan puluh sembilan tes | [Berjalan] |
| Kualitas Teknis | Audit kepatuhan kelas utilitas Tailwind CSS tanpa kelas hilang | [Berjalan] |
| Kualitas Teknis | Pencatatan keputusan arsitektur perangkat lunak terstruktur | [Berjalan] |

---

## 2. Detail Tiap Fitur

### Kelompok 1: Akun dan Verifikasi

#### Pendaftaran Akun Mahasiswa
- **Masalah:** Transaksi kampus rawan disusupi pihak luar tak bertanggung jawab.
- **Solusi:** Registrasi terisolasi khusus mahasiswa dengan validasi domain universitas resmi.
- **Cara Kerja:**
  1. Pengguna mengisi nama, username, email kampus, dan kata sandi.
  2. Sistem mencocokkan domain email dengan daftar kampus terdaftar.
  3. Akun dibuat dengan status awal belum terverifikasi.
- **Aturan Penting:** Domain email wajib berakhiran `.ac.id` untuk klaim sinyal resmi.
- **Bukti:** `apps/accounts/views.py:register_view`, tes di `apps/accounts/tests.py`.
- **Tampilan:** `templates/accounts/register.html`.
- **Poin Bicara:** Komunitas eksklusif mahasiswa terjaga sejak gerbang pendaftaran akun.
- **Pertanyaan Juri:** Bila kampus belum memakai `.ac.id`? Mahasiswa mendaftar dengan email umum dan memverifikasi KTM.

#### Verifikasi Kartu Tanda Mahasiswa dengan OCR
- **Masalah:** Verifikasi manual membebani staf kampus dan memperlambat antrean mahasiswa.
- **Solusi:** Pembacaan data teks identitas mahasiswa otomatis memakai Tesseract OCR.
- **Cara Kerja:**
  1. Mahasiswa mengunggah foto kartu identitas tampak depan.
  2. Modul OCR mengekstrak teks NIM dan nama mahasiswa.
  3. Algoritma kemiripan string mencocokkan data ke profil pendaftaran.
  4. Staf kampus menyetujui atau menolak permohonan.
- **Aturan Penting:** Ambang batas kecocokan otomatis disetel pada skor 85 persen.
- **Bukti:** ml/ktm_ocr.py:extract_ktm_data, pps/verification/views.py:ktm_upload_view, tes di pps/verification/tests.py.
- **Tampilan:** 	emplates/verification/ktm_stepper.html.
- **Poin Bicara:** OCR mempercepat verifikasi tanpa mengorbankan akurasi data.
- **Pertanyaan Juri:** Bila foto buram? Sistem mengarahkan pengajuan ke status Tinjau Manual admin.

#### Verifikasi Email dan Sinyal Kampus
- **Masalah:** Alamat email palsu digunakan untuk membuat akun penipuan sekali pakai.
- **Solusi:** Pengiriman tautan konfirmasi kepemilikan email sebelum status mahasiswa resmi disematkan.
- **Cara Kerja:**
  1. Sistem mengirimkan token konfirmasi ke email pengguna saat pendaftaran.
  2. Pengguna mengeklik tautan verifikasi sebelum masa kedaluwarsa.
  3. Status email aktif tercatat dan sinyal kepercayaan bertambah.
- **Aturan Penting:** Token kedaluwarsa dalam 24 jam.
- **Bukti:** `apps/accounts/views.py:verify_email_view`, tes di `apps/accounts/tests.py`.
- **Tampilan:** `templates/accounts/login.html`.
- **Poin Bicara:** Kepemilikan email aktif menjamin saluran komunikasi resmi saat terjadi kendala transaksi atau panggilan mediasi sengketa.
- **Pertanyaan Juri:** Apakah email mahasiswa wajib aktif sepanjang masa studi? Ya, notifikasi penagihan denda dan pembaruan kontrak sewa dikirimkan ke alamat ini.

#### Atur Ulang Kata Sandi Mandiri
- **Masalah:** Mahasiswa sering lupa kata sandi akun dan terhambat saat butuh menyewa mendesak.
- **Solusi:** Alur pemulihan kata sandi mandiri berbasis email dengan token kriptografis sekali pakai.
- **Cara Kerja:**
  1. Pengguna memasukkan alamat email terdaftar pada form pemulihan.
  2. Sistem mengirim tautan berisi token berbasis stempel waktu.
  3. Pengguna membuat kata sandi baru yang memenuhi standar keamanan.
- **Aturan Penting:** Standar kata sandi minimal 8 karakter dengan kombinasi angka dan huruf.
- **Bukti:** `apps/accounts/urls.py`, `templates/accounts/password_reset_confirm.html`.
- **Tampilan:** `templates/accounts/password_reset_form.html`.
- **Poin Bicara:** Pemulihan akun berjalan mandiri tanpa campur tangan staf, mengurangi beban tiket bantuan secara signifikan.
- **Pertanyaan Juri:** Apakah token reset bisa dipakai berulang kali? Tidak, token Django langsung hangus segera setelah kata sandi berhasil diperbarui.

---

### Kelompok 2: Modul Sewa-Menyewa (Rental)

#### Katalog Sewa Multi-Kategori
- **Masalah:** Mahasiswa kesulitan menemukan perlengkapan praktikum atau wisuda di kampus.
- **Solusi:** Katalog barang terstruktur 8 kategori resmi dengan pencarian kata kunci instan.
- **Cara Kerja:**
  1. Pengguna mengetik nama barang pada kolom pencarian.
  2. Sistem memfilter kecocokan nama, deskripsi, dan kategori.
  3. Kartu barang menampilkan tarif harian, kampus, dan reputasi pemilik.
- **Aturan Penting:** 8 kategori resmi: Kamera, Praktikum, Wisuda, Camping, Proyektor, Kostum, Laptop, Lain-lain.
- **Bukti:** `apps/catalog/views.py:item_list_view`, tes di `apps/catalog/tests.py`.
- **Tampilan:** `templates/catalog/item_list.html`.
- **Poin Bicara:** Katalog transparan memudahkan mahasiswa menemukan alat praktikum dalam sekejap.
- **Pertanyaan Juri:** Mengapa 8 kategori? Menjaga relevansi perkuliahan dan memudahkan ilustrasi SVG cadangan.

#### Penyaringan Berbasis Kampus
- **Masalah:** Mahasiswa enggan menyewa barang jika lokasinya terlalu jauh dari area perkuliahan sehari-hari.
- **Solusi:** Filter drop-down instan berdasarkan universitas asal pemilik barang.
- **Cara Kerja:**
  1. Pengguna memilih nama kampus pada menu navigasi atau filter samping.
  2. Daftar barang diperbarui otomatis hanya menampilkan barang di area kampus tersebut.
- **Aturan Penting:** Bawaan menampilkan seluruh kampus terdekat atau kampus terdaftar pengguna.
- **Bukti:** `apps/catalog/views.py:item_list_view`, tes di `apps/catalog/tests.py`.
- **Tampilan:** `templates/catalog/item_list.html`.
- **Poin Bicara:** Pertemuan tatap muka di lingkungan kampus sendiri jauh lebih aman dan tidak membutuhkan ongkos kirim ekspedisi.
- **Pertanyaan Juri:** Bisakah menyewa dari kampus lain? Bisa, filter bersifat terbuka untuk memfasilitasi kebutuhan antarkampus yang berdekatan.

#### Pemasangan Iklan Sewa dan Kalender Ketersediaan
- **Masalah:** Pemilik sering mendapat pesanan pada tanggal barang sedang dipakai sendiri.
- **Solusi:** Formulir pasang iklan lengkap dengan kalender pemblokiran tanggal sibuk.
- **Cara Kerja:**
  1. Pemilik memasukkan nama barang, tarif sewa harian, uang jaminan, dan foto barang.
  2. Kalender menampilkan tanggal yang sudah dibooking dan tanggal yang diblokir pemilik.
  3. Iklan langsung tayang dan dapat menerima pengajuan sewa.
- **Aturan Penting:** Uang jaminan sewa dibatasi proporsional terhadap nilai barang.
- **Bukti:** `apps/catalog/views.py:item_create_view`, `apps/catalog/services.py:get_unavailable_dates`, tes di `apps/catalog/tests.py`.
- **Tampilan:** `templates/catalog/item_form.html`.
- **Poin Bicara:** Kalender ketersediaan interaktif mencegah bentrok jadwal sewa secara otomatis sejak di tingkat pemilihan tanggal.
- **Pertanyaan Juri:** Bagaimana mencegah jadwal ganda saat pengajuan bersamaan? Database menggunakan klausa penguncian baris atomik pada transaksi sewa.

#### Pengajuan Sewa dengan Syarat dan Ketentuan Digital
- **Masalah:** Perjanjian lisan rawan sengketa saat barang rusak atau terlambat dipulangkan.
- **Solusi:** Penandatanganan Syarat dan Ketentuan digital dengan pencatatan jejak bukti hukum.
- **Cara Kerja:**
  1. Penyewa memilih tanggal sewa dan memeriksa kuitansi biaya.
  2. Membaca dan mencentang persetujuan perjanjian sewa.
  3. Sistem mencatat versi, stempel waktu, dan IP ke RentalAgreement.
- **Aturan Penting:** Pembatalan sepihak pascabayar tunduk pada regulasi pengembalian bertahap.
- **Bukti:** pps/rentals/views.py:rental_create_view, pps/rentals/models.py:RentalAgreement, tes di pps/rentals/tests.py.
- **Tampilan:** 	emplates/rentals/rental_agreement.html.
- **Poin Bicara:** Kepastian hukum kedua pihak terjamin sebelum pembayaran diteruskan.
- **Pertanyaan Juri:** Apakah sah secara hukum? Sah sebagai kontrak elektronik pembuktian perdata.

#### Persetujuan Pemilik dan Pencegahan Bentrok Jadwal
- **Masalah:** Pemilik butuh waktu meninjau rekam jejak penyewa sebelum menyerahkan barang berharga.
- **Solusi:** Alur tinjau pengajuan oleh pemilik dengan penolakan otomatis jadwal bentrok.
- **Cara Kerja:**
  1. Pengajuan masuk ke dasbor pemilik dengan batas waktu persetujuan 24 jam.
  2. Pemilik memeriksa skor kepercayaan penyewa dan menyetujui pengajuan.
  3. Pengajuan lain yang memiliki irisan tanggal sewa otomatis ditolak oleh sistem.
- **Aturan Penting:** Batas waktu konfirmasi pemilik adalah 24 jam sebelum kedaluwarsa otomatis.
- **Bukti:** `apps/rentals/services.py:approve_rental_request`, tes di `apps/rentals/tests.py`.
- **Tampilan:** `templates/rentals/rental_detail.html`.
- **Poin Bicara:** Pemilik memiliki kendali penuh atas siapa yang meminjam barang miliknya berdasarkan riwayat reputasi peminjam.
- **Pertanyaan Juri:** Apa akibatnya jika pemilik tidak merespons dalam 24 jam? Pengajuan otomatis dibatalkan tanpa memotong saldo peminjam.

#### Pembayaran Sewa Melalui Midtrans Snap
- **Masalah:** Transaksi tunai rawan penipuan deposit dan penggelapan dana.
- **Solusi:** Pembayaran gerbang digital Midtrans Snap dengan penahanan dana bersama platform.
- **Cara Kerja:**
  1. Penyewa membuka tagihan pembayaran setelah disetujui pemilik.
  2. Jendela Midtrans Snap menyajikan opsi QRIS dan Virtual Account.
  3. Webhook memproses konfirmasi pembayaran lunas secara otomatis.
  4. Status sewa diperbarui menjadi siap serah terima.
- **Aturan Penting:** Batas waktu pembayaran adalah 6 jam (`PAYMENT_DEADLINE_HOURS = 6`).
- **Bukti:** `apps/payments/services.py:create_midtrans_transaction`, webhook `apps/payments/views.py:midtrans_webhook_view`, tes di `apps/payments/tests.py`.
- **Tampilan:** `templates/rentals/rental_payment_finish.html`.
- **Poin Bicara:** Uang sewa dan jaminan aman terkunci di rekening platform.
- **Pertanyaan Juri:** Mengapa memakai Sandbox? Memastikan pengujian alur lunas tanpa memotong rupiah riil.

#### Kesepakatan Jadwal dan Titik Temu Kampus
- **Masalah:** Kebingungan menentukan lokasi aman untuk penyerahan barang berharga.
- **Solusi:** Pemilihan titik temu resmi di area kampus yang ramai dan terpantau keamanan.
- **Cara Kerja:**
  1. Kedua belah pihak memilih lokasi titik temu terdaftar (misal perpustakaan pusat atau kantin utama).
  2. Jam pertemuan disepakati melalui formulir jadwal.
  3. Konfirmasi jadwal memunculkan panduan keselamatan pertemuan.
- **Aturan Penting:** Titik temu wajib berada di dalam kawasan kampus terdaftar.
- **Bukti:** `apps/rentals/views.py:handover_schedule_view`, model `HandoverSchedule`, tes di `apps/rentals/tests.py`.
- **Tampilan:** `templates/rentals/rental_detail.html`.
- **Poin Bicara:** Menghindari penyerahan di tempat sepi demi keselamatan kedua mahasiswa yang bertransaksi.
- **Pertanyaan Juri:** Bisakah menambah titik temu baru? Admin kampus dapat mendaftarkan titik temu baru melalui portal administrasi.

#### Dokumentasi Foto Kondisi Fisik Barang
- **Masalah:** Tuduhan sepihak kerusakan barang lama antara pemilik dan penyewa.
- **Solusi:** Dokumentasi foto kondisi fisik sebelum dan sesudah sewa sebagai bukti pembanding.
- **Cara Kerja:**
  1. Penyewa memotret kondisi barang di titik temu saat serah terima.
  2. Foto kondisi akhir diunggah kembali saat pengembalian.
  3. Berkas disimpan privat untuk peninjauan objektif jika ada sengketa.
- **Aturan Penting:** Foto disimpan di direktori privat dan dibersihkan berkala pascatransaksi.
- **Bukti:** `apps/rentals/views.py:upload_condition_photo_view`, model `ConditionPhoto`, tes di `apps/rentals/tests.py`.
- **Tampilan:** `templates/rentals/rental_detail.html`.
- **Poin Bicara:** Bukti visual menghindarkan saling tuduh atas cacat fisik bawaan.
- **Pertanyaan Juri:** Apakah foto wajib diunggah? Wajib diunggah sebelum serah terima difinalisasi.

#### Konfirmasi Serah Terima Fisik
- **Masalah:** Transaksi macet karena tidak ada bukti kapan barang mulai berpindah tangan.
- **Solusi:** Tombol konfirmasi serah terima digital dua arah di antarmuka masing-masing.
- **Cara Kerja:**
  1. Penyewa memeriksa fisik barang di titik temu.
  2. Penyewa menekan tombol konfirmasi terima barang.
  3. Masa sewa resmi berjalan dan waktu pengembalian mulai dihitung mundur.
- **Aturan Penting:** Konfirmasi mengunci masa sewa aktif dan mengaktifkan perlindungan asuransi gotong royong.
- **Bukti:** `apps/rentals/services.py:konfirmasi_serah_terima`, tes di `apps/rentals/tests.py`.
- **Tampilan:** `templates/rentals/rental_detail.html`.
- **Poin Bicara:** Titik awal masa sewa tercatat akurat per detik untuk mencegah perselisihan durasi pemakaian.
- **Pertanyaan Juri:** Bagaimana jika penyewa tidak menekan tombol? Pemilik dapat menunjukkan foto penyerahan kepada admin untuk konfirmasi bantuan.

#### Pengembalian Barang dan Pelepasan Dana
- **Masalah:** Pemilik menahan deposit penyewa tanpa alasan setelah barang kembali utuh.
- **Solusi:** Pelepasan saldo sewa dan pengembalian deposit otomatis saat barang diterima baik.
- **Cara Kerja:**
  1. Kedua pihak bertemu kembali di titik temu pengembalian.
  2. Pemilik memverifikasi kelengkapan dan menekan konfirmasi barang baik.
  3. Sistem meneruskan sewa ke pemilik dan memulangkan deposit ke penyewa.
- **Aturan Penting:** Pembagian alokasi komisi platform dibukukan otomatis saat konfirmasi.
- **Bukti:** `apps/rentals/services.py:konfirmasi_pengembalian_baik`, tes di `apps/rentals/tests.py`.
- **Tampilan:** `templates/rentals/rental_detail.html`.
- **Poin Bicara:** Saldo cair instan ke dompet internal tanpa jeda hari kerja perbankan.
- **Pertanyaan Juri:** Kapan konfirmasi otomatis terjadi? Setelah 48 jam masa tenggang pengembalian lewat.

#### Penagihan Denda dan Biaya Tambahan
- **Masalah:** Peminjam terlambat mengembalikan barang sehingga merugikan jadwal sewa berikutnya.
- **Solusi:** Perhitungan denda keterlambatan harian otomatis dan penerbitan tagihan ganti rugi resmi.
- **Cara Kerja:**
  1. Sistem mengecek batas waktu pengembalian lewat perintah berkala `process_deadlines`.
  2. Keterlambatan menghasilkan denda harian proporsional.
  3. Pemilik dapat menerbitkan tagihan tambahan atas kerusakan yang disetujui admin.
- **Aturan Penting:** Pengguna dengan tagihan tertunggak dibekukan dari membuat transaksi baru.
- **Bukti:** `apps/rentals/models.py:Rental.calc_late_fee`, `apps/payments/models.py:ExtraCharge`, tes di `apps/rentals/tests.py`.
- **Tampilan:** `templates/rentals/rental_detail.html`.
- **Poin Bicara:** Penegakan kedisiplinan jadwal melindungi hak pemilik tanpa pemotongan saldo sepihak di luar kesepakatan.
- **Pertanyaan Juri:** Bagaimana bila peminjam menolak membayar denda? Akun ditangguhkan dan data diteruskan ke pembinaan kemahasiswaan kampus.

#### Pengajuan Sengketa Sewa dan Mediasi Admin
- **Masalah:** Konflik saat barang mengalami kerusakan fisik atau perselisihan kondisi.
- **Solusi:** Ruang mediasi sengketa resmi yang ditengahi staf operasional kampus.
- **Cara Kerja:**
  1. Salah satu pihak mengajukan sengketa sebelum transaksi selesai.
  2. Penahanan dana dibekukan sementara di sistem.
  3. Admin memeriksa perbandingan foto kondisi dan riwayat obrolan.
  4. Admin menetapkan putusan: potong deposit atau kembalikan dana.
- **Aturan Penting:** Putusan mediasi admin bersifat final dan tercatat di audit log.
- **Bukti:** `apps/rentals/views.py:dispute_create_view`, model `Dispute`, tes di `apps/rentals/tests.py`.
- **Tampilan:** `templates/rentals/rental_detail.html`.
- **Poin Bicara:** Mekanisme penyelesaian konflik adil mencegah perselisihan personal antarmahasiswa.
- **Pertanyaan Juri:** Bila barang dicuri bagaimana? Dana Gotong Royong menanggung kerugian sesuai plafon.

#### Ulasan Sewa Dua Arah
- **Masalah:** Sulit mengenali peminjam yang ceroboh atau pemilik yang tidak ramah.
- **Solusi:** Sistem ulasan dan penilaian bintang 1 sampai 5 yang saling mengisi setelah transaksi selesai.
- **Cara Kerja:**
  1. Transaksi selesai memicu pembukaan form ulasan bagi penyewa dan pemilik.
  2. Masing-masing memberi skor bintang dan komentar objektif.
  3. Ulasan tampil pada profil publik dan memengaruhi skor reputasi.
- **Aturan Penting:** Ulasan hanya bisa diberikan sekali per transaksi dan tidak dapat diubah setelah dikirim.
- **Bukti:** `apps/rentals/views.py:review_create_view`, model `Review`, tes di `apps/rentals/tests.py`.
- **Tampilan:** `templates/catalog/item_detail.html`.
- **Poin Bicara:** Transparansi ulasan membangun budaya saling menghargai barang milik sesama mahasiswa.
- **Pertanyaan Juri:** Bisakah ulasan bernada kebencian dihapus? Admin memiliki hak moderasi atas ulasan yang melanggar norma komunitas.

---

### Kelompok 3: Modul Jual Beli (Thrift Kampus)

#### Pemasangan Iklan Barang Jualan dengan Batas Harga Reputasi
- **Masalah:** Akun baru rawan memasang barang fiktif bernilai tinggi untuk penipuan.
- **Solusi:** Plafon harga jual bertingkat yang dibatasi berdasarkan reputasi penjual.
- **Cara Kerja:**
  1. Penjual mengisi deskripsi, kondisi, minus, dan harga barang.
  2. Sistem memvalidasi harga terhadap batas plafon reputasi akun.
  3. Iklan berhasil ditayangkan bila tidak melampaui limit.
- **Aturan Penting:** Batas harga: Baru Rp1.000.000, Tepercaya Rp3.000.000, Sangat Tepercaya Rp8.000.000.
- **Bukti:** `apps/sales/forms.py:SaleItemForm`, `apps/sales/services.py:get_seller_max_price`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/item_form.html`.
- **Poin Bicara:** Batas harga mencegah kerugian finansial dari akun baru tanpa riwayat.
- **Pertanyaan Juri:** Bagaimana menaikkan limit? Menuntaskan transaksi dengan ulasan bintang lima tanpa sengketa.

#### Penyaringan Kata Kunci Barang Terlarang Kampus
- **Masalah:** Kampus melarang keras peredaran barang ilegal, rokok, miras, obat keras, atau tugas bajakan.
- **Solusi:** Penyaringan kata kunci terlarang otomatis pada judul dan deskripsi iklan jual beli.
- **Cara Kerja:**
  1. Penjual menekan tombol publikasikan barang.
  2. Validasi form memeriksa kata kunci terhadap daftar hitam komprehensif.
  3. Formulir ditolak dengan pesan peringatan jika mengandung kata terlarang.
- **Aturan Penting:** Mencakup miras, senjata, rokok, vape, narkoba, joki tugas, akun bajakan, dan satwa.
- **Bukti:** `apps/sales/forms.py:clean_title`, `apps/sales/forms.py:clean_description`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/item_form.html`.
- **Poin Bicara:** Menjaga kebersihan dan etika ekosistem akademik kampus dari perdagangan produk terlarang.
- **Pertanyaan Juri:** Bagaimana jika penjual sengaja menyamarkan ejaan? Sistem menggunakan pencocokan ekspresi reguler dan menyediakan tombol laporkan bagi pengguna lain.

#### Masa Tayang Listing dan Perpanjangan
- **Masalah:** Barang yang sudah laku di luar platform tetap tayang dan mengacaukan hasil pencarian.
- **Solusi:** Penerapan masa tayang iklan otomatis selama 60 hari dengan opsi perpanjangan mandiri.
- **Cara Kerja:**
  1. Iklan aktif selama 60 hari sejak tanggal dibuat.
  2. Penjual dapat menekan tombol perpanjang 60 hari jika barang belum terjual.
  3. Iklan kedaluwarsa otomatis disembunyikan dari katalog publik.
- **Aturan Penting:** Masa aktif bawaan adalah 60 hari.
- **Bukti:** `apps/sales/models.py:SaleItem:is_expired`, `apps/sales/views.py:my_sales_view`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/my_items.html`.
- **Poin Bicara:** Menjamin katalog selalu segar dan berisi barang-barang yang memang siap dijual.
- **Pertanyaan Juri:** Apakah iklan yang kedaluwarsa dihapus permanen? Tidak, iklan tersimpan di arsip penjual dan dapat diaktifkan kembali.

#### Katalog Jual Beli Mandiri dan Filter Kondisi
- **Masalah:** Mahasiswa ingin mencari barang bekas hemat tanpa bercampur dengan barang sewa.
- **Solusi:** Antarmuka katalog jual beli mandiri di rute `/jual-beli/` dengan filter kondisi fisik terperinci.
- **Cara Kerja:**
  1. Pengguna membuka portal jual beli.
  2. Memfilter berdasarkan kondisi: baru segel, seperti baru, baik, cukup, atau ada cacat.
  3. Hasil diurutkan berdasarkan harga termurah, terbaru, atau persentase hemat dari harga asli.
- **Aturan Penting:** Lima kondisi fisik standar dengan penjelasan wajib jika ada cacat.
- **Bukti:** `apps/sales/views.py:sale_item_list_view`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/item_list.html`.
- **Poin Bicara:** Navigasi mandiri membedakan intensi transaksi sewa sementara vs kepemilikan permanen.
- **Pertanyaan Juri:** Apakah pembeli bisa melihat harga beli asli barang tersebut? Ya, form mewajibkan pencantuman harga beli baru sebagai perbandingan kehematan.

#### Pembekuan Snapshot Spesifikasi dan Foto Barang
- **Masalah:** Penjual mengubah spesifikasi barang setelah dibeli untuk memanipulasi bukti komplain.
- **Solusi:** Pembekuan data snapshot barang dan hash foto saat pesanan terbentuk.
- **Cara Kerja:**
  1. Pembeli menekan tombol beli barang.
  2. Sistem membekukan judul, kondisi, minus, dan hash foto ke pesanan.
  3. Perubahan iklan asal tidak mengubah rekaman snapshot pesanan.
- **Aturan Penting:** Snapshot bersifat kekal (*immutable*) pada field `listing_snapshot`.
- **Bukti:** `apps/sales/models.py:SaleOrder:listing_snapshot`, `apps/sales/services.py:create_sale_order`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/order_detail.html`.
- **Poin Bicara:** Fakta transaksi terlindungi utuh dari manipulasi pascapembelian.
- **Pertanyaan Juri:** Mengapa memakai hash SHA-256 foto? Memverifikasi foto sengketa identik dengan foto saat dibeli.

#### Persetujuan Syarat dan Ketentuan Jual Beli Digital
- **Masalah:** Pembeli menuntut hal-hal di luar kewajaran tanpa memahami batas tanggung jawab platform.
- **Solusi:** Formulir persetujuan Syarat dan Ketentuan digital sebelum pembayaran dilakukan.
- **Cara Kerja:**
  1. Pembeli memeriksa rincian pesanan dan kuitansi komisi platform.
  2. Mencentang persetujuan syarat dan ketentuan transaksi barang bekas.
  3. Sistem mencatat jejak digital persetujuan ke tabel `SaleAgreement`.
- **Aturan Penting:** Menolak klausul retur di luar masa periksa resmi 48 jam.
- **Bukti:** `apps/sales/models.py:SaleAgreement`, `apps/sales/views.py:sale_agreement_view`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/sale_agreement.html`.
- **Poin Bicara:** Menyelaraskan ekspektasi pembeli bahwa barang yang dibeli adalah barang bekas layak pakai sesuai deskripsi.
- **Pertanyaan Juri:** Kapan pembeli bisa membatalkan transaksi? Sebelum barang diserahterimakan secara fisik di titik temu.

#### Pembayaran Pesanan Ditahan dan Komisi Platform
- **Masalah:** Pembeli khawatir dana raib bila transfer langsung tanpa jaminan barang diserahkan.
- **Solusi:** Penahanan dana pada rekening bersama platform dan alokasi komisi otomatis.
- **Cara Kerja:**
  1. Pembeli melunasi tagihan lewat Midtrans dengan batas 6 jam.
  2. Dana ditahan platform, alokasi komisi 5% (min Rp2.000) dicatat.
  3. Penjual menerima pemberitahuan pesanan dibayar untuk menjadwalkan temu.
- **Aturan Penting:** Komisi platform sebesar 5% (minimal Rp2.000) dialokasikan ke kas.
- **Bukti:** `apps/sales/services.py:create_sale_order`, `apps/payments/services.py`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/order_detail.html`.
- **Poin Bicara:** Uang pembeli terjamin aman hingga barang diterima dan dicek langsung.
- **Pertanyaan Juri:** Bila pembeli tak bayar dalam 6 jam? Pesanan otomatis dibatalkan sistem.

#### Jadwal Temu dan Serah Terima Fisik Langsung
- **Masalah:** Ongkos kirim ekspedisi mahal dan barang rawan rusak di perjalanan paket.
- **Solusi:** Pertemuan langsung di titik temu kampus dalam rentang maksimal tujuh hari.
- **Cara Kerja:**
  1. Penjual dan pembeli menyepakati titik temu kampus dan tanggal pertemuan.
  2. Saat bertemu, pembeli memeriksa barang dan penjual mengunggah foto serah terima.
  3. Tombol serah terima ditekan untuk memulai masa inspeksi.
- **Aturan Penting:** Batas waktu pertemuan adalah 7 hari kalender sejak pembayaran.
- **Bukti:** `apps/sales/services.py:mark_sale_order_handed_over`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/order_detail.html`.
- **Poin Bicara:** Bebas ongkir, ramah lingkungan, dan mempererat interaksi positif komunitas mahasiswa satu kampus.
- **Pertanyaan Juri:** Bagaimana jika salah satu pihak tidak hadir? Transaksi dapat dibatalkan dan uang dikembalikan penuh ke dompet pembeli.

#### Masa Pemeriksaan Empat Puluh Delapan Jam
- **Masalah:** Kerusakan fungsi elektronik sering baru disadari saat dicoba di indekos.
- **Solusi:** Hak masa inspeksi 48 jam bagi pembeli sebelum dana dicairkan ke penjual.
- **Cara Kerja:**
  1. Waktu mundur 48 jam aktif setelah serah terima fisik selesai.
  2. Pembeli menguji fungsionalitas barang di tempat tinggalnya.
  3. Pembeli menekan konfirmasi terima, atau sistem mencairkan dana otomatis saat 48 jam usai.
- **Aturan Penting:** Dana tertahan penuh sepanjang jendela inspeksi 48 jam (`SALE_INSPECTION_HOURS = 48`).
- **Bukti:** `apps/sales/services.py:confirm_sale_order_received`, `apps/sales/services.py:settle_sale_order`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/order_detail.html`.
- **Poin Bicara:** Garansi periksa mandiri menjamin barang elektronik bekas benar-benar berfungsi normal.
- **Pertanyaan Juri:** Bisakah cair lebih cepat? Bisa jika pembeli menekan konfirmasi puas lebih awal.

#### Pembatalan Pesanan dan Pengembalian Saldo Instan
- **Masalah:** Penjual mendadak kehilangan barang atau pembeli membatalkan rencana perkuliahan.
- **Solusi:** Fitur pembatalan pesanan sebelum serah terima dengan pengembalian saldo instan seratus persen.
- **Cara Kerja:**
  1. Salah satu pihak menekan tombol batalkan pesanan sebelum serah terima terjadi.
  2. Sistem memvalidasi status pesanan belum diserahkan.
  3. Uang sewa dikembalikan seutuhnya ke dompet internal pembeli dalam detik yang sama.
- **Aturan Penting:** Pengembalian dana 100 persen tanpa potongan denda sebelum serah terima.
- **Bukti:** `apps/sales/services.py:cancel_sale_order`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/order_detail.html`.
- **Poin Bicara:** Tidak ada dana mahasiswa yang tersangkut atau hilang saat pembatalan wajar disepakati.
- **Pertanyaan Juri:** Bagaimana jika pembatalan dilakukan sepihak berulang kali? Akun yang sering membatalkan akan mengalami penurunan skor kepercayaan.

#### Sengketa Jual Beli dengan Perbandingan Snapshot
- **Masalah:** Barang yang diserahkan rusak atau tidak sesuai dengan informasi iklan.
- **Solusi:** Pengajuan klaim komplain selama masa periksa 48 jam berbasis snapshot.
- **Cara Kerja:**
  1. Pembeli mengunggah bukti foto cacat barang dan alasan komplain.
  2. Dana dibekukan dan tiket diteruskan ke dasbor admin.
  3. Admin membandingkan kondisi riil dengan snapshot pesanan awal.
  4. Putusan admin: pengembalian saldo pembeli atau pencairan penjual.
- **Aturan Penting:** Batas pengajuan sengketa adalah sebelum masa periksa 48 jam habis.
- **Bukti:** `apps/sales/models.py:SaleDispute`, `apps/sales/views.py:sale_dispute_create_view`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/order_detail.html`.
- **Poin Bicara:** Pembeli memiliki garansi keamanan tanpa rasa cemas tertipu barang rusak.
- **Pertanyaan Juri:** Alur retur barang? Admin mengatur jadwal temu pengembalian sebelum saldo dipulangkan.

#### Ulasan Dua Arah Jual Beli
- **Masalah:** Tidak ada jejak transparansi antara pembeli yang suka menunda janji dan penjual jujur.
- **Solusi:** Sistem ulasan dan rating dua arah khusus transaksi jual beli selesai.
- **Cara Kerja:**
  1. Setelah pesanan selesai, formulir ulasan terbuka untuk kedua pihak.
  2. Memberi skor 1 sampai 5 bintang dan teks komentar maksimal 300 karakter.
  3. Nilai rating langsung memengaruhi reputasi penjual dan pembeli.
- **Aturan Penting:** Ulasan bersifat permanen dan saling mengunci.
- **Bukti:** `apps/sales/models.py:SaleReview`, `apps/sales/views.py:sale_review_create_view`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/order_detail.html`.
- **Poin Bicara:** Membangun ekosistem jual beli yang sehat berdasarkan penilaian jujur sesama rekan mahasiswa.
- **Pertanyaan Juri:** Bisakah membalas ulasan yang tidak adil? Pengguna dapat melaporkan ulasan fitnah kepada admin untuk ditinjau.

#### Evaluasi Tingkat Reputasi Penjual Otomatis
- **Masalah:** Pembeli bingung membedakan penjual teruji dengan akun perdana.
- **Solusi:** Lencana reputasi bertingkat yang dihitung otomatis dari riwayat penjualan.
- **Cara Kerja:**
  1. Kalkulator mengevaluasi pesanan tuntas, rating rata-rata, dan sengketa.
  2. Menyematkan tingkat: Penjual Baru, Tepercaya, atau Sangat Tepercaya.
  3. Lencana reputasi disematkan pada etalase dan profil publik.
- **Aturan Penting:** Tepercaya butuh minimal 3 transaksi rating 4,5; Sangat Tepercaya 10 transaksi rating 4,8.
- **Bukti:** `apps/sales/services.py:get_seller_tier`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/partials/trust_ring.html`.
- **Poin Bicara:** Reputasi menjadi modal sosial berharga bagi mahasiswa di platform.
- **Pertanyaan Juri:** Apakah sengketa menurunkan reputasi? Sengketa terbukti bersalah menurunkan status ke Penjual Baru.

#### Pelaporan Barang Jualan dan Moderasi Penurunan Iklan
- **Masalah:** Iklan spam atau melanggar aturan yang lolos dari filter otomatis.
- **Solusi:** Tombol pelaporan masyarakat kampus dan fitur penurunan paksa oleh moderator.
- **Cara Kerja:**
  1. Mahasiswa mengeklik tombol laporkan barang pada halaman detail barang.
  2. Memilih 1 dari 6 alasan pelanggaran resmi.
  3. Admin meninjau antrean dan dapat menurunkan iklan dengan alasan wajib.
- **Aturan Penting:** Iklan yang diturunkan otomatis membatalkan pesanan yang belum dibayar.
- **Bukti:** `apps/sales/models.py:SaleItemReport`, `apps/sales/views.py:report_sale_item_view`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/item_detail.html`.
- **Poin Bicara:** Moderasi partisipatif melibatkan seluruh komunitas mahasiswa untuk menjaga keamanan kampus bersama.
- **Pertanyaan Juri:** Apakah pelapor diberi tahu tindak lanjut laporannya? Status penanganan tercatat di panel audit admin.

#### Penawaran Harga Terstruktur
- **Masalah:** Budaya tawar-menawar barang bekas di Indonesia sering tidak tertib dan bertele-tele di ruang obrolan.
- **Solusi:** Fitur negosiasi harga terstruktur dengan batas waktu penawaran resmi 24 jam.
- **Cara Kerja:**
  1. Calon pembeli mengajukan penawaran harga wajar di bawah harga iklan.
  2. Penjual memiliki waktu 24 jam untuk menerima atau menolak tawaran.
  3. Jika diterima, pesanan langsung terbentuk dengan harga baru dan batas waktu bayar 6 jam.
- **Aturan Penting:** Fitur dikendalikan saklar sistem `SALE_OFFERS_ENABLED` (bawaan: dinonaktifkan).
- **Bukti:** `apps/sales/models.py:SaleOffer`, `apps/sales/views.py:create_sale_offer_view`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/sales/item_detail.html`.
- **Poin Bicara:** Tawar-menawar menjadi terikat komitmen, bukan sekadar basa-basi tanpa kepastian bayar.
- **Pertanyaan Juri:** Mengapa statusnya saklar? Pengelola platform dapat mengaktifkannya bertahap sesuai dinamika likuiditas pasar kampus.

---

### Kelompok 4: Pengelolaan Keuangan (Finansial dan Buku Besar)

#### Penahanan Pembayaran Platform (Escrow)
- **Masalah:** Pembayaran langsung antarrekening pribadi sering berujung penipuan atau barang tidak dikembalikan.
- **Solusi:** Penahanan seluruh pembayaran pada rekening bersama platform hingga kewajiban transaksi selesai.
- **Cara Kerja:**
  1. Dana pembeli atau penyewa masuk ke rekening penampungan via payment gateway.
  2. Sistem mengunci status pembayaran pada tabel `Payment`.
  3. Dana baru dilepaskan setelah syarat fisik dan waktu terpenuhi.
- **Aturan Penting:** Tidak ada transfer dana langsung antarmahasiswa di luar sistem platform.
- **Bukti:** `apps/payments/models.py:Payment`, `apps/payments/services.py`, tes di `apps/payments/tests.py`.
- **Tampilan:** `templates/payments/wallet.html`.
- **Poin Bicara:** Garansi keamanan seratus persen bagi uang mahasiswa selama masa transaksi berlangsung.
- **Pertanyaan Juri:** Di mana dana disimpan secara fisik? Pada rekening giro resmi platform yang terhubung dengan akun merchant Midtrans.

#### Buku Besar Berpasangan (Double-Entry Ledger)
- **Masalah:** Selisih saldo dan ketidakjelasan arus uang masuk-keluar rawan menimbulkan kecurangan akuntansi.
- **Solusi:** Pencatatan setiap pergerakan rupiah ke dalam jurnal debit dan kredit berimbang yang permanen.
- **Cara Kerja:**
  1. Setiap transaksi memicu pembuatan sepasang entri jurnal (`LedgerEntry`).
  2. Sisi debit mencatat pos asal dan sisi kredit mencatat pos tujuan.
  3. Selisih total debit dan kredit pada sistem wajib bernilai nol.
- **Aturan Penting:** Catatan jurnal tidak dapat diedit atau dihapus (*append-only*).
- **Bukti:** `apps/payments/models.py:LedgerEntry`, `apps/payments/services.py:create_ledger_entry`, tes di `apps/payments/tests.py`.
- **Tampilan:** `templates/payments/admin_reconciliation.html`.
- **Poin Bicara:** Standar pencatatan keuangan Collective Campus setara dengan sistem inti perbankan modern.
- **Pertanyaan Juri:** Bagaimana jika terjadi kesalahan transfer? Diterbitkan jurnal koreksi baru berpasangan tanpa mengubah riwayat lama.

#### Dompet Internal Pengguna
- **Masalah:** Mahasiswa kerepotan harus transfer berulang kali saat sering menyewa atau menjual perlengkapan.
- **Solusi:** Dompet internal untuk menampung hasil sewa, hasil penjualan, dan pengembalian uang jaminan.
- **Cara Kerja:**
  1. Setiap pengguna terdaftar otomatis memiliki satu akun dompet internal.
  2. Saldo bertambah saat transaksi sewa tuntas atau deposit dikembalikan.
  3. Saldo dapat ditarik ke rekening bank riil kapan saja.
- **Aturan Penting:** Saldo dompet tidak dapat bernilai negatif.
- **Bukti:** `apps/payments/models.py:WalletTransaction`, `apps/payments/views.py:wallet_view`, tes di `apps/payments/tests.py`.
- **Tampilan:** `templates/payments/wallet.html`.
- **Poin Bicara:** Fleksibilitas tinggi bagi mahasiswa aktif untuk memutar kembali dananya di dalam ekosistem kampus.
- **Pertanyaan Juri:** Apakah saldo dompet dikenakan biaya admin bulanan? Bebas biaya administrasi bulanan sepeser pun.

#### Penarikan Dana Terenkripsi
- **Masalah:** Nomor rekening bank mahasiswa bocor dan disalahgunakan pihak ketiga.
- **Solusi:** Permohonan penarikan dana dengan enkripsi nomor rekening perbankan pada database.
- **Cara Kerja:**
  1. Pengguna memasukkan nama bank, nomor rekening, dan nominal penarikan.
  2. Nomor rekening dienkripsi menggunakan algoritma AES sebelum disimpan.
  3. Admin memproses transfer bank riil dan menandai penarikan selesai.
- **Aturan Penting:** Penarikan minimal Rp10.000 dengan saldo mencukupi.
- **Bukti:** `apps/payments/encryption.py:encrypt_account_number`, `apps/payments/views.py:withdrawal_request_view`, tes di `apps/payments/tests.py`.
- **Tampilan:** `templates/payments/withdrawal_form.html`.
- **Poin Bicara:** Keamanan informasi perbankan mahasiswa terlindungi bahkan jika database mengalami kebocoran fisik.
- **Pertanyaan Juri:** Kapan nomor rekening didekripsi? Hanya saat admin yang berwenang membuka permohonan transfer di portal staf.

#### Rekonsiliasi Otomatis Saldo dan Buku Besar
- **Masalah:** Terjadinya ketidaksinkronan data antara saldo dompet yang tampil dengan mutasi transaksi riil.
- **Solusi:** Perintah audit rekonsiliasi otomatis yang membandingkan saldo dompet terhadap total mutasi buku besar.
- **Cara Kerja:**
  1. Perintah manajemen `reconcile_finances` dijalankan sistem secara berkala.
  2. Menghitung akumulasi debit/kredit seluruh pengguna.
  3. Melaporkan anomali jika ditemukan ketidaksesuaian nilai rupiah.
- **Aturan Penting:** Toleransi selisih adalah Rp0 (nol rupiah).
- **Bukti:** `apps/payments/management/commands/reconcile_finances.py`, `apps/payments/reconciliation.py:run_financial_reconciliation`, tes di `apps/payments/tests.py`.
- **Tampilan:** `templates/payments/admin_reconciliation.html`.
- **Poin Bicara:** Audit internal transparan memastikan seluruh rupiah mahasiswa tercatat presisi hingga digit terakhir.
- **Pertanyaan Juri:** Apa tindakan sistem jika ditemukan anomali saldo? Akun terkait ditandai otomatis untuk audit manual admin sebelum penarikan diizinkan.

#### Pemotongan Komisi Platform dan Dana Gotong Royong
- **Masalah:** Kebutuhan biaya operasional server dan dana proteksi cadangan sengketa.
- **Solusi:** Pemotongan komisi 5% transparan untuk operasional dan alokasi perlindungan gotong royong.
- **Cara Kerja:**
  1. Sistem memotong komisi saat pembayaran transaksi tuntas.
  2. Dana dibagi ke kas operasional dan cadangan gotong royong.
  3. Saldo bersih diteruskan ke dompet pemilik atau penjual.
- **Aturan Penting:** Komisi jual beli adalah 5% dengan nilai batas minimal Rp2.000.
- **Bukti:** `config/settings.py:SALE_COMMISSION_PERCENT`, `apps/sales/services.py:calculate_sale_commission`, tes di `apps/sales/tests.py`.
- **Tampilan:** `templates/catalog/partials/receipt_summary.html`.
- **Poin Bicara:** Bagi hasil ringan menjamin kesinambungan platform kampus mandiri.
- **Pertanyaan Juri:** Fungsi Dana Gotong Royong? Menalangi kerugian insidental tanpa memberatkan mahasiswa.

---

### Kelompok 5: Kepercayaan dan Kecerdasan Buatan (Machine Learning)

#### Model Machine Learning Skor Kepercayaan Terkalibrasi
- **Masalah:** Penilaian risiko manual rentan diskriminasi dan bias subjektif.
- **Solusi:** Model regresi logistik terkalibrasi probabilitas (*Platt Scaling*) penaksir risiko transaksi sewa.
- **Cara Kerja:**
  1. Sistem mengekstrak fitur perilaku objektif (keterlambatan, sengketa, usia akun).
  2. Model menghitung probabilitas risiko dan mengonversinya ke skor 0-100.
  3. Skor dikelompokkan: Pengguna Baru, Cukup Tepercaya, atau Tepercaya.
- **Aturan Penting:** Bebas atribut sensitif (gender, suku, agama, jurusan dilarang keras).
- **Bukti:** `ml/train_trust_model.py`, `apps/trust/services.py:recompute_trust_score`, tes di `apps/trust/tests_ml.py`.
- **Tampilan:** `templates/trust/admin_model_score.html`.
- **Poin Bicara:** Kecerdasan buatan etis menilai murni dari rekam jejak perilaku.
- **Pertanyaan Juri:** Mengapa perlu dikalibrasi? Agar estimasi probabilitas selaras dengan frekuensi risiko faktual.

#### Penjelasan Transparan Faktor Skor Pengguna
- **Masalah:** Model kecerdasan buatan kerap menjadi kotak hitam tanpa alasan gamblang.
- **Solusi:** Penyajian tiga faktor penjelas utama berbasis kontribusi bobot koefisien fitur.
- **Cara Kerja:**
  1. Menghitung pengaruh relatif masing-masing fitur perilaku.
  2. Tiga faktor teratas diterjemahkan menjadi narasi bahasa Indonesia.
  3. Tampil mendampingi cincin skor pada etalase dan profil pengguna.
- **Aturan Penting:** Menyajikan 3 faktor penjelas konkret di field `top_factors`.
- **Bukti:** `apps/trust/services.py:explain_factors`, `apps/trust/models.py:TrustScore.top_factors`, tes di `apps/trust/tests_ml.py`.
- **Tampilan:** `templates/partials/trust_ring.html`.
- **Poin Bicara:** Transparansi edukatif memandu mahasiswa meningkatkan kredibilitasnya.
- **Pertanyaan Juri:** Bagaimana skor pengguna baru? Berstatus Pengguna Baru netral dengan skor dasar 60.

#### Pembelajaran Ulang Model dari Data Nyata
- **Masalah:** Model kecerdasan buatan statis usang terhadap pergeseran pola transaksi baru.
- **Solusi:** Pembelajaran ulang otomatis berkala dengan pengujian kriteria promosi versi ketat.
- **Cara Kerja:**
  1. Menghimpun rekaman contoh transaksi nyata yang tuntas.
  2. Melatih model baru dan mengukur Brier Score serta ROC-AUC.
  3. Versi baru dipromosikan bila performa lebih baik; otomatis rollback bila menurun.
- **Aturan Penting:** Promosi mensyaratkan perbaikan Brier Score minimal 1% dari versi aktif.
- **Bukti:** `apps/trust/management/commands/retrain_trust_model.py`, `apps/trust/models.py:TrustModelVersion`, tes di `apps/trust/tests_phase7c_ml.py`.
- **Tampilan:** `templates/trust/admin_model_score.html`.
- **Poin Bicara:** Model beradaptasi berkelanjutan dengan pagar pengaman regresi otomatis.
- **Pertanyaan Juri:** Bila data masih minim? Sistem menggunakan aturan dasar (*cold-start*) aman.

---

### Kelompok 6: Komunikasi dan Notifikasi

#### Percakapan Langsung Antarmahasiswa
- **Masalah:** Kebutuhan koordinasi transaksi tanpa harus membagikan kontak pribadi ke orang asing.
- **Solusi:** Ruang percakapan langsung internal yang terikat pada item transaksi terkait.
- **Cara Kerja:**
  1. Pengguna mengeklik tombol hubungi pemilik di halaman barang.
  2. Percakapan baru terbuat terikat id barang.
  3. Mahasiswa berkoordinasi secara instan di antarmuka web.
- **Aturan Penting:** Obrolan terisolasi khusus antara kedua pihak yang bertransaksi.
- **Bukti:** `apps/chat/views.py:chat_conversation_view`, model `Conversation`, model `Message`, tes di `apps/chat/tests.py`.
- **Tampilan:** `templates/chat/conversation.html`.
- **Poin Bicara:** Rekaman obrolan menjadi bukti pendukung resmi bila terjadi perselisihan.
- **Pertanyaan Juri:** Bisakah kirim gambar di chat? Pengiriman foto difasilitasi pada dokumentasi serah terima.

#### Penyamaran Nomor Kontak dan Tautan Luar
- **Masalah:** Pengguna nakal mengajak transaksi di luar platform (*off-platform*) yang menghilangkan perlindungan penahanan dana.
- **Solusi:** Algoritma penyamaran nomor telepon, alamat email, dan tautan luar pada ruang percakapan.
- **Cara Kerja:**
  1. Pesan yang diketik disaring ekspresi reguler pendeteksi nomor ponsel, format kontak, dan URL luar.
  2. Karakter sensitif otomatis disamarkan dengan tanda bintang sebelum disimpan ke database.
- **Aturan Penting:** Penyamaran aktif sebelum kesepakatan jadwal temu resmi dicapai.
- **Bukti:** `apps/chat/models.py:Message.mask_contact_info`, tes di `apps/chat/tests.py`.
- **Tampilan:** `templates/chat/conversation.html`.
- **Poin Bicara:** Mencegah kebocoran data pribadi mahasiswa dan menjaga transaksi tetap berada dalam koridor perlindungan platform.
- **Pertanyaan Juri:** Apakah kontak tetap disamarkan setelah jadwal temu disetujui? Setelah jadwal temu resmi disetujui kedua pihak, kontak koordinasi darurat dapat dibuka terbatas.

#### Panel Notifikasi Dalam Aplikasi
- **Masalah:** Mahasiswa terlambat mengetahui pengajuan sewanya disetujui sehingga jadwal pengambilan terlewat.
- **Solusi:** Lonceng notifikasi dalam aplikasi dengan panel dropdown HTMX responsif.
- **Cara Kerja:**
  1. Peristiwa transaksi (pengajuan disetujui, pembayaran diterima, jadwal disepakati) memicu pembuatan notifikasi.
  2. Lencana angka merah muncul di bilah navigasi atas.
  3. Pengguna mengeklik lonceng untuk membaca ringkasan dan langsung dialihkan ke detail transaksi.
- **Aturan Penting:** Dilengkapi tombol tandai semua dibaca dengan pembaruan dinamis tanpa reload halaman.
- **Bukti:** `apps/core/models.py:Notification.notify`, `apps/core/views.py:notification_panel_view`, tes di `apps/core/tests_phase7a.py`.
- **Tampilan:** `templates/core/partials/notification_panel.html`.
- **Poin Bicara:** Pengalaman pengguna yang mulus dan cepat berkat integrasi teknologi HTMX modern.
- **Pertanyaan Juri:** Apakah ada notifikasi lewat email? Ya, pemberitahuan kritis seperti tagihan dan konfirmasi akun diduplikasi ke email terdaftar.

---

### Kelompok 7: Keamanan, Privasi, dan Kepatuhan

#### Isolasi Berkas Identitas Pribadi Mahasiswa
- **Masalah:** Kebocoran foto identitas mahasiswa rawan disalahgunakan kejahatan digital eksternal.
- **Solusi:** Isolasi foto Kartu Tanda Mahasiswa di direktori tertutup tanpa rute URL publik.
- **Cara Kerja:**
  1. Foto identitas diunggah saat verifikasi akun.
  2. Berkas disimpan dengan penamaan hash acak di `private_media/`.
  3. Web server dilarang melayani akses langsung ke folder privat.
- **Aturan Penting:** Berkas hanya dapat dibuka oleh staf kampus melalui view terautentikasi.
- **Bukti:** `config/settings.py:PRIVATE_MEDIA_ROOT`, `apps/verification/views.py`, tes di `apps/verification/tests.py`.
- **Tampilan:** `templates/admin/index.html`.
- **Poin Bicara:** Kepatuhan privasi mahasiswa diterapkan sebagai fondasi arsitektur utama.
- **Pertanyaan Juri:** Kepatuhan terhadap regulasi PDP? Menerapkan pembatasan peran ketat dan enkripsi lokasi.

#### Pembersihan Berkas Foto Identitas dan Serah Terima Berkala
- **Masalah:** Penumpukan foto identitas lama di server memperbesar risiko keamanan data.
- **Solusi:** Penghapusan berkas otomatis setelah masa retensi transaksi tuntas terlampaui.
- **Cara Kerja:**
  1. Perintah `process_deadlines` memindai transaksi tuntas melewati masa retensi.
  2. Memusnahkan berkas fisik foto dari disk server secara permanen.
  3. Memperbarui stempel audit bahwa berkas telah dibersihkan.
- **Aturan Penting:** Foto serah terima dihapus otomatis setelah masa retensi (`HANDOVER_PHOTO_RETENTION_DAYS`).
- **Bukti:** `apps/rentals/photos.py:purge_handover_photos`, perintah `process_deadlines`, tes di `apps/rentals/tests.py`.
- **Tampilan:** `templates/admin/index.html`.
- **Poin Bicara:** Menjaga kebersihan data server sesuai prinsip penghapusan berkas usang.
- **Pertanyaan Juri:** Jika timbul sengketa pascapenghapusan? Sengketa hanya sah diajukan saat masa transaksi aktif.

#### Pencatatan Log Akses Nomor Rekening Bank
- **Masalah:** Staf internal berpotensi menyalahgunakan wewenang melihat data perbankan mahasiswa.
- **Solusi:** Pencatatan log otomatis setiap kali data rekening bank pengguna dibuka oleh akun staf.
- **Cara Kerja:**
  1. Staf membuka rincian permohonan penarikan dana di portal admin.
  2. Sistem mendekripsi nomor rekening dan mencatat nama staf, stempel waktu, alamat IP, serta alasan akses ke tabel log audit.
- **Aturan Penting:** Rekaman log audit bersifat kekal dan tidak dapat diubah oleh staf.
- **Bukti:** `apps/payments/models.py:WithdrawalAccountAccessLog`, `apps/payments/views.py`, tes di `apps/payments/tests.py`.
- **Tampilan:** `templates/payments/admin_withdrawals.html`.
- **Poin Bicara:** Akuntabilitas internal tingkat tinggi yang mencegah penyalahgunaan wewenang staf platform.
- **Pertanyaan Juri:** Siapa yang bisa melihat rekaman log audit ini? Hanya pimpinan tim atau auditor keamanan bersertifikat superuser.

#### Penangguhan Akun Mahasiswa Pelanggar
- **Masalah:** Pengguna yang melanggar etika tetap berupaya melakukan transaksi di kampus.
- **Solusi:** Penangguhan (*suspend*) akun dengan pembekuan hak akses dan pencatatan sanksi resmi.
- **Cara Kerja:**
  1. Staf menetapkan status penangguhan pada profil mahasiswa bermasalah.
  2. Alasan pelanggaran dicatat di model `SuspensionRecord`.
  3. Sesi aktif diputus dan seluruh iklan otomatis diturunkan dari etalase.
- **Aturan Penting:** Mahasiswa ditangguhkan dilarang masuk dan meminjam barang.
- **Bukti:** `apps/accounts/models.py:SuspensionRecord`, `apps/accounts/decorators.py:active_student_required`, tes di `apps/accounts/tests.py`.
- **Tampilan:** `templates/admin/accounts/user/suspend_intermediate.html`.
- **Poin Bicara:** Ekosistem kampus terjaga steril dari pihak yang merugikan mahasiswa.
- **Pertanyaan Juri:** Bisakah mendaftar ulang? NIM otomatis diblokir di `BlacklistedNim`.

---

### Kelompok 8: Administrasi dan Pengelolaan Platform

#### Pusat Operasional Terpadu (Single Admin Framework)
- **Masalah:** Pengawasan operasional staf terhambat bila menu aplikasi terpecah-pecah.
- **Solusi:** Dasbor administrasi terpadu kustomisasi Django Admin bernuansa kertas dan tinta.
- **Cara Kerja:**
  1. Staf masuk ke portal `/admin/` dengan kredensial berwenang.
  2. Halaman depan menyajikan antrean prioritas dan statistik volume.
  3. Bilah navigasi mengelompokkan modul transaksi, keuangan, dan kecerdasan buatan.
- **Aturan Penting:** Izin dibatasi granular melalui hak akses peran (*role-based permission*).
- **Bukti:** `config/urls.py`, `templates/admin/index.html`, `apps/core/admin_nav.py`.
- **Tampilan:** `templates/admin/index.html`.
- **Poin Bicara:** Tata kelola kampus efisien dengan seluruh kendali operasional terintegrasi.
- **Pertanyaan Juri:** Mengapa memilih Django Admin? Tangguh dari segi keamanan bawaan dan cepat diintegrasikan.

#### Antrean Operasional Staf
- **Masalah:** Permohonan verifikasi dan pencairan dana rentan terlewat bila tidak diagregasi.
- **Solusi:** Widget antrean tindakan terpadu yang menampilkan akumulasi berkas pending.
- **Cara Kerja:**
  1. Dasbor memuat badge antrean verifikasi, pencairan, sengketa, dan laporan.
  2. Angka badge bertindak sebagai tautan filter cepat ke daftar tugas.
  3. Staf memproses tiket operasional dengan konfirmasi modal aman.
- **Aturan Penting:** Standar respons operasional staf ditargetkan tuntas dalam 24 jam.
- **Bukti:** `templates/admin/index.html`, context processor admin di `apps/core/views.py`.
- **Tampilan:** `templates/admin/index.html`.
- **Poin Bicara:** Kecepatan layanan terjaga prima melalui visibilitas beban kerja terpusat.
- **Pertanyaan Juri:** Apakah multi-staf didukung? Staf kampus dapat berkolaborasi serentak tanpa konflik.

#### Dasbor Pemantauan Kinerja Model Machine Learning
- **Masalah:** Kesulitan memantau degradasi performa model kecerdasan buatan di lapangan.
- **Solusi:** Dasbor evaluasi metrik kalibrasi dan simulator skor interaktif di `/admin/model-skor/`.
- **Cara Kerja:**
  1. Staf membuka portal pemantauan model Machine Learning.
  2. Mengamati kurva ROC-AUC, kurva kalibrasi probabilitas, dan bobot fitur.
  3. Menguji simulasi skor profil hipotetis menggunakan slider interaktif.
- **Aturan Penting:** Menampilkan versi model aktif dan riwayat evaluasi rollback.
- **Bukti:** `apps/trust/views.py:admin_model_score_view`, `templates/trust/admin_model_score.html`, tes di `apps/trust/tests_ml.py`.
- **Tampilan:** `templates/trust/admin_model_score.html`.
- **Poin Bicara:** Akuntabilitas ilmiah kecerdasan buatan disajikan transparan dan dapat diaudit.
- **Pertanyaan Juri:** Hak rollback model? Terbatas khusus bagi staf teknis berwenang.

#### Pengumuman Siaran Massal Berjadwal
- **Masalah:** Informasi penting kampus lambat sampai ke seluruh mahasiswa secara serentak.
- **Solusi:** Siaran pengumuman massal portal admin langsung ke lonceng notifikasi pengguna.
- **Cara Kerja:**
  1. Admin mengisi judul, pesan pengumuman, dan tautan arahan.
  2. Menekan tombol siarkan ke seluruh mahasiswa aktif.
  3. Sistem mendistribusikan notifikasi massal secara serentak.
- **Aturan Penting:** Menggunakan transaksi batch efisien via `Notification.objects.bulk_create`.
- **Bukti:** `apps/core/views.py:admin_broadcast_announcement_view`, `templates/admin/broadcast_announcement.html`, tes di `apps/core/tests_phase7e_admin_shell.py`.
- **Tampilan:** `templates/admin/broadcast_announcement.html`.
- **Poin Bicara:** Komunikasi darurat kampus terdistribusi instan tanpa biaya transmisi eksternal.
- **Pertanyaan Juri:** Dapatkah dimatikan mahasiswa? Pengumuman darurat bersifat mutlak tampil di lonceng.

---

### Kelompok 9: Identitas Visual dan Pengalaman Pengguna (UI/UX)

#### Bahasa Desain Kertas dan Tinta (Paper and Ink)
- **Masalah:** Antarmuka modern kerap tampak seperti template generik dengan efek blur berlebihan.
- **Solusi:** Visual khas kertas hangat dan tinta navy berkarakter dokumen resmi terpercaya.
- **Cara Kerja:**
  1. Menerapkan token palet: paper `#F8F5EE`, ink `#141B34`, brand `#1F45C4`.
  2. Menghilangkan gradien visual, bayangan tebal, dan efek kaca buram.
  3. Membatasi komponen dengan garis tegas 1 piksel (`line #E4DECF`).
- **Aturan Penting:** Larangan keras terhadap efek *backdrop-blur* dan gradien warna.
- **Bukti:** `docs/references/AGENT.md`, `tailwind.config.js`, tes kepatuhan di `apps/core/tests_phase7b.py`.
- **Tampilan:** `templates/home.html`.
- **Poin Bicara:** Karakter kertas cetak memberikan impresi institusi kampus yang kokoh dan berwibawa.
- **Pertanyaan Juri:** Mengapa melarang gradien? Gradien artifisial menurunkan kredibilitas dan kontras keterbacaan.

#### Sentuhan Budaya Lokal Lampung-Nusantara Terukur
- **Masalah:** Aksen budaya kerap dipasang berlebihan hingga merusak keterbacaan antarmuka web.
- **Solusi:** Penerapan ornamen geometris Tapis dan Siger Lampung terukur pada lokasi strategis.
- **Cara Kerja:**
  1. Motif disematkan sebagai pita pembatas kuitansi dan pembatas footer.
  2. Memakai warna kunyit di atas kanvas tinta atau marun Tapis (`#5B1A24`).
  3. Seluruh aset dekoratif diberi atribut aksesibilitas `aria-hidden="true"`.
- **Aturan Penting:** Luas ornamen dibatasi maksimal 10% dari total area tampilan.
- **Bukti:** `docs/references/AGENT.md`, `templates/partials/kain_border.html`, `static/img/tapis-tile.svg`.
- **Tampilan:** `templates/home.html`.
- **Poin Bicara:** Memadukan kearifan lokal Nusantara secara modern dan ramah aksesibilitas.
- **Pertanyaan Juri:** Apakah aset memberatkan beban web? Berkas SVG berukuran kurang dari 2 kilobita.

#### Antarmuka Responsif Layar Ponsel dan Desktop
- **Masalah:** Mahasiswa sering bertransaksi lewat ponsel di koridor kampus maupun kantin.
- **Solusi:** Desain responsif penuh yang dioptimalkan dari lebar 320px hingga desktop 1280px.
- **Cara Kerja:**
  1. Tata letak hero dua kolom tersusun vertikal di layar ponsel.
  2. Bilah navigasi menyediakan laci menu geser ramah ibu jari.
  3. Tabel transaksi dilengkapi pembungkus geser horizontal aman.
- **Aturan Penting:** Target sentuh tombol minimal 44x44 piksel untuk ergonomi layar sentuh.
- **Bukti:** `scripts/responsive_audit.py`, `scripts/spacing_audit.py`, tes di `apps/core/tests_phase7b.py`.
- **Tampilan:** `templates/base.html`.
- **Poin Bicara:** Pengalaman pengguna seragam dari ponsel murah hingga layar monitor laptop.
- **Pertanyaan Juri:** Metode pengujian responsif? Diaudit otomatis lewat peramban pada beragam resolusi layar.

---

### Kelompok 10: Kualitas Teknis dan Keandalan Rekayasa

#### Rangkaian Pengujian Otomatis Menyeluruh (Regression Test Suite)
- **Masalah:** Penambahan fitur baru rawan menimbulkan kerusakan fitur lama tak terduga.
- **Solusi:** Rangkaian 389 pengujian regresi otomatis unit dan integrasi menyeluruh.
- **Cara Kerja:**
  1. Menguji model, form, view, buku besar, dan pipeline kecerdasan buatan.
  2. Dijalankan serentak lewat perintah `python manage.py test`.
  3. Eksekusi berjalan pada database isolasi tanpa mencemari data asli.
- **Aturan Penting:** Kelulusan mutlak seratus persen (389 dari 389 pengujian wajib lulus).
- **Bukti:** 389 tes lulus dalam ~48 detik di seluruh berkas pengujian lokal.
- **Tampilan:** Konsol terminal eksekusi pengujian.
- **Poin Bicara:** Stabilitas perangkat lunak dijamin secara presisi melalui verifikasi otomatis berulang.
- **Pertanyaan Juri:** Berapa lama durasi tes? Seluruh 389 pengujian tuntas dalam sekitar 48 detik.

#### Audit Kelas Utilitas Tailwind CSS Otomatis
- **Masalah:** Kelas CSS di template yang tidak terkompilasi merusak tampilan antarmuka produksi.
- **Solusi:** Pemindai statis `check_tailwind_classes.py` pemverifikasi integritas kelas gaya antarmuka.
- **Cara Kerja:**
  1. Memindai atribut `class` pada 79 berkas template HTML.
  2. Mengekstraksi 688 kelas unik dan mencocokkan ke `static/css/styles.css`.
  3. Memastikan tidak ada kelas template yang luput dari bundel kompilasi.
- **Aturan Penting:** Toleransi kelas hilang adalah nol (0 missing classes).
- **Bukti:** `scripts/check_tailwind_classes.py`, terverifikasi pada rilis proyek.
- **Tampilan:** Konsol terminal eksekusi skrip audit CSS.
- **Poin Bicara:** Integritas desain konsisten tanpa cacat rendering di seluruh browser.
- **Pertanyaan Juri:** Kapan diaudit? Dijalankan pada setiap pemeriksaan pra-rilis produksi.

#### Dokumentasi Keputusan Arsitektur Perangkat Lunak (ADR)
- **Masalah:** Pengembang kehilangan jejak rasional di balik keputusan teknis masa lampau.
- **Solusi:** Pencatatan Keputusan Arsitektur Perangkat Lunak (*Architecture Decision Records*) di `docs/DECISIONS.md`.
- **Cara Kerja:**
  1. Setiap keputusan arsitektur utama dirumuskan ke dalam dokumen standar.
  2. Memuat status, latar belakang masalah, keputusan, dan konsekuensinya.
- **Aturan Penting:** Memuat 15 catatan keputusan historis terstruktur.
- **Bukti:** `docs/DECISIONS.md`.
- **Tampilan:** `docs/DECISIONS.md`.
- **Poin Bicara:** Bukti kedewasaan proses rekayasa sistem yang terdokumentasi rapi.
- **Pertanyaan Juri:** Mengapa monolitik Django dipilih? Menjamin transaksi ACID buku besar terpusat dan efisiensi pemeliharaan kampus.

---

## 3. Alur Demo yang Disarankan (Tujuh Menit)

Alur demonstrasi langsung tanpa menampilkan kredensial rahasia di layar proyektor:

1. **Menit 0.00 – 1.00: Beranda dan Filosofi Produk (`/`)**
   - Buka halaman beranda desktop. Tunjukkan identitas visual kertas dan tinta, ketiadaan gradien, dan motif Tapis geometris yang terukur di seksi Bukti dan footer.
   - Sorot kolom pencarian pil, chip kategori, dan kartu barang sewa berfoto nyata dengan format rupiah bertitik ribuan.
2. **Menit 1.00 – 2.00: Katalog Sewa dan Booking Transparan (`/barang/` dan detail barang)**
   - Buka salah satu barang (misal Kamera DSLR atau Jas Wisuda).
   - Perlihatkan kalender ketersediaan, estimasi rincian biaya sewa bergaya perforasi kuitansi, dan segel verifikasi identitas pemilik.
   - Sorot cincin skor kepercayaan pemilik beserta 3 faktor penjelas transparan.
3. **Menit 2.00 – 3.30: Alur Transaksi Sewa Aman (`/sewa/<kode>/`)**
   - Tunjukkan perjanjian sewa digital yang ditandatangani dengan pencatatan stempel waktu dan hash naskah.
   - Perlihatkan antarmuka pembayaran Midtrans Snap sandbox.
   - Tunjukkan pemilihan titik temu aman di area kampus dan form pengunggahan foto kondisi fisik barang sebelum dipakai.
4. **Menit 3.30 – 4.30: Modul Jual Beli Mahasiswa (`/jual-beli/` dan detail barang)**
   - Buka katalog jual beli perlengkapan kuliah. Tunjukkan lencana kondisi fisik (baru, seperti baru, ada cacat) dan persentase hemat dibanding harga beli baru.
   - Tunjukkan lencana reputasi penjual (Penjual Tepercaya) dan plafon harga maksimal.
   - Sorot pembekuan snapshot spesifikasi dan masa pemeriksaan 48 jam yang melindungi pembeli dari barang rusak.
5. **Menit 4.30 – 5.30: Dompet Internal dan Pembukuan Berimbang (`/dompet/`)**
   - Masuk ke dasbor dompet pengguna. Perlihatkan saldo tersedia dan tabel riwayat mutasi dana.
   - Buka form penarikan dana ke rekening bank, jelaskan bahwa nomor rekening dienkripsi menggunakan AES di database.
6. **Menit 5.30 – 6.30: Portal Staf dan Pemantauan Machine Learning (`/admin/` dan `/admin/model-skor/`)**
   - Buka dasbor operasional admin: tunjukkan widget antrean verifikasi identitas mahasiswa, sengketa, dan permohonan penarikan dana.
   - Buka menu pemantauan model Machine Learning: perlihatkan kurva kalibrasi probabilitas Brier Score, ROC-AUC, dan simulator pengujian skor risiko mahasiswa secara langsung.
7. **Menit 6.30 – 7.00: Penutup dan Kualitas Rekayasa**
   - Tunjukkan statistik 389 tes otomatis lulus seratus persen dan kepatuhan privasi pembersihan berkas otomatis sesuai regulasi perlindungan data.

---

## 4. Batasan yang Jujur

Sebagai wujud kejujuran ilmiah dan integritas teknis, berikut batasan platform saat ini:
1. **Data Latih Awal Berbasis Sintetis Terarah:** Sebelum model Machine Learning menerima ratusan transaksi nyata di lapangan, data latih awal dibangun menggunakan generator data sintetis berbasis aturan statistik kampus yang realistis.
2. **OCR Membaca Teks, Bukan Membuktikan Keaslian Fisik Kartu:** Tesseract OCR hanya mengekstrak teks dari gambar kartu mahasiswa; verifikasi keaslian fisik hologram atau material kartu tetap membutuhkan tinjauan visual staf kampus.
3. **Pencairan Dana Dilakukan Secara Terverifikasi Manual oleh Admin:** Penarikan saldo dompet ke rekening bank saat ini belum terhubung ke API disbursement otomatis (seperti Iris Midtrans), melainkan ditinjau dan ditransfer manual oleh staf bendahara kampus demi pencegahan pencucian uang.
4. **Koneksi Pembayaran Berada di Lingkungan Sandbox:** Seluruh transaksi perbankan dan QRIS saat ini terhubung ke lingkungan pengujian Midtrans Sandbox, siap dialihkan ke kunci produksi saat izin operasional kampus terbit.
5. **Naskah Perjanjian Membutuhkan Telaah Lanjutan Pakar Hukum:** Draf syarat dan ketentuan sewa serta jual beli dirancang berdasarkan norma umum perdata dan UU ITE, namun tetap disarankan mendapat tinjauan formal dari biro hukum universitas sebelum penerapan skala luas.
6. **Penyimpanan Foto Masih di Disk Lokal Server:** Penyimpanan foto saat ini memanfaatkan sistem berkas lokal terlindungi; untuk skala jutaan pengguna, arsitektur perlu ditingkatkan ke penyimpanan objek terisolasi (*private object storage* S3).

---

## 5. Roadmap Pengembangan Masa Depan

Daftar fitur inovatif berstatus `[Rencana]` yang dipersiapkan untuk fase pengembangan berikutnya:
1. **Sewa Dulu Beli Kemudian (Rent-to-Own):** Fitur yang memungkinkan penyewa membeli barang yang sedang disewanya secara permanen jika merasa cocok, dengan biaya sewa yang telah dibayar diperhitungkan sebagai pengurang harga beli.
2. **Skor Reputasi Penjual Berbasis Algoritma Dinamis:** Pengembangan model Machine Learning kedua khusus untuk menilai keandalan penjual barang bekas berdasarkan kecepatan membalas chat dan akurasi deskripsi minus barang.
3. **Saran Harga Wajar Otomatis (Price Recommendation Engine):** Algoritma estimasi harga jual wajar untuk buku teks dan elektronik bekas berdasarkan merk, tahun rilis, dan tingkat depresiasi fisik barang.
4. **Pencairan Saldo Otomatis (Automated Payout API):** Integrasi langsung ke layanan pencairan dana otomatis perbankan setelah permohonan penarikan disetujui staf bendahara.
5. **Perpanjangan Masa Sewa Fleksibel (Rental Extension):** Fitur perpanjangan masa sewa langsung dari dasbor aktif tanpa harus membuat permohonan baru dari awal, selama jadwal tanggal berikutnya belum dibooking pengguna lain.
6. **Daftar Barang Favorit dan Peringatan Ketersediaan (Wishlist and Stock Alert):** Fitur penyimpanan barang idaman dan pengiriman notifikasi otomatis saat barang incaran yang sedang disewa orang lain telah kembali tersedia.

---

## 6. Dua Puluh Pertanyaan Juri dan Jawaban Berbasis Fakta

### 1. Bagaimana Anda menjamin orang luar kampus tidak bisa bertransaksi di sini?
Pendaftaran diisolasi menggunakan validasi domain email universitas resmi `.ac.id` pada form registrasi (`apps/accounts/forms.py:clean_email`), serta kewajiban verifikasi fisik Kartu Tanda Mahasiswa yang ditinjau manual staf kampus sebelum hak transaksi dibuka (`apps/verification/views.py`).

### 2. Mengapa tidak menggunakan marketplace besar yang sudah ada saja?
Marketplace besar tidak memfasilitasi transaksi sewa jangka pendek antarmahasiswa, tidak menyediakan titik temu fisik aman di dalam kampus, serta mengenakan biaya potongan dan ongkos kirim ekspedisi yang memberatkan mahasiswa untuk transaksi berjarak dekat.

### 3. Apa yang terjadi jika penyewa merusak barang dan menolak membayar ganti rugi?
Platform menahan uang deposit sewa di rekening bersama, mewajibkan foto kondisi sebelum dan sesudah pakai sebagai bukti sah, serta memiliki fitur penagihan resmi `ExtraCharge` yang akan membekukan akun mahasiswa dari seluruh aktivitas kampus jika menolak membayar ganti rugi.

### 4. Bagaimana platform menangani risiko pembeli barang bekas tertipu barang rusak?
Tersedia hak masa pemeriksaan selama 48 jam sejak barang diserahterimakan. Selama 48 jam tersebut, uang pembayaran ditahan penuh di rekening bersama dan pembeli berhak mengajukan sengketa pengembalian dana penuh jika kondisi barang tidak sesuai snapshot awal.

### 5. Apa fungsi pembekuan snapshot saat pemesanan barang jual beli?
Model `SaleOrder` menyalin seluruh teks deskripsi, harga, minus, dan nilai hash SHA-256 seluruh foto iklan saat tombol beli ditekan. Penjual tidak dapat lagi mengedit iklan untuk menghilangkan catatan cacat barang demi mengelabui komplain pembeli.

### 6. Bagaimana Anda mencegah akun baru menjual barang curian bernilai puluhan juta?
Sistem menerapkan batasan harga bertingkat (`TIER_PRICE_LIMITS`): Penjual Baru hanya boleh memasang harga maksimal Rp1.000.000. Batas harga hanya naik menjadi Rp3.000.000 dan Rp8.000.000 setelah penjual berhasil menyelesaikan transaksi nyata dengan ulasan bintang tinggi.

### 7. Mengapa model Machine Learning Anda tidak menggunakan data jurusan atau jenis kelamin?
Sesuai prinsip kecerdasan buatan etis dan regulasi pencegahan diskriminasi, model murni dilatih menggunakan fitur perilaku transaksi (keterlambatan, sengketa, kelengkapan data). Menggunakan gender atau jurusan akan melahirkan bias diskriminatif yang tidak adil bagi mahasiswa.

### 8. Apa yang dimaksud dengan kalibrasi probabilitas Platt Scaling pada model skor Anda?
Regresi logistik standar sering kali terlalu percaya diri pada nilai ekstrem. Kalibrasi Platt Scaling menyelaraskan nilai prediksi probabilitas keluaran model agar tepat mencerminkan tingkat risiko nyata empiris (diukur lewat nilai Brier Score di `ml/train_trust_model.py`).

### 9. Bagaimana platform melindungi privasi foto kartu mahasiswa yang tersimpan di server?
Seluruh berkas identitas disimpan pada direktori `private_media/` yang diisolasi ketat dari web server publik. Selain itu, perintah berkala `purge_handover_photos` menghapus berkas foto fisik secara permanen dari penyimpanan server setelah proses peninjauan selesai demi kepatuhan UU PDP.

### 10. Mengapa sistem dompet Anda menggunakan pembukuan buku besar berpasangan?
Pencatatan saldo satu kolom rawan manipulasi atau selisih tak terlacak. Sistem buku besar berpasangan (`LedgerEntry`) mencatat debit dan kredit berimbang pada setiap pergerakan rupiah, menjamin audit saldo dompet selalu bernilai nol selisih terhadap arus kas riil.

### 11. Bagaimana jika terjadi jadwal sewa yang bentrok saat dua mahasiswa mengajukan di saat yang sama?
Layanan pemesanan `apps/rentals/services.py` membungkus transaksi dengan fungsi atomik database `select_for_update()`, mengunci baris data barang sehingga pengajuan kedua otomatis tertolak jika rentang tanggal telah terisi.

### 12. Mengapa tidak ada pembayaran tunai langsung saat serah terima barang?
Pembayaran tunai menghilangkan kemampuan platform untuk melindungi dana mahasiswa, memfasilitasi sengketa, memotong komisi gotong royong, maupun mengembalikan deposit secara adil jika terjadi wanprestasi.

### 13. Bagaimana sistem mencegah pengguna bertransaksi di luar aplikasi melalui ruang pesan?
Layanan percakapan `apps/chat/services.py:mask_contact_info` secara otomatis mendeteksi dan menyamarkan nomor telepon, alamat email, dan tautan luar sebelum jadwal pertemuan resmi disetujui kedua belah pihak di platform.

### 14. Apa dasar penentuan komisi platform sebesar lima persen?
Komisi lima persen (dengan batas minimal Rp2.000) adalah angka wajar yang jauh lebih rendah daripada potongan lokapasar komersial (yang mencapai 8 hingga 15 persen), di mana separuh komisi dialokasikan langsung untuk memupuk kas Dana Gotong Royong penanggung risiko mahasiswa.

### 15. Bagaimana jika penjual membatalkan janji temu secara mendadak?
Pembeli dapat membatalkan pesanan sebelum serah terima dilakukan, dan sistem secara otomatis mengembalikan 100 persen saldo pembayaran ke dompet internal pembeli detik itu juga tanpa potongan apa pun (`apps/sales/services.py:cancel_sale_order`).

### 16. Apa bukti bahwa antarmuka sistem ramah pengguna dan tidak merusak tampilan di ponsel?
Sistem telah diaudit secara otomatis menggunakan mesin peramban Playwright pada layar 320 piksel, 375 piksel (iPhone SE), 393 piksel (Pixel 5), hingga 1280 piksel (desktop), dengan hasil seluruh komponen lulus uji jarak dan tidak ada teks tumpang tindih.

### 17. Mengapa desain antarmuka Collective Campus melarang gradien dan bayangan warna-warni?
Berdasarkan panduan desain `docs/references/AGENT.md`, gradien dan efek blur adalah ciri khas template kecerdasan buatan generik yang menurunkan citra keseriusan produk. Konsep kertas dan tinta dengan kontras tinggi menjamin keterbacaan prima dan kesan produk institusional terpercaya.

### 18. Bagaimana kesiapan kode Anda terhadap risiko keamanan siber umum?
Pengujian `check --deploy` memverifikasi proteksi CSRF di seluruh form, proteksi clickjacking X-Frame-Options, pembatasan session cookie HTTP-only, pencegahan SQL Injection lewat Django ORM parameterized queries, serta enkripsi AES untuk data perbankan sensitif.

### 19. Bagaimana bila staf kampus keliru menyetujui pengembalian barang yang rusak?
Seluruh aksi staf tercatat dalam log audit administratif. Kesalahan penanganan dapat dianulir melalui penerbitan tiket sengketa susulan dan pembiayaan ganti rugi dialihkan ke kas Dana Gotong Royong platform.

### 20. Seberapa siap platform ini untuk diluncurkan ke lingkungan produksi kampus?
Sangat siap. Seluruh 389 pengujian unit dan integrasi lulus seratus persen, skrip migrasi database bersih tanpa konflik, kelas utilitas CSS terverifikasi lengkap, dan arsitektur telah terbukti aman pada pengujian smoke test 15 rute utama mandiri.

---

## 7. Lampiran Teknis

### Perintah Pengulangan Hitungan Metrik
Seluruh angka metrik pada dokumen ini dihitung langsung dari basis kode aktif menggunakan perintah Python berikut di terminal root:

```bash
# Perintah kalkulasi metrik lengkap (Aplikasi, Model, Rute, Migrasi, Command, Template, LOC, Dokumen):
python -c "
import os, sys, django
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.apps import apps
from django.urls import get_resolver

local_apps = [a.name for a in apps.get_app_configs() if a.name.startswith('apps.') or a.name == 'dev_tools']
local_models = [m for m in apps.get_models() if m._meta.app_label in [a.split('.')[-1] for a in local_apps]]

def list_urls(lis, acc=''):
    r = []
    for e in lis:
        if hasattr(e, 'url_patterns'): r.extend(list_urls(e.url_patterns, acc + str(e.pattern)))
        else: r.append(acc + str(e.pattern))
    return r

routes = list_urls(get_resolver().url_patterns)
migrations = [f for r, d, fs in os.walk('apps') if os.path.basename(r) == 'migrations' for f in fs if f.endswith('.py') and f != '__init__.py']
commands = [f for r, d, fs in os.walk('.') if 'management' in r and 'commands' in r for f in fs if f.endswith('.py') and f != '__init__.py']
templates = [f for r, d, fs in os.walk('templates') for f in fs if f.endswith(('.html', '.txt'))]

loc = {'Python': 0, 'HTML': 0, 'JS': 0}
for r, d, fs in os.walk('.'):
    d[:] = [x for x in d if x not in {'.venv', 'node_modules', '.git', 'staticfiles', 'scratch'}]
    for f in fs:
        ext = os.path.splitext(f)[1].lower()
        lang = 'Python' if ext == '.py' else ('HTML' if ext in ['.html', '.htm'] else ('JS' if ext == '.js' else None))
        if lang:
            with open(os.path.join(r, f), 'r', encoding='utf-8', errors='ignore') as fp:
                loc[lang] += sum(1 for _ in fp)

docs = ['README.md'] + [os.path.join(r, f) for r, d, fs in os.walk('docs') for f in fs if f.endswith('.md')]

print(f'Apps: {len(local_apps)} | Models: {len(local_models)} | Routes: {len(routes)} | Migrations: {len(migrations)} | Commands: {len(commands)} | Templates: {len(templates)} | LOC: {loc} | Docs: {len(docs)}')
"
```

### Daftar Lima Belas Rute Utama Platform
1. `GET /`: Beranda publik sewa perlengkapan mahasiswa.
2. `GET /jual-beli/`: Katalog utama bursa barang perlengkapan bekas (thrift).
3. `GET /barang/`: Katalog lengkap pencarian dan filter barang sewa.
4. `GET /barang/<slug>/`: Detail spesifikasi barang sewa, kalender, kuitansi estimasi, dan ulasan.
5. `GET /jual-beli/<slug>/`: Detail spesifikasi barang jualan, foto kondisi minus, dan batas harga.
6. `GET /tentang/`: Profil visi misi, prinsip kertas-tinta, dan identitas budaya platform.
7. `GET /bantuan/`: Pusat bantuan interaktif dan daftar pertanyaan umum mahasiswa.
8. `GET /syarat-ketentuan/`: Naskah resmi syarat dan ketentuan hukum transaksi platform.
9. `GET /kebijakan-privasi/`: Pernyataan resmi kepatuhan perlindungan data pribadi mahasiswa.
10. `GET /panduan-komunitas/`: Norma dan aturan kesopanan transaksi lingkungan kampus.
11. `GET /kontak/`: Saluran komunikasi resmi pengelola bantuan platform kampus.
12. `GET /kalkulator-sewa/`: Simulasi estimasi biaya sewa, deposit, dan komisi platform.
13. `GET /masuk/`: Gerbang masuk autentikasi mahasiswa terdaftar.
14. `GET /daftar/`: Formulir registrasi akun mahasiswa baru.
15. `GET /dashboard/`: Dasbor pengguna ringkasan transaksi sewa, jualan, dan status verifikasi.

### Daftar Variabel Lingkungan Penting (.env)
Daftar variabel konfigurasi operasional (tanpa memuat nilai rahasia produksi):
- `DEBUG`: Status mode pengembangan sistem (diwajibkan `False` pada server produksi publik).
- `SECRET_KEY`: Kunci kriptografi utama enkripsi sesi dan token Django.
- `DATABASE_URL`: URI koneksi database PostgreSQL produksi (`postgresql://user:pass@host:port/dbname`).
- `MIDTRANS_SERVER_KEY`: Kunci autentikasi server gateway pembayaran Midtrans.
- `MIDTRANS_CLIENT_KEY`: Kunci otentikasi antarmuka web Snap popup Midtrans.
- `MIDTRANS_IS_PRODUCTION`: Saklar lingkungan gateway pembayaran (`False` untuk Sandbox, `True` untuk Produksi).
- `FIELD_ENCRYPTION_KEY`: Kunci simetris AES/Fernet untuk enkripsi nomor rekening bank mahasiswa.
- `ALLOWED_HOSTS`: Daftar nama domain resmi yang diizinkan melayani lalu lintas web server.
- `DEFAULT_FROM_EMAIL`: Alamat email resmi pengirim notifikasi dan token akun kampus.
- `SALE_OFFERS_ENABLED`: Saklar fitur penawaran harga jual beli terstruktur (`True` atau `False`).
