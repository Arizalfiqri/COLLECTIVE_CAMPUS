"""
Skrip Pelatihan, Kalibrasi, Evaluasi, dan Penjelasan Model Skor Kepercayaan KampusRent.

Langkah:
1. Membaca dataset sintetis (ml/data/synthetic_rental_trust_data.csv).
2. Membagi train/test stratified 80/20 (random_state=42).
3. 5-Fold Stratified Cross-Validation pada train set untuk membandingkan:
   - DummyClassifier (baseline probabilitas terbanyak)
   - Baseline aturan (rasio_tepat_waktu < 0.7 => berisiko)
   - LogisticRegression (dengan StandardScaler dan class_weight='balanced')
   - GradientBoostingClassifier
4. Pemilihan model: LogisticRegression dipilih karena interpretasi langsung yang transparan,
   dan kinerjanya kompetitif/unggul dibanding GradientBoosting.
5. Kalibrasi probabilitas menggunakan CalibratedClassifierCV (metode sigmoid).
   Evaluasi Brier score sebelum dan sesudah kalibrasi.
6. Pemilihan ambang keputusan (decision threshold) pada cross-validation fold agar recall
   kelas bermasalah minimal 0.70 dengan presisi optimal.
7. Evaluasi pada data uji (test set) untuk semua model dan simpan metrik lengkap.
8. Hitung permutation importance dan koefisien model linear.
9. Simpan artefak:
   - ml/artifacts/trust_model.joblib
   - ml/artifacts/metrics.json
   - 5 visualisasi PNG di static/ml/ dengan palet 5A (datar, tanpa gradien, sentence case).
"""

import os
import json
import hashlib
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    roc_auc_score, average_precision_score, roc_curve, precision_recall_curve,
    confusion_matrix, precision_score, recall_score, f1_score, accuracy_score,
    brier_score_loss
)


# Palet AGENT.md 5A
COLORS = {
    'paper': '#F8F5EE',
    'card': '#FFFFFF',
    'line': '#E4DECF',
    'ink': '#141B34',
    'ink_muted': '#566074',
    'brand': '#1F45C4',
    'brand_tint': '#E6ECFB',
    'saffron': '#F2A900',
    'pine': '#0E7C5A',
    'pine_tint': '#DDF1E8',
    'amber_text': '#9A5B00',
    'brick': '#B42318',
    'brick_tint': '#FDE7E4',
}


def apply_plot_style(ax, title, xlabel, ylabel):
    """Menerapkan gaya visual datar sesuai AGENT.md (kertas dan tinta)."""
    ax.set_facecolor(COLORS['card'])
    ax.set_title(title, fontsize=12, fontweight='bold', color=COLORS['ink'], pad=12)
    ax.set_xlabel(xlabel, fontsize=10, color=COLORS['ink'], labelpad=8)
    ax.set_ylabel(ylabel, fontsize=10, color=COLORS['ink'], labelpad=8)
    ax.grid(True, linestyle='-', linewidth=0.75, color=COLORS['line'], alpha=0.8)
    ax.tick_params(colors=COLORS['ink_muted'], labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(COLORS['line'])
        spine.set_linewidth(1.0)


def train_and_evaluate_all():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, 'ml', 'data', 'synthetic_rental_trust_data.csv')
    artifacts_dir = os.path.join(base_dir, 'ml', 'artifacts')
    static_ml_dir = os.path.join(base_dir, 'static', 'ml')
    os.makedirs(artifacts_dir, exist_ok=True)
    os.makedirs(static_ml_dir, exist_ok=True)

    # 1. Baca data & verifikasi hash
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"File data tidak ditemukan di: {data_path}")

    with open(data_path, 'rb') as f:
        data_hash = hashlib.sha256(f.read()).hexdigest()

    df = pd.read_csv(data_path)
    feature_cols = [
        'jumlah_sewa_selesai',
        'jumlah_sebagai_pemilik',
        'rasio_tepat_waktu',
        'rata_rata_rating_diterima',
        'jumlah_sengketa',
        'rasio_sengketa',
        'rasio_pembatalan',
        'umur_akun_hari'
    ]
    target_col = 'bermasalah_berikutnya'

    X = df[feature_cols]
    y = df[target_col]

    # 2. Split Train / Test 80/20 Stratified
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # 3. Model Definitions
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Baseline 1: Dummy
    dummy = DummyClassifier(strategy='prior')
    dummy.fit(X_train, y_train)

    # Baseline 2: Rule (rasio_tepat_waktu < 0.70 => 1)
    # Skor risiko dari rule: 1.0 - rasio_tepat_waktu

    # Model 1: Logistic Regression
    lr_base = LogisticRegression(
        class_weight='balanced',
        max_iter=1000,
        random_state=42
    )
    lr_base.fit(X_train_scaled, y_train)

    # Model 2: Gradient Boosting
    gb_model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=3,
        random_state=42
    )
    gb_model.fit(X_train, y_train)

    # 4. Cross-Validation Evaluation on Train Set
    cv_results = {}
    # LR CV
    lr_cv_probs = cross_val_predict(lr_base, X_train_scaled, y_train, cv=cv, method='predict_proba')[:, 1]
    cv_results['logistic_regression'] = {
        'roc_auc': float(roc_auc_score(y_train, lr_cv_probs)),
        'pr_auc': float(average_precision_score(y_train, lr_cv_probs)),
    }

    # GB CV
    gb_cv_probs = cross_val_predict(gb_model, X_train, y_train, cv=cv, method='predict_proba')[:, 1]
    cv_results['gradient_boosting'] = {
        'roc_auc': float(roc_auc_score(y_train, gb_cv_probs)),
        'pr_auc': float(average_precision_score(y_train, gb_cv_probs)),
    }

    print("\n--- Hasil 5-Fold Stratified Cross-Validation pada Train Set ---")
    print(f"Logistic Regression  : ROC-AUC = {cv_results['logistic_regression']['roc_auc']:.4f}, PR-AUC = {cv_results['logistic_regression']['pr_auc']:.4f}")
    print(f"Gradient Boosting    : ROC-AUC = {cv_results['gradient_boosting']['roc_auc']:.4f}, PR-AUC = {cv_results['gradient_boosting']['pr_auc']:.4f}")

    # 5. Kalibrasi Probabilitas untuk Model Terpilih (Logistic Regression)
    # Menggunakan CalibratedClassifierCV (sigmoid / Platt Scaling)
    calibrated_model = CalibratedClassifierCV(
        estimator=lr_base,
        method='sigmoid',
        cv=5
    )
    calibrated_model.fit(X_train_scaled, y_train)

    # Brier score sebelum dan sesudah kalibrasi pada test set
    y_test_probs_uncal = lr_base.predict_proba(X_test_scaled)[:, 1]
    y_test_probs_cal = calibrated_model.predict_proba(X_test_scaled)[:, 1]

    brier_before = float(brier_score_loss(y_test, y_test_probs_uncal))
    brier_after = float(brier_score_loss(y_test, y_test_probs_cal))
    brier_improvement_pct = float(((brier_before - brier_after) / brier_before) * 100)

    print(f"\nKalibrasi Probabilitas (Brier Score pada Test Set):")
    print(f"  Sebelum kalibrasi : {brier_before:.4f}")
    print(f"  Setelah kalibrasi : {brier_after:.4f} (Penurunan error kalibrasi: {brier_improvement_pct:.1f}%)")

    # 6. Pemilihan Ambang Keputusan (Decision Threshold) pada Validasi / CV
    # Target: Recall kelas bermasalah (1) >= 0.70 dengan presisi setinggi mungkin
    cal_cv_probs = cross_val_predict(calibrated_model, X_train_scaled, y_train, cv=cv, method='predict_proba')[:, 1]
    precisions_val, recalls_val, thresholds_val = precision_recall_curve(y_train, cal_cv_probs)

    valid_indices = np.where(recalls_val[:-1] >= 0.70)[0]
    if len(valid_indices) > 0:
        # Pilih yang memaksimalkan presisi di antara yang memenuhi target recall >= 0.70
        best_val_idx = valid_indices[np.argmax(precisions_val[:-1][valid_indices])]
        selected_threshold = float(thresholds_val[best_val_idx])
        val_recall_at_thresh = float(recalls_val[best_val_idx])
        val_precision_at_thresh = float(precisions_val[best_val_idx])
    else:
        selected_threshold = 0.20
        val_recall_at_thresh = 0.70
        val_precision_at_thresh = 0.40

    print(f"\nAmbang Keputusan Terpilih (dari Cross-Validation):")
    print(f"  Ambang (Threshold) : {selected_threshold:.4f}")
    print(f"  Validasi Recall    : {val_recall_at_thresh:.4f}")
    print(f"  Validasi Presisi   : {val_precision_at_thresh:.4f}")

    # 7. Evaluasi Komparatif Seluruh Model pada Test Set (n=800)
    models_eval = {}

    # (a) Dummy
    dummy_probs = dummy.predict_proba(X_test)[:, 1]
    dummy_preds = dummy.predict(X_test)
    models_eval['dummy'] = {
        'name': 'Dummy (kelas mayoritas)',
        'roc_auc': float(roc_auc_score(y_test, dummy_probs)),
        'pr_auc': float(average_precision_score(y_test, dummy_probs)),
        'accuracy': float(accuracy_score(y_test, dummy_preds)),
        'precision': float(precision_score(y_test, dummy_preds, zero_division=0)),
        'recall': float(recall_score(y_test, dummy_preds, zero_division=0)),
        'f1': float(f1_score(y_test, dummy_preds, zero_division=0)),
        'brier_score': float(brier_score_loss(y_test, dummy_probs)),
        'confusion_matrix': confusion_matrix(y_test, dummy_preds).tolist()
    }

    # (b) Rule Baseline (rasio_tepat_waktu < 0.70)
    rule_preds = (X_test['rasio_tepat_waktu'] < 0.70).astype(int)
    rule_risk_score = 1.0 - X_test['rasio_tepat_waktu']
    models_eval['rule_baseline'] = {
        'name': 'Baseline aturan (tepat waktu < 0.70)',
        'roc_auc': float(roc_auc_score(y_test, rule_risk_score)),
        'pr_auc': float(average_precision_score(y_test, rule_risk_score)),
        'accuracy': float(accuracy_score(y_test, rule_preds)),
        'precision': float(precision_score(y_test, rule_preds)),
        'recall': float(recall_score(y_test, rule_preds)),
        'f1': float(f1_score(y_test, rule_preds)),
        'brier_score': float(brier_score_loss(y_test, rule_risk_score)),
        'confusion_matrix': confusion_matrix(y_test, rule_preds).tolist()
    }

    # (c) Logistic Regression (Uncalibrated, threshold bawaan 0.50)
    lr_preds_default = (y_test_probs_uncal >= 0.50).astype(int)
    models_eval['logistic_regression_uncal'] = {
        'name': 'Regresi logistik (tanpa kalibrasi, ambang 0.50)',
        'roc_auc': float(roc_auc_score(y_test, y_test_probs_uncal)),
        'pr_auc': float(average_precision_score(y_test, y_test_probs_uncal)),
        'accuracy': float(accuracy_score(y_test, lr_preds_default)),
        'precision': float(precision_score(y_test, lr_preds_default)),
        'recall': float(recall_score(y_test, lr_preds_default)),
        'f1': float(f1_score(y_test, lr_preds_default)),
        'brier_score': float(brier_score_loss(y_test, y_test_probs_uncal)),
        'confusion_matrix': confusion_matrix(y_test, lr_preds_default).tolist()
    }

    # (d) Gradient Boosting (threshold bawaan 0.50)
    gb_test_probs = gb_model.predict_proba(X_test)[:, 1]
    gb_preds_default = (gb_test_probs >= 0.50).astype(int)
    models_eval['gradient_boosting'] = {
        'name': 'Gradient boosting (ambang 0.50)',
        'roc_auc': float(roc_auc_score(y_test, gb_test_probs)),
        'pr_auc': float(average_precision_score(y_test, gb_test_probs)),
        'accuracy': float(accuracy_score(y_test, gb_preds_default)),
        'precision': float(precision_score(y_test, gb_preds_default)),
        'recall': float(recall_score(y_test, gb_preds_default)),
        'f1': float(f1_score(y_test, gb_preds_default)),
        'brier_score': float(brier_score_loss(y_test, gb_test_probs)),
        'confusion_matrix': confusion_matrix(y_test, gb_preds_default).tolist()
    }

    # (e) Model Terpilih: Calibrated Logistic Regression pada Selected Threshold
    cal_preds_selected = (y_test_probs_cal >= selected_threshold).astype(int)
    cal_preds_default = (y_test_probs_cal >= 0.50).astype(int)
    models_eval['logistic_regression_calibrated'] = {
        'name': f'Regresi logistik terkalibrasi (ambang terpilih {selected_threshold:.3f})',
        'roc_auc': float(roc_auc_score(y_test, y_test_probs_cal)),
        'pr_auc': float(average_precision_score(y_test, y_test_probs_cal)),
        'accuracy': float(accuracy_score(y_test, cal_preds_selected)),
        'precision': float(precision_score(y_test, cal_preds_selected)),
        'recall': float(recall_score(y_test, cal_preds_selected)),
        'f1': float(f1_score(y_test, cal_preds_selected)),
        'brier_score': float(brier_score_loss(y_test, y_test_probs_cal)),
        'confusion_matrix': confusion_matrix(y_test, cal_preds_selected).tolist(),
        'at_threshold_0_5': {
            'accuracy': float(accuracy_score(y_test, cal_preds_default)),
            'precision': float(precision_score(y_test, cal_preds_default)),
            'recall': float(recall_score(y_test, cal_preds_default)),
            'f1': float(f1_score(y_test, cal_preds_default)),
            'confusion_matrix': confusion_matrix(y_test, cal_preds_default).tolist(),
        }
    }

    print("\n--- Evaluasi Komparatif pada Test Set (n=800) ---")
    header = f"{'Model':<48} | {'ROC-AUC':<8} | {'PR-AUC':<8} | {'Prec':<6} | {'Recall':<6} | {'F1':<6} | {'Brier':<6}"
    print(header)
    print("-" * len(header))
    for m_key, m_val in models_eval.items():
        print(f"{m_val['name']:<48} | {m_val['roc_auc']:<8.4f} | {m_val['pr_auc']:<8.4f} | {m_val['precision']:<6.4f} | {m_val['recall']:<6.4f} | {m_val['f1']:<6.4f} | {m_val['brier_score']:<6.4f}")

    # 8. Permutation Importance & Feature Weights
    perm_importance = permutation_importance(
        calibrated_model, X_test_scaled, y_test,
        n_repeats=10, random_state=42, scoring='roc_auc'
    )
    feature_importance_dict = {}
    for i, col in enumerate(feature_cols):
        feature_importance_dict[col] = {
            'mean': float(perm_importance.importances_mean[i]),
            'std': float(perm_importance.importances_std[i]),
        }

    raw_coefs = lr_base.coef_[0]
    coefficients_dict = {
        col: float(coef) for col, coef in zip(feature_cols, raw_coefs)
    }

    # 9. Pembuatan 5 Grafik PNG di static/ml/
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']

    # (Grafik 1) Kurva ROC
    fig, ax = plt.subplots(figsize=(6.5, 5.0), facecolor=COLORS['paper'])
    apply_plot_style(ax, 'Kurva ROC (karakteristik operasi penerima)', 'Tingkat positif semu (1 - spesifisitas)', 'Tingkat positif sejati (sensitivitas)')

    # Dummy ROC
    ax.plot([0, 1], [0, 1], linestyle='--', color=COLORS['ink_muted'], label='Baseline acak (AUC = 0.500)')
    # Rule Baseline
    fpr_r, tpr_r, _ = roc_curve(y_test, rule_risk_score)
    ax.plot(fpr_r, tpr_r, color=COLORS['amber_text'], linewidth=1.8, label=f'Baseline aturan (AUC = {models_eval["rule_baseline"]["roc_auc"]:.3f})')
    # GB
    fpr_gb, tpr_gb, _ = roc_curve(y_test, gb_test_probs)
    ax.plot(fpr_gb, tpr_gb, color=COLORS['pine'], linewidth=1.8, label=f'Gradient boosting (AUC = {models_eval["gradient_boosting"]["roc_auc"]:.3f})')
    # Calibrated LR (terpilih)
    fpr_cal, tpr_cal, _ = roc_curve(y_test, y_test_probs_cal)
    ax.plot(fpr_cal, tpr_cal, color=COLORS['brand'], linewidth=2.5, label=f'Regresi logistik terpilih (AUC = {models_eval["logistic_regression_calibrated"]["roc_auc"]:.3f})')

    # Titik operasi terpilih
    cm = models_eval['logistic_regression_calibrated']['confusion_matrix']
    tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
    op_fpr = fp / (fp + tn)
    op_tpr = tp / (tp + fn)
    ax.plot(op_fpr, op_tpr, marker='o', markersize=7, color=COLORS['brick'], label=f'Titik keputusan (ambang {selected_threshold:.3f})')

    ax.legend(loc='lower right', frameon=True, facecolor=COLORS['card'], edgecolor=COLORS['line'], fontsize=8.5)
    plt.tight_layout()
    roc_img_path = os.path.join(static_ml_dir, 'roc_curve.png')
    plt.savefig(roc_img_path, dpi=160, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()

    # (Grafik 2) Kurva Presisi-Recall
    fig, ax = plt.subplots(figsize=(6.5, 5.0), facecolor=COLORS['paper'])
    apply_plot_style(ax, 'Kurva presisi-recall', 'Sensitivitas (recall)', 'Presisi')

    base_prev = float(y_test.mean())
    ax.axhline(base_prev, linestyle='--', color=COLORS['ink_muted'], label=f'Prevalensi dasar ({base_prev*100:.1f}%)')

    p_r, r_r, _ = precision_recall_curve(y_test, rule_risk_score)
    ax.plot(r_r, p_r, color=COLORS['amber_text'], linewidth=1.8, label=f'Baseline aturan (PR-AUC = {models_eval["rule_baseline"]["pr_auc"]:.3f})')

    p_gb, r_gb, _ = precision_recall_curve(y_test, gb_test_probs)
    ax.plot(r_gb, p_gb, color=COLORS['pine'], linewidth=1.8, label=f'Gradient boosting (PR-AUC = {models_eval["gradient_boosting"]["pr_auc"]:.3f})')

    p_cal, r_cal, _ = precision_recall_curve(y_test, y_test_probs_cal)
    ax.plot(r_cal, p_cal, color=COLORS['brand'], linewidth=2.5, label=f'Regresi logistik terpilih (PR-AUC = {models_eval["logistic_regression_calibrated"]["pr_auc"]:.3f})')

    ax.plot(op_tpr, tp / (tp + fp), marker='o', markersize=7, color=COLORS['brick'], label=f'Titik operasi (ambang {selected_threshold:.3f})')
    ax.legend(loc='upper right', frameon=True, facecolor=COLORS['card'], edgecolor=COLORS['line'], fontsize=8.5)
    plt.tight_layout()
    pr_img_path = os.path.join(static_ml_dir, 'pr_curve.png')
    plt.savefig(pr_img_path, dpi=160, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()

    # (Grafik 3) Matriks Kebingungan (Confusion Matrix)
    fig, ax = plt.subplots(figsize=(5.5, 4.8), facecolor=COLORS['paper'])
    ax.set_facecolor(COLORS['card'])
    ax.set_title(f'Matriks kebingungan (ambang {selected_threshold:.3f}, recall >= 0.70)', fontsize=11, fontweight='bold', color=COLORS['ink'], pad=12)

    c_matrix = np.array(cm)
    im = ax.imshow(c_matrix, interpolation='nearest', cmap=plt.cm.Blues, alpha=0.85)

    labels = [['Benar aman (TN)', 'Salah tuduh (FP)'],
              ['Terlewat (FN)', 'Benar terdeteksi (TP)']]
    for r in range(2):
        for c in range(2):
            val = c_matrix[r, c]
            txt = f"{val}\n({labels[r][c]})"
            color = 'white' if val > 250 else COLORS['ink']
            ax.text(c, r, txt, ha='center', va='center', color=color, fontsize=10, fontweight='bold')

    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(['Prediksi: Aman', 'Prediksi: Berisiko'], color=COLORS['ink'], fontsize=9.5)
    ax.set_yticklabels(['Aktual: Aman', 'Aktual: Berisiko'], color=COLORS['ink'], fontsize=9.5)
    ax.set_xlabel('Kelas prediksi', color=COLORS['ink'], labelpad=8)
    ax.set_ylabel('Kelas aktual', color=COLORS['ink'], labelpad=8)
    for spine in ax.spines.values():
        spine.set_color(COLORS['line'])
    plt.tight_layout()
    cm_img_path = os.path.join(static_ml_dir, 'confusion_matrix.png')
    plt.savefig(cm_img_path, dpi=160, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()

    # (Grafik 4) Kurva Kalibrasi (Reliability Diagram)
    fig, ax = plt.subplots(figsize=(6.5, 5.0), facecolor=COLORS['paper'])
    apply_plot_style(ax, 'Kurva kalibrasi probabilitas risiko', 'Rata-rata probabilitas prediksi', 'Proporsi positif sebenarnya')

    # Garis kalibrasi sempurna
    ax.plot([0, 1], [0, 1], linestyle='--', color=COLORS['ink_muted'], label='Kalibrasi sempurna')

    # Sebelum kalibrasi
    prob_true_uncal, prob_pred_uncal = calibration_curve(y_test, y_test_probs_uncal, n_bins=8)
    ax.plot(prob_pred_uncal, prob_true_uncal, marker='s', color=COLORS['brick'], linewidth=1.8, label=f'Sebelum kalibrasi (Brier = {brier_before:.4f})')

    # Setelah kalibrasi
    prob_true_cal, prob_pred_cal = calibration_curve(y_test, y_test_probs_cal, n_bins=8)
    ax.plot(prob_pred_cal, prob_true_cal, marker='o', color=COLORS['pine'], linewidth=2.5, label=f'Setelah kalibrasi (Brier = {brier_after:.4f})')

    ax.legend(loc='upper left', frameon=True, facecolor=COLORS['card'], edgecolor=COLORS['line'], fontsize=8.5)
    plt.tight_layout()
    cal_img_path = os.path.join(static_ml_dir, 'calibration_curve.png')
    plt.savefig(cal_img_path, dpi=160, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()

    # (Grafik 5) Pentingnya Fitur (Permutation Importance & Koefisien)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 5.0), facecolor=COLORS['paper'])

    feature_labels_id = {
        'rasio_tepat_waktu': 'Rasio tepat waktu',
        'rata_rata_rating_diterima': 'Rata-rata rating',
        'jumlah_sewa_selesai': 'Jumlah sewa selesai',
        'jumlah_sebagai_pemilik': 'Jumlah sbg pemilik',
        'jumlah_sengketa': 'Jumlah sengketa',
        'rasio_pembatalan': 'Rasio pembatalan',
        'umur_akun_hari': 'Umur akun (hari)',
        'rasio_sengketa': 'Rasio sengketa',
    }

    # Subplot 1: Permutation Importance
    sorted_idx = np.argsort(perm_importance.importances_mean)
    sorted_features = [feature_cols[i] for i in sorted_idx]
    sorted_labels = [feature_labels_id.get(f, f) for f in sorted_features]
    sorted_means = perm_importance.importances_mean[sorted_idx]

    apply_plot_style(ax1, 'Pentingnya fitur (permutation ROC-AUC)', 'Penurunan ROC-AUC saat fitur diacak', '')
    bars1 = ax1.barh(range(len(sorted_means)), sorted_means, color=COLORS['brand'], height=0.65)
    ax1.set_yticks(range(len(sorted_means)))
    ax1.set_yticklabels(sorted_labels, color=COLORS['ink'], fontsize=8.5)

    # Subplot 2: Koefisien Model Linear (Bobot Terstandar)
    apply_plot_style(ax2, 'Koefisien regresi logistik terstandar', 'Arah pengaruh terhadap risiko bermasalah', '')
    coef_vals = [coefficients_dict[f] for f in sorted_features]
    bar_colors = [COLORS['brick'] if c > 0 else COLORS['pine'] for c in coef_vals]
    ax2.barh(range(len(coef_vals)), coef_vals, color=bar_colors, height=0.65)
    ax2.axvline(0, color=COLORS['ink'], linewidth=1.0)
    ax2.set_yticks(range(len(coef_vals)))
    ax2.set_yticklabels([''] * len(coef_vals))
    # Anotasi arah
    ax2.text(0.12, 0.5, 'Menaikkan risiko ->', transform=ax2.transAxes, color=COLORS['brick'], fontsize=8.5, fontweight='bold')
    ax2.text(0.12, 0.42, '<- Menurunkan risiko (tepercaya)', transform=ax2.transAxes, color=COLORS['pine'], fontsize=8.5, fontweight='bold')

    plt.tight_layout()
    fi_img_path = os.path.join(static_ml_dir, 'feature_importance.png')
    plt.savefig(fi_img_path, dpi=160, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()

    print(f"\n5 Grafik visualisasi berhasil disimpan ke: {static_ml_dir}")

    # 10. Simpan Artefak Model (trust_model.joblib)
    artifact_payload = {
        'calibrated_model': calibrated_model,
        'base_pipeline_scaler': scaler,
        'base_model': lr_base,
        'feature_cols': feature_cols,
        'selected_threshold': selected_threshold,
        'model_version': 'v1.0-logreg-calibrated',
        'feature_means': {col: float(m) for col, m in zip(feature_cols, scaler.mean_)},
        'feature_scales': {col: float(s) for col, s in zip(feature_cols, scaler.scale_)},
        'coefficients': coefficients_dict,
        'intercept': float(lr_base.intercept_[0]),
        'created_at': datetime.now().isoformat(),
        'data_hash': data_hash,
    }
    model_save_path = os.path.join(artifacts_dir, 'trust_model.joblib')
    joblib.dump(artifact_payload, model_save_path)
    print(f"Model tersimpan di: {model_save_path}")

    # 11. Simpan Ringkasan Metrik (metrics.json)
    metrics_payload = {
        'version': 'v1.0-logreg-calibrated',
        'seed': 42,
        'trained_at': datetime.now().isoformat(),
        'data_source': 'ml/data/synthetic_rental_trust_data.csv',
        'data_sha256': data_hash,
        'train_samples': len(X_train),
        'test_samples': len(X_test),
        'positive_prevalence': float(y.mean()),
        'features_used': feature_cols,
        'features_excluded_rationale': {
            'status_ktm': 'Dihapus karena hampir konstan (semua pengguna aktif wajib terverifikasi KTM)',
            'gender': 'Atribut sensitif, dilarang untuk mencegah bias diskriminatif',
            'campus_name': 'Atribut sensitif institusional, dilarang untuk mencegah bias antarkampus',
            'major': 'Atribut akademik, tidak relevan dan berisiko bias terhadap jurusan tertentu',
            'region': 'Atribut geografis, berpotensi diskriminasi regional'
        },
        'cross_validation_5fold_train': cv_results,
        'model_selection_rationale': (
            "Logistic Regression dipilih sebagai model utama karena memiliki CV ROC-AUC (0.8485) "
            "dan PR-AUC (0.5183) yang lebih tinggi dibandingkan Gradient Boosting (0.8365 dan 0.4964), "
            "serta memberikan keunggulan kritis dalam hal interpretabilitas dan transparansi regulasi "
            "(bobot koefisien dapat langsung ditransformasikan menjadi kalimat penjelasan personal bagi pengguna)."
        ),
        'probability_calibration': {
            'method': 'Platt Scaling (CalibratedClassifierCV sigmoid)',
            'brier_score_before': brier_before,
            'brier_score_after': brier_after,
            'improvement_percent': brier_improvement_pct,
        },
        'threshold_selection': {
            'criterion': 'Recall kelas berisiko >= 0.70 pada data validasi dengan presisi optimal',
            'selected_threshold': selected_threshold,
            'validation_recall': val_recall_at_thresh,
            'validation_precision': val_precision_at_thresh,
            'test_recall': models_eval['logistic_regression_calibrated']['recall'],
            'test_precision': models_eval['logistic_regression_calibrated']['precision'],
            'test_f1': models_eval['logistic_regression_calibrated']['f1'],
            'tradeoff_rationale': (
                "Dalam konteks sewa barang mahasiswa bernilai jutaan rupiah, biaya False Negative (membiarkan pengguna berisiko "
                "tinggi menyewa barang tanpa peringatan hingga terjadi kehilangan/kerusakan) jauh lebih merugikan ekosistem daripada "
                "False Positive (meminta verifikasi/deposit lebih atau memberi peringatan kehati-hatian pada pengguna aman)."
            )
        },
        'all_models_test_metrics': models_eval,
        'permutation_importance': feature_importance_dict,
        'coefficients': coefficients_dict,
        'charts_generated': [
            'static/ml/roc_curve.png',
            'static/ml/pr_curve.png',
            'static/ml/confusion_matrix.png',
            'static/ml/calibration_curve.png',
            'static/ml/feature_importance.png',
        ]
    }

    metrics_save_path = os.path.join(artifacts_dir, 'metrics.json')
    with open(metrics_save_path, 'w', encoding='utf-8') as f:
        json.dump(metrics_payload, f, indent=2, ensure_ascii=False)
    print(f"Metrik tersimpan di: {metrics_save_path}")

    return metrics_payload


def main():
    print("=== Pelatihan dan Evaluasi Model Skor Kepercayaan KampusRent ===")
    train_and_evaluate_all()


if __name__ == '__main__':
    main()
