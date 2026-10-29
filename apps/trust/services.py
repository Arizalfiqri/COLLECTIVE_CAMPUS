import os
import logging
import joblib
import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)

# Cache modul untuk lazy loading model ML
_MODEL_CACHE = None

SENSITIVE_ATTRIBUTES = [
    'gender', 'jenis_kelamin', 'campus', 'campus_name',
    'major', 'prodi', 'jurusan', 'origin', 'asal_daerah',
    'address', 'alamat', 'religion', 'agama'
]

FEATURE_NAMES = [
    'jumlah_sewa_selesai',
    'jumlah_sebagai_pemilik',
    'rasio_tepat_waktu',
    'rata_rata_rating_diterima',
    'jumlah_sengketa',
    'rasio_sengketa',
    'rasio_pembatalan',
    'umur_akun_hari',
]

TIER_RANK = {
    'baru': 1,
    'tepercaya': 2,
    'sangat_tepercaya': 3,
}

TIER_LABELS = {
    'baru': 'Penyewa Baru',
    'tepercaya': 'Penyewa Tepercaya',
    'sangat_tepercaya': 'Penyewa Sangat Tepercaya',
}


def parse_trust_tiers():
    """
    Mengurai konfigurasi TRUST_TIERS dari settings.py.
    Format raw: 'baru:750000:15,tepercaya:1500000:10,sangat_tepercaya:3000000:10'
    """
    raw = getattr(settings, 'TRUST_TIERS_RAW', 'baru:750000:15,tepercaya:1500000:10,sangat_tepercaya:3000000:10')
    tiers = {}
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            name, max_val, dep_pct = part.split(':')
            val = int(max_val.strip())
            tiers[name.strip()] = {
                'name': name.strip(),
                'label': TIER_LABELS.get(name.strip(), name.strip().replace('_', ' ').title()),
                'max_item_value': val,
                'max_value': val,
                'deposit_percent': int(dep_pct.strip()),
            }
        except Exception as e:
            logger.warning(f"Gagal parse trust tier '{part}': {e}")

    if not tiers:
        tiers = {
            'baru': {'name': 'baru', 'label': 'Penyewa Baru', 'max_item_value': 750000, 'max_value': 750000, 'deposit_percent': 15},
            'tepercaya': {'name': 'tepercaya', 'label': 'Penyewa Tepercaya', 'max_item_value': 1500000, 'max_value': 1500000, 'deposit_percent': 10},
            'sangat_tepercaya': {'name': 'sangat_tepercaya', 'label': 'Penyewa Sangat Tepercaya', 'max_item_value': 3000000, 'max_value': 3000000, 'deposit_percent': 10},
        }
    return tiers


def get_tier_info(tier_name):
    """Mendapatkan info limit dan persentase deposit untuk tier tertentu."""
    tiers = parse_trust_tiers()
    return tiers.get(tier_name, tiers.get('baru'))


def get_renter_tier(user):
    """
    Menghitung tingkat penyewa sesuai SPEC v2 Bagian A.1:
    - 'baru': < 3 sewa selesai
    - 'tepercaya': 3-5 sewa selesai tanpa sengketa (dan skor 60+ bila skor sudah ada)
    - 'sangat_tepercaya': >= 6 sewa selesai tanpa sengketa (dan skor 75+ bila skor sudah ada)
    Menggunakan TrustScore.effective_score agar menghormati override admin bila ada.
    """
    if not user or not user.is_authenticated:
        return 'baru'

    from apps.rentals.models import Rental

    # Hitung jumlah sewa selesai tanpa sengketa
    completed_without_dispute = Rental.objects.filter(
        renter=user,
        status=Rental.Status.SELESAI
    ).exclude(dispute__isnull=False).count()

    # Periksa skor kepercayaan bila sudah dihitung atau di-override
    trust_score_obj = getattr(user, 'trust_score', None)
    has_score = False
    score = None
    if trust_score_obj:
        if trust_score_obj.override_score is not None:
            has_score = True
            score = trust_score_obj.effective_score
        elif not trust_score_obj.is_new_user:
            has_score = True
            score = trust_score_obj.effective_score

    if completed_without_dispute >= 6:
        if score is None or score >= 75:
            return 'sangat_tepercaya'
        elif score >= 60:
            return 'tepercaya'
        return 'baru'
    elif completed_without_dispute >= 3:
        if score is None or score >= 60:
            return 'tepercaya'
        return 'baru'
    else:
        return 'baru'


def calculate_minimum_deposit(item_value, renter_tier='baru', is_cross_campus=False):
    """
    Menghitung deposit minimum sesuai SPEC v2 & Fase 7G:
    - Jika DEPOSIT_MODE='off' (bawaan): selalu mengembalikan 0.
    - Jika DEPOSIT_MODE='optional': deposit minimum platform 0 (pemilik boleh menentukan sendiri).
    - Mode lama/lainnya:
      - Nilai barang <= NO_DEPOSIT_BELOW_VALUE (Rp150.000) boleh tanpa deposit (0).
      - Nilai barang > Rp150.000:
        - Deposit minimum = max(MIN_DEPOSIT_AMOUNT, item_value * (deposit_percent + cross_campus_extra) / 100).
        - MIN_DEPOSIT_AMOUNT bawaan Rp25.000.
        - Lintas kampus: deposit_percent + CROSS_CAMPUS_EXTRA_DEPOSIT_PERCENT (5 poin persen).
    """
    deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
    if deposit_mode in ['off', 'optional']:
        return 0

    item_value = int(item_value or 0)
    no_deposit_below = getattr(settings, 'NO_DEPOSIT_BELOW_VALUE', 150000)
    min_deposit = getattr(settings, 'MIN_DEPOSIT_AMOUNT', 25000)
    cross_campus_extra = getattr(settings, 'CROSS_CAMPUS_EXTRA_DEPOSIT_PERCENT', 5)

    if item_value <= no_deposit_below:
        return 0

    tier_info = get_tier_info(renter_tier)
    base_percent = tier_info.get('deposit_percent', 15)
    total_percent = base_percent + (cross_campus_extra if is_cross_campus else 0)

    calculated = round(item_value * total_percent / 100)
    return max(min_deposit, calculated)


def calculate_protection_fee(rent_total, estimated_value):
    """
    Menghitung biaya proteksi kerusakan ringan sesuai SPEC v2 Bagian A.3:
    - protection_fee = max(PROTECTION_FEE_MIN, round(rent_total * PROTECTION_FEE_PERCENT / 100))
    - Wajib jika estimated_value > PROTECTION_MANDATORY_ABOVE (Rp500.000)
    """
    rent_total = int(rent_total or 0)
    estimated_value = int(estimated_value or 0)

    fee_min = getattr(settings, 'PROTECTION_FEE_MIN', 3000)
    fee_pct = getattr(settings, 'PROTECTION_FEE_PERCENT', 5)
    mandatory_above = getattr(settings, 'PROTECTION_MANDATORY_ABOVE', 500000)

    fee = max(fee_min, round(rent_total * fee_pct / 100))
    is_mandatory = estimated_value > mandatory_above

    return {
        'fee': fee,
        'is_mandatory': is_mandatory,
    }


def is_renter_eligible_for_item(user, item):
    """
    Mengecek apakah penyewa memenuhi syarat pemilik dan batas nilai barang:
    1. Tingkat penyewa >= item.min_renter_tier
    2. Nilai barang item.estimated_value <= limit nilai barang tingkat penyewa
    """
    user_tier = get_renter_tier(user)
    tier_info = get_tier_info(user_tier)

    user_rank = TIER_RANK.get(user_tier, 1)
    required_rank = TIER_RANK.get(item.min_renter_tier, 1)

    if user_rank < required_rank:
        req_label = TIER_LABELS.get(item.min_renter_tier, item.min_renter_tier)
        user_label = TIER_LABELS.get(user_tier, user_tier)
        return False, f"Pemilik mensyaratkan minimal {req_label}. Tingkat Anda saat ini: {user_label}."

    max_val = tier_info.get('max_item_value', 750000)
    if item.estimated_value > max_val:
        user_label = TIER_LABELS.get(user_tier, user_tier)
        return False, f"Tingkat {user_label} hanya dapat menyewa barang dengan estimasi nilai hingga Rp{max_val:,}. Nilai barang ini: Rp{item.estimated_value:,}."

    return True, ""


def compute_features(user):
    """
    Menghitung 8 fitur perilaku riwayat sewa pengguna dari database secara objektif.
    Prinsip etika & UU PDP: Fitur sensitif (jenis kelamin, kampus, prodi,
    asal daerah, dsb.) secara ketat TIDAK PERNAH digunakan.
    """
    if not user or not getattr(user, 'is_authenticated', True):
        return {}

    from django.db.models import Q, Avg
    from django.utils import timezone
    from apps.rentals.models import Rental, Review

    user_id = getattr(user, 'id', getattr(user, 'pk', user))

    completed_all = Rental.objects.filter(
        Q(renter_id=user_id) | Q(owner_id=user_id),
        status=Rental.Status.SELESAI
    ).count()

    completed_as_renter = Rental.objects.filter(
        renter_id=user_id,
        status=Rental.Status.SELESAI
    ).count()

    completed_as_owner = Rental.objects.filter(
        owner_id=user_id,
        status=Rental.Status.SELESAI
    ).count()

    on_time_as_renter = Rental.objects.filter(
        renter_id=user_id,
        status=Rental.Status.SELESAI,
        late_days=0
    ).count()

    # Rasio tepat waktu sebagai penyewa (bawaan 1.0 jika belum pernah menyewa)
    if completed_as_renter > 0:
        rasio_tepat_waktu = round(float(on_time_as_renter) / float(completed_as_renter), 3)
    else:
        rasio_tepat_waktu = 1.0

    # Rata-rata rating yang diterima dari pihak lain
    avg_rating_val = Review.objects.filter(reviewee_id=user_id).aggregate(Avg('rating'))['rating__avg']
    if avg_rating_val is not None:
        rata_rata_rating = round(float(avg_rating_val), 2)
    else:
        # Default netral sesuai rata-rata populasi
        rata_rata_rating = 4.20

    # Sengketa yang melibatkan pengguna
    disputes_count = Rental.objects.filter(
        Q(renter_id=user_id) | Q(owner_id=user_id),
        dispute__isnull=False
    ).count()

    total_transaksi = completed_all
    rasio_sengketa = round(float(disputes_count) / float(max(1, total_transaksi)), 3)

    # Pembatalan yang diinisiasi oleh pengguna
    total_initiated = Rental.objects.filter(
        Q(renter_id=user_id) | Q(owner_id=user_id)
    ).count()
    cancelled_by_user = Rental.objects.filter(
        cancelled_by_id=user_id,
        status=Rental.Status.DIBATALKAN
    ).count()
    rasio_pembatalan = round(float(cancelled_by_user) / float(max(1, total_initiated)), 3)

    # Umur akun dalam hari
    now = timezone.now()
    user_date_joined = getattr(user, 'date_joined', now)
    umur_hari = max(1, (now - user_date_joined).days)

    features = {
        'jumlah_sewa_selesai': completed_all,
        'jumlah_sebagai_pemilik': completed_as_owner,
        'rasio_tepat_waktu': rasio_tepat_waktu,
        'rata_rata_rating_diterima': rata_rata_rating,
        'jumlah_sengketa': disputes_count,
        'rasio_sengketa': rasio_sengketa,
        'rasio_pembatalan': rasio_pembatalan,
        'umur_akun_hari': umur_hari,
    }

    # Audit keamanan & etika: verifikasi tidak ada atribut sensitif
    for sensitive_key in SENSITIVE_ATTRIBUTES:
        assert sensitive_key not in features, f"Atribut sensitif '{sensitive_key}' dilarang dalam fitur!"

    return features


def clear_model_cache():
    """Mengosongkan cache in-memory model ML agar pembaruan model segera aktif."""
    global _MODEL_CACHE
    _MODEL_CACHE = None


def load_trust_model():
    """
    Pemuat model ML malas (lazy loading) dari versi aktif di TrustModelVersion.
    Mendukung fallback bertingkat:
    1. Dari artefak folder berversi ml/artifacts/versions/<version>/trust_model.joblib
    2. Dari ml/artifacts/trust_model.joblib bawaan
    3. Mengembalikan None untuk fallback heuristik aman tanpa crash.
    """
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    artifact_path = None
    try:
        from apps.trust.models import TrustModelVersion
        active_ver = TrustModelVersion.objects.filter(is_active=True).first()
        if active_ver:
            candidate_path = os.path.join(
                settings.BASE_DIR, 'ml', 'artifacts', 'versions',
                active_ver.version, 'trust_model.joblib'
            )
            if os.path.exists(candidate_path):
                artifact_path = candidate_path
    except Exception as e:
        logger.debug(f"Pengecekan versi model aktif di DB dilewati: {e}")

    if not artifact_path or not os.path.exists(artifact_path):
        root_path = os.path.join(settings.BASE_DIR, 'ml', 'artifacts', 'trust_model.joblib')
        if os.path.exists(root_path):
            artifact_path = root_path

    if not artifact_path or not os.path.exists(artifact_path):
        logger.warning("Artefak model ML tidak ditemukan. Sistem akan menggunakan cadangan heuristik.")
        return None

    try:
        model_payload = joblib.load(artifact_path)
        _MODEL_CACHE = model_payload
        logger.info(f"Model ML skor kepercayaan berhasil dimuat: {model_payload.get('model_version')} (dari {artifact_path})")
        return _MODEL_CACHE
    except Exception as e:
        logger.error(f"Gagal memuat model ML dari {artifact_path}: {e}")
        return None


def predict_risk_from_features(features):
    """
    Menghitung prediksi probabilitas risiko (0.0 s.d 1.0) dari snapshot fitur.
    Menggunakan model aktif terkalibrasi atau estimasi fallback jika model belum ada.
    """
    model_data = load_trust_model()
    if model_data is not None:
        try:
            feature_cols = model_data.get('feature_cols', FEATURE_NAMES)
            scaler = model_data['base_pipeline_scaler']
            calibrated_model = model_data['calibrated_model']
            import pandas as pd
            x_df = pd.DataFrame([[features.get(c, 0.0) for c in feature_cols]], columns=feature_cols)
            x_scaled = scaler.transform(x_df)
            risk_prob = float(calibrated_model.predict_proba(x_scaled)[0, 1])
            return round(risk_prob, 4)
        except Exception as e:
            logger.warning(f"Inferensi prediksi risiko gagal: {e}")

    # Fallback heuristik jika artefak belum ada
    on_time_ratio = features.get('rasio_tepat_waktu', 1.0)
    disputes_count = features.get('jumlah_sengketa', 0)
    if on_time_ratio < 0.7 or disputes_count > 0:
        return 0.450
    return 0.154


def record_training_snapshot(rental, renter):
    """
    Menyimpan snapshot fitur penyewa dan prediksi risiko saat pengajuan sewa (source='live', label=None).
    """
    from apps.trust.models import TrustTrainingExample, TrustModelVersion
    features = compute_features(renter)
    predicted_risk = predict_risk_from_features(features)
    active_ver = TrustModelVersion.objects.filter(is_active=True).first()
    ver_str = active_ver.version if active_ver else 'v1.0-logreg-calibrated'

    example, created = TrustTrainingExample.objects.get_or_create(
        rental=rental,
        defaults={
            'user': renter,
            'features': features,
            'predicted_risk': predicted_risk,
            'model_version': ver_str,
            'source': TrustTrainingExample.Source.LIVE,
            'label_problem': None,
            'labeled_at': None,
        }
    )
    return example


def label_training_example_for_rental(rental):
    """
    Melabeli TrustTrainingExample untuk sewa yang telah mencapai status terminal (idempoten).
    Aturan label (Fase 7C Bagian B):
    - label_problem = 1 bila:
      * terlambat lebih dari 1 hari (late_days > 1)
      * ada potongan kerusakan (damage_fee > 0)
      * sengketa terjadi atau dimenangkan pemilik
      * barang tidak dikembalikan
    - selain itu 0.
    """
    from django.utils import timezone
    from apps.trust.models import TrustTrainingExample
    from apps.rentals.models import Rental

    # Hanya untuk sewa yang sudah terminal
    if rental.status not in [Rental.Status.SELESAI, Rental.Status.SENGKETA, Rental.Status.DIBATALKAN]:
        return None

    has_damage_charge = False
    has_loss_charge = False
    has_late_charge = False
    if hasattr(rental, 'extra_charges'):
        has_damage_charge = rental.extra_charges.filter(charge_type='kerusakan').exists()
        has_loss_charge = rental.extra_charges.filter(charge_type='kehilangan').exists()
        has_late_charge = rental.extra_charges.filter(charge_type='keterlambatan').exists()

    is_late = (getattr(rental, 'late_days', 0) > 1) or has_late_charge
    has_damage = (getattr(rental, 'damage_fee', 0) > 0) or has_damage_charge
    has_dispute = hasattr(rental, 'dispute') and rental.dispute is not None
    is_non_return = has_loss_charge
    if has_dispute and getattr(rental.dispute, 'reason', '') == 'barang_tidak_dikembalikan':
        is_non_return = True

    if rental.status == Rental.Status.SENGKETA:
        # Jika status sengketa terminal (seperti barang tidak dikembalikan)
        is_problem = 1
    elif rental.status == Rental.Status.DIBATALKAN:
        if is_late or has_damage or has_dispute or is_non_return:
            is_problem = 1
        else:
            return None
    else:
        is_problem = 1 if (is_late or has_damage or has_dispute or is_non_return) else 0

    example = TrustTrainingExample.objects.filter(rental=rental).first()
    if not example:
        from apps.trust.models import TrustModelVersion
        active_ver = TrustModelVersion.objects.filter(is_active=True).first()
        ver_str = active_ver.version if active_ver else 'v1.0-logreg-calibrated'
        example = TrustTrainingExample.objects.create(
            rental=rental,
            user=rental.renter,
            features=compute_features(rental.renter),
            predicted_risk=None,
            model_version=ver_str,
            label_problem=is_problem,
            labeled_at=timezone.now(),
            source=TrustTrainingExample.Source.LIVE,
        )
    else:
        if example.label_problem != is_problem or example.labeled_at is None:
            example.label_problem = is_problem
            example.labeled_at = timezone.now()
            example.save(update_fields=['label_problem', 'labeled_at'])

    return example



def explain_factors(features, feature_means, feature_scales, coefficients):
    """
    Membangkitkan 3 faktor penjelas teratas dari kontribusi koefisien dikali nilai terstandar.
    Hasil berupa kalimat Bahasa Indonesia sederhana yang transparan dan mudah dipahami.
    """
    contributions = []
    for col, coef in coefficients.items():
        if col not in features:
            continue
        val = features[col]
        mean = feature_means.get(col, 0.0)
        scale = feature_scales.get(col, 1.0)
        if scale == 0:
            scale = 1.0
        # z-score fitur terstandar
        z_val = (val - mean) / scale
        # trust_impact: karena target model adalah risiko (bermasalah),
        # maka pengaruh positif terhadap skor kepercayaan adalah kebalikan dari pengaruh risiko:
        # trust_impact = - (coef * z_val)
        trust_impact = - (coef * z_val)
        contributions.append((col, val, trust_impact, abs(trust_impact)))

    # Urutkan berdasarkan besaran dampak absolut terbesar
    contributions.sort(key=lambda x: x[3], reverse=True)
    top_3 = contributions[:3]

    factor_sentences = []
    for col, val, impact, _ in top_3:
        is_positive = impact >= 0
        if col == 'rasio_tepat_waktu':
            pct = int(round(val * 100))
            if is_positive:
                factor_sentences.append(f"Rasio tepat waktu {pct}% menaikkan skor")
            else:
                factor_sentences.append(f"Rasio tepat waktu {pct}% menurunkan skor")
        elif col == 'rata_rata_rating_diterima':
            if is_positive:
                factor_sentences.append(f"Rating diterima {val:.1f} dari 5 bintang menaikkan skor")
            else:
                factor_sentences.append(f"Rating diterima {val:.1f} dari 5 bintang menurunkan skor")
        elif col == 'jumlah_sewa_selesai':
            if is_positive:
                factor_sentences.append(f"Riwayat {val} transaksi sewa selesai menaikkan skor")
            else:
                factor_sentences.append(f"Riwayat sewa selesai masih {val} transaksi")
        elif col == 'jumlah_sebagai_pemilik':
            if is_positive:
                factor_sentences.append(f"Aktif sebagai pemilik ({val} transaksi selesai) menaikkan skor")
            else:
                factor_sentences.append(f"Belum banyak riwayat sebagai pemilik barang ({val} transaksi)")
        elif col == 'jumlah_sengketa':
            if val == 0:
                factor_sentences.append("Tidak ada catatan sengketa transaksi menaikkan skor")
            else:
                factor_sentences.append(f"Pernah memiliki {val} catatan sengketa menurunkan skor")
        elif col == 'rasio_pembatalan':
            pct = int(round(val * 100))
            if is_positive:
                factor_sentences.append(f"Rasio pembatalan rendah ({pct}%) menaikkan skor")
            else:
                factor_sentences.append(f"Pernah membatalkan sewa ({pct}%) menurunkan skor")
        elif col == 'umur_akun_hari':
            if is_positive:
                factor_sentences.append(f"Akun aktif selama {val} hari menaikkan skor")
            else:
                factor_sentences.append(f"Akun baru aktif {val} hari")
        elif col == 'rasio_sengketa':
            pct = int(round(val * 100))
            if is_positive:
                factor_sentences.append("Bebas dari sengketa transaksi menaikkan skor")
            else:
                factor_sentences.append(f"Rasio sengketa {pct}% menurunkan skor")
        else:
            action = "menaikkan" if is_positive else "menurunkan"
            factor_sentences.append(f"Fitur {col} ({val}) {action} skor")

    return factor_sentences


def recompute_trust_score(user):
    """
    Menghitung ulang skor kepercayaan pengguna (TrustScore):
    1. Pengguna dengan < 3 sewa selesai:
       - is_new_user = True
       - skor = 60
       - label = "Pengguna baru"
       - model ML tidak dipakai
    2. Pengguna dengan >= 3 sewa selesai:
       - Hitung 8 fitur riwayat dari database (bebas atribut sensitif)
       - Jika model tersedia:
         * Standardisasi fitur
         * Prediksi probabilitas risiko bermasalah dengan model terkalibrasi
         * skor = round((1 - probabilitas) * 100)
         * Simpan top_factors (3 kalimat penjelasan sederhana)
         * model_version = versi model (misal v1.0-logreg-calibrated)
       - Jika model belum dilatih / file hilang:
         * Cadangan aman: heuristik sederhana
         * model_version = 'model belum dilatih'
    """
    if not user or not user.is_authenticated:
        return None

    from django.db.models import Q
    from django.utils import timezone
    from apps.rentals.models import Rental
    from apps.trust.models import TrustScore

    completed_rentals = Rental.objects.filter(
        Q(renter=user) | Q(owner=user),
        status=Rental.Status.SELESAI
    ).count()

    is_new = completed_rentals < 3

    if is_new:
        score = 60
        risk_probability = 0.154  # Prevalensi dasar populasi
        top_factors = ["Pengguna baru (kurang dari 3 sewa selesai)"]
        features = compute_features(user)
        model_ver = "cold-start-rule"
    else:
        features = compute_features(user)
        model_data = load_trust_model()

        if model_data is not None:
            try:
                feature_cols = model_data['feature_cols']
                scaler = model_data['base_pipeline_scaler']
                calibrated_model = model_data['calibrated_model']

                # Susun dataframe fitur sesuai urutan kolom pelatihan
                import pandas as pd
                x_df = pd.DataFrame([[features[c] for c in feature_cols]], columns=feature_cols)
                x_scaled = scaler.transform(x_df)

                # Prediksi probabilitas risiko bermasalah (kelas 1)
                risk_prob = float(calibrated_model.predict_proba(x_scaled)[0, 1])
                risk_probability = round(risk_prob, 4)

                # Rumus skor kepercayaan: (1 - probabilitas) * 100
                raw_score = int(round((1.0 - risk_prob) * 100))
                score = max(0, min(100, raw_score))

                # Penjelasan 3 faktor penjelas teratas
                top_factors = explain_factors(
                    features=features,
                    feature_means=model_data.get('feature_means', {}),
                    feature_scales=model_data.get('feature_scales', {}),
                    coefficients=model_data.get('coefficients', {})
                )
                model_ver = model_data.get('model_version', 'v1.0-logreg-calibrated')
            except Exception as e:
                logger.error(f"Gagal melakukan inferensi model ML untuk {user.username}: {e}. Memakai cadangan aman.")
                model_data = None

        if model_data is None:
            # Cadangan aman jika artefak model hilang atau gagal diproses
            on_time_ratio = features.get('rasio_tepat_waktu', 1.0)
            disputes_count = features.get('jumlah_sengketa', 0)
            base = 70
            bonus_completed = min(20, completed_rentals * 2)
            bonus_punctual = 10 if on_time_ratio >= 0.9 else 0
            penalty_dispute = disputes_count * 15
            raw_score = base + bonus_completed + bonus_punctual - penalty_dispute
            score = max(10, min(100, raw_score))
            risk_probability = round((100 - score) / 100.0, 3)
            model_ver = "model belum dilatih"

            top_factors = [f"{completed_rentals} transaksi sewa sukses diselesaikan"]
            if on_time_ratio >= 0.9:
                top_factors.append("Rasio pengembalian tepat waktu sangat baik")
            else:
                top_factors.append("Pernah mengalami keterlambatan pengembalian")
            if disputes_count == 0:
                top_factors.append("Tidak memiliki catatan sengketa")
            else:
                top_factors.append(f"{disputes_count} sengketa pernah tercatat")

    trust_obj, _ = TrustScore.objects.update_or_create(
        user=user,
        defaults={
            'score': score,
            'risk_probability': risk_probability,
            'is_new_user': is_new,
            'features': features,
            'top_factors': top_factors,
            'model_version': model_ver,
            'computed_at': timezone.now(),
        }
    )
    logger.info(f"TrustScore recomputed for {user.username}: score={score}, effective={trust_obj.effective_score}, is_new={is_new}, version={model_ver}")
    return trust_obj
