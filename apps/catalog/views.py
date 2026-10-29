from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounts.decorators import verified_student_required
from apps.accounts.models import Campus
from apps.catalog.forms import ItemForm, validate_uploaded_photos
from apps.catalog.models import Category, Item, ItemPhoto
from apps.catalog.services import (
    calculate_min_deposit,
    get_suggested_deposit_range,
    get_unavailable_dates,
    calculate_rental_summary,
    is_item_available,
)
from apps.rentals.models import Rental, Review
from apps.trust.services import (
    get_renter_tier,
    get_tier_info,
    is_renter_eligible_for_item,
    calculate_minimum_deposit,
    calculate_protection_fee,
)


@verified_student_required
def item_create_view(request):
    """
    Halaman pasang barang baru (/barang/baru/).
    Hanya untuk mahasiswa yang sudah terverifikasi KTM.
    """
    user = request.user
    categories = Category.objects.for_rental().order_by('order', 'name')

    if request.method == 'POST':
        form = ItemForm(request.POST, user=user)
        photo_files = request.FILES.getlist('photos')

        valid_photos, photo_errors = validate_uploaded_photos(photo_files, existing_count=0)

        if form.is_valid() and not photo_errors:
            item = form.save(commit=False)
            item.owner = user
            item.save()

            # Simpan berkas-berkas foto barang
            for idx, photo_file in enumerate(valid_photos):
                ItemPhoto.objects.create(
                    item=item,
                    image=photo_file,
                    order=idx
                )

            messages.success(request, f"Barang '{item.title}' berhasil dipasang dan kini aktif di katalog!")
            return redirect('catalog:item_detail', slug=item.slug)
        else:
            # Gabungkan pesan error foto jika ada
            for err in photo_errors:
                form.add_error(None, err)
            messages.error(request, "Gagal memasang barang. Mohon periksa kembali isian formulir di bawah.")
    else:
        form = ItemForm(user=user)

    return render(request, 'catalog/item_form.html', {
        'form': form,
        'categories': categories,
        'is_edit': False,
    })


@login_required(login_url='/masuk/')
def my_items_view(request):
    """
    Daftar barang milik mahasiswa sendiri (/barang/saya/).
    Menampilkan barang aktif dan nonaktif beserta tombol kelola.
    """
    status_filter = request.GET.get('status', 'all')
    items_qs = (
        request.user.items
        .all()
        .select_related('category')
        .prefetch_related('photos')
        .order_by('-created_at')
    )

    if status_filter == 'active':
        items_qs = items_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        items_qs = items_qs.filter(is_active=False)

    return render(request, 'catalog/my_items.html', {
        'items': items_qs,
        'status_filter': status_filter,
        'total_count': request.user.items.count(),
        'active_count': request.user.items.filter(is_active=True).count(),
        'inactive_count': request.user.items.filter(is_active=False).count(),
    })


@verified_student_required
def item_update_view(request, slug):
    """
    Halaman ubah barang (/barang/<slug>/ubah/).
    Hanya pemilik barang yang berhak mengubah.
    """
    item = get_object_or_404(Item.objects.prefetch_related('photos'), slug=slug)

    # Cek kepemilikan objek (Cegah IDOR)
    if item.owner != request.user:
        return HttpResponseForbidden("Anda tidak memiliki izin untuk mengubah barang milik mahasiswa lain.")

    if request.method == 'POST':
        form = ItemForm(request.POST, instance=item, user=request.user)
        new_photos = request.FILES.getlist('photos')

        # Cek foto baru jika diunggah dan foto yang ditandai untuk dihapus
        delete_photo_ids = request.POST.getlist('delete_photo_ids')
        remaining_photos = item.photos.exclude(id__in=delete_photo_ids)
        current_photos_count = remaining_photos.count()

        photo_errors = []
        if current_photos_count + len(new_photos) == 0:
            photo_errors.append("Barang wajib memiliki minimal 1 foto aktif.")
        elif new_photos:
            valid_new_photos, photo_errors = validate_uploaded_photos(new_photos, existing_count=current_photos_count)
        else:
            valid_new_photos = []

        if form.is_valid() and not photo_errors:
            item = form.save()

            # Hapus foto yang dipilih
            if delete_photo_ids:
                for p_del in item.photos.filter(id__in=delete_photo_ids):
                    try:
                        if p_del.image and p_del.image.storage.exists(p_del.image.name):
                            p_del.image.storage.delete(p_del.image.name)
                    except Exception:
                        pass
                    p_del.delete()

            # Tambahkan foto baru jika ada
            if valid_new_photos:
                start_order = item.photos.count()
                for idx, photo_file in enumerate(valid_new_photos):
                    ItemPhoto.objects.create(
                        item=item,
                        image=photo_file,
                        order=start_order + idx,
                        is_primary=(idx == 0 and not item.photos.filter(is_primary=True).exists())
                    )

            # Pastikan selalu ada foto primary
            if item.photos.exists() and not item.photos.filter(is_primary=True).exists():
                first_photo = item.photos.order_by('order', 'id').first()
                if first_photo:
                    first_photo.is_primary = True
                    first_photo.save(update_fields=['is_primary'])

            messages.success(request, f"Perubahan pada '{item.title}' berhasil disimpan.")
            return redirect('catalog:item_detail', slug=item.slug)
        else:
            for err in photo_errors:
                form.add_error(None, err)
            messages.error(request, "Gagal menyimpan perubahan. Mohon periksa kembali isian formulir di bawah.")
    else:
        form = ItemForm(instance=item, user=request.user)

    return render(request, 'catalog/item_form.html', {
        'form': form,
        'item': item,
        'is_edit': True,
    })


@login_required(login_url='/masuk/')
def item_toggle_active_view(request, slug):
    """
    Soft delete / nonaktifkan / aktifkan kembali barang (/barang/<slug>/toggle-status/).
    Hanya pemilik barang yang berhak mengubah status.
    """
    if request.method != 'POST':
        return HttpResponseForbidden("Metode tidak diizinkan.")

    item = get_object_or_404(Item, slug=slug)

    if item.owner != request.user:
        return HttpResponseForbidden("Anda tidak berhak mengubah status barang ini.")

    item.is_active = not item.is_active
    item.save(update_fields=['is_active'])

    status_str = "diaktifkan kembali" if item.is_active else "dinonaktifkan (disembunyikan dari katalog)"
    messages.success(request, f"Barang '{item.title}' telah {status_str}.")
    return redirect('catalog:my_items')


def _get_active_campuses():
    """Mengambil daftar kampus yang memiliki barang aktif yang dipasang mahasiswanya, diurutkan jumlah terbanyak."""
    return list(
        Campus.objects.filter(is_active=True)
        .annotate(
            active_items_count=models.Count(
                'student_profiles__user__items',
                filter=models.Q(student_profiles__user__items__is_active=True),
                distinct=True
            )
        )
        .filter(active_items_count__gt=0)
        .order_by('-active_items_count', 'short_name')
    )


def _get_catalog_queryset(request, active_campuses=None):
    """
    Helper untuk memfilter dan mengurutkan barang di katalog secara efisien tanpa N+1 query.
    """
    qs = (
        Item.objects
        .filter(is_active=True)
        .select_related('owner', 'owner__student_profile', 'owner__student_profile__campus', 'category', 'owner__trust_score')
        .prefetch_related('photos')
    )

    # 0. Filter Kampus (Fase 7B: hanya kampus dengan barang aktif)
    current_kampus = request.GET.get('kampus')
    user_campus = getattr(getattr(request.user, 'student_profile', None), 'campus', None) if request.user.is_authenticated else None

    if active_campuses is None:
        # Hanya fetch jika belum disediakan dan dibutuhkan untuk penentuan default
        if current_kampus is None:
            active_campuses = _get_active_campuses()
        else:
            active_campuses = []

    user_campus_entry = next((c for c in active_campuses if c.id == user_campus.id), None) if user_campus else None
    user_campus_has_items = user_campus_entry is not None

    if current_kampus is None:
        if len(active_campuses) == 1:
            current_kampus = str(active_campuses[0].id)
        elif user_campus and user_campus_has_items:
            current_kampus = 'saya'
        else:
            current_kampus = 'semua'

    if current_kampus == 'saya' and user_campus and user_campus_has_items:
        qs = qs.filter(owner__student_profile__campus=user_campus)
    elif current_kampus and current_kampus.isdigit():
        qs = qs.filter(owner__student_profile__campus_id=int(current_kampus))
    # 'semua' tidak memfilter kampus

    # 1. Filter kata kunci pencarian
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(models.Q(title__icontains=q) | models.Q(description__icontains=q))

    # 2. Filter Kategori
    kategori_slug = request.GET.get('kategori', '').strip()
    if kategori_slug:
        qs = qs.filter(category__slug=kategori_slug)

    # 3. Filter Rentang Harga
    harga_min = request.GET.get('harga_min', '').strip()
    if harga_min.isdigit():
        qs = qs.filter(price_per_day__gte=int(harga_min))

    harga_max = request.GET.get('harga_max', '').strip()
    if harga_max.isdigit():
        qs = qs.filter(price_per_day__lte=int(harga_max))

    # 4. Filter Kondisi
    kondisi = request.GET.get('kondisi', '').strip()
    if kondisi in [c[0] for c in Item.Condition.choices]:
        qs = qs.filter(condition=kondisi)

    # 5. Filter Tanggal Ketersediaan (Anti double-booking)
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()
    if start_date_str and end_date_str:
        try:
            start_d = date.fromisoformat(start_date_str)
            end_d = date.fromisoformat(end_date_str)
            if start_d <= end_d:
                # Tabrakan terjadi bila sewa aktif overlap dengan rentang pilihan
                blocked_item_ids = (
                    Rental.objects
                    .filter(
                        status__in=Rental.BLOCKING_STATUSES,
                        start_date__lte=end_d,
                        end_date__gte=start_d
                    )
                    .values_list('item_id', flat=True)
                )
                qs = qs.exclude(id__in=blocked_item_ids)
        except ValueError:
            pass

    # 6. Urutan (Sort)
    urut = request.GET.get('urut', 'terbaru').strip()
    if urut == 'termurah':
        qs = qs.order_by('price_per_day', '-created_at')
    elif urut == 'termahal':
        qs = qs.order_by('-price_per_day', '-created_at')
    elif urut == 'skor_pemilik':
        qs = qs.order_by(models.F('owner__trust_score__score').desc(nulls_last=True), '-created_at')
    else:  # default 'terbaru'
        qs = qs.order_by('-created_at')

    return qs


def item_list_view(request):
    """Halaman katalog utama (/barang/)."""
    active_campuses = _get_active_campuses()
    user_campus = getattr(getattr(request.user, 'student_profile', None), 'campus', None) if request.user.is_authenticated else None
    user_campus_entry = next((c for c in active_campuses if c.id == user_campus.id), None) if user_campus else None
    user_campus_has_items = user_campus_entry is not None
    user_campus_item_count = user_campus_entry.active_items_count if user_campus_entry else 0

    current_kampus = request.GET.get('kampus')
    if current_kampus is None:
        if len(active_campuses) == 1:
            current_kampus = str(active_campuses[0].id)
        elif user_campus and user_campus_has_items:
            current_kampus = 'saya'
        else:
            current_kampus = 'semua'

    items_qs = _get_catalog_queryset(request, active_campuses=active_campuses)
    paginator = Paginator(items_qs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    categories = Category.objects.for_rental().order_by('order', 'name')

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
        'current_q': request.GET.get('q', ''),
        'current_kategori': request.GET.get('kategori', ''),
        'current_harga_min': request.GET.get('harga_min', ''),
        'current_harga_max': request.GET.get('harga_max', ''),
        'current_kondisi': request.GET.get('kondisi', ''),
        'current_start_date': request.GET.get('start_date', ''),
        'current_end_date': request.GET.get('end_date', ''),
        'current_urut': request.GET.get('urut', 'terbaru'),
        'conditions': Item.Condition.choices,
    }
    return render(request, 'catalog/item_list.html', context)


def item_list_partial_view(request):
    """Endpoint HTMX untuk partial grid katalog (/barang/hasil/)."""
    active_campuses = _get_active_campuses()
    user_campus = getattr(getattr(request.user, 'student_profile', None), 'campus', None) if request.user.is_authenticated else None
    user_campus_entry = next((c for c in active_campuses if c.id == user_campus.id), None) if user_campus else None
    user_campus_has_items = user_campus_entry is not None

    current_kampus = request.GET.get('kampus')
    if current_kampus is None:
        if len(active_campuses) == 1:
            current_kampus = str(active_campuses[0].id)
        elif user_campus and user_campus_has_items:
            current_kampus = 'saya'
        else:
            current_kampus = 'semua'

    items_qs = _get_catalog_queryset(request, active_campuses=active_campuses)
    paginator = Paginator(items_qs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'catalog/partials/item_grid.html', {
        'page_obj': page_obj,
        'current_kampus': current_kampus,
        'current_q': request.GET.get('q', ''),
        'current_kategori': request.GET.get('kategori', ''),
        'current_harga_min': request.GET.get('harga_min', ''),
        'current_harga_max': request.GET.get('harga_max', ''),
        'current_kondisi': request.GET.get('kondisi', ''),
        'current_start_date': request.GET.get('start_date', ''),
        'current_end_date': request.GET.get('end_date', ''),
        'current_urut': request.GET.get('urut', 'terbaru'),
    })


def item_detail_view(request, slug):
    """Halaman detail barang (/barang/<slug>/)."""
    item = get_object_or_404(
        Item.objects
        .select_related('owner', 'category', 'owner__trust_score')
        .prefetch_related('photos'),
        slug=slug
    )

    unavailable_data = get_unavailable_dates(item)
    reviews = (
        Review.objects
        .filter(rental__item=item, as_role='penyewa')
        .select_related('reviewer')
        .order_by('-created_at')
    )

    owner_trust = getattr(item.owner, 'trust_score', None)

    # Barang serupa di kategori yang sama
    similar_items = (
        Item.objects
        .filter(category=item.category, is_active=True)
        .exclude(pk=item.pk)
        .select_related('owner', 'category', 'owner__trust_score')
        .prefetch_related('photos')
        .order_by('-created_at')[:4]
    )

    from apps.core.models import TermsVersion
    active_terms_penyewa = TermsVersion.objects.filter(
        term_type=TermsVersion.TermType.PENYEWA,
        is_active=True
    ).order_by('-valid_from', '-created_at').first()

    return render(request, 'catalog/item_detail.html', {
        'item': item,
        'today_str': date.today().isoformat(),
        'unavailable_dates_json': unavailable_data['disabled_dates'],
        'unavailable_ranges': unavailable_data['ranges'],
        'reviews': reviews,
        'owner_trust': owner_trust,
        'similar_items': similar_items,
        'is_owner': request.user.is_authenticated and item.owner == request.user,
        'active_terms_penyewa': active_terms_penyewa,
    })


def item_price_summary_htmx_view(request, slug):
    """
    Endpoint HTMX ringkasan harga bergaya kuitansi (/barang/<slug>/ringkasan/).
    Memanggil service perhitungan Rental tanpa menulis ulang rumus.
    """
    item = get_object_or_404(Item, slug=slug)

    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()
    use_protection = request.GET.get('use_protection', 'false').lower() in ['true', '1', 'on']

    start_d = None
    end_d = None
    if start_date_str and end_date_str:
        try:
            start_d = date.fromisoformat(start_date_str)
            end_d = date.fromisoformat(end_date_str)
        except ValueError:
            pass

    summary = calculate_rental_summary(item, start_d, end_d, use_protection)

    return render(request, 'catalog/partials/receipt_summary.html', {
        'item': item,
        'summary': summary,
        'start_date_str': start_date_str,
        'end_date_str': end_date_str,
        'use_protection': use_protection,
    })
