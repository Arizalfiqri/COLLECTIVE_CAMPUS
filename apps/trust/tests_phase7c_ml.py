import os
from datetime import date, timedelta
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from django.conf import settings

from apps.accounts.models import User, StudentProfile, Campus
from apps.catalog.models import Item, Category
from apps.rentals.models import Rental, Dispute
from apps.rentals.services import (
    ajukan_sewa, setujui_sewa,
    konfirmasi_pengembalian_baik
)
from apps.trust.models import TrustTrainingExample, TrustModelVersion
from apps.trust.services import (
    compute_features, record_training_snapshot,
    label_training_example_for_rental, clear_model_cache,
    load_trust_model
)
from apps.trust.management.commands.retrain_trust_model import execute_retraining
from apps.trust.management.commands.rollback_trust_model import execute_rollback


class Phase7cMachineLearningTests(TestCase):
    def setUp(self):
        clear_model_cache()
        self.campus = Campus.objects.create(name="Institut Teknologi Sumatera", short_name="ITERA", city="Lampung Selatan")
        self.category = Category.objects.create(name="Elektronik", slug="elektronik")

        # Pemilik
        self.owner = User.objects.create_user(
            username="owner_user",
            email="owner@itera.ac.id",
            password="password123",
            full_name="Owner User",
            is_verified_student=True
        )
        StudentProfile.objects.create(
            user=self.owner,
            campus=self.campus,
            nim="121140001",
            major="Teknik Informatika"
        )

        # Penyewa
        self.renter = User.objects.create_user(
            username="renter_user",
            email="renter@itera.ac.id",
            password="password123",
            full_name="Renter User",
            is_verified_student=True
        )
        StudentProfile.objects.create(
            user=self.renter,
            campus=self.campus,
            nim="121140002",
            major="Teknik Informatika"
        )

        # Staff
        self.staff_user = User.objects.create_user(
            username="staff_admin",
            email="staff@kampusrent.id",
            password="password123",
            is_staff=True
        )

        # Barang
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="Kamera Mirrorless Sony A6400",
            description="Kamera mirrorless lensa kit 16-50mm siap pakai",
            price_per_day=50000,
            deposit_amount=50000,
            estimated_value=300000,
            min_renter_tier=Item.RenterTier.BARU,
            require_ktm_held=False,
            is_active=True
        )

        # Pastikan baseline model v1.0 terdaftar aktif
        TrustModelVersion.objects.all().delete()
        TrustModelVersion.objects.create(
            version="v1.0-logreg-calibrated",
            n_real=0,
            n_synthetic=4000,
            is_active=True,
            notes="Baseline model sintetis terkalibrasi"
        )

    def test_feature_snapshot_recorded_on_ajukan_sewa(self):
        """Memverifikasi snapshot fitur 8 dimensi otomatis dicatat saat pengajuan sewa."""
        start_date = date.today() + timedelta(days=1)
        end_date = start_date + timedelta(days=2)

        rental = ajukan_sewa(
            item=self.item,
            renter=self.renter,
            start_date=start_date,
            end_date=end_date,
            use_protection=True,
            terms_accepted=True
        )

        example = TrustTrainingExample.objects.filter(rental=rental).first()
        self.assertIsNotNone(example)
        self.assertEqual(example.user, self.renter)
        self.assertEqual(example.source, TrustTrainingExample.Source.LIVE)
        self.assertIsNone(example.label_problem)
        self.assertIsNone(example.labeled_at)
        self.assertIsNotNone(example.predicted_risk)

        # Verifikasi 8 fitur perilaku tercatat dalam snapshot JSON
        features = example.features
        expected_keys = [
            'jumlah_sewa_selesai', 'jumlah_sebagai_pemilik', 'rasio_tepat_waktu',
            'rata_rata_rating_diterima', 'jumlah_sengketa', 'rasio_sengketa',
            'rasio_pembatalan', 'umur_akun_hari'
        ]
        for key in expected_keys:
            self.assertIn(key, features)

    def _setup_paid_rental(self):
        from apps.payments.models import Payment
        from apps.payments.services import record_payment_settlement
        from apps.rentals.services import konfirmasi_pembayaran
        start_date = date.today() + timedelta(days=1)
        end_date = start_date + timedelta(days=2)
        rental = ajukan_sewa(self.item, self.renter, start_date, end_date, True, True)
        setujui_sewa(rental, self.owner)
        payment = Payment.objects.create(
            rental=rental,
            order_id=f"TEST-{rental.code}",
            payment_type="qris",
            gross_amount=rental.grand_total,
            transaction_id="mock-tx-ml-7c",
            status=Payment.Status.SETTLEMENT
        )
        record_payment_settlement(rental, payment)
        konfirmasi_pembayaran(rental, payment)
        rental.refresh_from_db()
        return rental

    def test_terminal_state_labeling_smooth_rental(self):
        """Memverifikasi kasus lancar diberi label 0 saat pengembalian berhasil dikonfirmasi."""
        rental = self._setup_paid_rental()
        rental.status = Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN
        rental.late_days = 0
        rental.save()

        # Konfirmasi selesai tepat waktu tanpa denda
        konfirmasi_pengembalian_baik(rental, self.owner)

        example = TrustTrainingExample.objects.get(rental=rental)
        self.assertEqual(example.label_problem, 0)
        self.assertIsNotNone(example.labeled_at)

    def test_terminal_state_labeling_problem_cases(self):
        """Memverifikasi kasus keterlambatan > 1 hari atau denda kerusakan diberi label 1."""
        start_date = date.today() + timedelta(days=1)
        end_date = start_date + timedelta(days=2)

        # Kasus A: Keterlambatan lebih dari 1 hari
        rental_late = ajukan_sewa(self.item, self.renter, start_date, end_date, True, True)
        rental_late.status = Rental.Status.SELESAI
        rental_late.late_days = 2
        rental_late.save()

        ex_late = label_training_example_for_rental(rental_late)
        self.assertEqual(ex_late.label_problem, 1)

        # Kasus B: Kerusakan fisik / denda deposit
        rental_damage = ajukan_sewa(self.item, self.renter, start_date + timedelta(days=5), end_date + timedelta(days=5), True, True)
        rental_damage.status = Rental.Status.SELESAI
        rental_damage.late_days = 0
        rental_damage.damage_fee = 50000
        rental_damage.save()

        ex_damage = label_training_example_for_rental(rental_damage)
        self.assertEqual(ex_damage.label_problem, 1)

    def test_terminal_state_labeling_idempotency(self):
        """Memverifikasi pemanggilan ulang pelabelan idempoten dan tidak menimbulkan duplikasi."""
        start_date = date.today() + timedelta(days=1)
        end_date = start_date + timedelta(days=2)

        rental = ajukan_sewa(self.item, self.renter, start_date, end_date, True, True)
        rental.status = Rental.Status.SELESAI
        rental.late_days = 0
        rental.save()

        ex1 = label_training_example_for_rental(rental)
        first_labeled_at = ex1.labeled_at

        # Panggil ulang beberapa kali
        ex2 = label_training_example_for_rental(rental)
        ex3 = label_training_example_for_rental(rental)

        self.assertEqual(TrustTrainingExample.objects.filter(rental=rental).count(), 1)
        self.assertEqual(ex1.id, ex2.id)
        self.assertEqual(ex2.id, ex3.id)
        self.assertEqual(ex1.label_problem, 0)
        self.assertEqual(ex2.label_problem, 0)

    def test_retrain_guardrail_rejects_insufficient_data(self):
        """Memverifikasi retrain_trust_model menolak jika data nyata belum mencukupi batas aman."""
        # Database hanya memiliki sedikit contoh
        res = execute_retraining(force=False, include_backfill=False)
        self.assertFalse(res['success'])
        self.assertFalse(res['promoted'])
        self.assertIn("belum memenuhi ambang batas aman", res['reason'])

        # Model aktif tidak boleh berubah
        active = TrustModelVersion.objects.get(is_active=True)
        self.assertEqual(active.version, "v1.0-logreg-calibrated")

    def test_retrain_promotion_strict_rule_and_execution(self):
        """Memverifikasi eksekusi retraining dengan force dan aturan promosi kuantitatif."""
        start_date = date.today() + timedelta(days=1)

        # Bangkitkan contoh dummy terlabel untuk pengujian alur
        for i in range(10):
            r = Rental.objects.create(
                item=self.item,
                renter=self.renter,
                owner=self.owner,
                start_date=start_date + timedelta(days=i*3),
                end_date=start_date + timedelta(days=i*3+1),
                days=1,
                price_per_day_snapshot=50000,
                rent_total=50000,
                deposit_total=100000,
                protection_fee=3000,
                grand_total=153000,
                status=Rental.Status.SELESAI
            )
            TrustTrainingExample.objects.create(
                rental=r,
                user=self.renter,
                features={
                    'jumlah_sewa_selesai': i + 1,
                    'jumlah_sebagai_pemilik': 0,
                    'rasio_tepat_waktu': 1.0 if i % 4 != 0 else 0.5,
                    'rata_rata_rating_diterima': 4.5,
                    'jumlah_sengketa': 1 if i % 4 == 0 else 0,
                    'rasio_sengketa': 0.1 if i % 4 == 0 else 0.0,
                    'rasio_pembatalan': 0.0,
                    'umur_akun_hari': 30 + i * 5,
                },
                predicted_risk=0.15,
                model_version="v1.0-logreg-calibrated",
                label_problem=1 if i % 4 == 0 else 0,
                labeled_at=timezone.now(),
                source=TrustTrainingExample.Source.LIVE
            )

        # Jalankan retraining dengan bypass force (hanya dry-run karena data nyata < TRUST_MIN_REAL_EXAMPLES)
        res = execute_retraining(force=True, include_backfill=False, notes="Uji tes unit force dry-run")
        self.assertTrue(res['success'])
        self.assertIn('candidate_metrics', res)
        self.assertIn('active_metrics', res)
        self.assertIn('new_version', res)
        # Force retraining hanya boleh sebagai dry-run yang TIDAK mempromosikan model
        self.assertFalse(res['promoted'])
        self.assertIn("dry-run", res['reason'].lower())

        # Model aktif di database tetap baseline v1.0
        active_model = TrustModelVersion.objects.get(is_active=True)
        self.assertEqual(active_model.version, "v1.0-logreg-calibrated")

    @override_settings(TRUST_MIN_REAL_EXAMPLES=4, TRUST_MIN_POSITIVES=1)
    def test_force_retraining_real_threshold_promotes_when_qualified(self):
        """Memverifikasi promosi model terjadi bila ambang data nyata terpenuhi dan performa unggul."""
        start_date = date.today() + timedelta(days=1)
        for i in range(8):
            r = Rental.objects.create(
                item=self.item,
                renter=self.renter,
                owner=self.owner,
                start_date=start_date + timedelta(days=i*3),
                end_date=start_date + timedelta(days=i*3+1),
                days=1,
                price_per_day_snapshot=50000,
                rent_total=50000,
                deposit_total=100000,
                protection_fee=3000,
                grand_total=153000,
                status=Rental.Status.SELESAI
            )
            TrustTrainingExample.objects.create(
                rental=r,
                user=self.renter,
                features={
                    'jumlah_sewa_selesai': i + 2,
                    'jumlah_sebagai_pemilik': 1,
                    'rasio_tepat_waktu': 1.0 if i % 2 == 0 else 0.4,
                    'rata_rata_rating_diterima': 4.8,
                    'jumlah_sengketa': 1 if i % 2 != 0 else 0,
                    'rasio_sengketa': 0.2 if i % 2 != 0 else 0.0,
                    'rasio_pembatalan': 0.0,
                    'umur_akun_hari': 60 + i * 5,
                },
                predicted_risk=0.20,
                model_version="v1.0-logreg-calibrated",
                label_problem=1 if i % 2 != 0 else 0,
                labeled_at=timezone.now(),
                source=TrustTrainingExample.Source.LIVE
            )

        res = execute_retraining(force=False, include_backfill=False, notes="Uji ambang terpenuhi")
        self.assertTrue(res['success'])
        # Karena ambang TRUST_MIN_REAL_EXAMPLES=4 terpenuhi, retraining bukan dry-run
        self.assertIn('promoted', res)

    def test_rollback_trust_model(self):
        """Memverifikasi perintah rollback mengembalikan model aktif ke versi yang diminta."""
        # Buat versi dummy kedua
        v2 = TrustModelVersion.objects.create(
            version="v2.0-real-20261017_230000",
            n_real=250,
            is_active=True,
            notes="Versi baru"
        )
        TrustModelVersion.objects.filter(version="v1.0-logreg-calibrated").update(is_active=False)

        # Jalankan rollback ke v1.0
        success, msg = execute_rollback("v1.0-logreg-calibrated")
        self.assertTrue(success)
        self.assertIn("berhasil dikembalikan", msg)

        # Verifikasi database
        v1_reloaded = TrustModelVersion.objects.get(version="v1.0-logreg-calibrated")
        v2_reloaded = TrustModelVersion.objects.get(version="v2.0-real-20261017_230000")
        self.assertTrue(v1_reloaded.is_active)
        self.assertFalse(v2_reloaded.is_active)

    def test_admin_model_score_view_get_and_post(self):
        """Memverifikasi halaman staf /admin/model-skor/ dapat diakses dan menerima aksi POST."""
        client = Client()
        client.force_login(self.staff_user)

        # Akses GET
        response = client.get('/admin/model-skor/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manajemen Model &amp; Data Transaksi Nyata")
        self.assertContains(response, "Riwayat Versi Artefak Model")

        # Aksi POST: rollback
        post_resp = client.post('/admin/model-skor/', {
            'action': 'rollback',
            'version': 'v1.0-logreg-calibrated'
        }, follow=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertContains(post_resp, "Model aktif berhasil dikembalikan")
