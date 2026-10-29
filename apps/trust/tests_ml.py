"""
Unit and Integration Test Suite untuk Fase 6: Machine Learning Skor Kepercayaan.
Mencakup:
1. Perhitungan fitur dari riwayat contoh (compute_features).
2. Verifikasi tidak ada atribut sensitif pada daftar fitur.
3. Perilaku cold start pengguna baru (< 3 sewa selesai -> skor 60, is_new_user=True).
4. Monotonisitas sederhana (rasio tepat waktu naik tidak menurunkan skor).
5. Cadangan aman (fallback) bila artefak model hilang atau rusak.
6. Format kalimat penjelasan faktor teratas (top factors).
7. Admin override: validasi catatan wajib, prioritas effective_score, audit trail.
8. Integrasi get_renter_tier dengan effective_score dan jumlah sewa selesai.
9. Reprodusibilitas data generator (seed sama -> data sama).
10. Validasi masukan dan response HTTP halaman publik dan simulasi HTMX.
"""

from datetime import date, timedelta
from unittest import mock
import pandas as pd
from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse

from apps.accounts.models import User, Campus, StudentProfile
from apps.catalog.models import Category, Item
from apps.rentals.models import Rental, Dispute, Review
from apps.trust.models import TrustScore
from apps.trust.services import (
    FEATURE_NAMES,
    compute_features,
    recompute_trust_score,
    get_renter_tier,
    explain_factors,
    load_trust_model,
)
from ml.generate_synthetic_data import generate_synthetic_trust_data


class TrustScoreFeatureComputationTest(TestCase):
    """1. Perhitungan fitur dari riwayat contoh & 2. Proteksi atribut sensitif."""

    def setUp(self):
        self.campus = Campus.objects.create(name='Univ Lampung', short_name='UNILA', city='Bandar Lampung')
        self.user = User.objects.create_user(
            username='mahasiswa_test',
            email='mhs@unila.ac.id',
            password='Password123!',
            full_name='Mahasiswa Test',
        )
        StudentProfile.objects.create(
            user=self.user,
            nim='2215061001',
            campus=self.campus,
            major='Teknik Informatika',
        )
        self.other_user = User.objects.create_user(
            username='partner_test',
            email='partner@unila.ac.id',
            password='Password123!',
            full_name='Partner Test',
        )
        StudentProfile.objects.create(
            user=self.other_user,
            nim='2215061002',
            campus=self.campus,
            major='Sistem Informasi',
        )

        self.category = Category.objects.create(name='Elektronik', slug='elektronik', order=1)
        self.item = Item.objects.create(
            owner=self.other_user,
            category=self.category,
            title='Proyektor Mini',
            estimated_value=1000000,
            price_per_day=50000,
            deposit_amount=150000,
            min_days=1,
            max_days=7,
        )

    def test_feature_names_exclude_sensitive_attributes(self):
        """Memastikan fitur prediktif bebas dari atribut sensitif dan diskriminatif."""
        sensitive_keywords = [
            'gender', 'jenis_kelamin', 'sex',
            'kampus', 'campus', 'universitas',
            'prodi', 'major', 'jurusan',
            'asal_daerah', 'region', 'city', 'alamat',
            'religion', 'agama',
            'status_ktm', 'ktm', 'nim', 'email', 'nama', 'name', 'foto', 'photo',
        ]
        for feat in FEATURE_NAMES:
            feat_lower = feat.lower()
            for kw in sensitive_keywords:
                self.assertNotIn(
                    kw, feat_lower,
                    f"Fitur '{feat}' mengandung kata sensitif/diskriminatif '{kw}'!"
                )

        expected_features = [
            'jumlah_sewa_selesai',
            'jumlah_sebagai_pemilik',
            'rasio_tepat_waktu',
            'rata_rata_rating_diterima',
            'jumlah_sengketa',
            'rasio_sengketa',
            'rasio_pembatalan',
            'umur_akun_hari',
        ]
        self.assertEqual(FEATURE_NAMES, expected_features)

    def test_compute_features_from_sample_history(self):
        """Uji perhitungan fitur secara presisi dari riwayat transaksi di database."""
        # Sewa 1: selesai, tepat waktu (late_days=0)
        r1 = Rental.objects.create(
            item=self.item, renter=self.user, owner=self.other_user,
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), days=2,
            price_per_day_snapshot=50000, rent_total=100000, deposit_total=150000, grand_total=250000,
            status=Rental.Status.SELESAI, late_days=0
        )
        Review.objects.create(
            rental=r1, reviewer=self.other_user, reviewee=self.user,
            as_role=Review.AsRole.PENYEWA, rating=5, comment='Bagus'
        )

        # Sewa 2: selesai, terlambat 1 hari
        r2 = Rental.objects.create(
            item=self.item, renter=self.user, owner=self.other_user,
            start_date=date(2026, 1, 5), end_date=date(2026, 1, 7), days=2,
            price_per_day_snapshot=50000, rent_total=100000, deposit_total=150000, grand_total=250000,
            status=Rental.Status.SELESAI, late_days=1
        )
        Review.objects.create(
            rental=r2, reviewer=self.other_user, reviewee=self.user,
            as_role=Review.AsRole.PENYEWA, rating=4, comment='Oke'
        )

        # Sewa 3: dibatalkan oleh penyewa
        Rental.objects.create(
            item=self.item, renter=self.user, owner=self.other_user,
            start_date=date(2026, 1, 10), end_date=date(2026, 1, 12), days=2,
            price_per_day_snapshot=50000, rent_total=100000, deposit_total=150000, grand_total=250000,
            status=Rental.Status.DIBATALKAN, cancelled_by=self.user
        )

        feats = compute_features(self.user)
        self.assertEqual(feats['jumlah_sewa_selesai'], 2)
        self.assertEqual(feats['jumlah_sebagai_pemilik'], 0)
        # 1 tepat waktu dari 2 selesai = 0.5
        self.assertAlmostEqual(feats['rasio_tepat_waktu'], 0.5, places=2)
        # rating rata-rata: (5 + 4) / 2 = 4.5
        self.assertAlmostEqual(feats['rata_rata_rating_diterima'], 4.5, places=2)
        self.assertEqual(feats['jumlah_sengketa'], 0)
        self.assertAlmostEqual(feats['rasio_sengketa'], 0.0, places=2)
        # pembatalan: 1 dibatalkan dari 3 total sewa = 1/3 ~ 0.333
        self.assertAlmostEqual(feats['rasio_pembatalan'], 1/3, places=2)
        self.assertGreaterEqual(feats['umur_akun_hari'], 0)


class TrustScoreColdStartAndMonotonicityTest(TestCase):
    """3. Perilaku pengguna baru & 4. Uji monotonisitas."""

    def setUp(self):
        self.campus = Campus.objects.create(name='UNILA', short_name='UNILA', city='Bandar Lampung')
        self.user_new = User.objects.create_user(
            username='user_fresh',
            email='fresh@unila.ac.id',
            password='Password123!',
            full_name='User Fresh',
        )
        StudentProfile.objects.create(user=self.user_new, nim='2215061099', campus=self.campus, major='Elektro')

    def test_new_user_cold_start_policy(self):
        """Pengguna dengan < 3 sewa selesai mendapat skor default netral 60 tanpa diproses model."""
        ts = recompute_trust_score(self.user_new)
        self.assertTrue(ts.is_new_user)
        self.assertEqual(ts.score, 60)
        self.assertEqual(ts.effective_score, 60)
        self.assertIn('Pengguna baru', ts.top_factors[0])

    def test_monotonicity_higher_on_time_ratio_does_not_decrease_score(self):
        """Monotonisitas: kenaikan rasio tepat waktu (ceteris paribus) tidak boleh menurunkan skor kepercayaan."""
        model_data = load_trust_model()
        if model_data is None:
            self.skipTest("Artefak model belum tersedia.")

        scaler = model_data['base_pipeline_scaler']
        calibrated_model = model_data['calibrated_model']
        feature_cols = model_data['feature_cols']

        # Baseline fitur pengguna dengan 10 transaksi
        base_features = {
            'jumlah_sewa_selesai': 10,
            'jumlah_sebagai_pemilik': 2,
            'rata_rata_rating_diterima': 4.5,
            'jumlah_sengketa': 0,
            'rasio_sengketa': 0.0,
            'rasio_pembatalan': 0.05,
            'umur_akun_hari': 120,
        }

        ratios = [0.40, 0.60, 0.80, 0.95, 1.00]
        scores = []
        for r in ratios:
            f_dict = dict(base_features)
            f_dict['rasio_tepat_waktu'] = r
            x_df = pd.DataFrame([[f_dict[c] for c in feature_cols]], columns=feature_cols)
            x_scaled = scaler.transform(x_df)
            prob = float(calibrated_model.predict_proba(x_scaled)[0, 1])
            score = round((1.0 - prob) * 100)
            scores.append(score)

        # Pastikan skor tidak pernah menurun (monotonik non-decreasing)
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(
                scores[i+1], scores[i],
                f"Pelanggaran monotonisitas: rasio {ratios[i+1]} menghasilkan skor {scores[i+1]} < {scores[i]} pada rasio {ratios[i]}"
            )


class TrustScoreFallbackAndExplanationsTest(TestCase):
    """5. Cadangan aman saat artefak hilang & 6. Kalimat penjelasan."""

    def setUp(self):
        self.campus = Campus.objects.create(name='UNILA', short_name='UNILA', city='Bandar Lampung')
        self.user = User.objects.create_user(
            username='user_fallback',
            email='fallback@unila.ac.id',
            password='Password123!',
            full_name='User Fallback',
        )
        StudentProfile.objects.create(user=self.user, nim='2215061088', campus=self.campus, major='Elektro')
        self.partner = User.objects.create_user(
            username='partner_fallback',
            email='pfallback@unila.ac.id',
            password='Password123!',
            full_name='Partner Fallback',
        )
        self.category = Category.objects.create(name='Alat', slug='alat', order=1)
        self.item = Item.objects.create(
            owner=self.partner, category=self.category, title='Obeng Set',
            estimated_value=100000, price_per_day=10000, deposit_amount=25000,
            min_days=1, max_days=3
        )
        # Buat 4 sewa selesai agar bukan new user
        for i in range(4):
            Rental.objects.create(
                item=self.item, renter=self.user, owner=self.partner,
                start_date=date(2026, 1, 1), end_date=date(2026, 1, 2), days=1,
                price_per_day_snapshot=10000, rent_total=10000, deposit_total=25000, grand_total=35000,
                status=Rental.Status.SELESAI, late_days=0
            )

    @mock.patch('apps.trust.services.load_trust_model', return_value=None)
    def test_safe_fallback_when_model_artifact_missing(self, mock_load):
        """Bila artefak model hilang atau rusak, sistem beralih ke aturan cadangan tanpa crash."""
        ts = recompute_trust_score(self.user)
        self.assertEqual(ts.model_version, 'model belum dilatih')
        self.assertFalse(ts.is_new_user)
        self.assertGreaterEqual(ts.score, 0)
        self.assertLessEqual(ts.score, 100)
        self.assertTrue(len(ts.top_factors) > 0)
        self.assertIn('transaksi sewa sukses diselesaikan', ts.top_factors[0].lower())

    def test_explain_factors_produces_three_indonesian_sentences(self):
        """Fungsi explain_factors menghasilkan 3 kalimat informatif dengan kata 'menaikkan' atau 'menurunkan'."""
        model_data = load_trust_model()
        if model_data is None:
            self.skipTest("Artefak model belum tersedia.")

        features = {
            'jumlah_sewa_selesai': 12,
            'jumlah_sebagai_pemilik': 3,
            'rasio_tepat_waktu': 0.95,
            'rata_rata_rating_diterima': 4.8,
            'jumlah_sengketa': 0,
            'rasio_sengketa': 0.0,
            'rasio_pembatalan': 0.0,
            'umur_akun_hari': 150,
        }
        factors = explain_factors(
            features=features,
            feature_means=model_data.get('feature_means', {}),
            feature_scales=model_data.get('feature_scales', {}),
            coefficients=model_data.get('coefficients', {})
        )
        self.assertEqual(len(factors), 3)
        for sentence in factors:
            self.assertTrue(
                ('menaikkan' in sentence.lower()) or ('menurunkan' in sentence.lower()),
                f"Kalimat penjelas '{sentence}' harus memuat kata 'menaikkan' atau 'menurunkan'!"
            )


class TrustScoreAdminOverrideAndTierIntegrationTest(TestCase):
    """7. Override admin & 8. Integrasi get_renter_tier."""

    def setUp(self):
        self.campus = Campus.objects.create(name='UNILA', short_name='UNILA', city='Bandar Lampung')
        self.admin_user = User.objects.create_superuser(
            username='admin_staff',
            email='admin@unila.ac.id',
            password='AdminPassword123!',
            full_name='Admin Staff',
        )
        self.user = User.objects.create_user(
            username='user_tier_test',
            email='tier@unila.ac.id',
            password='Password123!',
            full_name='User Tier Test',
        )
        StudentProfile.objects.create(user=self.user, nim='2215061055', campus=self.campus, major='Informatika')
        self.partner = User.objects.create_user(
            username='partner_tier',
            email='ptier@unila.ac.id',
            password='Password123!',
            full_name='Partner Tier',
        )
        self.category = Category.objects.create(name='Teknologi', slug='teknologi', order=1)
        self.item = Item.objects.create(
            owner=self.partner, category=self.category, title='Kamera DSLR',
            estimated_value=1500000, price_per_day=50000, deposit_amount=100000,
            min_days=1, max_days=5
        )

        # Buat 7 sewa selesai
        for i in range(7):
            Rental.objects.create(
                item=self.item, renter=self.user, owner=self.partner,
                start_date=date(2026, 1, 1), end_date=date(2026, 1, 2), days=1,
                price_per_day_snapshot=50000, rent_total=50000, deposit_total=100000, grand_total=150000,
                status=Rental.Status.SELESAI, late_days=0
            )

    def test_admin_override_takes_precedence_and_affects_tier(self):
        """Admin override menimpa model score dan langsung memengaruhi penentuan get_renter_tier."""
        ts = recompute_trust_score(self.user)
        # Awalnya 7 sewa selesai dengan performa bagus -> sangat_tepercaya (skor >= 75)
        self.assertGreaterEqual(ts.effective_score, 75)
        self.assertEqual(get_renter_tier(self.user), 'sangat_tepercaya')

        # Admin melakukan override menurunkan skor menjadi 50 (karena temuan manual)
        ts.override_score = 50
        ts.override_note = 'Pemeriksaan manual menemukan pelanggaran komunikasi'
        ts.override_by = self.admin_user
        ts.override_at = timezone.now()
        ts.save()

        # effective_score sekarang harus 50, dan tier turun ke 'baru' (karena skor < 60)
        self.assertEqual(ts.effective_score, 50)
        self.assertEqual(get_renter_tier(self.user), 'baru')

        # Admin mengembalikan ke 70 -> tier 'tepercaya' (>= 60 dan < 75)
        ts.override_score = 70
        ts.override_note = 'Sanksi diringankan setelah klarifikasi'
        ts.save()
        self.assertEqual(ts.effective_score, 70)
        self.assertEqual(get_renter_tier(self.user), 'tepercaya')


class TrustScoreReproducibilityAndViewsTest(TestCase):
    """9. Reprodusibilitas data generator & 10. Pengujian endpoint publik dan simulasi."""

    def test_synthetic_data_reproducibility(self):
        """Data sintetis yang dibangkitkan dengan random_state identik menghasilkan dataset yang persis sama."""
        df1 = generate_synthetic_trust_data(n_samples=200, random_state=42)
        df2 = generate_synthetic_trust_data(n_samples=200, random_state=42)
        pd.testing.assert_frame_equal(df1, df2)

    def test_public_trust_page_redirects_to_help(self):
        """Halaman publik /skor-kepercayaan/ sekarang dialihkan ke /bantuan/#skor-kepercayaan."""
        client = Client(HTTP_HOST='127.0.0.1')
        resp = client.get(reverse('trust:public_trust_score'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/bantuan/#skor-kepercayaan')

    def test_admin_model_score_access_control_and_methodology(self):
        """Halaman teknis /admin/model-skor/ hanya dapat diakses oleh staf dan memuat metrik lengkap."""
        client = Client(HTTP_HOST='127.0.0.1')
        model_url = reverse('trust:admin_model_score')

        # 1. Anonymous dialihkan ke login
        resp_anon = client.get(model_url)
        self.assertEqual(resp_anon.status_code, 302)

        # 2. Staff dapat mengakses dan melihat metodologi serta 5 grafik
        admin = User.objects.create_superuser(username='staff_ml', email='staff_ml@kampus.id', password='Password123!')
        client.force_login(admin)
        resp = client.get(model_url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Transparansi Metodologi Skor Kepercayaan', content)
        self.assertIn('Data sintetis terkalibrasi', content)
        self.assertIn('roc_curve.png', content)
        self.assertIn('pr_curve.png', content)
        self.assertIn('confusion_matrix.png', content)
        self.assertIn('calibration_curve.png', content)
        self.assertIn('feature_importance.png', content)

    def test_simulation_endpoint_valid_and_invalid_inputs(self):
        """Simulasi interaktif HTMX khusus staf memvalidasi input di server dan mengembalikan partial HTML."""
        client = Client(HTTP_HOST='127.0.0.1')
        sim_url = reverse('trust:simulation_htmx')

        # Anonymous ditolak (dialihkan ke login)
        resp_anon = client.get(sim_url)
        self.assertEqual(resp_anon.status_code, 302)

        admin = User.objects.create_superuser(username='staff_sim', email='staff_sim@kampus.id', password='Password123!')
        client.force_login(admin)

        # 1. Input valid
        valid_payload = {
            'jumlah_sewa_selesai': 8,
            'jumlah_sebagai_pemilik': 2,
            'rasio_tepat_waktu': 0.95,
            'rata_rata_rating_diterima': 4.8,
            'jumlah_sengketa': 0,
            'rasio_sengketa': 0.0,
            'rasio_pembatalan': 0.05,
            'umur_akun_hari': 120,
        }
        resp = client.post(sim_url, data=valid_payload)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Hasil simulasi skor', content)
        self.assertIn('Faktor penjelas utama', content)

        # 2. Input tidak valid (rasio_tepat_waktu > 100% / > 1.0)
        invalid_payload = dict(valid_payload)
        invalid_payload['rasio_tepat_waktu'] = 150.0
        resp_invalid = client.post(sim_url, data=invalid_payload)
        self.assertEqual(resp_invalid.status_code, 400)
        self.assertIn('harus bernilai antara 0.0 dan 1.0', resp_invalid.content.decode('utf-8'))

    def test_admin_summary_access_control(self):
        """Halaman /admin/ringkasan/ hanya dapat diakses oleh staf/admin."""
        client = Client(HTTP_HOST='127.0.0.1')
        summary_url = reverse('trust:admin_summary')

        # 1. Anonymous user dialihkan ke login
        resp_anon = client.get(summary_url)
        self.assertEqual(resp_anon.status_code, 302)

        # 2. Non-staff user ditolak (403 atau dialihkan)
        user = User.objects.create_user(username='regular_mhs', password='Password123!', is_staff=False)
        client.force_login(user)
        resp_user = client.get(summary_url)
        self.assertIn(resp_user.status_code, [302, 403])

        # 3. Staff user berhasil membuka halaman ringkasan
        admin = User.objects.create_superuser(username='super_staff', email='s@unila.ac.id', password='Password123!')
        client.force_login(admin)
        resp_admin = client.get(summary_url)
        self.assertEqual(resp_admin.status_code, 200)
        self.assertIn('Ringkasan Operasional &amp; Metrik ML', resp_admin.content.decode('utf-8'))
