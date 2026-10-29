# SPEC_UPDATE_v2: Pembaruan Spesifikasi Collective Campus

> Dokumen ini **menggantikan bagian yang bertentangan** di `PROJECT_SPEC.md`. Bagian yang tidak disebut di sini tetap berlaku. Semua angka adalah nilai awal yang bisa diubah lewat `.env` atau `settings.py`, jangan ditulis langsung (hardcode) di banyak tempat.

## A. Prinsip jaminan (menggantikan baris deposit di 7.1 dan 7.3)

**Prinsip:** deposit melindungi dari **kerusakan dan keterlambatan**. Risiko **kehilangan total** ditangani lapisan lain: batas nilai barang, identitas, bukti foto, dana proteksi, dan syarat dari pemilik. Pemilik menanggung risiko sisa, jadi **pemilik boleh mengatur syaratnya sendiri** di atas batas minimum platform. Penyewa melihat semua syarat sebelum mengajukan sewa.

### A.1 Tangga kepercayaan (`TRUST_TIERS` di settings)

| Tingkat | Syarat | Maks. nilai barang | Deposit minimum |
|---|---|---|---|
| `baru` | kurang dari 3 sewa selesai | Rp750.000 | 15% dari nilai barang |
| `tepercaya` | 3-5 sewa selesai tanpa sengketa (dan skor 60 atau lebih bila skor sudah ada) | Rp1.500.000 | 10% |
| `sangat_tepercaya` | 6 sewa selesai atau lebih tanpa sengketa (dan skor 75 atau lebih bila skor sudah ada) | Rp3.000.000 | 10% |

- Sebelum model ML jadi (Fase 6), tingkat ditentukan **hanya dari jumlah sewa selesai tanpa sengketa**.
- Barang bernilai Rp150.000 atau kurang boleh **tanpa deposit**.
- Untuk barang bernilai di atas Rp150.000, deposit tidak kurang dari Rp25.000.
- **Lintas kampus:** deposit minimum ditambah `CROSS_CAMPUS_EXTRA_DEPOSIT_PERCENT` (5 poin persen).
- Tingkat penyewa dihitung oleh satu fungsi service (`apps/trust/services.py: get_renter_tier(user)`), dipakai di katalog, detail barang, dan pengajuan sewa.

### A.2 Syarat dari pemilik (field baru di `Item`)

- `deposit_amount`: boleh lebih tinggi dari minimum, tidak boleh lebih rendah.
- `min_renter_tier`: tingkat penyewa minimal (bawaan `baru`).
- `require_ktm_held` (bool): mensyaratkan jaminan KTM ditahan (lihat B).
- Barang dengan `estimated_value` di atas `MAX_ITEM_VALUE` (Rp3.000.000) **ditolak saat dipasang**. Kategori Laptop dihapus atau dibatasi pada nilai yang sama.

### A.3 Biaya proteksi dan dana proteksi (menggantikan biaya proteksi Rp3.000)

- `protection_fee = max(PROTECTION_FEE_MIN, round(rent_total * PROTECTION_FEE_PERCENT / 100))`, dengan 5% dan minimum Rp3.000.
- **Wajib** untuk barang bernilai di atas `PROTECTION_MANDATORY_ABOVE` (Rp500.000), opsional di bawahnya.
- Dicatat di buku besar sebagai `masuk_dana_proteksi` (bukan pendapatan langsung platform).
- Klaim (simulasi): bila admin memutuskan sengketa "barang tidak dikembalikan", pemilik dapat ganti rugi dari dana proteksi sebesar paling banyak 50% nilai barang dikurangi deposit yang sudah diterimanya. Versi produksi memerlukan asuransi mitra, dan hal ini dinyatakan terbuka di presentasi.
- Pembaruan rumus: `platform_income = commission`. Dana proteksi dipisahkan dari pendapatan.

## B. Jaminan KTM ditahan (opsional, dipilih pemilik)

Disetujui sebagai **syarat tambahan dari pemilik, bukan kewajiban sistem**, dan **bukan pengganti** deposit dan batas nilai.

**Aturan:**
1. Penyewa melihat syarat ini sebelum mengajukan dan menyetujuinya di perjanjian sewa (lihat C.2).
2. Pemilik **dilarang memfoto atau menyalin** KTM, wajib menyimpannya dengan aman, dan wajib mengembalikannya saat barang kembali.
3. Kedua pihak mengonfirmasi di aplikasi saat KTM **diserahkan** dan saat **dikembalikan** (`Rental.ktm_held_confirmed_at`, `Rental.ktm_returned_confirmed_at`).
4. Sewa tidak dapat menjadi `selesai` sebelum pengembalian KTM dikonfirmasi.
5. KTM yang hilang selama ditahan menjadi tanggung jawab pemilik.
6. Platform **tidak menyimpan gambar** KTM yang ditahan. Ini kesepakatan di luar platform yang hanya dicatat statusnya.

**Catatan risiko (tampilkan sebagai peringatan di UI dan sebut di presentasi):** KTM yang ditahan bisa difoto lalu dipakai mendaftar akun palsu atas nama penyewa, padahal verifikasi KTM kita berbasis foto KTM. Mitigasi rencana lanjutan: verifikasi kedua (email kampus `.ac.id` atau selfie). Konsultasikan aspek hukum menahan dokumen identitas sebelum dipakai di luar lomba.

## C. Protokol serah terima (menggantikan 8.3)

1. **Pemeriksaan identitas langsung:** pemilik melihat KTM asli penyewa dan mencocokkannya dengan nama di aplikasi (tidak ditahan, kecuali syarat B).
2. **Foto kondisi barang sebelum** (minimal 2), seperti sebelumnya.
3. **Foto serah terima** diambil **di dalam aplikasi** (kamera langsung, bukan galeri): penyewa memegang barang dengan wajah terlihat jelas. KTM tidak perlu masuk bingkai.
   - Penyewa mencentang **persetujuan** pengambilan foto (`Rental.handover_photo_consent_at`).
   - `ConditionPhoto.phase` bertambah nilai `serah_terima`.
   - Disimpan privat. Hanya pemilik, penyewa, dan admin yang bisa melihat.
   - Dihapus `HANDOVER_PHOTO_RETENTION_DAYS` (30 hari) setelah sewa `selesai` tanpa sengketa. Disimpan bila ada sengketa.
4. Kedua pihak **mengonfirmasi serah terima** di aplikasi, lalu status menjadi `sedang_disewa`.

### C.2 Perjanjian sewa digital

Saat mengajukan sewa, penyewa mencentang persetujuan syarat. Disimpan sebagai `RentalAgreement` (`rental`, `terms_snapshot` JSON berisi deposit, denda, ganti rugi kehilangan sebesar nilai barang, status KTM ditahan, `accepted_at`). Ini bukti persetujuan, **bukan jaminan kekuatan hukum**.

## D. Jadwal serah terima (terstruktur, bukan hanya chat)

- **MeetingPoint**: `campus`, `name`, `is_public` (titik temu kampus yang ramai).
- **HandoverSchedule**: `rental`, `proposed_by`, `meet_at`, `meeting_point`, `status` (`diusulkan`/`dikonfirmasi`/`diubah`), `note`.
- Alur: setelah `dibayar`, pemilik mengusulkan jam dan titik temu, penyewa mengonfirmasi atau mengusulkan ulang. Tampil di halaman sewa dan dashboard, dengan pengingat (notifikasi dalam aplikasi) satu hari sebelumnya lewat `process_deadlines`.
- Penyewa lintas kampus hanya bisa memilih titik `is_public=True`.

## E. Chat dalam sistem (aplikasi baru `chat`)

**Model**
- `Conversation`: `item`, `renter`, `owner`, `rental` (boleh kosong, diisi setelah ada sewa), `last_message_at`. Unik pada (`item`, `renter`).
- `Message`: `conversation`, `sender`, `body` (maksimal 500 karakter), `created_at`, `read_at`.

**Aturan**
- Hanya akun terverifikasi. **Hanya penyewa yang boleh memulai** percakapan (mencegah spam ke pemilik). Hanya dua peserta yang bisa membaca.
- **Sebelum pembayaran berhasil:** nomor telepon (pola `08...`, `+62...`, 8 digit berurutan atau lebih), tautan (`http`, `wa.me`, `t.me`), dan alamat email **disamarkan** menjadi "[disamarkan sampai pembayaran]". **Setelah dibayar:** tidak disamarkan.
- Teks otomatis di-escape. Batas kirim 20 pesan per menit per pengguna.
- Pembaruan lewat **HTMX polling** setiap 5 detik (tanpa WebSocket).
- Penanda pesan belum dibaca di navbar. Tombol **"Tanya pemilik"** di detail barang. Halaman `/pesan/` (kotak masuk) dan `/pesan/<id>/` (percakapan).
- Riwayat disimpan dan **dapat dibaca admin saat sengketa**. Beri tahu pengguna hal ini di halaman chat.

## F. Multi-kampus

- **Campus**: `name`, `short_name`, `city`, `ktm_keywords` (daftar kata kunci), `nim_pattern` (opsional), `is_active`.
- `StudentProfile.campus` (ForeignKey) menggantikan `campus_name` (teks). Pindahkan data lama lewat migrasi data.
- Katalog: filter **"Kampus saya"** (bawaan) atau **"Semua kampus"**.
- OCR: `campus_match` memakai `ktm_keywords` kampus yang dipilih, dan pola NIM mengikuti `nim_pattern` bila ada.
- Seed: 3 kampus fiktif dengan titik temu masing-masing.

## G. Barang tidak dikembalikan (menggantikan bagian terkait di 9.5)

Perintah `process_deadlines` (jalan manual atau lewat tombol admin):
1. Bila `end_date + NON_RETURN_GRACE_HOURS` (48 jam) terlewati, status `sedang_disewa`, dan penyewa belum melapor pengembalian: buat `Dispute` otomatis dengan alasan `barang_tidak_dikembalikan`.
2. Seluruh deposit diberikan ke pemilik (`LedgerEntry` `keluar_deposit_ke_pemilik`).
3. Akun penyewa `User.is_suspended = True` (tidak bisa mengajukan atau memasang barang), dan NIM masuk `BlacklistedNim` (tidak bisa mendaftar ulang).
4. Admin meninjau dan memutuskan klaim dana proteksi (A.3).
5. Pemilik melihat riwayat chat, foto serah terima, dan perjanjian sewa sebagai bukti.

## H. Tambahan konfigurasi `.env`

```
TRUST_TIERS=baru:750000:15,tepercaya:1500000:10,sangat_tepercaya:3000000:10
MAX_ITEM_VALUE=3000000
NO_DEPOSIT_BELOW_VALUE=150000
MIN_DEPOSIT_AMOUNT=25000
CROSS_CAMPUS_EXTRA_DEPOSIT_PERCENT=5
PROTECTION_FEE_PERCENT=5
PROTECTION_FEE_MIN=3000
PROTECTION_MANDATORY_ABOVE=500000
HANDOVER_PHOTO_RETENTION_DAYS=30
NON_RETURN_GRACE_HOURS=48
```

## I. Tes tambahan yang wajib ada

- Penentuan tingkat penyewa dan batas nilai barang (baru, tepercaya, sangat tepercaya).
- Perhitungan deposit minimum (tanpa deposit, minimum Rp25.000, lintas kampus).
- Penolakan barang di atas `MAX_ITEM_VALUE` saat dipasang.
- Penyamaran nomor, tautan, dan email sebelum bayar, dan tidak disamarkan sesudah bayar.
- Hanya peserta yang bisa membaca percakapan, dan hanya penyewa yang bisa memulainya.
- Sewa tidak bisa `selesai` sebelum KTM yang ditahan dikembalikan.
- `process_deadlines`: sengketa otomatis, deposit ke pemilik, pembekuan akun, dan daftar hitam NIM.
- Penghapusan foto serah terima setelah masa simpan, dan tidak dihapus bila ada sengketa.
- Invarian buku besar tetap lolos dengan dana proteksi.
