import datetime
from django.utils import timezone
from django.db.models import Sum, Q

from apps.accounts.models import User
from apps.verification.models import KtmVerification
from apps.payments.models import WithdrawalRequest
from apps.rentals.models import Dispute, Rental
from apps.sales.models import SaleOrder
from apps.payments.reconciliation import run_financial_reconciliation


def get_staff_operational_stats():
    """
    Menghitung statistik antrean dan indikator finansial untuk Pusat Operasional Staf.
    """
    now = timezone.now()
    threshold_48h = now - datetime.timedelta(hours=48)

    # 1. Antrean Verifikasi KTM (menunggu atau butuh tinjauan)
    ktm_queue_count = KtmVerification.objects.filter(
        status__in=[KtmVerification.Status.MENUNGGU, KtmVerification.Status.PERLU_TINJAUAN]
    ).count()

    # 2. Antrean Penarikan Dana (diminta atau diproses)
    withdrawal_queue_count = WithdrawalRequest.objects.filter(
        status__in=[WithdrawalRequest.Status.DIMINTA, WithdrawalRequest.Status.DIPROSES]
    ).count()

    # 3. Antrean Sengketa Terbuka (status TERBUKA)
    dispute_queue_count = Dispute.objects.filter(
        status=Dispute.Status.TERBUKA
    ).count()

    # 4. Sewa Menunggu Konfirmasi lebih dari 48 jam
    rental_stale_count = Rental.objects.filter(
        status=Rental.Status.MENUNGGU_PERSETUJUAN,
        created_at__lte=threshold_48h
    ).count()

    # 5. Pesanan Jual Beli Bermasalah (sengketa aktif atau janji temu terlewat)
    sale_dispute_count = SaleOrder.objects.filter(
        status=SaleOrder.Status.SENGKETA
    ).count()
    sale_overdue_meetup_count = SaleOrder.objects.filter(
        status=SaleOrder.Status.DIBAYAR,
        handed_over_at__isnull=True,
        meetup_at__lt=now
    ).count()
    sale_problematic_count = sale_dispute_count + sale_overdue_meetup_count

    # 6. Laporan Barang Jual Beli Menunggu Tindak Lanjut
    from apps.sales.models import SaleItemReport
    sale_report_queue_count = SaleItemReport.objects.filter(
        status=SaleItemReport.Status.MENUNGGU
    ).count()

    total_queue = (
        ktm_queue_count +
        withdrawal_queue_count +
        dispute_queue_count +
        rental_stale_count +
        sale_problematic_count +
        sale_report_queue_count
    )

    # 7. Indikator Keuangan (dari Rekonsiliasi Keuangan Independen)
    recon = run_financial_reconciliation()
    escrow_held = recon.get('total_escrow_held', 0)
    user_balances_total = recon.get('total_user_wallets', 0)
    platform_commission_total = recon.get('total_commission', 0)
    gotong_royong_fund = recon.get('total_protection_fund', 0)
    recon_balanced = recon['summary']['global_balanced']
    recon_discrepancy = recon['summary']['discrepancy']

    return {
        'ktm_queue_count': ktm_queue_count,
        'withdrawal_queue_count': withdrawal_queue_count,
        'dispute_queue_count': dispute_queue_count,
        'rental_stale_count': rental_stale_count,
        'sale_dispute_count': sale_dispute_count,
        'sale_overdue_meetup_count': sale_overdue_meetup_count,
        'sale_problematic_count': sale_problematic_count,
        'sale_report_queue_count': sale_report_queue_count,
        'total_queue': total_queue,
        'escrow_held': escrow_held,
        'user_balances_total': user_balances_total,
        'platform_commission_total': platform_commission_total,
        'gotong_royong_fund': gotong_royong_fund,
        'recon_balanced': recon_balanced,
        'recon_discrepancy': recon_discrepancy,
    }


def _format_change_chip(curr, prev):
    if prev == 0:
        return {'text': '-', 'is_positive': None}
    diff = curr - prev
    pct = round((diff / prev) * 100, 1)
    if pct > 0:
        return {'text': f"+{pct}%", 'is_positive': True}
    elif pct < 0:
        return {'text': f"{pct}%", 'is_positive': False}
    else:
        return {'text': "0%", 'is_positive': None}


def get_admin_dashboard_summary():
    """
    Menghitung 4 metrik ringkasan kartu Saledash:
    1. Pengguna terverifikasi (count, change chip vs periode sebelumnya)
    2. Sewa aktif (count, change chip)
    3. Transaksi selesai (count, nilai/GMV, change chip)
    4. Dana ditahan (nilai escrow held, change chip)
    Jika data periode sebelumnya nol, tampilkan '-' pada chip perubahan.
    """
    now = timezone.now()
    d30 = datetime.timedelta(days=30)
    d60 = datetime.timedelta(days=60)

    # 1. Pengguna terverifikasi
    total_verified = User.objects.filter(is_verified_student=True).count()
    prev_verified = User.objects.filter(is_verified_student=True, created_at__lt=now - d30).count()
    verified_change = _format_change_chip(total_verified, prev_verified)

    # 2. Sewa aktif
    active_statuses = [
        Rental.Status.DIBAYAR,
        Rental.Status.SEDANG_DISEWA,
        Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN,
    ]
    active_count = Rental.objects.filter(status__in=active_statuses).count()
    prev_active = Rental.objects.filter(
        status__in=active_statuses,
        created_at__lt=now - d30
    ).count()
    active_change = _format_change_chip(active_count, prev_active)

    # 3. Transaksi selesai beserta nilainya
    completed_qs = Rental.objects.filter(status=Rental.Status.SELESAI)
    completed_count = completed_qs.count()
    completed_val = completed_qs.aggregate(s=Sum('grand_total'))['s'] or 0

    curr_period_completed = Rental.objects.filter(
        status=Rental.Status.SELESAI,
        updated_at__gte=now - d30
    ).count()
    prev_period_completed = Rental.objects.filter(
        status=Rental.Status.SELESAI,
        updated_at__gte=now - d60,
        updated_at__lt=now - d30
    ).count()
    completed_change = _format_change_chip(curr_period_completed, prev_period_completed)

    # 4. Dana ditahan
    recon = run_financial_reconciliation()
    escrow_held = recon.get('total_escrow_held', 0)
    prev_escrow = 0
    escrow_change = _format_change_chip(escrow_held, prev_escrow)

    return {
        'verified_users': {
            'count': total_verified,
            'change': verified_change['text'],
            'is_positive': verified_change['is_positive'],
        },
        'active_rentals': {
            'count': active_count,
            'change': active_change['text'],
            'is_positive': active_change['is_positive'],
        },
        'completed_rentals': {
            'count': completed_count,
            'value': completed_val,
            'change': completed_change['text'],
            'is_positive': completed_change['is_positive'],
        },
        'escrow_held': {
            'value': escrow_held,
            'change': escrow_change['text'],
            'is_positive': escrow_change['is_positive'],
        },
    }


def get_rental_chart_data(days=30):
    """
    Menghasilkan data grafik SVG garis untuk 'Laporan sewa' berdasarkan rentang hari (7, 30, 90).
    Menghitung nilai transaksi selesai per hari, menghasilkan koordinat poligon & polyline SVG,
    serta titik-titik data dengan nilai dan tanggal untuk interaksi tooltip.
    """
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 30
    if days not in (7, 30, 90):
        days = 30

    now = timezone.localtime()
    today = now.date()
    start_date = today - datetime.timedelta(days=days - 1)

    daily_totals = {}
    completed_rentals = Rental.objects.filter(
        status=Rental.Status.SELESAI,
        updated_at__date__gte=start_date,
        updated_at__date__lte=today
    )
    for r in completed_rentals:
        dt = timezone.localtime(r.updated_at).date()
        daily_totals[dt] = daily_totals.get(dt, 0) + (r.grand_total or r.rent_total or 0)

    bulan_singkat = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mei', 6: 'Jun',
        7: 'Jul', 8: 'Ags', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Des'
    }

    days_list = []
    curr = start_date
    while curr <= today:
        val = daily_totals.get(curr, 0)
        days_list.append({
            'date': curr,
            'date_str': f"{curr.day} {bulan_singkat.get(curr.month, '')}",
            'val': val,
        })
        curr += datetime.timedelta(days=1)

    svg_w = 760
    svg_h = 240
    pad_left = 75
    pad_right = 24
    pad_top = 24
    pad_bottom = 42
    plot_w = svg_w - pad_left - pad_right
    plot_h = svg_h - pad_top - pad_bottom

    max_val = max([d['val'] for d in days_list] + [100000])
    scale_max = ((max_val // 50000) + 1) * 50000

    n_pts = len(days_list)
    points = []
    pts_str_list = []

    for i, d in enumerate(days_list):
        if n_pts > 1:
            x = pad_left + (i / (n_pts - 1)) * plot_w
        else:
            x = pad_left + plot_w / 2
        ratio = d['val'] / scale_max
        y = pad_top + plot_h - (ratio * plot_h)
        x_rounded = round(x, 1)
        y_rounded = round(y, 1)

        pts_str_list.append(f"{x_rounded},{y_rounded}")
        points.append({
            'x': x_rounded,
            'y': y_rounded,
            'date': d['date_str'],
            'val': d['val'],
            'val_formatted': f"Rp{d['val']:,}".replace(',', '.'),
        })

    polyline_points = " ".join(pts_str_list)
    baseline_y = round(pad_top + plot_h, 1)
    first_x = points[0]['x'] if points else pad_left
    last_x = points[-1]['x'] if points else (pad_left + plot_w)
    area_points = f"{polyline_points} {last_x},{baseline_y} {first_x},{baseline_y}"

    grid_lines = [
        {
            'y': round(pad_top, 1),
            'text_y': int(pad_top + 4),
            'label': f"Rp{scale_max:,}".replace(',', '.')
        },
        {
            'y': round(pad_top + plot_h / 2, 1),
            'text_y': int(pad_top + plot_h / 2 + 4),
            'label': f"Rp{int(scale_max / 2):,}".replace(',', '.')
        },
        {
            'y': baseline_y,
            'text_y': int(baseline_y + 4),
            'label': "Rp0"
        },
    ]

    stride = max(1, n_pts // 6)
    x_labels = []
    for i in range(0, n_pts, stride):
        x_labels.append({
            'x': points[i]['x'],
            'y': baseline_y + 22,
            'text': points[i]['date'],
        })
    if x_labels and x_labels[-1]['text'] != points[-1]['date']:
        x_labels.append({
            'x': points[-1]['x'],
            'y': baseline_y + 22,
            'text': points[-1]['date'],
        })

    total_period_val = sum(d['val'] for d in days_list)

    return {
        'days': days,
        'points': points,
        'polyline_points': polyline_points,
        'area_points': area_points,
        'grid_lines': grid_lines,
        'x_labels': x_labels,
        'svg_w': svg_w,
        'svg_h': svg_h,
        'baseline_y': baseline_y,
        'total_period_val': total_period_val,
        'total_period_val_formatted': f"Rp{total_period_val:,}".replace(',', '.'),
    }


def get_recent_rentals(search_query='', limit=8):
    """
    Mengambil transaksi sewa terbaru untuk tabel Saledash dengan dukungan filter pencarian.
    """
    qs = Rental.objects.select_related('item', 'renter', 'owner').order_by('-created_at')
    if search_query:
        q = search_query.strip()
        qs = qs.filter(
            Q(code__icontains=q) |
            Q(item__title__icontains=q) |
            Q(renter__username__icontains=q) |
            Q(renter__full_name__icontains=q) |
            Q(owner__username__icontains=q) |
            Q(owner__full_name__icontains=q)
        )
    return qs[:limit]
