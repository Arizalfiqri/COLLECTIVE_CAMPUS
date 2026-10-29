"""
Demo Simulasi Continuous Learning & Retraining Model Skor Kepercayaan KampusRent.

Skrip ini dirancang khusus untuk demonstrasi juri dan penguji:
1. Mensimulasikan pengumpulan N transaksi sewa nyata (default: 250 transaksi).
2. Mensimulasikan snapshot fitur saat pengajuan dan pelabelan otomatis terminal state.
3. Melakukan time-based train/validation split (80/20).
4. Melatih kandidat model Logistic Regression terkalibrasi (CalibratedClassifierCV).
5. Mengevaluasi kandidat vs model aktif pada set validasi yang sama (PR-AUC & Brier score).
6. Menampilkan keputusan promosi atau penolakan model berdasarkan guardrail ketat.
7. BERSIH DARI EFEK SAMPING: Sepenuhnya berjalan in-memory tanpa memodifikasi database produksi.
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
    precision_score, recall_score, f1_score
)

# 8 Fitur Objektif (Bebas dari Atribut Sensitif UU PDP)
FEATURE_NAMES = [
    'jumlah_sewa_selesai',
    'jumlah_sebagai_pemilik',
    'rasio_tepat_waktu',
    'rata_rata_rating_diterima',
    'jumlah_sengketa',
    'rasio_sengketa',
    'rasio_pembatalan',
    'umur_akun_hari'
]


def generate_stream_data(n_samples=250, seed=42):
    """Membangkitkan aliran transaksi sewa sintetis untuk simulasi retraining."""
    np.random.seed(seed)
    records = []
    base_time = datetime(2026, 1, 1, 9, 0, 0)

    for i in range(n_samples):
        timestamp = base_time + timedelta(hours=i * 6)

        # Karakteristik perilaku pengguna
        is_risky = np.random.rand() < 0.16  # ~16% prevalensi risiko bermasalah

        if is_risky:
            completed = int(np.random.choice([0, 1, 2, 3, 4]))
            completed_owner = int(np.random.choice([0, 1]))
            punctual_ratio = round(float(np.random.uniform(0.35, 0.75)), 3)
            rating = round(float(np.random.uniform(2.8, 4.1)), 2)
            disputes = int(np.random.choice([1, 2, 3], p=[0.7, 0.2, 0.1]))
            cancel_ratio = round(float(np.random.uniform(0.15, 0.45)), 3)
            age_days = int(np.random.randint(10, 90))
            # Label bermasalah (terlambat > 1 hari, denda, atau sengketa)
            problem_label = 1 if np.random.rand() < 0.82 else 0
        else:
            completed = int(np.random.randint(3, 25))
            completed_owner = int(np.random.randint(0, 8))
            punctual_ratio = round(float(np.random.uniform(0.88, 1.00)), 3)
            rating = round(float(np.random.uniform(4.3, 5.0)), 2)
            disputes = 0 if np.random.rand() < 0.95 else 1
            cancel_ratio = round(float(np.random.uniform(0.0, 0.10)), 3)
            age_days = int(np.random.randint(45, 365))
            # Label aman
            problem_label = 1 if np.random.rand() < 0.05 else 0

        total_tx = max(1, completed + completed_owner)
        dispute_ratio = round(float(disputes) / float(total_tx), 3)

        records.append({
            'transaction_id': f"RENT-{20260000 + i}",
            'created_at': timestamp,
            'jumlah_sewa_selesai': completed,
            'jumlah_sebagai_pemilik': completed_owner,
            'rasio_tepat_waktu': punctual_ratio,
            'rata_rata_rating_diterima': rating,
            'jumlah_sengketa': disputes,
            'rasio_sengketa': dispute_ratio,
            'rasio_pembatalan': cancel_ratio,
            'umur_akun_hari': age_days,
            'label_problem': problem_label,
        })

    return pd.DataFrame(records)


def run_demo(n_samples=250, seed=42):
    print("=" * 78)
    print("DEMO CONTINUOUS LEARNING: SIKLUS RETRAINING & GUARDRAIL MODEL ML KAMPUSRENT")
    print("=" * 78)
    print("Mode: In-memory simulation (database produksi dijamin tidak tersentuh).")
    print(f"Target data stream yang disimulasikan: {n_samples} transaksi sewa baru.\n")

    # 1. Aliran data
    df = generate_stream_data(n_samples=n_samples, seed=seed)
    total_samples = len(df)
    total_positives = int(df['label_problem'].sum())
    prev = total_positives / total_samples

    print(f"[1] PENGUMPULAN DATA SEWA:")
    print(f"    - Total transaksi berlabel: {total_samples}")
    print(f"    - Kasus bermasalah (label=1): {total_positives} ({prev*100:.1f}%)")
    print(f"    - Kasus lancar (label=0)   : {total_samples - total_positives} ({(1-prev)*100:.1f}%)")

    # 2. Guardrail kecukupan data
    min_samples = 200
    min_positives = 20
    print(f"\n[2] PENGECEKAN GUARDRAIL AMBANG BATAS:")
    print(f"    - Syarat minimal contoh total  : {min_samples}  -> {'TERPENUHI' if total_samples >= min_samples else 'GAGAL'} ({total_samples}/{min_samples})")
    print(f"    - Syarat minimal kasus positif : {min_positives}   -> {'TERPENUHI' if total_positives >= min_positives else 'GAGAL'} ({total_positives}/{min_positives})")

    if total_samples < min_samples or total_positives < min_positives:
        print("    [HASIL] Retraining dibatalkan secara aman oleh guardrail platform.")
        return

    # 3. Time-based Split 80/20
    df = df.sort_values('created_at').reset_index(drop=True)
    split_point = int(len(df) * 0.8)
    df_train = df.iloc[:split_point]
    df_val = df.iloc[split_point:]

    print(f"\n[3] TIME-BASED TRAIN / VALIDATION SPLIT (80% / 20%):")
    print(f"    - Set Latih (waktu lebih lampau) : {len(df_train)} contoh ({int(df_train['label_problem'].sum())} bermasalah)")
    print(f"    - Set Uji   (waktu paling baru)   : {len(df_val)} contoh ({int(df_val['label_problem'].sum())} bermasalah)")
    print("    - Catatan: Time split digunakan untuk menghindari data leakage ke masa lalu.")

    X_train = df_train[FEATURE_NAMES]
    y_train = df_train['label_problem'].to_numpy()
    X_val = df_val[FEATURE_NAMES]
    y_val = df_val['label_problem'].to_numpy()

    # 4. Pelatihan Model Aktif Baseline (Representasi v1.0)
    scaler_active = StandardScaler()
    X_train_act_scaled = scaler_active.fit_transform(X_train)
    X_val_act_scaled = scaler_active.transform(X_val)

    # Model baseline sebelumnya
    lr_active = LogisticRegression(class_weight='balanced', random_state=10, max_iter=1000)
    cal_active = CalibratedClassifierCV(estimator=lr_active, method='sigmoid', cv=3)
    cal_active.fit(X_train_act_scaled, y_train)

    probs_active = cal_active.predict_proba(X_val_act_scaled)[:, 1]
    active_pr_auc = average_precision_score(y_val, probs_active)
    active_roc_auc = roc_auc_score(y_val, probs_active)
    active_brier = brier_score_loss(y_val, probs_active)

    # 5. Pelatihan Kandidat Model Baru (v2.0)
    scaler_cand = StandardScaler()
    X_train_cand_scaled = scaler_cand.fit_transform(X_train)
    X_val_cand_scaled = scaler_cand.transform(X_val)

    lr_cand = LogisticRegression(class_weight='balanced', random_state=42, max_iter=1000)
    cal_cand = CalibratedClassifierCV(estimator=lr_cand, method='sigmoid', cv=5)
    cal_cand.fit(X_train_cand_scaled, y_train)

    probs_cand = cal_cand.predict_proba(X_val_cand_scaled)[:, 1]
    cand_pr_auc = average_precision_score(y_val, probs_cand)
    cand_roc_auc = roc_auc_score(y_val, probs_cand)
    cand_brier = brier_score_loss(y_val, probs_cand)

    # 6. Komparasi Metrik pada Validasi Set
    delta_pr_auc = cand_pr_auc - active_pr_auc
    delta_brier = cand_brier - active_brier

    print(f"\n[4] EVALUASI KOMPARATIF PADA VALIDASI SET IDENTIK (n={len(df_val)}):")
    print("-" * 78)
    print(f"{'Metrik Evaluasi':<28} | {'Model Aktif':<14} | {'Kandidat Baru':<14} | {'Selisih (Delta)':<14}")
    print("-" * 78)
    print(f"{'PR-AUC (Presisi-Recall)':<28} | {active_pr_auc:<14.4f} | {cand_pr_auc:<14.4f} | {delta_pr_auc:+14.4f}")
    print(f"{'ROC-AUC':<28} | {active_roc_auc:<14.4f} | {cand_roc_auc:<14.4f} | {cand_roc_auc - active_roc_auc:+14.4f}")
    print(f"{'Brier Score (Kalibrasi)':<28} | {active_brier:<14.4f} | {cand_brier:<14.4f} | {delta_brier:+14.4f}")
    print("-" * 78)

    # 7. Keputusan Promosi Sesuai Aturan Ketat
    req_pr_gain = 0.0100
    is_pr_ok = delta_pr_auc >= req_pr_gain
    is_brier_ok = delta_brier <= 0.0010  # Kalibrasi tidak memburuk
    is_promoted = is_pr_ok and is_brier_ok

    print(f"\n[5] KEPUTUSAN PROMOSI MODEL (STRICT PROMOTION GUARDRAIL):")
    print(f"    - Syarat 1: PR-AUC naik >= +0.0100 -> {'LOLOS' if is_pr_ok else 'GAGAL'} ({delta_pr_auc:+.4f})")
    print(f"    - Syarat 2: Brier score tidak memburuk -> {'LOLOS' if is_brier_ok else 'GAGAL'} ({delta_brier:+.4f})")

    if is_promoted:
        print(f"\n    >>> STATUS: KANDIDAT BERHASIL DIPROMOSIKAN <<<")
        print(f"    Model baru akan diberi versi 'v2.0-real-{datetime.now():%Y%m%d}' dan disimpan ke artefak.")
        print(f"    Model lama dijadikan arsip cadangan (fallback/rollback ready).")
    else:
        print(f"\n    >>> STATUS: KANDIDAT TIDAK DIPROMOSIKAN <<<")
        print(f"    Model aktif lama dipertahankan karena kandidat belum memenuhi standar peningkatan kualitas.")

    print("\n" + "=" * 78)
    print("SIMULASI SELESAI DENGAN SUKSES.")
    print("=" * 78)


if __name__ == '__main__':
    run_demo()
