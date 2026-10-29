# Model Card: TrustScore (Skor Kepercayaan Collective Campus)

Dokumen ini mendokumentasikan model machine learning penilaian risiko transaksi dan skor kepercayaan (TrustScore) pada platform Collective Campus sesuai standar pelaporan ilmiah dan etika kecerdasan buatan.

---

## 1. Ringkasan Model (Model Details)

- **Pengembang:** Tim Pengembang Collective Campus (Technopreneurship Mahasiswa)
- **Versi Model:** `v1.0-logreg-calibrated`
- **Tanggal Pelatihan:** 15 Oktober 2026
- **Tipe Model:** Pipeline `StandardScaler` + `LogisticRegression(class_weight='balanced')` yang dikalibrasi menggunakan `CalibratedClassifierCV(method='sigmoid', cv=5)` (Platt Scaling).
- **Lisensi:** MIT / Proyek Akademik
- **Artefak:** `ml/artifacts/trust_model.joblib`, `ml/artifacts/metrics.json`
- **Visualisasi Evaluasi:** `static/ml/*.png`

---

## 2. Tujuan Penggunaan (Intended Use)

- **Tujuan Utama:** Memperkirakan probabilitas risiko ($p \in [0, 1]$) bahwa seorang mahasiswa akan mengalami kendala pada sewa berikutnya (keterlambatan pengembalian $> 1$ hari, pemotongan deposit akibat kerusakan fisik barang, atau pembukaan sengketa).
- **Konversi Skor:** Probabilitas risiko dikonversikan menjadi skor kepercayaan 0–100 yang mudah dipahami:
  $$\text{Skor Kepercayaan} = \text{round}((1 - p) \times 100)$$
- **Aplikasi Bisnis:**
  - Penentuan tingkat penyewa (Tangga Kepercayaan SPEC v2 A.1):
    - *Penyewa Baru* ($< 3$ sewa selesai): Limit nilai barang Rp750.000, deposit 15%.
    - *Penyewa Tepercaya* (3–5 sewa selesai tanpa sengketa & skor $\ge 60$): Limit nilai barang Rp1.500.000, deposit 10%.
    - *Penyewa Sangat Tepercaya* ($\ge 6$ sewa selesai tanpa sengketa & skor $\ge 75$): Limit nilai barang Rp3.000.000, deposit 10%.
  - Transparansi bagi pemilik barang sebelum menyetujui permintaan sewa.
- **Batasan Penggunaan:**
  - Model **TIDAK DIGUNAKAN** untuk pengguna baru dengan riwayat sewa $< 3$ transaksi (ditangani aturan bisnis cold-start).
  - Model **TIDAK DIGUNAKAN** untuk menentukan kelayakan verifikasi identitas mahasiswa.

---

## 3. Data Pelatihan & Pembangkitan Sintetis (Training Data)

### 3.1 Mengapa Menggunakan Data Sintetis?
Sebagai platform yang baru dikembangkan, belum terdapat riwayat transaksi nyata berskala ribuan dalam database. Melaporkan metrik tinggi pada data riil yang belum ada adalah bentuk ketidakjujuran ilmiah. Oleh karena itu, data dibangkitkan secara sintetis dengan pendekatan statistik yang ketat dan dinyatakan terbuka.

### 3.2 Metodologi Pembangkitan (`ml/generate_synthetic_data.py`)
- **Ukuran Sampel:** 4.000 baris.
- **Seed / Reproduksibilitas:** `random_state = 42`.
- **SHA-256 Checksum:** `6c071490ca381cfc9413b6a7971e7ed61e9c300ebb6fb3f93affdbe9fc535e5d`.
- **Variabel Laten Keandalan ($z$):**
  Setiap baris dibangkitkan dari variabel laten keandalan psikologis pengguna $z \sim \mathcal{N}(0, 1)$. Nilai $z$ tinggi merepresentasikan pengguna yang cermat, tepat waktu, dan komunikatif.
- **Korelasi Antarfitur:**
  Fitur riwayat (rasio tepat waktu, rata-rata rating, frekuensi sengketa) dibangkitkan terkondisi pada $z$ melalui distribusi Beta, Poisson, dan Gamma.
- **Pencegahan Target Leakage:**
  Semua fitur murni merepresentasikan metrik agregat riwayat sebelum transaksi yang dilabeli.
- **Tumpang Tindih Kelas (Bayes Error Realistis):**
  Label target dibangkitkan dari kombinasi linear logistik laten ditambah derau logistik terkalibrasi ($\text{scale}=0.75$). Kelas positif tidak terpisah secara sempurna (overlap realistis, Bayes error $\approx 10\%$).
- **Prevalensi Risiko:** 616 positif dari 4.000 baris (15.40%).

---

## 4. Fitur Model (Features)

### 4.1 Fitur yang Digunakan (8 Fitur Riwayat Perilaku)
1. `jumlah_sewa_selesai`: Total transaksi sewa selesai berhasil (integer $\ge 3$).
2. `jumlah_sebagai_pemilik`: Total transaksi barang milik pengguna yang sukses disewakan (integer $\ge 0$).
3. `rasio_tepat_waktu`: Rasio pengembalian tanpa denda telat sebagai penyewa (float $[0.0, 1.0]$).
4. `rata_rata_rating_diterima`: Rata-rata bintang ulasan dari pihak lain (float $[1.0, 5.0]$).
5. `jumlah_sengketa`: Total perselisihan klaim kerusakan/hilang yang pernah dialami (integer $\ge 0$).
6. `rasio_sengketa`: Proporsi sengketa terhadap total transaksi (float $[0.0, 1.0]$).
7. `rasio_pembatalan`: Proporsi pembatalan sepihak setelah disetujui (float $[0.0, 1.0]$).
8. `umur_akun_hari`: Jumlah hari sejak akun terdaftar (integer $\ge 1$).

### 4.2 Fitur yang Sengaja Dihapus & Dilarang
- **`status_ktm` (Dihapus):** Fitur ini hampir konstan (seluruh penyewa aktif wajib berstatus terverifikasi KTM), sehingga bernilai informasi mendekati nol (zero variance) dan dihapus untuk efisiensi komputasi.
- **Jenis Kelamin / Gender (Dilarang):** Perlindungan dari diskriminasi gender.
- **Nama Kampus / Universitas (Dilarang):** Mencegah bias keistimewaan reputasi universitas besar.
- **Program Studi / Jurusan (Dilarang):** Menghindari bias persepsi jurusan eksak vs sosial.
- **Asal Daerah / Geografi (Dilarang):** Kepatuhan asas pelindungan hak kewilayahan.
- **Agama / Etnis / Suku (Dilarang):** Kepatuhan mutlak UU PDP No. 27 Tahun 2022.

---

## 5. Metrik Evaluasi & Perbandingan Model (Performance)

Evaluasi dilakukan pada *test set* independen berukuran 800 sampel (20% stratified holdout):

| Model | ROC-AUC | PR-AUC | Presisi | Recall | F1-Score | Brier Score | Catatan |
|---|---|---|---|---|---|---|---|
| **Dummy (kelas mayoritas)** | 0.5000 | 0.1538 | 0.0000 | 0.0000 | 0.0000 | 0.1301 | Baseline tebakan frekuensi |
| **Baseline Aturan (tepat waktu < 0.70)** | 0.7951 | 0.4197 | 0.2783 | 0.7805 | 0.4103 | 0.1349 | Heuristik aturan tunggal |
| **Regresi Logistik (tanpa kalibrasi, 0.50)** | 0.8293 | 0.5152 | 0.3705 | 0.7561 | 0.4973 | 0.1641 | Probabilitas belum terkalibrasi |
| **Gradient Boosting (ambang 0.50)** | 0.8135 | 0.4494 | 0.5161 | 0.2602 | 0.3459 | 0.1071 | Recall rendah, 'black box' |
| **Regresi Logistik Terkalibrasi (Terpilih, ambang 0.209)** | **0.8292** | **0.5139** | **0.4301** | **0.6504** | **0.5178** | **0.1001** | **Model produksi terbaik** |

### 5.1 Alasan Pemilihan Model
Regresi Logistik dipilih sebagai model utama karena:
1. **Keunggulan Metrik CV:** Pada 5-fold stratified cross-validation data latih, Regresi Logistik memperoleh ROC-AUC 0.8478 dan PR-AUC 0.5107, melampaui Gradient Boosting (ROC-AUC 0.8348 dan PR-AUC 0.4845).
2. **Kebutuhan Interpretabilitas:** Koefisien model linear terstandar dapat langsung ditransformasikan menjadi kalimat penjelasan personal bagi pengguna.

---

## 6. Kalibrasi Probabilitas (Calibration)

Model awal yang dilatih dengan `class_weight='balanced'` menghasilkan probabilitas nominal yang terdistorsi ke atas. Kalibrasi dilakukan menggunakan **Platt Scaling** (`CalibratedClassifierCV(method='sigmoid', cv=5)`).

- **Brier Score Sebelum Kalibrasi:** `0.1641`
- **Brier Score Setelah Kalibrasi:** `0.1001`
- **Penurunan Error Kalibrasi:** **39.0%**
- **Dampak Praktis:** Probabilitas keluaran model benar-benar merefleksikan frekuensi empiris risiko transaksi, sehingga rumus skor $(1 - p) \times 100$ akurat secara kuantitatif.

---

## 7. Pemilihan Ambang Keputusan & Analisis Trade-Off

Ambang keputusan ($T$) dipilih pada data validasi cross-validation dengan kriteria:
> *Memaksimalkan presisi pada kondisi recall kelas berisiko minimal 0.70.*

- **Ambang Terpilih ($T$):** `0.2094`
- **Kinerja Validasi:** Recall = `0.7018`, Presisi = `0.4488`
- **Kinerja Test Set:** Recall = `0.6504`, Presisi = `0.4301`, F1 = `0.5178`

### Analisis Trade-Off Biaya (Error Cost Asymmetry)
Dalam marketplace sewa barang kampus bernilai tinggi (kamera, proyektor, toga seharga ratusan ribu hingga jutaan rupiah):
- **False Negative (FN):** Pengguna berisiko tinggi salah diprediksi aman sehingga menyewa barang bernilai tinggi tanpa deposit memadai, berujung barang hilang atau rusak berat. Biaya: **Sangat Tinggi**.
- **False Positive (FP):** Pengguna aman diprediksi berisiko sehingga diminta deposit standar atau diingatkan untuk berhati-hati. Biaya: **Rendah / Sedang**.
Oleh karena itu, pemilihan ambang 0.209 mengutamakan recall tinggi di atas presisi murni.

---

## 8. Penjelasan Keputusan Model (Explainability)

Setiap prediksi skor disertai oleh **3 faktor penjelas teratas** yang dihitung dari kontribusi fitur terstandar:

$$\text{trust\_impact}_j = - \left( \beta_j \times \frac{x_j - \mu_j}{\sigma_j} \right)$$

Tiga faktor dengan $|\text{trust\_impact}_j|$ terbesar diterjemahkan menjadi kalimat sederhana:
- *"Rasio tepat waktu 96% menaikkan skor"*
- *"Rating diterima 4.8 dari 5 bintang menaikkan skor"*
- *"Pernah memiliki 1 catatan sengketa menurunkan skor"*

---

## 9. Keterbatasan & Rencana Data Nyata

### 9.1 Keterbatasan Model
1. **Domain Gap Data Sintetis:** Belum mencerminkan pola musiman nyata (periode wisuda semester ganjil/genap).
2. **Ketergantungan Cold-Start:** Pengguna baru tetap bergantung pada proteksi batas nilai barang dan deposit awal.

### 9.2 Rencana Transisi Data Nyata (MLOps Roadmap)
1. **Persetujuan Pengguna (Informed Consent):** Mengumpulkan data riwayat transaksi mahasiswa nyata dengan persetujuan sesuai UU PDP.
2. **Retraining Terjadwal:** Model dilatih ulang secara otomatis atau semi-otomatis ketika transaksi selesai baru terkumpul memenuhi ambang guardrail.
3. **Admin Override:** Panel admin menyediakan fitur override skor manual yang disertai catatan audit wajib bila terjadi anomali teknis.

---

## 10. Pembelajaran Model dari Data Nyata (Continuous Learning Architecture - Fase 7C)

Mulai Fase 7C, Collective Campus mengimplementasikan arsitektur *continuous learning* yang memungkinkan model ML berevolusi dari data sintetis awal menuju data transaksi mahasiswa nyata secara terkontrol dan aman.

```
+-----------------------------------------------------------------------------------+
|                            ALUR SIKLUS PEMBELAJARAN DATA NYATA                    |
+-----------------------------------------------------------------------------------+
| 1. Pengajuan Sewa    --> Simpan Snapshot 8 Fitur X & Prediksi Risiko (source='live')|
| 2. Terminal State    --> Pelabelan Idempoten Target y (0: Lancar, 1: Bermasalah)  |
| 3. Guardrail Cek     --> Abort jika n_real < 200 atau n_positives < 20            |
| 4. Time Split 80/20  --> 80% Transaksi Lama (Train), 20% Transaksi Baru (Val)     |
| 5. Latih Kandidat    --> CalibratedClassifierCV(LogisticRegression, sigmoid)      |
| 6. Evaluasi Setara   --> Bandingkan Kandidat vs Aktif pada Set Validasi Identik   |
| 7. Promosi Ketat     --> Promosi HANYA jika delta PR-AUC >= +0.01 & Brier stabil  |
| 8. Versi Artefak     --> Simpan ke ml/artifacts/versions/<version>/ & DB lineage  |
+-----------------------------------------------------------------------------------+
```

### 10.1 Pipeline Pencatatan Data Latih (`TrustTrainingExample`)
1. **Pencatatan Snapshot (`ajukan_sewa`):**
   Saat penyewa mengajukan permohonan sewa, sistem mencatat snapshot 8 fitur objektif (`features`), prediksi risiko awal (`predicted_risk`), versi model aktif, dan `source='live'` dengan `label_problem=None`. Hal ini menjamin fitur mencerminkan kondisi riil pengguna sebelum transaksi terjadi.
2. **Pelabelan Idempoten Terminal State (`label_training_example_for_rental`):**
   Saat transaksi sewa selesai:
   - **Label `1` (Bermasalah):** Terlambat lebih dari 1 hari (`late_days > 1`), ada pemotongan deposit kerusakan fisik (`damage_fee > 0`), terjadi sengketa perselisihan, atau barang tidak dikembalikan.
   - **Label `0` (Lancar):** Transaksi selesai tepat waktu tanpa denda kerusakan atau sengketa.
   - Operasi ini bersifat idempoten: jika fungsi dipanggil ulang atau status sewa diperbarui, label tidak akan berubah ganda atau memicu inkonsistensi data.
3. **Isolasi Data Historis Backfill:**
   Data transaksi sebelum implementasi pipeline diberi label `source='backfill'`. Data backfill ini secara bawaan **dikecualikan** dari set evaluasi utama retraining untuk mencegah bias kebocoran data (*data leakage*) masa lampau.

### 10.2 Guardrail Retraining Ketat (`retrain_trust_model`)
Untuk mencegah *catastrophic forgetting* atau degradasi performa akibat fluktuasi sampel kecil:
- **Ambang Batas Data Minimal:** Retraining otomatis/manual akan **dibatalkan** jika total data nyata berlabel $< 200$ (`TRUST_MIN_REAL_EXAMPLES`) atau jumlah kasus bermasalah $< 20$ (`TRUST_MIN_POSITIVES`).
- **Validasi Berbasis Waktu (Time-Based Split):** Pembagian data dilakukan secara kronologis: 80% data transaksi lebih lampau dialokasikan untuk data latih, dan 20% data transaksi paling baru dialokasikan untuk data validasi. Pembagian acak (*random shuffle*) dilarang keras guna menghindari kebocoran informasi masa depan ke masa lalu.

### 10.3 Aturan Promosi Model Baru
Model kandidat **HANYA** dipromosikan menggantikan model aktif jika memenuhi dua kriteria kuantitatif simultan:
1. **Peningkatan PR-AUC $\ge +0.0100$:** Karena data riwayat sewa memiliki ketidakseimbangan kelas (*imbalanced data*, ~15% positif), PR-AUC (*Precision-Recall Area Under Curve*) dijadikan metrik utama diskriminasi risiko.
2. **Brier Score Tidak Memburuk ($\Delta \le +0.0010$):** Brier score mengukur kualitas kalibrasi probabilitas. Model kandidat dilarang mengorbankan akurasi probabilitas nominal demi kenaikan presisi semu.

Jika kriteria tidak terpenuhi, model kandidat tetap disimpan dalam arsip versi (`is_active=False`) dengan catatan audit kegagalan, dan model aktif lama dipertahankan tanpa interupsi.

### 10.4 Mitigasi Feedback Loop (Trust Ladder Bias) & Safety Valve
- **Risiko Feedback Loop:** Pengguna dengan skor rendah dibatasi menyewa barang berharga tinggi atau diminta deposit lebih besar, sehingga riwayat transaksinya berkurang. Sebaliknya, pengguna dengan skor tinggi terus mendapat peluang transaksi, memperkuat bias model (*rich get richer*).
- **Mitigasi Algoritmik & Operasional:**
  1. *Perjalanan Awal Setara:* Seluruh pengguna baru memulai dari skor dasar 60 dengan deposit standar platform, tanpa diskriminasi awal.
  2. *Asisten Bukan Hakim Mutlak:* Model ML hanya bertindak sebagai indikator pembantu pemilik barang; pemilik barang tetap memiliki diskresi penuh untuk menyetujui penyewa.
  3. *Admin Override (Safety Valve):* Staf admin memiliki hak koreksi skor manual melalui antarmuka admin dengan kewajiban mengisi alasan audit jika terdeteksi kesenjangan algoritma.

### 10.5 Kepatuhan Pelindungan Data Pribadi (UU PDP No. 27/2022)
1. **Fitur Bebas Atribut Pribadi:** Tidak ada data demografis mahasiswa (NIM lengkap, jenis kelamin, agama, asal daerah, program studi, IPK) yang disertakan dalam matriks pelatihan.
2. **Penyimpanan Snapshot Terenkripsi & Terisolasi:** Snapshot fitur hanya berisi metrik perilaku transaksi agregat platform.
3. **Hak Koreksi & Audit:** Seluruh pembaruan model dan tindakan *rollback* dicatat secara permanen di model `TrustModelVersion` dengan pencatatan staf penanggung jawab.

### 10.6 Prosedur Rollback Cepat (`rollback_trust_model`)
Jika pada pemantauan produksi pasca-promosi terdeteksi perilaku anomali (misalnya lonjakan penolakan palsu), staf dapat segera mengembalikan model aktif ke versi stabil sebelumnya:
```bash
python manage.py rollback_trust_model --version=v1.0-logreg-calibrated
```
Perintah ini otomatis memperbarui penanda status versi di database dan membersihkan *cache* memori aplikasi secara *zero-downtime*.

---

## 11. Roadmap Machine Learning untuk Modul Jual Beli (Fase 8 & Masa Depan)

> **Catatan Status Implementasi:**
> Seluruh inisiatif di bawah ini merupakan **rencana pengembangan teknis (roadmap)** untuk fase mendatang. Saat ini, modul jual beli mengandalkan aturan bisnis deterministik (*rule-based*) untuk `get_seller_tier` dan batas plafon harga. Model-model berikut **belum diaktifkan dalam pipeline inferensi produksi saat ini**, dan didokumentasikan di sini untuk transparansi arah riset platform.

### 11.1 Model Penilaian Risiko Penjual (Seller Risk & Scoring Model)
- **Tujuan:** Menghitung skor keandalan penjual barang bekas secara dinamis guna melengkapi Tangga Penjual deterministik.
- **Rencana Fitur:**
  1. Rasio pesanan selesai tanpa sanggahan inspeksi 48 jam;
  2. Rasio sengketa jual beli per total pesanan;
  3. Frekuensi pembatalan sepihak oleh penjual;
  4. Analisis sentimen dari ulasan tekstual pembeli (`SaleReview.comment`);
  5. Kecepatan rata-rata penjual dalam merespons konfirmasi jadwal temu.
- **Arsitektur Kandidat:** Model klasifikasi terkalibrasi (*Gradient Boosting*) dengan output probabilitas sengketa $\hat{p}_{\text{dispute}}$.

### 11.2 Model Estimasi Harga Wajar Barang Bekas (Fair Price Suggestion Model)
- **Tujuan:** Membantu mahasiswa menentukan harga jual yang wajar dan cepat laku, sekaligus mendeteksi anomali harga (harga terlalu tinggi indikasi manipulasi, atau harga terlalu murah indikasi barang curian/palsu).
- **Rencana Fitur:**
  1. Kategori barang dan subkategori;
  2. Kondisi fisik yang dilaporkan (`baru_segel`, `seperti_baru`, `baik`, `cukup`, `ada_cacat`);
  3. Rasio harga jual terhadap harga beli asli (`original_price`);
  4. Deskripsi panjang teks dan kelengkapan aksesoris;
  5. Tren harga riwayat transaksi serupa di kampus setempat.
- **Arsitektur Kandidat:** Model regresi kuantil (*Quantile Regression*) untuk memberikan rentang harga rekomendasi bawah, tengah, dan atas ($P_{25}, P_{50}, P_{75}$).

### 11.3 Model Kelayakan Skema Sewa-Milik (Rent-to-Own Viability Prediction)
- **Tujuan:** Memprediksi kelayakan transisi dari barang sewaan jangka panjang menjadi barang milik penyewa (*Rent-to-Own*), di mana akumulasi biaya sewa dapat diperhitungkan sebagai pembayaran cicilan harga beli.
- **Rencana Fitur:**
  1. Durasi dan kontinuitas sewa aktif penyewa;
  2. TrustScore dan rekam jejak kepatuhan penyewa;
  3. Depresiasi taksiran nilai fisik barang seiring waktu pemakaian;
  4. Persetujuan bilateral pemilik barang dan penyewa.
- **Prinsip Etika:** Evaluasi kelayakan wajib transparan, tanpa biaya tersembunyi, dan tidak memberatkan kondisi finansial mahasiswa.


