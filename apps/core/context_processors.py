from django.conf import settings
from apps.core.models import Notification
from apps.core.services import (
    get_staff_operational_stats,
    get_admin_dashboard_summary,
    get_rental_chart_data,
    get_recent_rentals,
)
from apps.core.admin_nav import get_admin_navigation, get_time_greeting, get_indonesian_date_chip


def unread_notifications_count(request):
    """
    Context processor untuk menyediakan jumlah notifikasi yang belum dibaca
    pada seluruh halaman aplikasi.
    """
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}


def staff_operational_counts(request):
    """
    Context processor untuk menyediakan statistik antrean, indikator keuangan,
    serta navigasi kerangka admin terpadu bagi pengguna berstatus staf/admin.
    """
    commission_pct = getattr(settings, 'PLATFORM_COMMISSION_PERCENT', 8)
    protection_pct = getattr(settings, 'PROTECTION_FEE_PERCENT', 5)

    if getattr(request, 'user', None) and request.user.is_authenticated and request.user.is_staff:
        stats = get_staff_operational_stats()
        nav_groups = get_admin_navigation(request)
        greeting = get_time_greeting(request.user)
        date_chip = get_indonesian_date_chip()
        active_group_id = next((g['id'] for g in nav_groups if g.get('is_open') and not g.get('is_single')), '')

        ctx = {
            'staff_stats': stats,
            'admin_nav_groups': nav_groups,
            'admin_active_group_id': active_group_id,
            'admin_time_greeting': greeting,
            'admin_date_chip': date_chip,
            'platform_commission_percent': commission_pct,
            'protection_fee_percent': protection_pct,
        }

        # Jika di indeks admin, tambahkan konteks dashboard Saledash
        if request.path in ('/admin/', '/admin'):
            ctx['admin_dashboard_summary'] = get_admin_dashboard_summary()
            ctx['admin_rental_chart'] = get_rental_chart_data(30)
            ctx['admin_recent_rentals'] = get_recent_rentals(limit=8)

        return ctx

    return {
        'staff_stats': {},
        'admin_nav_groups': [],
        'admin_time_greeting': '',
        'admin_date_chip': '',
        'platform_commission_percent': commission_pct,
        'protection_fee_percent': protection_pct,
    }


def platform_settings(request):
    """
    Context processor untuk menyediakan saklar konfigurasi platform
    seperti DEPOSIT_MODE pada seluruh template.
    """
    mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
    data = {
        'DEPOSIT_MODE': mode,
        'is_deposit_off': mode == 'off',
        'is_deposit_optional': mode == 'optional',
    }
    return {
        **data,
        'platform_settings': data,
    }


def site_branding(request):
    """
    Context processor untuk menyediakan nama merek, logotype (dua bagian:
    teks gelap dan biru), tagline, nama singkat (short name), domain,
    batas penarikan, serta pengaturan komisi platform.
    """
    from django.utils.safestring import mark_safe
    site_name = getattr(settings, 'SITE_NAME', 'Collective Campus')
    site_short_name = getattr(settings, 'SITE_SHORT_NAME', 'Collective')
    dark = getattr(settings, 'SITE_LOGOTYPE_DARK', 'Collective')
    accent = getattr(settings, 'SITE_LOGOTYPE_ACCENT', 'Campus')
    logotype_dict = {
        'dark': dark,
        'accent': accent,
        'blue': accent,
        'html': mark_safe(f'<span class="text-ink">{dark}</span><span class="text-brand">{accent}</span>'),
    }
    tagline = getattr(settings, 'SITE_TAGLINE', 'Saling sewa, saling jual, saling bantu.')
    domain = getattr(settings, 'SITE_DOMAIN', '')
    konfirmasi_budaya = getattr(settings, 'KONFIRMASI_BUDAYA', 'tidak').lower().strip()

    commission_sewa = getattr(settings, 'PLATFORM_COMMISSION_PERCENT', 8)
    commission_sale = getattr(settings, 'SALE_COMMISSION_PERCENT', 5)
    commission_sale_min = getattr(settings, 'SALE_COMMISSION_MIN', 2000)
    withdrawal_min = getattr(settings, 'WITHDRAWAL_MIN', 20000)

    return {
        'SITE_NAME': site_name,
        'site_name': site_name,
        'SITE_SHORT_NAME': site_short_name,
        'site_short_name': site_short_name,
        'SITE_LOGOTYPE_DARK': dark,
        'SITE_LOGOTYPE_ACCENT': accent,
        'SITE_LOGOTYPE_BLUE': accent,
        'SITE_LOGOTYPE': logotype_dict,
        'site_logotype': logotype_dict,
        'SITE_TAGLINE': tagline,
        'site_tagline': tagline,
        'SITE_DOMAIN': domain,
        'site_domain': domain,
        'KONFIRMASI_BUDAYA': konfirmasi_budaya,
        'is_budaya_confirmed': konfirmasi_budaya == 'ya',
        'SUPPORT_EMAIL': getattr(settings, 'SUPPORT_EMAIL', 'bantuan@collectivecampus.id'),
        'platform_commission_percent': commission_sewa,
        'sale_commission_percent': commission_sale,
        'sale_commission_min': commission_sale_min,
        'WITHDRAWAL_MIN': withdrawal_min,
        'withdrawal_min': withdrawal_min,
    }


