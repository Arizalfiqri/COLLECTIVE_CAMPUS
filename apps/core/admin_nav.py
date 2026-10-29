import datetime
from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from apps.core.services import get_staff_operational_stats


MENU_CONFIG = [
    {
        'id': 'ikhtisar',
        'title': 'Ikhtisar',
        'icon': 'layout-dashboard',
        'is_single': True,
        'url_name': 'admin:index',
        'perm': None,
    },
    {
        'id': 'operasional',
        'title': 'Operasional',
        'icon': 'activity',
        'badge_key': 'total_queue',
        'items': [
            {'title': 'Antrean KTM', 'url_name': 'admin:verification_ktmverification_changelist', 'perm': 'verification.view_ktmverification'},
            {'title': 'Penarikan dana', 'url_name': 'payments:admin_withdrawals', 'perm': 'payments.view_withdrawalrequest'},
            {'title': 'Sengketa', 'url_name': 'admin:rentals_dispute_changelist', 'perm': 'rentals.view_dispute'},
            {'title': 'Laporan listing jualan', 'url_name': 'admin:sales_saleitemreport_changelist', 'perm': 'sales.view_saleitemreport'},
            {'title': 'Rekonsiliasi', 'url_name': 'payments:admin_reconciliation', 'perm': 'payments.view_ledgerentry'},
        ]
    },
    {
        'id': 'pengguna',
        'title': 'Pengguna',
        'icon': 'users',
        'items': [
            {'title': 'Pengguna', 'url_name': 'admin:accounts_user_changelist', 'perm': 'accounts.view_user'},
            {'title': 'Profil mahasiswa', 'url_name': 'admin:accounts_studentprofile_changelist', 'perm': 'accounts.view_studentprofile'},
            {'title': 'Kampus', 'url_name': 'admin:accounts_campus_changelist', 'perm': 'accounts.view_campus'},
            {'title': 'Titik temu', 'url_name': 'admin:accounts_meetingpoint_changelist', 'perm': 'accounts.view_meetingpoint'},
            {'title': 'NIM diblokir', 'url_name': 'admin:accounts_blacklistednim_changelist', 'perm': 'accounts.view_blacklistednim'},
            {'title': 'Riwayat pembekuan', 'url_name': 'admin:accounts_suspensionrecord_changelist', 'perm': 'accounts.view_suspensionrecord'},
        ]
    },
    {
        'id': 'katalog',
        'title': 'Katalog',
        'icon': 'layers',
        'items': [
            {'title': 'Barang', 'url_name': 'admin:catalog_item_changelist', 'perm': 'catalog.view_item'},
            {'title': 'Foto barang', 'url_name': 'admin:catalog_itemphoto_changelist', 'perm': 'catalog.view_itemphoto'},
            {'title': 'Kategori', 'url_name': 'admin:catalog_category_changelist', 'perm': 'catalog.view_category'},
        ]
    },
    {
        'id': 'jual_beli',
        'title': 'Jual beli',
        'icon': 'tag',
        'items': [
            {'title': 'Barang jualan', 'url_name': 'admin:sales_saleitem_changelist', 'perm': 'sales.view_saleitem'},
            {'title': 'Foto barang jualan', 'url_name': 'admin:sales_saleitemphoto_changelist', 'perm': 'sales.view_saleitemphoto'},
            {'title': 'Pesanan jual beli', 'url_name': 'admin:sales_saleorder_changelist', 'perm': 'sales.view_saleorder'},
            {'title': 'Sengketa jual beli', 'url_name': 'admin:sales_saledispute_changelist', 'perm': 'sales.view_saledispute'},
            {'title': 'Laporan barang jualan', 'url_name': 'admin:sales_saleitemreport_changelist', 'perm': 'sales.view_saleitemreport'},
            {'title': 'Ulasan jual beli', 'url_name': 'admin:sales_salereview_changelist', 'perm': 'sales.view_salereview'},
            {'title': 'Perjanjian jual beli', 'url_name': 'admin:sales_saleagreement_changelist', 'perm': 'sales.view_saleagreement'},
            {'title': 'Persetujuan S&K penjual', 'url_name': 'admin:sales_sellertermsacceptance_changelist', 'perm': 'sales.view_sellertermsacceptance'},
        ]
    },
    {
        'id': 'transaksi',
        'title': 'Transaksi',
        'icon': 'shopping-bag',
        'items': [
            {'title': 'Sewa', 'url_name': 'admin:rentals_rental_changelist', 'perm': 'rentals.view_rental'},
            {'title': 'Pembayaran', 'url_name': 'admin:payments_payment_changelist', 'perm': 'payments.view_payment'},
            {'title': 'Deposit ditahan', 'url_name': 'admin:payments_deposithold_changelist', 'perm': 'payments.view_deposithold'},
            {'title': 'Payout', 'url_name': 'admin:payments_payout_changelist', 'perm': 'payments.view_payout'},
            {'title': 'Buku besar', 'url_name': 'admin:payments_ledgerentry_changelist', 'perm': 'payments.view_ledgerentry'},
            {'title': 'Perjanjian sewa', 'url_name': 'admin:rentals_rentalagreement_changelist', 'perm': 'rentals.view_rentalagreement'},
            {'title': 'Jadwal serah terima', 'url_name': 'admin:rentals_handoverschedule_changelist', 'perm': 'rentals.view_handoverschedule'},
            {'title': 'Foto kondisi', 'url_name': 'admin:rentals_conditionphoto_changelist', 'perm': 'rentals.view_conditionphoto'},
            {'title': 'Ulasan', 'url_name': 'admin:rentals_review_changelist', 'perm': 'rentals.view_review'},
        ]
    },
    {
        'id': 'keuangan',
        'title': 'Keuangan',
        'icon': 'wallet',
        'items': [
            {'title': 'Transaksi dompet', 'url_name': 'admin:payments_wallettransaction_changelist', 'perm': 'payments.view_wallettransaction'},
            {'title': 'Permintaan penarikan dana', 'url_name': 'admin:payments_withdrawalrequest_changelist', 'perm': 'payments.view_withdrawalrequest'},
            {'title': 'Log akses rekening', 'url_name': 'admin:payments_withdrawalaccountaccesslog_changelist', 'perm': 'payments.view_withdrawalaccountaccesslog'},
        ]
    },
    {
        'id': 'skor_ml',
        'title': 'Skor dan ML',
        'icon': 'trending-up',
        'items': [
            {'title': 'Skor kepercayaan', 'url_name': 'admin:trust_trustscore_changelist', 'perm': 'trust.view_trustscore'},
            {'title': 'Evaluasi model', 'url_name': 'trust:admin_model_score', 'perm': None},
            {'title': 'Contoh pelatihan', 'url_name': 'admin:trust_trusttrainingexample_changelist', 'perm': 'trust.view_trusttrainingexample'},
            {'title': 'Versi model', 'url_name': 'admin:trust_trustmodelversion_changelist', 'perm': 'trust.view_trustmodelversion'},
        ]
    },
    {
        'id': 'komunikasi',
        'title': 'Komunikasi',
        'icon': 'message-square',
        'items': [
            {'title': 'Percakapan', 'url_name': 'admin:chat_conversation_changelist', 'perm': 'chat.view_conversation'},
            {'title': 'Pesan', 'url_name': 'admin:chat_message_changelist', 'perm': 'chat.view_message'},
            {'title': 'Notifikasi', 'url_name': 'admin:core_notification_changelist', 'perm': 'core.view_notification'},
            {'title': 'Pengumuman massal', 'url_name': 'core:admin_broadcast_announcement', 'perm': None},
        ]
    },
    {
        'id': 'sistem',
        'title': 'Sistem',
        'icon': 'settings',
        'items': [
            {'title': 'Grup', 'url_name': 'admin:auth_group_changelist', 'perm': 'auth.view_group'},
            {'title': 'Django admin penuh', 'url_name': 'admin:index', 'perm': None},
        ]
    },
]


def resolve_url(url_name):
    """Mencoba me-reverse nama URL, jika gagal kembalikan string apa adanya."""
    try:
        return reverse(url_name)
    except NoReverseMatch:
        if url_name.startswith('/'):
            return url_name
        return f"/admin/{url_name.replace(':', '/')}/"


def get_cached_staff_stats():
    """Mengambil statistik antrean operasional staf dengan cache 30 detik."""
    cache_key = 'admin_staff_stats_cache'
    stats = cache.get(cache_key)
    if stats is None:
        stats = get_staff_operational_stats()
        cache.set(cache_key, stats, timeout=30)
    return stats


def get_time_greeting(user):
    """Menghasilkan sapaan waktu Indonesia formal (sentence case)."""
    current_hour = timezone.localtime().hour
    if 4 <= current_hour < 11:
        sapaan = "Selamat pagi"
    elif 11 <= current_hour < 15:
        sapaan = "Selamat siang"
    elif 15 <= current_hour < 18:
        sapaan = "Selamat sore"
    else:
        sapaan = "Selamat malam"

    nama_depan = user.first_name or (user.full_name.split()[0] if getattr(user, 'full_name', '') else user.username)
    return f"{sapaan}, {nama_depan}"


def get_indonesian_date_chip():
    """Menghasilkan tanggal format Indonesia, contoh: Minggu, 18 Okt 2026."""
    now = timezone.localtime()
    hari_map = {
        0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis',
        4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'
    }
    bulan_map = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mei', 6: 'Jun',
        7: 'Jul', 8: 'Ags', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Des'
    }
    hari = hari_map.get(now.weekday(), '')
    bulan = bulan_map.get(now.month, '')
    return f"{hari}, {now.day} {bulan} {now.year}"


def get_admin_navigation(request):
    """
    Menyusun struktur navigasi sidebar akordeon untuk pengguna staf yang sedang login.
    Menjamin:
    - Hanya item yang pengguna memiliki izin yang tampil.
    - Menandai item dan grup yang aktif berdasarkan request.path.
    - HANYA SATU grup yang aktif/terbuka saat halaman dimuat.
    - Memasukkan lencana angka antrean bila ada.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_staff:
        return []

    path = request.path
    stats = get_cached_staff_stats()

    nav_groups = []
    matched_group_id = None
    best_match_len = -1
    best_item_ref = None

    # Langkah 1: Bangun daftar grup dan item yang memiliki izin
    for g in MENU_CONFIG:
        # Single link item (misal Ikhtisar)
        if g.get('is_single'):
            url = resolve_url(g['url_name'])
            is_active = (path == url) or (url != '/admin/' and path.startswith(url))
            group_data = {
                'id': g['id'],
                'title': g['title'],
                'icon': g['icon'],
                'is_single': True,
                'url': url,
                'is_active': is_active,
                'is_open': is_active,
                'items': [],
                'badge': 0,
            }
            if is_active:
                matched_group_id = g['id']
            nav_groups.append(group_data)
            continue

        # Accordion group
        visible_items = []
        for it in g.get('items', []):
            perm = it.get('perm')
            if perm and not (user.is_superuser or user.has_perm(perm)):
                continue

            item_url = resolve_url(it['url_name'])
            is_item_active = False

            if path == item_url:
                is_item_active = True
                match_len = len(item_url)
            elif item_url != '/admin/' and path.startswith(item_url):
                is_item_active = True
                match_len = len(item_url)
            else:
                match_len = -1

            item_dict = {
                'title': it['title'],
                'url': item_url,
                'is_active': False,  # Diisi final setelah best match comparison
            }
            visible_items.append((item_dict, is_item_active, match_len, g['id']))

        if not visible_items:
            continue

        badge_val = 0
        if g.get('badge_key') == 'total_queue':
            badge_val = stats.get('total_queue', 0)

        nav_groups.append({
            'id': g['id'],
            'title': g['title'],
            'icon': g['icon'],
            'is_single': False,
            'url': None,
            'is_active': False,
            'is_open': False,
            'items': [x[0] for x in visible_items],
            'badge': badge_val,
            '_raw_matches': visible_items,
        })

    # Langkah 2: Cari best match spesifik (paling panjang URL-nya) agar hanya SATU item & SATU grup aktif
    active_group_id = None
    longest_match = -1
    target_item_dict = None

    for g_dict in nav_groups:
        if g_dict.get('is_single'):
            if g_dict['is_active'] and len(g_dict['url']) > longest_match:
                longest_match = len(g_dict['url'])
                active_group_id = g_dict['id']
            continue

        for item_dict, is_act, m_len, g_id in g_dict.get('_raw_matches', []):
            if is_act and m_len > longest_match:
                longest_match = m_len
                active_group_id = g_id
                target_item_dict = item_dict

    # Bersihkan _raw_matches dan tetapkan is_active / is_open secara deterministik (HANYA SATU)
    for g_dict in nav_groups:
        g_dict.pop('_raw_matches', None)
        if g_dict['id'] == active_group_id:
            g_dict['is_active'] = True
            g_dict['is_open'] = True
        else:
            g_dict['is_active'] = False
            g_dict['is_open'] = False

    if target_item_dict:
        target_item_dict['is_active'] = True

    # Jika di root /admin/ dan belum ada yang match, default-kan Ikhtisar aktif
    if path == '/admin/' or not active_group_id:
        for g_dict in nav_groups:
            if g_dict['id'] == 'ikhtisar':
                g_dict['is_active'] = True
                g_dict['is_open'] = True
                break

    return nav_groups
