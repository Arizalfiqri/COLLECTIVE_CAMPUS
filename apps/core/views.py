from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Count, Q
from django.conf import settings
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required

from apps.catalog.models import Category, Item
from apps.trust.services import calculate_minimum_deposit, calculate_protection_fee, get_tier_info
from .models import Notification


def _calculate_rental_amounts_helper(price_per_day, days, tier, estimated_value, use_protection):
    """Fungsi helper internal untuk perhitungan biaya sewa sesuai aturan resmi platform."""
    price_per_day = max(0, int(price_per_day or 0))
    days = max(1, int(days or 1))
    estimated_value = max(0, int(estimated_value or 0))
    tier = tier if tier in ['baru', 'tepercaya', 'sangat_tepercaya'] else 'baru'

    tier_info = get_tier_info(tier)
    max_item_value = tier_info.get('max_item_value', 750000)

    tier_label_map = {
        'baru': 'Penyewa baru',
        'tepercaya': 'Penyewa tepercaya',
        'sangat_tepercaya': 'Penyewa sangat tepercaya',
    }
    tier_label = tier_label_map.get(tier, 'Penyewa baru')
    commission_pct = getattr(settings, 'PLATFORM_COMMISSION_PERCENT', 8)

    # Validasi batas nilai barang terhadap batas tingkat penyewa (AGENT.md & SPEC)
    if estimated_value > max_item_value:
        formatted_max = f"Rp{max_item_value:,}".replace(',', '.')
        error_msg = f"{tier_label} dapat menyewa barang hingga {formatted_max}."
        return {
            'price_per_day': price_per_day,
            'days': days,
            'tier': tier,
            'estimated_value': estimated_value,
            'use_protection': use_protection,
            'max_item_value': max_item_value,
            'is_exceeded': True,
            'error_message': error_msg,
            'is_mandatory_protection': False,
            'rent_total': None,
            'commission_pct': commission_pct,
            'commission': None,
            'owner_net': None,
            'deposit': None,
            'protection_fee': None,
            'grand_total': None,
            'real_cost': None,
        }

    rent_total = price_per_day * days
    commission = round(rent_total * commission_pct / 100)
    owner_net = rent_total - commission

    deposit = calculate_minimum_deposit(estimated_value, renter_tier=tier, is_cross_campus=False)
    prot_calc = calculate_protection_fee(rent_total, estimated_value)
    protection_fee = prot_calc['fee'] if use_protection else 0

    grand_total = rent_total + deposit + protection_fee
    real_cost = rent_total + protection_fee

    return {
        'price_per_day': price_per_day,
        'days': days,
        'tier': tier,
        'estimated_value': estimated_value,
        'use_protection': use_protection,
        'max_item_value': max_item_value,
        'is_exceeded': False,
        'error_message': None,
        'is_mandatory_protection': prot_calc.get('is_mandatory', False),
        'rent_total': rent_total,
        'commission_pct': commission_pct,
        'commission': commission,
        'owner_net': owner_net,
        'deposit': deposit,
        'protection_fee': protection_fee,
        'grand_total': grand_total,
        'real_cost': real_cost,
    }


def home(request):
    """Halaman beranda KampusRent."""
    # 1e: Hitung barang populer dari sewa 7 hari terakhir
    seven_days_ago = timezone.now() - timedelta(days=7)
    items_with_recent_rentals = list(
        Item.objects
        .filter(is_active=True)
        .annotate(
            recent_rentals_count=Count('rentals', filter=Q(rentals__created_at__gte=seven_days_ago))
        )
        .filter(recent_rentals_count__gt=0)
        .select_related('owner', 'category', 'owner__trust_score', 'owner__student_profile__campus')
        .prefetch_related('photos')
        .order_by('-recent_rentals_count', '-created_at')[:8]
    )

    if len(items_with_recent_rentals) >= 4:
        featured_items = items_with_recent_rentals
        featured_section_title = "Barang populer"
        featured_section_subtitle = "Paling banyak disewa minggu ini"
    else:
        featured_items = list(
            Item.objects
            .filter(is_active=True)
            .select_related('owner', 'category', 'owner__trust_score', 'owner__student_profile__campus')
            .prefetch_related('photos')
            .order_by('-created_at')[:8]
        )
        featured_section_title = "Barang terbaru"
        featured_section_subtitle = "Baru dipasang oleh mahasiswa"

    # 1d: Hanya kategori yang punya minimal 1 barang aktif, urut jumlah barang terbanyak,
    # 'Lainnya' selalu terakhir dan hanya bila punya barang.
    active_cats = list(
        Category.objects
        .filter(items__is_active=True)
        .annotate(active_items_count=Count('items', filter=Q(items__is_active=True)))
        .filter(active_items_count__gte=1)
    )
    standard_cats = [c for c in active_cats if c.slug not in ('lain-lain', 'lainnya')]
    other_cats = [c for c in active_cats if c.slug in ('lain-lain', 'lainnya')]

    standard_cats.sort(key=lambda c: (-c.active_items_count, c.order, c.name))
    other_cats.sort(key=lambda c: (-c.active_items_count, c.order, c.name))

    categories = standard_cats + other_cats

    # 1c: 3 kategori dengan barang aktif terbanyak untuk pencarian populer
    all_by_count = sorted(active_cats, key=lambda c: (-c.active_items_count, c.name))
    popular_search_categories = all_by_count[:3]

    # Hero sisi kanan: tampilkan 3 barang terbaru yang NYATA bila ada
    hero_items = (
        Item.objects
        .filter(is_active=True)
        .select_related('owner', 'category', 'owner__trust_score', 'owner__student_profile__campus')
        .prefetch_related('photos')
        .order_by('-created_at')[:3]
    )

    # Kategori jual beli dan barang jualan terbaru (Fase 8A Butir 8)
    from apps.sales.models import SaleItem
    from apps.accounts.models import Campus
    now = timezone.now()
    sale_categories = list(Category.objects.for_sale().order_by('order', 'name'))
    latest_sale_items = list(
        SaleItem.objects.filter(
            status=SaleItem.Status.AKTIF,
            expires_at__gt=now
        )
        .select_related('owner', 'category', 'owner__student_profile__campus')
        .prefetch_related('photos')
        .order_by('-created_at')[:8]
    )
    hero_sale_items = latest_sale_items[:3]
    campuses = list(Campus.objects.filter(is_active=True).order_by('name'))

    # Kalkulator sewa interaktif awal untuk SSR (nilai bawaan: Rp40.000/hari, 3 hari, barang Rp500.000)
    initial_calc = _calculate_rental_amounts_helper(
        price_per_day=40000,
        days=3,
        tier='baru',
        estimated_value=500000,
        use_protection=True,
    )

    return render(request, 'home.html', {
        'featured_items': featured_items,
        'featured_section_title': "Disewakan terbaru",
        'featured_section_subtitle': "Perlengkapan kuliah yang dapat kamu sewa dari sesama mahasiswa",
        'popular_items': featured_items,
        'hero_items': hero_items,
        'hero_sale_items': hero_sale_items,
        'categories': categories,
        'sale_categories': sale_categories,
        'latest_sale_items': latest_sale_items,
        'popular_search_categories': popular_search_categories,
        'campuses': campuses,
        'calc': initial_calc,
    })


def rental_calculator_view(request):
    """
    Endpoint HTMX /kalkulator-sewa/ untuk kalkulator biaya sewa interaktif
    menggunakan aturan bisnis nyata platform:
    - calculate_minimum_deposit (tangga kepercayaan)
    - calculate_protection_fee (Dana Gotong Royong)
    - PLATFORM_COMMISSION_PERCENT (komisi 8%)
    """
    raw_ppd = str(request.GET.get('price_per_day', '40000')).replace('.', '').replace(' ', '')
    try:
        price_per_day = int(raw_ppd)
    except (ValueError, TypeError):
        price_per_day = 40000

    raw_days = str(request.GET.get('days', '3')).replace('.', '').replace(' ', '')
    try:
        days = int(raw_days)
    except (ValueError, TypeError):
        days = 3

    tier = request.GET.get('tier', 'baru')

    raw_val = str(request.GET.get('estimated_value', '500000')).replace('.', '').replace(' ', '')
    try:
        estimated_value = int(raw_val)
    except (ValueError, TypeError):
        estimated_value = 500000

    use_protection = request.GET.get('use_protection', '1') in ['1', 'true', 'on']

    calc = _calculate_rental_amounts_helper(
        price_per_day=price_per_day,
        days=days,
        tier=tier,
        estimated_value=estimated_value,
        use_protection=use_protection,
    )

    return render(request, 'core/partials/rental_calculator.html', {'calc': calc})


def notifications_view(request):
    """
    Pengalihan /notifikasi/ ke dashboard.
    Notifikasi kini disajikan melalui panel modal/dropdown HTMX sesuai spesifikasi Fase 7A.
    """
    return redirect('/dashboard/')


@login_required(login_url='/masuk/')
def notification_panel_view(request):
    """
    Endpoint partial modal notifikasi HTMX (/notifikasi/panel/).
    Mengembalikan 20 item notifikasi terbaru, mendukung 'Muat lebih banyak',
    serta otomatis menandai notifikasi yang ditampilkan sebagai terbaca dan
    memperbarui badge lonceng navbar via HTMX OOB swap.
    """
    notifs_qs = Notification.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(notifs_qs, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Tandai notifikasi yang ditampilkan pada halaman ini sebagai terbaca
    displayed_ids = [n.id for n in page_obj.object_list if not n.is_read]
    if displayed_ids:
        Notification.objects.filter(id__in=displayed_ids).update(is_read=True)

    return render(request, 'core/partials/notification_panel.html', {
        'notifications': page_obj.object_list,
        'page_obj': page_obj,
    })


def mark_all_notifications_read_htmx(request):
    """Menandai seluruh notifikasi user sebagai sudah dibaca via HTMX."""
    if not request.user.is_authenticated:
        return HttpResponseForbidden("Silakan masuk terlebih dahulu.")

    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    notifs_qs = Notification.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(notifs_qs, 20)
    page_obj = paginator.get_page(1)

    return render(request, 'core/partials/notification_panel.html', {
        'notifications': page_obj.object_list,
        'page_obj': page_obj,
    })


def notification_click_view(request, pk):
    """
    GET /notifikasi/<int:pk>/
    Membuka notifikasi spesifik: menandai sebagai terbaca dan mengarahkan langsung
    ke URL rincian sewa terkait (atau ke /dashboard/ bila tidak ada URL).
    """
    if not request.user.is_authenticated:
        return redirect(f'/masuk/?next=/notifikasi/{pk}/')
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notif.is_read:
        notif.is_read = True
        notif.save(update_fields=['is_read', 'updated_at'])
    if notif.url:
        target_url = notif.url
        if ('penarikan' in notif.title.lower() or 'pencairan' in notif.title.lower()) and target_url == '/dompet/':
            target_url = '/dompet/#riwayat-penarikan'
        return redirect(target_url)
    return redirect('/dashboard/')


def tentang_view(request):
    """Halaman Tentang KampusRent (/tentang/)."""
    return render(request, 'core/tentang.html')


def bantuan_view(request):
    """Halaman Pusat Bantuan & Pertanyaan Umum / FAQ (/bantuan/)."""
    return render(request, 'core/bantuan.html')


def syarat_ketentuan_view(request):
    """Halaman Syarat dan Ketentuan Layanan (/syarat-ketentuan/)."""
    return render(request, 'core/syarat_ketentuan.html')


def kebijakan_privasi_view(request):
    """Halaman Kebijakan Privasi & PDP (/kebijakan-privasi/)."""
    return render(request, 'core/kebijakan_privasi.html')


def panduan_komunitas_view(request):
    """Halaman Panduan Komunitas & Etika Sewa (/panduan-komunitas/)."""
    return render(request, 'core/panduan_komunitas.html')


def kontak_view(request):
    """Halaman Kontak & Layanan Dukungan (/kontak/)."""
    support_email = getattr(settings, 'SUPPORT_EMAIL', 'bantuan@kampusrent.id')
    return render(request, 'core/kontak.html', {'support_email': support_email})


def csrf_failure_view(request, reason=""):
    """Tampilan kustom saat kegagalan verifikasi token CSRF (403 Forbidden)."""
    return render(request, '403_csrf.html', {'reason': reason}, status=403)


def handler404(request, exception=None):
    """Tampilan kustom 404 Tidak Ditemukan."""
    return render(request, '404.html', status=404)


def handler500(request):
    """Tampilan kustom 500 Kesalahan Server."""
    return render(request, '500.html', status=500)


def handler403(request, exception=None):
    """Tampilan kustom 403 Akses Ditolak."""
    return render(request, '403.html', status=403)


def robots_txt_view(request):
    """File robots.txt dinamis untuk mesin pencari publik."""
    content = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /dashboard/\n"
        "Disallow: /sewa/\n"
        "Disallow: /verifikasi/\n"
        "Disallow: /pesan/\n"
        "Disallow: /midtrans/\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml\n"
    )
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


def sitemap_xml_view(request):
    """Sitemap XML untuk halaman publik platform KampusRent."""
    base_url = f"{request.scheme}://{request.get_host()}"
    static_urls = [
        ('/', 'daily', '1.0'),
        ('/barang/', 'hourly', '0.9'),
        ('/tentang/', 'monthly', '0.5'),
        ('/bantuan/', 'weekly', '0.7'),
        ('/syarat-ketentuan/', 'monthly', '0.4'),
        ('/kebijakan-privasi/', 'monthly', '0.4'),
        ('/panduan-komunitas/', 'monthly', '0.4'),
        ('/kontak/', 'monthly', '0.6'),
    ]

    items = Item.objects.filter(is_active=True).values('slug', 'updated_at')[:500]

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for path, changefreq, priority in static_urls:
        xml.append('  <url>')
        xml.append(f'    <loc>{base_url}{path}</loc>')
        xml.append(f'    <changefreq>{changefreq}</changefreq>')
        xml.append(f'    <priority>{priority}</priority>')
        xml.append('  </url>')

    for item in items:
        xml.append('  <url>')
        xml.append(f'    <loc>{base_url}/barang/{item["slug"]}/</loc>')
        xml.append('    <changefreq>weekly</changefreq>')
        xml.append('    <priority>0.8</priority>')
        if item.get('updated_at'):
            xml.append(f'    <lastmod>{item["updated_at"].strftime("%Y-%m-%d")}</lastmod>')
        xml.append('  </url>')

    xml.append('</urlset>')
    return HttpResponse('\n'.join(xml), content_type="application/xml; charset=utf-8")


def preview_card_fallback_view(request):
    """Pratinjau visual kartu barang tanpa foto untuk membuktikan cadangan template (Fase 7B-Fix)."""
    if not settings.DEBUG:
        return HttpResponseForbidden("Hanya dapat diakses saat DEBUG=True.")

    first_item = Item.objects.select_related('owner', 'category', 'owner__trust_score').first()

    class MockItem:
        pass

    mock = MockItem()
    mock.slug = 'kamera-mirrorless-demo'
    mock.title = 'Canon EOS M50 Mark II (Tanpa Foto)'
    mock.price_per_day = 75000
    mock.pickup_area = 'Gedung Sains & Seni'
    mock.primary_photo = None
    mock.owner = first_item.owner if first_item else None

    return render(request, 'dev/preview_fallback.html', {'mock_item': mock})


def dev_login_as_view(request, username):
    """Dev helper for automated screenshot capture under DEBUG=True."""
    if not settings.DEBUG:
        return HttpResponseForbidden("Hanya dapat diakses saat DEBUG=True.")
    from django.contrib.auth import get_user_model, login
    from django.http import HttpResponseNotFound
    User = get_user_model()
    user = User.objects.filter(username=username).first()
    if not user:
        return HttpResponseNotFound("User tidak ditemukan")
    login(request, user)
    next_url = request.GET.get('next', '/dashboard/')
    return redirect(next_url)


def admin_broadcast_announcement_view(request):
    """Halaman pengumuman massal staf (/admin/pengumuman/): mengirimkan notifikasi ke semua pengguna aktif."""
    if not (request.user.is_authenticated and request.user.is_staff):
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path(), login_url='admin:login')

    from django.contrib.auth import get_user_model
    from django.contrib import messages
    User = get_user_model()
    active_count = User.objects.filter(is_active=True).count()

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        message = request.POST.get('message', '').strip()
        url = request.POST.get('url', '').strip()
        if not message:
            messages.error(request, "Isi pesan pengumuman wajib diisi.")
        else:
            active_users = User.objects.filter(is_active=True)
            notifs = [
                Notification(
                    user=u,
                    title=title or "Pengumuman Platform KampusRent",
                    message=message,
                    url=url
                )
                for u in active_users
            ]
            Notification.objects.bulk_create(notifs)
            messages.success(request, f"Pengumuman berhasil disiarkan kepada {len(notifs)} pengguna aktif.")
            return redirect('core:admin_broadcast_announcement')

    return render(request, 'admin/broadcast_announcement.html', {
        'active_count': active_count,
        'title': 'Kirim Pengumuman Massal Platform',
    })


def admin_rental_chart_htmx(request):
    """Partial HTMX untuk memperbarui tab grafik laporan sewa (7, 30, 90 hari)."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponseForbidden("Akses hanya untuk staf.")
    days = request.GET.get('days', 30)
    from apps.core.services import get_rental_chart_data
    chart = get_rental_chart_data(days)
    return render(request, 'admin/partials/rental_chart.html', {
        'admin_rental_chart': chart,
    })


def admin_recent_transactions_htmx(request):
    """Partial HTMX untuk pencarian transaksi terbaru pada tabel Saledash."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponseForbidden("Akses hanya untuk staf.")
    q = request.GET.get('q', '').strip()
    from apps.core.services import get_recent_rentals
    rentals = get_recent_rentals(search_query=q, limit=8)
    return render(request, 'admin/partials/recent_transactions_table.html', {
        'admin_recent_rentals': rentals,
    })




