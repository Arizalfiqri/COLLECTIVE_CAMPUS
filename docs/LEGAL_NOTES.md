# Catatan Hukum dan Kepatuhan Digital Collective Campus

> **Perhatian & Penafian Hukum (Legal Disclaimer):**
> Dokumen dan klausul Syarat & Ketentuan (S&K) digital yang tersedia pada platform ini disusun sebagai kerangka operasional komunitas mahasiswa untuk memfasilitasi transaksi yang tertib, transparan, dan berkeadilan. Teks ini **wajib ditinjau oleh konsultan atau praktisi hukum independen** sebelum dipergunakan sebagai dasar pembuktian litigasi formal di peradilan. Platform **tidak pernah memberikan klaim kepastian penuntutan pidana maupun perdata** di muka pengadilan tanpa pembuktian materiil yang sah menurut hukum acara yang berlaku di Republik Indonesia.

---

## 1. Status Perjanjian Digital Sewa dan Jual Beli

- **Persetujuan Eksplisit Terverifikasi:** Setiap transaksi sewa (`RentalAgreement`) dan pesanan jual beli (`SaleAgreement`) mewajibkan persetujuan eksplisit pengguna sebelum transaksi diproses.
- **Integritas Bukti Digital:** Sistem mencatat:
  1. Nomor versi resmi S&K yang berlaku saat transaksi disepakati (`terms_version`);
  2. Nilai *hash kriptografis* SHA-256 dari teks klausul yang disetujui (`terms_hash`);
  3. Snapshot beku rincian transaksi (`listing_snapshot` / `text_snapshot`);
  4. Stempel waktu transaksi berakurasi tinggi (`agreed_at`);
  5. Jejak jaringan (*IP address* dan string *user-agent* peramban).
- **Asas Subjek Hukum:** Identitas para pihak (nama lengkap, Nomor Induk Mahasiswa/NIM, dan institusi kampus) dicatat pada bukti perjanjian guna memenuhi syarat sahnya perjanjian perdata sesuai Pasal 1320 Kitab Undang-Undang Hukum Perdata (KUHPerdata).

---

## 2. Batasan Tanggung Jawab Platform (Penyelenggara Sistem Elektronik)

- **Kedudukan Hukum:** Collective Campus bertindak murni sebagai Penyelenggara Sistem Elektronik (PSE) / platform perantara yang memfasilitasi interaksi antarmahasiswa terverifikasi.
- **Ketiadaan Kepemilikan Fisik:** Platform tidak memiliki, menyimpan, menguasai, maupun menggaransi kondisi fisik barang yang disewakan atau dijual secara langsung oleh pengguna.
- **Kondisi Barang "Apa Adanya" (*As-Is*):** Barang yang ditransaksikan pada Modul Jual Beli (Thrift) merupakan barang bekas pemakaian mahasiswa dan dialihkan dalam kondisi apa adanya (*as-is*) sesuai deskripsi, kelengkapan, minus, dan foto yang dilampirkan penjual saat listing dibuat.

---

## 3. Perlindungan Data Pribadi (Kepatuhan UU No. 27 Tahun 2022 PDP)

- **Dasar Pemrosesan Data Pribadi:** Data berupa nama lengkap, NIM, universitas, foto fisik serah terima, alamat IP, dan user-agent diproses atas dasar persetujuan eksplisit pemilik data dan kebutuhan pelaksanaan kontrak (*performance of a contract*).
- **Prinsip Minimisasi Data & Retensi Berkas:**
  - Foto fisik identitas KTM disimpan secara terenkripsi/terisolasi di direktori privat (`private_media/`) dan dibersihkan dari server segera setelah peninjauan status mahasiswa selesai.
  - Foto dokumentasi kondisi barang serah terima awal dan pengembalian dihapus otomatis oleh task pembersihan berkala (`purge_handover_photos`) setelah masa sengketa berakhir.
- **Hak Subjek Data:** Pengguna berhak memperbarui biodata profil dan mengajukan permohonan penutupan akun secara mandiri.

---

## 4. Ketentuan Jual Beli Barang Bekas (Thrift) & Hak Inspeksi 48 Jam

- **Batas Waktu Pembayaran:** Pesanan jual beli yang terbentuk memiliki batas waktu pembayaran maksimal 6 jam melalui saluran pembayaran resmi platform (escrow Midtrans). Jika batas waktu terlampaui, reservasi barang dibatalkan otomatis dan barang kembali berstatus aktif.
- **Kewajiban Titik Temu di Kampus:** Penjual dan pembeli wajib melakukan serah terima barang secara fisik di lingkungan kampus terbuka atau area publik yang ramai dalam batas waktu 7 hari demi keselamatan para pihak.
- **Dokumentasi Foto Serah Terima:** Penjual dan pembeli wajib mengambil foto fisik barang saat serah terima tatap muka sebagai bukti objektif perpindahan penguasaan barang.
- **Hak Inspeksi 48 Jam Pembeli:**
  - Dana pembayaran ditahan di rekening escrow platform selama 48 jam sejak waktu serah terima fisik dicatat sistem.
  - Dalam kurun waktu 48 jam, pembeli berhak memeriksa fungsi dan fisik barang.
  - Pembeli dapat menekan tombol "Konfirmasi terima" untuk langsung melepaskan dana ke penjual, atau sistem akan melepaskan dana secara otomatis setelah 48 jam apabila tidak ada sanggahan atau sengketa yang diajukan.

---

## 5. Kebijakan Barang Terlarang & Tindakan Penurunan (*Takedown*)

- **Daftar Barang Terlarang Kampus:** Dilarang keras memperjualbelikan maupun menyewakan:
  1. Obat-obatan terlarang, narkotika, psikotropika, dan obat keras resep dokter;
  2. Minuman beralkohol (miras);
  3. Rokok, cerutu, tembakau, vape / rokok elektrik, dan cairan nikotin (liquid);
  4. Senjata tajam, senjata api, replika airsoft gun, dan bahan kimia berbahaya / bahan peledak;
  5. Satwa atau hewan peliharaan apa pun;
  6. Makanan olahan basah atau makanan yang mudah basi;
  7. Barang palsu, bajakan, tiruan (KW), atau barang hasil tindak kejahatan/curian;
  8. Akun digital, akun game, lisensi perangkat lunak bajakan, atau jasa joki akademik.
- **Hak Penurunan (*Takedown*):** Platform berhak secara sepihak menurunkan listing barang yang dilaporkan melanggar atau terdeteksi mengandung kata kunci terlarang, serta berhak membekukan akun mahasiswa yang bersangkutan.

---

## 6. Prosedur Penyelesaian Sengketa & Musyawarah Kampus

- **Prioritas Mediasi Internal:** Setiap perselisihan antarpengguna mengenai kondisi barang, keterlambatan pengembalian, atau ketidaksesuaian deskripsi diselesaikan terlebih dahulu melalui mekanisme sengketa internal platform (`SaleDispute` / `RentalDispute`) yang dimediasi oleh tim moderator kampus.
- **Alat Bukti Peninjauan:** Moderator memeriksa snapshot listing beku, rekaman foto serah terima, foto sengketa, dan transkrip obrolan (*chat transcript*) untuk memutuskan pelepasan dana, pengembalian dana, atau pembagian ganti rugi secara proporsional.
- **Putusan Administratif:** Keputusan moderator bersifat administratif internal platform terkait pencairan atau pemulangan dana pada sistem escrow. Hal ini tidak menghapuskan iktikad baik para pihak untuk bermusyawarah secara kekeluargaan di lingkungan kampus.
