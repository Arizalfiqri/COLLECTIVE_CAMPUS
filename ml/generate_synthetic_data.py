"""
Skrip pembangkitan data sintetis untuk pemodelan skor kepercayaan (Trust Score) KampusRent.

Metodologi:
1. Menghasilkan variabel laten keandalan (latent diligence/reliability) z ~ N(0, 1) per baris/pengguna.
2. Membangkitkan 8 fitur perilaku riwayat sewa sebelum transaksi yang dievaluasi (bebas target leakage).
   Catatan: fitur status_ktm sengaja dihapus karena hampir konstan (semua pengguna aktif wajib terverifikasi KTM).
3. Membangkitkan label target 'bermasalah_berikutnya' (~15% positif) menggunakan fungsi logistik laten
   dengan noise terkalibrasi untuk menjamin tumpang tindih antarkelas yang realistis (tidak terpisah sempurna).
4. Menyimpan dataset ke CSV dan menghitung hash SHA-256 untuk audit reproduktibilitas.
"""

import os
import hashlib
import numpy as np
import pandas as pd


def generate_synthetic_trust_data(n_samples: int = 4000, random_state: int = 42) -> pd.DataFrame:
    """
    Membangkitkan data sintetis riwayat sewa dan target risiko keandalan berikutnya.
    """
    rng = np.random.default_rng(random_state)

    # 1. Variabel laten keandalan / conscientiousness (z ~ N(0, 1))
    # Nilai z tinggi = pengguna sangat andal, teliti, tepat waktu, komunikatif.
    # Nilai z rendah = rentan lalai, menunda pengembalian, atau ceroboh merawat barang.
    z = rng.normal(loc=0.0, scale=1.0, size=n_samples)

    # CDF normal standar untuk mendapatkan persentil keandalan u in (0, 1)
    from scipy.stats import norm
    u = norm.cdf(z)

    # 2. Fitur riwayat:
    # Umur akun dalam hari (15 s.d. 730 hari)
    umur_akun_hari = np.clip(
        rng.gamma(shape=3.0, scale=60.0, size=n_samples) + 15,
        15,
        730
    ).astype(int)

    # Jumlah sewa selesai (minimal 3 karena pengguna baru < 3 memiliki aturan cold-start khusus)
    completed_base = rng.poisson(
        lam=np.clip(umur_akun_hari / 28.0 + 1.2 * z + 3.0, 1.0, 45.0),
        size=n_samples
    )
    jumlah_sewa_selesai = np.clip(completed_base + 3, 3, 70).astype(int)

    # Jumlah transaksi sebagai pemilik (beberapa mahasiswa juga pemilik barang)
    is_owner_prob = np.clip(0.35 + 0.15 * u, 0.1, 0.6)
    is_owner = rng.random(size=n_samples) < is_owner_prob
    owner_base = rng.poisson(
        lam=np.clip(jumlah_sewa_selesai * 0.45 + 0.8 * z, 0.5, 30.0),
        size=n_samples
    )
    jumlah_sebagai_pemilik = np.where(is_owner, owner_base, 0).astype(int)

    # Rasio tepat waktu (0.0 s.d. 1.0)
    # Pengguna berkeandalan tinggi memiliki rasio tepat waktu mendekati 1.0
    alpha_pw = np.clip(3.0 + 18.0 * u, 1.5, 35.0)
    beta_pw = np.clip(1.2 + 6.0 * (1.0 - u), 1.0, 12.0)
    rasio_tepat_waktu = rng.beta(alpha_pw, beta_pw, size=n_samples)
    rasio_tepat_waktu = np.clip(np.round(rasio_tepat_waktu, 3), 0.0, 1.0)

    # Rata-rata rating diterima (1.0 s.d. 5.0)
    rating_mean = 3.6 + 1.2 * u
    rating_noise = rng.normal(0, 0.25, size=n_samples)
    rata_rata_rating_diterima = np.clip(np.round(rating_mean + rating_noise, 2), 1.0, 5.0)

    # Jumlah sengketa (integer >= 0)
    total_transaksi = jumlah_sewa_selesai + jumlah_sebagai_pemilik
    # Peluang sengketa lebih tinggi jika keandalan z rendah
    dispute_intensity = np.exp(-1.4 - 1.1 * z) * (total_transaksi / 15.0)
    jumlah_sengketa = rng.poisson(lam=np.clip(dispute_intensity, 0.02, 6.0), size=n_samples).astype(int)
    # Pembatasan logis: jumlah sengketa tidak melebihi total transaksi
    jumlah_sengketa = np.minimum(jumlah_sengketa, total_transaksi)

    # Rasio sengketa terhadap total transaksi
    rasio_sengketa = np.clip(np.round(jumlah_sengketa / np.maximum(1, total_transaksi), 3), 0.0, 1.0)

    # Rasio pembatalan sewa (0.0 s.d. 1.0)
    cancel_alpha = np.clip(1.2 + 2.0 * (1.0 - u), 0.8, 5.0)
    cancel_beta = np.clip(10.0 + 15.0 * u, 5.0, 30.0)
    rasio_pembatalan = np.clip(np.round(rng.beta(cancel_alpha, cancel_beta, size=n_samples), 3), 0.0, 1.0)

    # 3. Pembentukan Target 'bermasalah_berikutnya':
    # Bernilai 1 jika pada transaksi berikutnya: telat > 1 hari, ada potongan kerusakan, atau sengketa.
    # Menggunakan fungsi logistik laten dari variabel laten z + noise logistik terkalibrasi.
    # Target prevalensi ~ 15.0% dengan overlap realistis.
    noise = rng.logistic(loc=0.0, scale=0.75, size=n_samples)
    latent_risk_logit = -2.03 - 1.45 * z + noise
    latent_risk_prob = 1.0 / (1.0 + np.exp(-latent_risk_logit))

    # Binerisasi dengan probabilitas latent atau cutoff
    bermasalah_berikutnya = (latent_risk_prob >= 0.50).astype(int)

    # Dataframe fitur dan target
    df = pd.DataFrame({
        'jumlah_sewa_selesai': jumlah_sewa_selesai,
        'jumlah_sebagai_pemilik': jumlah_sebagai_pemilik,
        'rasio_tepat_waktu': rasio_tepat_waktu,
        'rata_rata_rating_diterima': rata_rata_rating_diterima,
        'jumlah_sengketa': jumlah_sengketa,
        'rasio_sengketa': rasio_sengketa,
        'rasio_pembatalan': rasio_pembatalan,
        'umur_akun_hari': umur_akun_hari,
        'bermasalah_berikutnya': bermasalah_berikutnya
    })

    return df


def save_dataset_and_hash(df: pd.DataFrame, output_csv_path: str) -> str:
    """
    Menyimpan dataset ke file CSV dan membuat file .sha256 checksum.
    """
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    df.to_csv(output_csv_path, index=False)

    with open(output_csv_path, 'rb') as f:
        sha256_hash = hashlib.sha256(f.read()).hexdigest()

    hash_path = output_csv_path + ".sha256"
    with open(hash_path, 'w', encoding='utf-8') as f:
        f.write(f"{sha256_hash}  {os.path.basename(output_csv_path)}\n")

    return sha256_hash


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(base_dir, 'ml', 'data', 'synthetic_rental_trust_data.csv')

    print("=== Pembangkitan Data Sintetis Skor Kepercayaan KampusRent ===")
    df = generate_synthetic_trust_data(n_samples=4000, random_state=42)

    pos_count = df['bermasalah_berikutnya'].sum()
    pos_rate = df['bermasalah_berikutnya'].mean() * 100

    print(f"Total baris: {len(df)}")
    print(f"Kelas bermasalah (1): {pos_count} ({pos_rate:.2f}%)")
    print(f"Kelas aman (0): {len(df) - pos_count} ({100 - pos_rate:.2f}%)")
    print("\nRingkasan Statistik Fitur:")
    print(df.describe().round(3).T[['count', 'mean', 'std', 'min', '50%', 'max']])

    sha256 = save_dataset_and_hash(df, output_path)
    print(f"\nDataset berhasil disimpan ke: {output_path}")
    print(f"SHA-256 Hash: {sha256}")


if __name__ == '__main__':
    main()
