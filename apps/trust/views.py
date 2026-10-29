import os
import json
import logging
import pandas as pd
import numpy as np
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q

from django.contrib import messages
from apps.accounts.models import User
from apps.catalog.models import Item
from apps.rentals.models import Rental
from apps.payments.models import LedgerEntry, DepositHold
from apps.trust.models import TrustTrainingExample, TrustModelVersion
from apps.trust.services import load_trust_model, explain_factors
from apps.trust.management.commands.retrain_trust_model import execute_retraining
from apps.trust.management.commands.rollback_trust_model import execute_rollback

logger = logging.getLogger(__name__)


def _load_metrics_json():
    """Membaca file metrics.json bila ada."""
    metrics_path = os.path.join(settings.BASE_DIR, 'ml', 'artifacts', 'metrics.json')
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Gagal membaca metrics.json: {e}")
    return None


def public_trust_score_redirect_view(request):
    """
    Pengalihan rute publik lama /skor-kepercayaan/ ke bagian edukasi di /bantuan/#skor-kepercayaan.
    """
    return redirect('/bantuan/#skor-kepercayaan')


@staff_member_required(login_url='/admin/login/')
def admin_model_score_view(request):
    """
    Halaman khusus staf /admin/model-skor/:
    - Continuous learning dari data nyata dan guardrail retraining
    - Metrik data latih terlabel (live vs backfill)
    - Riwayat versi model artefak dan kontrol rollback
    - Cara kerja model Machine Learning TrustScore
    - 8 Fitur yang dipakai dan atribut sensitif yang sengaja TIDAK dipakai
    - Simulator interaktif skor berbasis HTMX
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'retrain':
            force = (request.POST.get('force') == '1')
            include_backfill = (request.POST.get('include_backfill') == '1')
            notes = request.POST.get('notes', '').strip() or f"Dipicu manual oleh {request.user.username} via UI Staf"
            res = execute_retraining(
                force=force,
                include_backfill=include_backfill,
                notes=notes,
                user=request.user
            )
            if res.get('promoted'):
                messages.success(request, f"Model baru '{res['new_version']}' berhasil dipromosikan! {res['reason']}")
            elif res.get('success'):
                messages.warning(request, f"Evaluasi selesai tanpa promosi model: {res['reason']}")
            else:
                messages.error(request, f"Retraining dibatalkan oleh guardrail: {res.get('reason')}")
            return redirect('trust:admin_model_score')

        elif action == 'rollback':
            target_version = request.POST.get('version', '').strip()
            if not target_version:
                messages.error(request, "Nama versi target rollback tidak valid.")
            else:
                success, msg = execute_rollback(target_version, user=request.user)
                if success:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            return redirect('trust:admin_model_score')

    metrics = _load_metrics_json()

    # Hitung statistik data latih nyata
    live_count = TrustTrainingExample.objects.filter(
        source=TrustTrainingExample.Source.LIVE,
        label_problem__isnull=False
    ).count()
    backfill_count = TrustTrainingExample.objects.filter(
        source=TrustTrainingExample.Source.BACKFILL,
        label_problem__isnull=False
    ).count()
    unlabeled_live = TrustTrainingExample.objects.filter(
        source=TrustTrainingExample.Source.LIVE,
        label_problem__isnull=True
    ).count()
    problem_live = TrustTrainingExample.objects.filter(
        source=TrustTrainingExample.Source.LIVE,
        label_problem=1
    ).count()
    problem_backfill = TrustTrainingExample.objects.filter(
        source=TrustTrainingExample.Source.BACKFILL,
        label_problem=1
    ).count()
    total_problems = problem_live + problem_backfill

    min_real = getattr(settings, 'TRUST_MIN_REAL_EXAMPLES', 200)
    min_positives = getattr(settings, 'TRUST_MIN_POSITIVES', 20)
    progress_real_pct = min(100, int((live_count / max(1, min_real)) * 100))
    progress_pos_pct = min(100, int((problem_live / max(1, min_positives)) * 100))

    model_versions = TrustModelVersion.objects.all().order_by('-trained_at')
    active_version = TrustModelVersion.objects.filter(is_active=True).first()

    # Nilai awal untuk simulasi interaktif
    initial_inputs = {
        'jumlah_sewa_selesai': 12,
        'jumlah_sebagai_pemilik': 3,
        'rasio_tepat_waktu': 0.95,
        'rata_rata_rating_diterima': 4.80,
        'jumlah_sengketa': 0,
        'rasio_pembatalan': 0.05,
        'umur_akun_hari': 180,
    }
    initial_simulation = _simulate_score(initial_inputs)

    context = {
        'metrics': metrics,
        'initial_inputs': initial_inputs,
        'initial_simulation': initial_simulation,
        'live_count': live_count,
        'backfill_count': backfill_count,
        'unlabeled_live': unlabeled_live,
        'problem_live': problem_live,
        'problem_backfill': problem_backfill,
        'total_problems': total_problems,
        'min_real': min_real,
        'min_positives': min_positives,
        'progress_real_pct': progress_real_pct,
        'progress_pos_pct': progress_pos_pct,
        'model_versions': model_versions,
        'active_version': active_version,
    }
    return render(request, 'trust/admin_model_score.html', context)


def _simulate_score(inputs: dict):
    """
    Menghitung skor dan 3 faktor penjelas untuk simulasi interaktif
    tanpa menyentuh data database pengguna (murni fitur simulasi).
    """
    completed = int(inputs.get('jumlah_sewa_selesai', 0))
    is_new = completed < 3

    if is_new:
        return {
            'score': 60,
            'label': 'Pengguna baru',
            'token_color': 'ink-muted',
            'risk_probability': 0.154,
            'is_new_user': True,
            'top_factors': [
                "Pengguna baru (kurang dari 3 transaksi sewa selesai)",
                "Batas nilai barang sewa maksimal Rp750.000 untuk pengguna baru",
                "Model penilaian risiko ML baru aktif setelah minimal 3 transaksi"
            ],
            'model_version': 'cold-start-rule',
        }

    # Hitung turunan rasio sengketa
    total_tx = max(1, completed + int(inputs.get('jumlah_sebagai_pemilik', 0)))
    disputes = int(inputs.get('jumlah_sengketa', 0))
    rasio_sengketa = round(float(disputes) / float(total_tx), 3)

    features = {
        'jumlah_sewa_selesai': completed,
        'jumlah_sebagai_pemilik': int(inputs.get('jumlah_sebagai_pemilik', 0)),
        'rasio_tepat_waktu': float(inputs.get('rasio_tepat_waktu', 1.0)),
        'rata_rata_rating_diterima': float(inputs.get('rata_rata_rating_diterima', 4.2)),
        'jumlah_sengketa': disputes,
        'rasio_sengketa': rasio_sengketa,
        'rasio_pembatalan': float(inputs.get('rasio_pembatalan', 0.0)),
        'umur_akun_hari': int(inputs.get('umur_akun_hari', 30)),
    }

    model_data = load_trust_model()
    if model_data is not None:
        try:
            feature_cols = model_data['feature_cols']
            scaler = model_data['base_pipeline_scaler']
            calibrated_model = model_data['calibrated_model']

            x_df = pd.DataFrame([[features[c] for c in feature_cols]], columns=feature_cols)
            x_scaled = scaler.transform(x_df)

            risk_prob = float(calibrated_model.predict_proba(x_scaled)[0, 1])
            raw_score = int(round((1.0 - risk_prob) * 100))
            score = max(0, min(100, raw_score))

            top_factors = explain_factors(
                features=features,
                feature_means=model_data.get('feature_means', {}),
                feature_scales=model_data.get('feature_scales', {}),
                coefficients=model_data.get('coefficients', {})
            )
            model_ver = model_data.get('model_version', 'v1.0-logreg-calibrated')
        except Exception as e:
            logger.error(f"Gagal menghitung simulasi ML: {e}")
            model_data = None

    if model_data is None:
        # Cadangan jika model belum ada
        on_time = features['rasio_tepat_waktu']
        base = 70 + min(20, completed * 2) + (10 if on_time >= 0.9 else 0) - disputes * 15
        score = max(10, min(100, base))
        risk_prob = round((100 - score) / 100.0, 3)
        top_factors = [
            f"{completed} transaksi sewa selesai",
            f"Rasio tepat waktu {int(on_time*100)}%",
            "Tidak ada sengketa tercatat" if disputes == 0 else f"{disputes} catatan sengketa"
        ]
        model_ver = "cadangan heuristik"

    if score >= 70:
        label = "Tepercaya"
        token_color = "pine"
    elif score >= 40:
        label = "Cukup"
        token_color = "amber-text"
    else:
        label = "Perlu hati-hati"
        token_color = "brick"

    return {
        'score': score,
        'label': label,
        'token_color': token_color,
        'risk_probability': round(risk_prob, 4),
        'is_new_user': False,
        'top_factors': top_factors,
        'model_version': model_ver,
    }


@staff_member_required(login_url='/admin/login/')
def trust_score_simulation_htmx_view(request):
    """
    Endpoint HTMX khusus staf untuk simulasi skor kepercayaan interaktif (/admin/model-skor/simulasi/).
    Memvalidasi seluruh masukan di sisi server dan mengembalikan partial HTML ringkasan skor.
    """
    data_src = request.POST if request.method == 'POST' else request.GET

    try:
        # Ekstraksi parameter dengan validasi batas ketat di sisi server
        jumlah_sewa_selesai = int(data_src.get('jumlah_sewa_selesai', 10))
        if not (0 <= jumlah_sewa_selesai <= 500):
            return HttpResponse('<div class="p-3 bg-brick-tint text-brick rounded text-xs">Jumlah sewa selesai harus bernilai antara 0 dan 500.</div>', status=400)

        jumlah_sebagai_pemilik = int(data_src.get('jumlah_sebagai_pemilik', 2))
        if not (0 <= jumlah_sebagai_pemilik <= 500):
            return HttpResponse('<div class="p-3 bg-brick-tint text-brick rounded text-xs">Jumlah sebagai pemilik harus bernilai antara 0 dan 500.</div>', status=400)

        raw_rtw = float(data_src.get('rasio_tepat_waktu', 95))
        if 0.0 <= raw_rtw <= 1.0:
            rasio_tepat_waktu = raw_rtw
        elif 1.0 < raw_rtw <= 100.0:
            rasio_tepat_waktu = raw_rtw / 100.0
        else:
            return HttpResponse('<div class="p-3 bg-brick-tint text-brick rounded text-xs">Rasio tepat waktu harus bernilai antara 0.0 dan 1.0 (atau 0% dan 100%).</div>', status=400)

        rata_rata_rating = float(data_src.get('rata_rata_rating_diterima', 4.8))
        if not (1.0 <= rata_rata_rating <= 5.0):
            return HttpResponse('<div class="p-3 bg-brick-tint text-brick rounded text-xs">Rata-rata rating harus bernilai antara 1.0 dan 5.0.</div>', status=400)

        jumlah_sengketa = int(data_src.get('jumlah_sengketa', 0))
        if not (0 <= jumlah_sengketa <= 100):
            return HttpResponse('<div class="p-3 bg-brick-tint text-brick rounded text-xs">Jumlah sengketa harus bernilai antara 0 dan 100.</div>', status=400)

        raw_rp = float(data_src.get('rasio_pembatalan', 5))
        if 0.0 <= raw_rp <= 1.0:
            rasio_pembatalan = raw_rp
        elif 1.0 < raw_rp <= 100.0:
            rasio_pembatalan = raw_rp / 100.0
        else:
            return HttpResponse('<div class="p-3 bg-brick-tint text-brick rounded text-xs">Rasio pembatalan harus bernilai antara 0.0 dan 1.0 (atau 0% dan 100%).</div>', status=400)

        umur_akun_hari = int(data_src.get('umur_akun_hari', 180))
        if not (1 <= umur_akun_hari <= 3650):
            return HttpResponse('<div class="p-3 bg-brick-tint text-brick rounded text-xs">Umur akun harus bernilai antara 1 dan 3650 hari.</div>', status=400)

    except (ValueError, TypeError) as e:
        return HttpResponse(
            '<div class="p-4 bg-brick-tint border border-brick text-brick rounded-xl text-xs">'
            'Format data masukan simulasi tidak valid. Silakan gunakan angka sesuai rentang.'
            '</div>',
            status=400
        )

    inputs = {
        'jumlah_sewa_selesai': jumlah_sewa_selesai,
        'jumlah_sebagai_pemilik': jumlah_sebagai_pemilik,
        'rasio_tepat_waktu': rasio_tepat_waktu,
        'rata_rata_rating_diterima': rata_rata_rating,
        'jumlah_sengketa': jumlah_sengketa,
        'rasio_pembatalan': rasio_pembatalan,
        'umur_akun_hari': umur_akun_hari,
    }

    result = _simulate_score(inputs)

    return render(request, 'trust/partials/simulation_result.html', {
        'sim': result,
        'inputs': inputs,
    })


@staff_member_required(login_url='/admin/login/')
def admin_summary_view(request):
    """
    Halaman ringkasan platform dan metrik ML (/admin/ringkasan/)
    khusus staf/admin platform:
    - Statistik operasional: pengguna terdaftar, verifikasi KTM, sewa, transaksi (GMV)
    - Finansial: total komisi platform, dana escrow ditahan
    - Metrik model ML TrustScore: perbandingan baseline, AUC, Brier, ambang keputusan
    """
    metrics = _load_metrics_json()

    total_users = User.objects.count()
    verified_users = User.objects.filter(is_verified_student=True).count()
    total_items = Item.objects.count()
    active_items = Item.objects.filter(is_active=True).count()

    total_rentals = Rental.objects.count()
    completed_rentals = Rental.objects.filter(status=Rental.Status.SELESAI).count()
    active_rentals = Rental.objects.filter(
        status__in=[
            Rental.Status.DIBAYAR,
            Rental.Status.SEDANG_DISEWA,
            Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN
        ]
    ).count()
    disputed_rentals = Rental.objects.filter(status=Rental.Status.SENGKETA).count()

    gmv_val = Rental.objects.filter(status=Rental.Status.SELESAI).aggregate(Sum('rent_total'))['rent_total__sum'] or 0
    commission_val = LedgerEntry.objects.filter(kind='keluar_komisi_platform').aggregate(Sum('amount'))['amount__sum'] or 0
    deposit_held_val = DepositHold.objects.filter(status='ditahan').aggregate(Sum('amount'))['amount__sum'] or 0

    context = {
        'total_users': total_users,
        'verified_users': verified_users,
        'total_items': total_items,
        'active_items': active_items,
        'total_rentals': total_rentals,
        'completed_rentals': completed_rentals,
        'active_rentals': active_rentals,
        'disputed_rentals': disputed_rentals,
        'gmv': gmv_val,
        'commission': commission_val,
        'deposit_held': deposit_held_val,
        'metrics': metrics,
    }
    return render(request, 'trust/admin_summary.html', context)
