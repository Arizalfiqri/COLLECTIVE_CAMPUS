from django.core.management.base import BaseCommand
from ml.train_trust_model import train_and_evaluate_all


class Command(BaseCommand):
    help = "Melatih, mengalibrasi, dan mengevaluasi model skor kepercayaan (Trust Score) KampusRent"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Memulai pelatihan model skor kepercayaan..."))
        try:
            metrics = train_and_evaluate_all()
            self.stdout.write(self.style.SUCCESS(
                f"Model berhasil dilatih dan dievaluasi!\n"
                f"Versi model: {metrics['version']}\n"
                f"ROC-AUC Model Terpilih: {metrics['all_models_test_metrics']['logistic_regression_calibrated']['roc_auc']:.4f}\n"
                f"PR-AUC Model Terpilih: {metrics['all_models_test_metrics']['logistic_regression_calibrated']['pr_auc']:.4f}\n"
                f"Ambang Keputusan: {metrics['threshold_selection']['selected_threshold']:.4f}\n"
                f"Artefak model: ml/artifacts/trust_model.joblib\n"
                f"Ringkasan metrik: ml/artifacts/metrics.json\n"
                f"Visualisasi disimpan di: static/ml/"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Gagal melatih model: {e}"))
            raise e
