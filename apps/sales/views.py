import logging
from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, Http404, FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

from apps.accounts.decorators import verified_student_required
from apps.accounts.models import Campus
from apps.catalog.forms import validate_uploaded_photos
from apps.catalog.models import Category
from apps.sales.forms import SaleItemForm
from apps.sales.models import SaleItem, SaleItemPhoto, SaleOrder, SaleAgreement, SaleDispute, SaleReview, SaleOffer
from apps.sales.services import (
    get_seller_tier,
    get_seller_max_price,
    get_active_seller_terms,
    get_active_buyer_terms,
    record_seller_terms_acceptance,
    record_buyer_terms_agreement,
    extend_sale_item_listing,
    create_sale_order,
    mark_sale_order_paid,
    set_sale_order_meetup,
    mark_sale_order_handed_over,
    confirm_sale_order_received,
    settle_sale_order,
    cancel_sale_order,
    open_sale_dispute,
    create_sale_review,
    create_sale_offer,
    accept_sale_offer,
    reject_sale_offer,
    cancel_sale_offer,
    SaleOrderError,
    SaleOrderStateError,
    SaleOrderPermissionError,
    SaleOrderValidationError,
    SELLER_TIER_LABELS,
    SELLER_TIER_CHIP_CLASSES,
)


@login_required(login_url='/masuk/')
@verified_student_required
def sale_item_create_view(request):
    """
    Halaman pasang barang jualan baru (/jual/baru/).
    Wajib terverifikasi KTM dan akun tidak dibekukan.
    """
    user = request.user
    if getattr(user, 'is_suspended', False):
        messages.error(request, "Akun Anda sedang dibekukan sehingga tidak dapat memasang barang jualan.")
        return redirect('accounts:dashboard')

    seller_tier = get_seller_tier(user)
    max_price = get_seller_max_price(seller_tier)
    seller_terms = get_active_seller_terms()
    categories = Category.objects.for_sale().order_by('order', 'name')

    photo_errors = []

    if request.method == 'POST':
        form = SaleItemForm(request.POST, user=user)
        photo_files = request.FILES.getlist('photos')

        valid_photos, p_errors = validate_uploaded_photos(photo_files, existing_count=0)
        photo_errors.extend(p_errors)

        if len(photo_files) < 1:
            photo_errors.append("Wajib mengunggah minimal 1 foto barang jualan.")
        elif len(photo_files) > 6:
            photo_errors.append("Maksimal 6 foto yang dapat diunggah.")

        if form.is_valid() and not photo_errors:
            item = form.save(commit=False)
            item.owner = user
            item.status = SaleItem.Status.AKTIF
            item.save()

            # Simpan foto-foto barang
            for order_idx, p_file in enumerate(valid_photos, start=1):
                SaleItemPhoto.objects.create(
                    sale_item=item,
                    image=p_file,
                    order=order_idx
                )

            # Simpan pencatatan persetujuan S&K Penjual
            if seller_terms:
                ip_addr = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')
                if ip_addr and ',' in ip_addr:
                    ip_addr = ip_addr.split(',')[0].strip()
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                record_seller_terms_acceptance(
                    user=user,
                    terms_version=seller_terms,
                    ip_address=ip_addr,
                    user_agent=user_agent
                )

            messages.success(request, f"Barang jualan '{item.title}' berhasil dipasang dan kini aktif di katalog.")
            return redirect('sales:my_items')
    else:
        form = SaleItemForm(user=user)

    return render(request, 'sales/item_form.html', {
        'form': form,
        'is_edit': False,
        'categories': categories,
        'seller_tier': seller_tier,
        'seller_tier_label': SELLER_TIER_LABELS.get(seller_tier, seller_tier),
        'max_price': max_price,
        'seller_terms': seller_terms,
        'photo_errors': photo_errors,
    })


@login_required(login_url='/masuk/')
def my_sale_items_view(request):
    """
    Halaman kelola barang jualan saya (/jual/saya/).
    Mendukung tab: aktif, dipesan, terjual, nonaktif.
    """
    user = request.user
    tab = request.GET.get('tab', 'aktif').lower().strip()
    if tab not in ('aktif', 'dipesan', 'terjual', 'nonaktif'):
        tab = 'aktif'

    base_qs = SaleItem.objects.filter(owner=user).select_related('category').prefetch_related('photos')

    aktif_count = base_qs.filter(status=SaleItem.Status.AKTIF).count()
    dipesan_count = base_qs.filter(status=SaleItem.Status.DIPESAN).count()
    terjual_count = base_qs.filter(status=SaleItem.Status.TERJUAL).count()
    nonaktif_count = base_qs.filter(status__in=[SaleItem.Status.NONAKTIF, SaleItem.Status.KEDALUWARSA]).count()

    if tab == 'aktif':
        items = base_qs.filter(status=SaleItem.Status.AKTIF)
    elif tab == 'dipesan':
        items = base_qs.filter(status=SaleItem.Status.DIPESAN)
    elif tab == 'terjual':
        items = base_qs.filter(status=SaleItem.Status.TERJUAL)
    else:  # nonaktif
        items = base_qs.filter(status__in=[SaleItem.Status.NONAKTIF, SaleItem.Status.KEDALUWARSA])

    return render(request, 'sales/my_items.html', {
        'items': items,
        'current_tab': tab,
        'aktif_count': aktif_count,
        'dipesan_count': dipesan_count,
        'terjual_count': terjual_count,
        'nonaktif_count': nonaktif_count,
        'seller_tier': get_seller_tier(user),
        'seller_tier_label': SELLER_TIER_LABELS.get(get_seller_tier(user), 'Penjual baru'),
    })


@login_required(login_url='/masuk/')
def sale_item_edit_view(request, slug):
    """
    Halaman ubah barang jualan (/jual/<slug>/ubah/).
    """
    item = get_object_or_404(SaleItem, slug=slug, owner=request.user)
    seller_tier = get_seller_tier(request.user)
    max_price = get_seller_max_price(seller_tier)
    categories = Category.objects.for_sale().order_by('order', 'name')

    photo_errors = []

    if request.method == 'POST':
        form = SaleItemForm(request.POST, instance=item, user=request.user)
        photo_files = request.FILES.getlist('photos')

        existing_count = item.photos.count()
        valid_photos, p_errors = validate_uploaded_photos(photo_files, existing_count=existing_count)
        photo_errors.extend(p_errors)

        if existing_count + len(photo_files) > 6:
            photo_errors.append("Total foto tidak boleh melebihi 6.")

        if form.is_valid() and not photo_errors:
            item = form.save()

            if valid_photos:
                for idx, p_file in enumerate(valid_photos, start=existing_count + 1):
                    SaleItemPhoto.objects.create(sale_item=item, image=p_file, order=idx)

            messages.success(request, f"Perubahan barang '{item.title}' berhasil disimpan.")
            return redirect('sales:my_items')
    else:
        form = SaleItemForm(instance=item, user=request.user)

    return render(request, 'sales/item_form.html', {
        'form': form,
        'is_edit': True,
        'item': item,
        'categories': categories,
        'seller_tier': seller_tier,
        'seller_tier_label': SELLER_TIER_LABELS.get(seller_tier, seller_tier),
        'max_price': max_price,
        'photo_errors': photo_errors,
    })


@login_required(login_url='/masuk/')
def sale_item_toggle_status_view(request, slug):
    """
    Mengubah status barang antara aktif dan nonaktif (POST only).
    """
    if request.method != 'POST':
        return HttpResponseForbidden("Metode tidak diizinkan.")

    item = get_object_or_404(SaleItem, slug=slug, owner=request.user)

    if item.status == SaleItem.Status.AKTIF:
        item.status = SaleItem.Status.NONAKTIF
        item.save(update_fields=['status', 'updated_at'])
        messages.success(request, f"Barang '{item.title}' berhasil dinonaktifkan.")
        return redirect('/jual/saya/?tab=nonaktif')
    elif item.status in (SaleItem.Status.NONAKTIF, SaleItem.Status.KEDALUWARSA):
        # Jika kedaluwarsa, otomatis perpanjang juga
        now = timezone.now()
        if item.expires_at <= now:
            extend_sale_item_listing(item)
        else:
            item.status = SaleItem.Status.AKTIF
            item.save(update_fields=['status', 'updated_at'])
        messages.success(request, f"Barang '{item.title}' berhasil diaktifkan kembali.")
        return redirect('/jual/saya/?tab=aktif')

    return redirect('sales:my_items')


@login_required(login_url='/masuk/')
def sale_item_extend_view(request, slug):
    """
    Memperpanjang masa tayang listing barang jualan 60 hari (POST only).
    """
    if request.method != 'POST':
        return HttpResponseForbidden("Metode tidak diizinkan.")

    item = get_object_or_404(SaleItem, slug=slug, owner=request.user)
    extend_sale_item_listing(item)
    messages.success(request, f"Masa tayang barang '{item.title}' berhasil diperpanjang 60 hari.")
    return redirect('/jual/saya/?tab=aktif')


def _get_active_sale_campuses():
    """Mengambil daftar kampus yang memiliki barang jualan aktif."""
    now = timezone.now()
    return list(
        Campus.objects.filter(is_active=True)
        .annotate(
            active_items_count=models.Count(
                'student_profiles__user__sale_items',
                filter=models.Q(
                    student_profiles__user__sale_items__status=SaleItem.Status.AKTIF,
                    student_profiles__user__sale_items__expires_at__gt=now
                ),
                distinct=True
            )
        )
        .filter(active_items_count__gt=0)
        .order_by('-active_items_count', 'short_name')
    )


def _get_sale_catalog_queryset(request, active_campuses=None):
    """Filter dan urutkan barang jualan di katalog."""
    now = timezone.now()
    qs = (
        SaleItem.objects
        .filter(status=SaleItem.Status.AKTIF, expires_at__gt=now)
        .select_related('owner', 'owner__student_profile', 'owner__student_profile__campus', 'category')
        .prefetch_related('photos')
    )

    # 1. Filter Kampus
    current_kampus = request.GET.get('kampus')
    user_campus = getattr(getattr(request.user, 'student_profile', None), 'campus', None) if request.user.is_authenticated else None

    if active_campuses is None:
        if current_kampus is None:
            active_campuses = _get_active_sale_campuses()
        else:
            active_campuses = []

    user_campus_entry = next((c for c in active_campuses if c.id == user_campus.id), None) if user_campus else None
    user_campus_has_items = user_campus_entry is not None

    if current_kampus is None:
        if user_campus and user_campus_has_items:
            current_kampus = 'saya'
        else:
            current_kampus = 'semua'

    if current_kampus == 'saya' and user_campus:
        qs = qs.filter(owner__student_profile__campus=user_campus)
    elif current_kampus and current_kampus != 'semua' and current_kampus.isdigit():
        qs = qs.filter(owner__student_profile__campus_id=int(current_kampus))

    # 2. Pencarian kata kunci
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(pickup_area__icontains=q) |
            Q(included_items__icontains=q)
        )

    # 3. Filter Kategori
    kategori = request.GET.get('kategori', '').strip()
    if kategori:
        if kategori in ('elektronik', 'elektronik-jual'):
            qs = qs.filter(category__slug__in=['elektronik', 'elektronik-jual'])
        elif kategori in ('lainnya', 'lainnya-jual', 'lain-lain'):
            qs = qs.filter(category__slug__in=['lainnya', 'lainnya-jual', 'lain-lain'])
        else:
            qs = qs.filter(category__slug=kategori)

    # 4. Filter Kondisi
    kondisi = request.GET.get('kondisi', '').strip()
    if kondisi in [c[0] for c in SaleItem.Condition.choices]:
        qs = qs.filter(condition=kondisi)

    # 5. Rentang Harga
    harga_min = request.GET.get('harga_min', '').strip()
    if harga_min.isdigit():
        qs = qs.filter(price__gte=int(harga_min))

    harga_max = request.GET.get('harga_max', '').strip()
    if harga_max.isdigit():
        qs = qs.filter(price__lte=int(harga_max))

    # 6. Urutan (Sort)
    urut = request.GET.get('urut', 'terbaru').strip()
    if urut == 'termurah':
        qs = qs.order_by('price', '-created_at')
    elif urut == 'termahal':
        qs = qs.order_by('-price', '-created_at')
    else:  # terbaru
        qs = qs.order_by('-created_at')

    return qs


def sale_item_list_view(request):
    """Halaman katalog utama jual beli (/jual-beli/)."""
    active_campuses = _get_active_sale_campuses()
    user_campus = getattr(getattr(request.user, 'student_profile', None), 'campus', None) if request.user.is_authenticated else None
    user_campus_entry = next((c for c in active_campuses if c.id == user_campus.id), None) if user_campus else None
    user_campus_has_items = user_campus_entry is not None
    user_campus_item_count = user_campus_entry.active_items_count if user_campus_entry else 0

    current_kampus = request.GET.get('kampus')
    if current_kampus is None:
        if user_campus and user_campus_has_items:
            current_kampus = 'saya'
        else:
            current_kampus = 'semua'

    items_qs = _get_sale_catalog_queryset(request, active_campuses=active_campuses)
    paginator = Paginator(items_qs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    categories = Category.objects.for_sale().order_by('order', 'name')

    if user_campus and user_campus_has_items:
        display_campuses = [c for c in active_campuses if c.id != user_campus.id]
    else:
        display_campuses = active_campuses

    context = {
        'page_obj': page_obj,
        'categories': categories,
        'active_campuses': active_campuses,
        'display_campuses': display_campuses,
        'other_campuses': display_campuses,
        'campuses': display_campuses,
        'user_campus': user_campus,
        'user_campus_has_items': user_campus_has_items,
        'user_campus_item_count': user_campus_item_count,
        'current_kampus': current_kampus,
        'current_q': request.GET.get('q', '').strip(),
        'current_kategori': request.GET.get('kategori', '').strip(),
        'current_kondisi': request.GET.get('kondisi', '').strip(),
        'current_harga_min': request.GET.get('harga_min', '').strip(),
        'current_harga_max': request.GET.get('harga_max', '').strip(),
        'current_urut': request.GET.get('urut', 'terbaru').strip(),
        'conditions': SaleItem.Condition.choices,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'sales/partials/item_grid.html', context)

    return render(request, 'sales/item_list.html', context)


def sale_item_results_partial(request):
    """Endpoint partial HTMX untuk filter dinamis katalog jual beli."""
    active_campuses = _get_active_sale_campuses()
    items_qs = _get_sale_catalog_queryset(request, active_campuses=active_campuses)
    paginator = Paginator(items_qs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'sales/partials/item_grid.html', {
        'page_obj': page_obj,
    })


def sale_item_detail_view(request, slug):
    """
    Halaman detail barang jualan (/jual-beli/<slug>/).
    """
    item = get_object_or_404(
        SaleItem.objects.select_related(
            'owner', 'owner__student_profile', 'owner__student_profile__campus', 'category'
        ).prefetch_related('photos'),
        slug=slug
    )

    # Statistik penjual
    seller_tier = get_seller_tier(item.owner)
    seller_tier_label = SELLER_TIER_LABELS.get(seller_tier, 'Penjual baru')
    seller_chip_class = SELLER_TIER_CHIP_CLASSES.get(seller_tier, 'bg-stone-100 text-stone-700')

    # Hitung jumlah barang terjual
    sold_count = SaleItem.objects.filter(owner=item.owner, status=SaleItem.Status.TERJUAL).count()

    # Hitung rating ulasan penjual dari modul jual beli dan sewa
    from apps.rentals.models import Review
    sale_ratings = list(SaleReview.objects.filter(reviewee=item.owner, role=SaleReview.Role.PENJUAL).values_list('rating', flat=True))
    rental_ratings = list(Review.objects.filter(reviewee=item.owner, as_role='pemilik').values_list('rating', flat=True))
    all_ratings = sale_ratings + rental_ratings
    seller_review_count = len(all_ratings)
    seller_rating = round(sum(all_ratings) / len(all_ratings), 1) if all_ratings else None

    is_owner = request.user.is_authenticated and request.user == item.owner
    buyer_terms = get_active_buyer_terms()

    from apps.sales.models import SaleItemReport
    report_reasons = SaleItemReport.Reason.choices
    sale_offers_enabled = getattr(settings, 'SALE_OFFERS_ENABLED', False)

    return render(request, 'sales/item_detail.html', {
        'item': item,
        'seller_tier': seller_tier,
        'seller_tier_label': seller_tier_label,
        'seller_chip_class': seller_chip_class,
        'sold_count': sold_count,
        'seller_rating': seller_rating,
        'seller_review_count': seller_review_count,
        'is_owner': is_owner,
        'buyer_terms': buyer_terms,
        'report_reasons': report_reasons,
        'sale_offers_enabled': sale_offers_enabled,
    })


@login_required(login_url='/masuk/')
def sale_item_report_view(request, slug):
    """
    POST /jual-beli/<slug>/lapor/
    Mengirim laporan moderasi terhadap listing barang jualan.
    """
    item = get_object_or_404(SaleItem, slug=slug)

    if request.method != 'POST':
        return redirect('sales:item_detail', slug=slug)

    if request.user == item.owner:
        messages.error(request, "Anda tidak dapat melaporkan barang milik Anda sendiri.")
        return redirect('sales:item_detail', slug=slug)

    reason = request.POST.get('reason', '').strip()
    notes = request.POST.get('notes', '').strip()

    try:
        from apps.sales.services import create_sale_item_report
        create_sale_item_report(item=item, reporter=request.user, reason=reason, notes=notes)
        messages.success(request, "Laporan Anda telah diterima dan akan segera ditinjau oleh staf operasional.")
    except Exception as e:
        messages.error(request, f"Gagal mengirim laporan: {e}")

    return redirect('sales:item_detail', slug=slug)


@login_required(login_url='/masuk/')
@verified_student_required
def buy_sale_item_view(request, slug):
    """
    POST /jual-beli/<slug>/beli/
    Membuat pesanan jual beli (SaleOrder) untuk barang aktif:
    - Verifikasi pembeli (login, email, KTM, tidak dibekukan, tanpa tagihan terutang).
    - Bukan barang sendiri.
    - Validasi kotak centang S&K Pembeli (terms_accepted).
    - Memanggil create_sale_order() yang menggunakan select_for_update().
    - Mengarahkan ke /pesanan/<kode>/.
    """
    item = get_object_or_404(SaleItem, slug=slug)

    if request.method != 'POST':
        return redirect('sales:item_detail', slug=slug)

    terms_accepted = request.POST.get('terms_accepted') in ('1', 'true', 'on', 'True')
    if not terms_accepted:
        messages.error(request, "Anda wajib mencentang persetujuan Syarat & Ketentuan Pembeli.")
        return redirect('sales:item_detail', slug=slug)

    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        order = create_sale_order(
            item=item,
            buyer=request.user,
            terms_accepted=terms_accepted,
            ip_address=ip_address,
            user_agent=user_agent
        )
        messages.success(request, f"Pesanan {order.code} berhasil dibuat! Silakan selesaikan pembayaran.")
        return redirect('sales:order_detail', code=order.code)
    except SaleOrderError as e:
        messages.error(request, str(e))
        return redirect('sales:item_detail', slug=slug)


@login_required(login_url='/masuk/')
def sale_order_detail_view(request, code):
    """
    GET /pesanan/<kode>/
    Detail pesanan jual beli: timeline status, aksi peran, rincian kuitansi,
    perjanjian, tautan chat internal, dan jadwal temu (Anti-IDOR).
    """
    order = get_object_or_404(
        SaleOrder.objects.select_related(
            'item', 'buyer', 'seller', 'meeting_point',
            'buyer__student_profile', 'seller__student_profile',
            'buyer__student_profile__campus', 'seller__student_profile__campus'
        ).prefetch_related('ledger_entries', 'payments', 'reviews'),
        code=code
    )

    if request.user != order.buyer and request.user != order.seller and not request.user.is_staff:
        return HttpResponseForbidden("Anda tidak memiliki izin untuk melihat pesanan ini.")

    is_buyer = request.user == order.buyer
    is_seller = request.user == order.seller

    user_review = order.reviews.filter(reviewer=request.user).first() if request.user.is_authenticated else None
    counterpart_review = order.reviews.exclude(reviewer=request.user).first() if request.user.is_authenticated else None

    from apps.accounts.models import MeetingPoint
    seller_campus = getattr(getattr(order.seller, 'student_profile', None), 'campus', None)
    buyer_campus = getattr(getattr(order.buyer, 'student_profile', None), 'campus', None)

    meeting_points = MeetingPoint.objects.none()
    if seller_campus and buyer_campus:
        if seller_campus == buyer_campus:
            meeting_points = MeetingPoint.objects.filter(campus=seller_campus)
        else:
            meeting_points = MeetingPoint.objects.filter(
                models.Q(campus__in=[seller_campus, buyer_campus]),
                is_public=True
            )

    # Sinkronisasi otomatis dari Midtrans jika status masih menunggu pembayaran dan ada payment pending
    latest_payment = order.payments.order_by('-created_at').first()
    if order.status == SaleOrder.Status.MENUNGGU_PEMBAYARAN and latest_payment and latest_payment.status == 'pending':
        try:
            from apps.payments.services import sync_payment_status, is_midtrans_configured
            if is_midtrans_configured():
                sync_payment_status(latest_payment.order_id)
                order.refresh_from_db()
                latest_payment.refresh_from_db()
        except Exception as e:
            logger.debug(f"Auto-sync payment on sale order_detail_view for {order.code}: {e}")

    agreement = getattr(order, 'agreement', None)

    # Ambil payment token jika menunggu pembayaran
    snap_token = None
    if order.status == SaleOrder.Status.MENUNGGU_PEMBAYARAN and is_buyer:
        payment = order.payments.filter(status='pending').first()
        if payment and payment.snap_token:
            snap_token = payment.snap_token

    return render(request, 'sales/order_detail.html', {
        'order': order,
        'is_buyer': is_buyer,
        'is_seller': is_seller,
        'agreement': agreement,
        'meeting_points': meeting_points,
        'snap_token': snap_token,
        'user_review': user_review,
        'counterpart_review': counterpart_review,
    })


@login_required(login_url='/masuk/')
def sale_agreement_print_view(request, code):
    """
    GET /pesanan/<kode>/perjanjian/
    Halaman perjanjian pembelian digital resmi yang dapat dicetak.
    Anti-IDOR: hanya pembeli, penjual, atau staf.
    """
    order = get_object_or_404(
        SaleOrder.objects.select_related(
            'item', 'buyer', 'seller',
            'buyer__student_profile', 'seller__student_profile',
            'buyer__student_profile__campus', 'seller__student_profile__campus',
            'agreement'
        ),
        code=code
    )
    if request.user != order.buyer and request.user != order.seller and not request.user.is_staff:
        return HttpResponseForbidden("Anda tidak berhak melihat perjanjian ini.")

    return render(request, 'sales/sale_agreement.html', {
        'order': order,
        'agreement': getattr(order, 'agreement', None),
    })


@login_required(login_url='/masuk/')
@require_POST
def sale_order_set_meetup_view(request, code):
    """POST /pesanan/<kode>/jadwal-temu/"""
    order = get_object_or_404(SaleOrder, code=code)
    if request.user != order.buyer and request.user != order.seller and not request.user.is_staff:
        return HttpResponseForbidden("Anda tidak memiliki izin untuk pesanan ini.")

    meeting_point_id = request.POST.get('meeting_point_id')
    meetup_at_str = request.POST.get('meetup_at')

    from apps.accounts.models import MeetingPoint
    meeting_point = None
    if meeting_point_id:
        meeting_point = get_object_or_404(MeetingPoint, id=meeting_point_id)

    from django.utils.dateparse import parse_datetime
    meetup_at = parse_datetime(meetup_at_str) if meetup_at_str else None
    if meetup_at and timezone.is_naive(meetup_at):
        meetup_at = timezone.make_aware(meetup_at)

    try:
        set_sale_order_meetup(order, user=request.user, meetup_at=meetup_at, meeting_point=meeting_point)
        messages.success(request, "Jadwal dan titik temu berhasil disimpan.")
    except Exception as e:
        messages.error(request, str(e))

    return redirect('sales:order_detail', code=order.code)


@login_required(login_url='/masuk/')
@require_POST
def sale_order_handover_view(request, code):
    """POST /pesanan/<kode>/serah-terima/"""
    order = get_object_or_404(SaleOrder, code=code)
    if request.user != order.buyer and request.user != order.seller and not request.user.is_staff:
        return HttpResponseForbidden("Anda tidak memiliki izin untuk pesanan ini.")

    photo_file = request.FILES.get('handover_photo')
    notes = request.POST.get('notes', '').strip()
    try:
        mark_sale_order_handed_over(order, user=request.user, notes=notes, photo_file=photo_file)
        messages.success(request, "Penyerahan barang berhasil dikonfirmasi. Pembeli memiliki masa pemeriksaan 48 jam.")
    except Exception as e:
        messages.error(request, str(e))
    return redirect('sales:order_detail', code=order.code)


@login_required(login_url='/masuk/')
@require_POST
def sale_order_confirm_received_view(request, code):
    """POST /pesanan/<kode>/konfirmasi/"""
    order = get_object_or_404(SaleOrder, code=code)
    if request.user != order.buyer and request.user != order.seller and not request.user.is_staff:
        return HttpResponseForbidden("Anda tidak memiliki izin untuk pesanan ini.")

    try:
        confirm_sale_order_received(order, user=request.user)
        messages.success(request, "Terima kasih! Pesanan telah selesai dan dana telah diteruskan ke dompet penjual.")
    except Exception as e:
        messages.error(request, str(e))
    return redirect('sales:order_detail', code=order.code)


@login_required(login_url='/masuk/')
@require_POST
def sale_order_dispute_view(request, code):
    """POST /pesanan/<kode>/sengketa/"""
    order = get_object_or_404(SaleOrder, code=code)
    if request.user != order.buyer and request.user != order.seller and not request.user.is_staff:
        return HttpResponseForbidden("Anda tidak memiliki izin untuk pesanan ini.")

    reason = request.POST.get('reason', '').strip()
    issue_type = request.POST.get('dispute_type') or request.POST.get('issue_type', 'lainnya')
    photo_files = request.FILES.getlist('dispute_photos')[:3]
    try:
        open_sale_dispute(
            order, user=request.user,
            reason=reason,
            photo_files=photo_files,
            dispute_type=issue_type
        )
        messages.success(request, "Laporan masalah berhasil dikirim. Tim admin platform akan memediasi sengketa.")
    except Exception as e:
        messages.error(request, str(e))
    return redirect('sales:order_detail', code=order.code)


@login_required(login_url='/masuk/')
def sale_order_dispute_photo_view(request, code, idx):
    """GET /pesanan/<kode>/foto-sengketa/<idx>/"""
    order = get_object_or_404(SaleOrder, code=code)
    if request.user != order.buyer and request.user != order.seller and not request.user.is_staff:
        return HttpResponseForbidden("Anda tidak memiliki izin melihat bukti foto ini.")

    dispute = getattr(order, 'dispute', None)
    photos = dispute.evidence_photos if dispute else (order.listing_snapshot or {}).get('dispute_photos', [])
    if idx < 0 or idx >= len(photos):
        raise Http404("Foto tidak ditemukan.")

    photo_rel_path = photos[idx]
    file_path = Path(settings.PRIVATE_MEDIA_ROOT) / photo_rel_path
    if not file_path.exists():
        raise Http404("Berkas foto tidak ditemukan di server.")

    return FileResponse(open(file_path, 'rb'), content_type='image/jpeg')


@login_required(login_url='/masuk/')
@require_POST
def sale_order_cancel_view(request, code):
    """POST /pesanan/<kode>/batal/"""
    order = get_object_or_404(SaleOrder, code=code)
    if request.user != order.buyer and request.user != order.seller and not request.user.is_staff:
        return HttpResponseForbidden("Anda tidak berhak membatalkan pesanan ini.")

    cancel_reason = request.POST.get('cancel_reason', '').strip()
    try:
        cancel_sale_order(order, user=request.user, reason=cancel_reason)
        messages.success(request, f"Pesanan {order.code} berhasil dibatalkan.")
    except Exception as e:
        messages.error(request, str(e))
    return redirect('sales:order_detail', code=order.code)


@login_required(login_url='/masuk/')
@require_POST
def sale_order_review_view(request, code):
    """
    POST /pesanan/<kode>/ulasan/
    Kirim ulasan dua arah setelah pesanan selesai.
    """
    order = get_object_or_404(SaleOrder, code=code)
    if request.user != order.buyer and request.user != order.seller and not request.user.is_staff:
        return HttpResponseForbidden("Anda tidak memiliki izin mengulas pesanan ini.")

    rating = request.POST.get('rating')
    comment = request.POST.get('comment', '').strip()

    try:
        create_sale_review(order, reviewer=request.user, rating=rating, comment=comment)
        messages.success(request, "Ulasan Anda berhasil dikirim. Terima kasih telah bertransaksi!")
    except Exception as e:
        messages.error(request, str(e))

    return redirect('sales:order_detail', code=order.code)


@login_required(login_url='/masuk/')
@require_POST
def sale_item_offer_view(request, slug):
    """
    POST /jual-beli/<slug>/tawar/
    Mengirim tawaran harga terstruktur untuk barang jualan.
    """
    if not getattr(settings, 'SALE_OFFERS_ENABLED', False):
        return HttpResponseForbidden("Fitur penawaran harga dinonaktifkan.")

    item = get_object_or_404(SaleItem, slug=slug)
    offered_price = request.POST.get('offered_price')

    try:
        offer = create_sale_offer(item, request.user, offered_price)
        messages.success(request, f"Tawaran harga sebesar Rp{offer.offered_price:,} berhasil diajukan ke penjual. Berlaku 24 jam.")
    except Exception as e:
        messages.error(request, str(e))

    return redirect('sales:item_detail', slug=slug)


@login_required(login_url='/masuk/')
@require_POST
def sale_offer_accept_view(request, offer_id):
    """
    POST /jual-beli/tawaran/<offer_id>/terima/
    Penjual menyetujui tawaran harga.
    """
    if not getattr(settings, 'SALE_OFFERS_ENABLED', False):
        return HttpResponseForbidden("Fitur penawaran harga dinonaktifkan.")

    offer = get_object_or_404(SaleOffer, id=offer_id)
    if offer.item.owner != request.user:
        return HttpResponseForbidden("Hanya penjual barang yang berhak menyetujui tawaran.")

    try:
        ip_addr = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        order = accept_sale_offer(offer, request.user, ip_address=ip_addr, user_agent=user_agent)
        messages.success(request, f"Tawaran disetujui. Pesanan {order.code} telah dibuat dan menunggu pembayaran pembeli.")
        return redirect('sales:order_detail', code=order.code)
    except Exception as e:
        messages.error(request, str(e))
        return redirect('sales:item_detail', slug=offer.item.slug)


@login_required(login_url='/masuk/')
@require_POST
def sale_offer_reject_view(request, offer_id):
    """
    POST /jual-beli/tawaran/<offer_id>/tolak/
    Penjual menolak tawaran harga.
    """
    if not getattr(settings, 'SALE_OFFERS_ENABLED', False):
        return HttpResponseForbidden("Fitur penawaran harga dinonaktifkan.")

    offer = get_object_or_404(SaleOffer, id=offer_id)
    if offer.item.owner != request.user:
        return HttpResponseForbidden("Hanya penjual barang yang berhak menolak tawaran.")

    try:
        reject_sale_offer(offer, request.user)
        messages.info(request, "Tawaran harga telah ditolak.")
    except Exception as e:
        messages.error(request, str(e))

    return redirect('sales:item_detail', slug=offer.item.slug)



