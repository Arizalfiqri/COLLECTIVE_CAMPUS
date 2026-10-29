import os
import json
import logging
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
    precision_score, recall_score, f1_score, accuracy_score
)

from apps.trust.models import TrustTrainingExample, TrustModelVersion
from apps.trust.services import FEATURE_NAMES, load_trust_model, clear_model_cache

logger = logging.getLogger(__name__)


def evaluate_model_on_data(calibrated_model, scaler, feature_cols, X_df, y_array):
    """Mengevaluasi model pada dataframe fitur dan label biner."""
    X_scaled = scaler.transform(X_df[feature_cols])
    probs = calibrated_model.predict_proba(X_scaled)[:, 1]
    preds = (probs >= 0.5).astype(int)

    # Antisipasi edge-case jika label hanya 1 kelas pada set kecil
    has_both_classes = len(np.unique(y_array)) > 1
    pr_auc = float(average_precision_score(y_array, probs)) if has_both_classes else float(np.mean(y_array))
    roc_auc = float(roc_auc_score(y_array, probs)) if has_both_classes else 0.5
    brier = float(brier_score_loss(y_array, probs))

    prec = float(precision_score(y_array, preds, zero_division=0))
    rec = float(recall_score(y_array, preds, zero_division=0))
    f1 = float(f1_score(y_array, preds, zero_division=0))
    acc = float(accuracy_score(y_array, preds))

    return {
        'pr_auc': round(pr_auc, 4),
        'roc_auc': round(roc_auc, 4),
        'brier_score': round(brier, 4),
        'precision': round(prec, 4),
        'recall': round(rec, 4),
        'f1': round(f1, 4),
        'accuracy': round(acc, 4),
    }


def execute_retraining(force=False, include_backfill=False, dry_run=False, notes='', user=None):
    """
    Eksekutor inti retraining model kepercayaan dari data nyata dengan guardrail ketat.
    Mengembalikan dictionary hasil evaluasi dan status promosi.
    """
    min_real_examples = getattr(settings, 'TRUST_MIN_REAL_EXAMPLES', 200)
    min_positives = getattr(settings, 'TRUST_MIN_POSITIVES', 20)

    # 1. Kueri dataset berlabel
    qs = TrustTrainingExample.objects.filter(label_problem__isnull=False)
    if not include_backfill:
        qs = qs.filter(source=TrustTrainingExample.Source.LIVE)

    total_count = qs.count()
    positive_count = qs.filter(label_problem=1).count()

    # 2. Guardrail kecukupan data
    if not force:
        if total_count < min_real_examples or positive_count < min_positives:
            reason = (
                f"Data belum memenuhi ambang batas aman: {total_count}/{min_real_examples} data nyata, "
                f"{positive_count}/{min_positives} kasus bermasalah."
            )
            return {
                'success': False,
                'promoted': False,
                'reason': reason,
                'total_count': total_count,
                'positive_count': positive_count,
            }

    if total_count < 4 or positive_count < 1:
        return {
            'success': False,
            'promoted': False,
            'reason': f"Data terlalu sedikit untuk proses latih & validasi ({total_count} data, {positive_count} positif).",
            'total_count': total_count,
            'positive_count': positive_count,
        }

    # 3. Time-based split: 80% data lama untuk train, 20% data terbaru untuk validasi
    examples = list(qs.order_by('created_at'))
    split_idx = max(2, int(len(examples) * 0.8))
    train_ex = examples[:split_idx]
    val_ex = examples[split_idx:]
    if not val_ex:
        # Jika data pas-pasan, ambil minimal 1 untuk validasi
        train_ex = examples[:-1]
        val_ex = examples[-1:]

    train_data = []
    for ex in train_ex:
        row = {col: float(ex.features.get(col, 0.0)) for col in FEATURE_NAMES}
        row['target'] = ex.label_problem
        train_data.append(row)

    val_data = []
    for ex in val_ex:
        row = {col: float(ex.features.get(col, 0.0)) for col in FEATURE_NAMES}
        row['target'] = ex.label_problem
        val_data.append(row)

    df_train = pd.DataFrame(train_data)
    df_val = pd.DataFrame(val_data)

    X_train = df_train[FEATURE_NAMES]
    y_train = df_train['target'].to_numpy()
    X_val = df_val[FEATURE_NAMES]
    y_val = df_val['target'].to_numpy()

    # 4. Latih kandidat Logistic Regression terkalibrasi
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)

    # Penentuan CV fold untuk kalibrasi
    n_pos_train = int(np.sum(y_train == 1))
    n_neg_train = int(np.sum(y_train == 0))
    cv_splits = min(5, max(2, min(n_pos_train, n_neg_train))) if (n_pos_train >= 2 and n_neg_train >= 2) else 2

    lr_base = LogisticRegression(class_weight='balanced', random_state=42, max_iter=1000)
    try:
        if cv_splits >= 2 and min(n_pos_train, n_neg_train) >= cv_splits:
            calibrated_model = CalibratedClassifierCV(estimator=lr_base, method='sigmoid', cv=cv_splits)
            calibrated_model.fit(X_train_scaled, y_train)
        else:
            # Fallback jika fold tidak mencukupi untuk split bertingkat
            lr_base.fit(X_train_scaled, y_train)
            calibrated_model = CalibratedClassifierCV(estimator=lr_base, method='sigmoid', cv='prefit')
            calibrated_model.fit(X_train_scaled, y_train)
    except Exception as e:
        logger.warning(f"Kalibrasi CV gagal ({e}), melatih regresi logistik dasar sebagai estimator.")
        lr_base.fit(X_train_scaled, y_train)
        calibrated_model = CalibratedClassifierCV(estimator=lr_base, method='sigmoid', cv='prefit')
        calibrated_model.fit(X_train_scaled, y_train)

    # Pastikan base model juga di-fit untuk koefisien
    try:
        lr_base.fit(X_train_scaled, y_train)
        raw_coefs = lr_base.coef_[0]
        coefficients_dict = {col: float(coef) for col, coef in zip(FEATURE_NAMES, raw_coefs)}
    except Exception:
        coefficients_dict = {}

    cand_eval = evaluate_model_on_data(calibrated_model, scaler, FEATURE_NAMES, df_val, y_val)

    # 5. Evaluasi model aktif pada set validasi yang sama
    active_eval = None
    active_model = load_trust_model()
    active_ver_obj = TrustModelVersion.objects.filter(is_active=True).first()
    active_ver_str = active_ver_obj.version if active_ver_obj else 'baseline'

    if active_model is not None:
        try:
            act_scaler = active_model['base_pipeline_scaler']
            act_cal = active_model['calibrated_model']
            act_cols = active_model.get('feature_cols', FEATURE_NAMES)
            active_eval = evaluate_model_on_data(act_cal, act_scaler, act_cols, df_val, y_val)
        except Exception as e:
            logger.warning(f"Evaluasi model aktif gagal: {e}")

    if active_eval is None:
        # Prevalensi dasar sebagai baseline jika model aktif belum pernah dievaluasi
        base_prev = float(np.mean(y_val))
        active_eval = {
            'pr_auc': round(base_prev, 4),
            'roc_auc': 0.5000,
            'brier_score': 0.2500,
            'precision': 0.0,
            'recall': 0.0,
            'f1': 0.0,
            'accuracy': round(float(np.mean(y_val == 0)), 4),
        }

    # 6. Aturan Promosi Ketat: PR-AUC naik >= 0.01 dan Brier score tidak memburuk
    pr_auc_gain = round(cand_eval['pr_auc'] - active_eval['pr_auc'], 4)
    brier_diff = round(cand_eval['brier_score'] - active_eval['brier_score'], 4)

    meets_threshold = (total_count >= min_real_examples and positive_count >= min_positives)
    meets_gain_and_brier = (pr_auc_gain >= 0.01) and (brier_diff <= 0.001)

    # Promosi model resmi HANYA boleh terjadi bila ambang data nyata terpenuhi
    # "Force retraining" hanya boleh sebagai dry-run / evaluasi yang TIDAK mempromosikan model
    is_promoted = bool(meets_threshold and meets_gain_and_brier and not dry_run)

    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    new_version = f"v{TrustModelVersion.objects.count() + 1}.0-real-{timestamp_str}"

    if force and not meets_threshold:
        decision_reason = (
            f"Force retraining dieksekusi sebagai dry-run evaluasi. Model TIDAK dipromosikan karena belum memenuhi "
            f"ambang batas data nyata ({total_count}/{min_real_examples} data, {positive_count}/{min_positives} kasus bermasalah). "
            f"Metrik kandidat: PR-AUC={cand_eval['pr_auc']} (delta {pr_auc_gain:+.4f}), Brier={cand_eval['brier_score']} (delta {brier_diff:+.4f})."
        )
    elif dry_run:
        decision_reason = (
            f"Mode dry-run aktif. Model tidak dipromosikan. "
            f"PR-AUC kandidat: {cand_eval['pr_auc']} vs aktif: {active_eval['pr_auc']} (delta: {pr_auc_gain:+.4f}). "
            f"Brier kandidat: {cand_eval['brier_score']} vs aktif: {active_eval['brier_score']} (delta: {brier_diff:+.4f})."
        )
    else:
        decision_reason = (
            f"Kandidat {'dipromosikan' if is_promoted else 'tidak dipromosikan'}. "
            f"PR-AUC kandidat: {cand_eval['pr_auc']} vs aktif: {active_eval['pr_auc']} (delta: {pr_auc_gain:+.4f}, min: +0.0100). "
            f"Brier kandidat: {cand_eval['brier_score']} vs aktif: {active_eval['brier_score']} (delta: {brier_diff:+.4f}, max: +0.0010)."
        )

    if not dry_run:
        # Buat folder artefak berversi jika dipromosikan
        version_dir = os.path.join(settings.BASE_DIR, 'ml', 'artifacts', 'versions', new_version)
        os.makedirs(version_dir, exist_ok=True)

        artifact_payload = {
            'calibrated_model': calibrated_model,
            'base_pipeline_scaler': scaler,
            'base_model': lr_base,
            'feature_cols': FEATURE_NAMES,
            'selected_threshold': 0.35,
            'model_version': new_version,
            'feature_means': {col: float(m) for col, m in zip(FEATURE_NAMES, scaler.mean_)},
            'feature_scales': {col: float(s) for col, s in zip(FEATURE_NAMES, scaler.scale_)},
            'coefficients': coefficients_dict,
            'trained_at': timezone.now().isoformat(),
            'training_examples_count': len(train_ex),
            'validation_examples_count': len(val_ex),
        }
        joblib.dump(artifact_payload, os.path.join(version_dir, 'trust_model.joblib'))

        metrics_data = {
            'version': new_version,
            'trained_at': timezone.now().isoformat(),
            'candidate_metrics': cand_eval,
            'active_metrics': active_eval,
            'pr_auc_gain': pr_auc_gain,
            'brier_diff': brier_diff,
            'promoted': is_promoted,
            'decision_reason': decision_reason,
        }
        with open(os.path.join(version_dir, 'metrics.json'), 'w', encoding='utf-8') as f:
            json.dump(metrics_data, f, indent=2)

        if is_promoted:
            # Nonaktifkan model lama & aktifkan model baru
            TrustModelVersion.objects.filter(is_active=True).update(is_active=False)
            TrustModelVersion.objects.create(
                version=new_version,
                n_real=total_count,
                n_synthetic=0,
                metrics={
                    'candidate': cand_eval,
                    'active_baseline': active_eval,
                    'pr_auc_gain': pr_auc_gain,
                    'brier_diff': brier_diff,
                },
                is_active=True,
                notes=(notes or '') + f" [Dipromosikan: {decision_reason}]"
            )
            clear_model_cache()
            logger.info(f"Model baru {new_version} resmi dipromosikan sebagai model aktif.")
        else:
            TrustModelVersion.objects.create(
                version=new_version,
                n_real=total_count,
                n_synthetic=0,
                metrics={
                    'candidate': cand_eval,
                    'active_baseline': active_eval,
                    'pr_auc_gain': pr_auc_gain,
                    'brier_diff': brier_diff,
                },
                is_active=False,
                notes=(notes or '') + f" [Ditolak promosi: {decision_reason}]"
            )

    return {
        'success': True,
        'promoted': is_promoted,
        'new_version': new_version,
        'active_version': active_ver_str,
        'total_count': total_count,
        'positive_count': positive_count,
        'train_count': len(train_ex),
        'val_count': len(val_ex),
        'candidate_metrics': cand_eval,
        'active_metrics': active_eval,
        'pr_auc_gain': pr_auc_gain,
        'brier_diff': brier_diff,
        'reason': decision_reason,
    }


class Command(BaseCommand):
    help = "Melatih ulang model skor kepercayaan dari data nyata dengan guardrail ketat"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Abaikan guardrail ambang batas data minimal (hanya untuk pengujian atau override darurat)'
        )
        parser.add_argument(
            '--include-backfill', action='store_true',
            help='Sertakan data backfill lama dalam proses retraining'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Jalankan simulasi tanpa menyimpan artefak atau mengubah status model di database'
        )
        parser.add_argument(
            '--notes', type=str, default='',
            help='Catatan tambahan mengenai pemicu atau alasan retraining'
        )

    def handle(self, *args, **options):
        force = options['force']
        include_backfill = options['include_backfill']
        dry_run = options['dry_run']
        notes = options['notes']

        self.stdout.write(self.style.NOTICE("Memulai evaluasi continuous learning model skor kepercayaan..."))

        result = execute_retraining(
            force=force,
            include_backfill=include_backfill,
            dry_run=dry_run,
            notes=notes
        )

        if not result['success']:
            self.stdout.write(self.style.WARNING(f"\n[RETRAINING DIBATALKAN] {result['reason']}"))
            return

        self.stdout.write("\nRingkasan Evaluasi Retraining:")
        self.stdout.write(f"  Total Data Nyata   : {result['total_count']} (Kasus Bermasalah: {result['positive_count']})")
        self.stdout.write(f"  Time Split         : Latih {result['train_count']} | Validasi {result['val_count']}")
        self.stdout.write(f"  PR-AUC Kandidat    : {result['candidate_metrics']['pr_auc']:.4f} (Aktif: {result['active_metrics']['pr_auc']:.4f}, Delta: {result['pr_auc_gain']:+.4f})")
        self.stdout.write(f"  Brier Score        : {result['candidate_metrics']['brier_score']:.4f} (Aktif: {result['active_metrics']['brier_score']:.4f}, Delta: {result['brier_diff']:+.4f})")
        self.stdout.write(f"  Status Promosi     : {'DIPROMOSIKAN' if result['promoted'] else 'TIDAK DIPROMOSIKAN'}")
        self.stdout.write(f"  Keterangan         : {result['reason']}")

        if result['promoted']:
            self.stdout.write(self.style.SUCCESS(f"\nModel versi '{result['new_version']}' kini aktif menggantikan '{result['active_version']}'."))
        else:
            self.stdout.write(self.style.NOTICE(f"\nModel aktif '{result['active_version']}' tetap dipertahankan."))
