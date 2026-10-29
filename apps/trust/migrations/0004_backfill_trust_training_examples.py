from django.db import migrations
from django.utils import timezone
import json
import os


def backfill_training_examples_and_version(apps, schema_editor):
    Rental = apps.get_model('rentals', 'Rental')
    TrustTrainingExample = apps.get_model('trust', 'TrustTrainingExample')
    TrustModelVersion = apps.get_model('trust', 'TrustModelVersion')

    # 1. Catat versi model aktif awal jika belum ada
    from django.conf import settings
    base_dir = settings.BASE_DIR
    metrics_path = os.path.join(base_dir, 'ml', 'artifacts', 'metrics.json')
    initial_metrics = {}
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, 'r', encoding='utf-8') as f:
                initial_metrics = json.load(f)
        except Exception:
            pass

    version_name = initial_metrics.get('version', 'v1.0-logreg-calibrated')
    if not TrustModelVersion.objects.filter(version=version_name).exists():
        TrustModelVersion.objects.create(
            version=version_name,
            n_real=0,
            n_synthetic=initial_metrics.get('train_samples', 3200) + initial_metrics.get('test_samples', 800),
            metrics=initial_metrics,
            is_active=True,
            notes="Versi dasar terlatih pada dataset sintetis awal terkalibrasi."
        )

    # 2. Backfill contoh pelatihan dari sewa lama yang telah mencapai status terminal
    terminal_rentals = Rental.objects.filter(
        status__in=['selesai', 'dibatalkan']
    ).select_related('renter', 'owner', 'item')

    backfill_count = 0
    problem_count = 0

    from apps.trust.services import compute_features

    for rental in terminal_rentals:
        if TrustTrainingExample.objects.filter(rental=rental).exists():
            continue

        # Hitung fitur penyewa
        features = compute_features(rental.renter)

        # Aturan pelabelan:
        # label_problem = 1 bila terlambat > 1 hari, ada potongan kerusakan, sengketa, atau tidak dikembalikan
        is_late_over_1_day = (rental.late_days > 1)
        has_damage = (rental.damage_fee > 0)
        has_dispute = hasattr(rental, 'dispute') and rental.dispute is not None
        is_non_return = False
        if has_dispute and getattr(rental.dispute, 'reason', '') == 'barang_tidak_dikembalikan':
            is_non_return = True

        if is_late_over_1_day or has_damage or has_dispute or is_non_return:
            label_problem = 1
            problem_count += 1
        else:
            label_problem = 0

        labeled_time = rental.status_changed_at or rental.updated_at or timezone.now()

        TrustTrainingExample.objects.create(
            rental=rental,
            user=rental.renter,
            features=features,
            predicted_risk=None,
            model_version=version_name,
            label_problem=label_problem,
            labeled_at=labeled_time,
            source='backfill'
        )
        backfill_count += 1

    print(f"\n=== [MIGRASI ML DATA NYATA] BACKFILL SELESAI ===")
    print(f"Total contoh pelatihan dibackfill (source=backfill): {backfill_count}")
    print(f"Kasus bermasalah (label_problem=1): {problem_count}")
    print(f"Versi model aktif: {version_name}")
    print("================================================\n")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('trust', '0003_trustmodelversion_trusttrainingexample'),
        ('rentals', '0004_add_wallet_and_withdrawals'),
    ]

    operations = [
        migrations.RunPython(backfill_training_examples_and_version, noop),
    ]
