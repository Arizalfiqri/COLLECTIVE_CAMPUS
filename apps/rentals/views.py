import hashlib
from datetime import datetime, time as time_module, timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from apps.rentals.models import (
    Rental,
    ConditionPhoto,
    HandoverSchedule,
    Dispute,
    Review,
    RentalAgreement,
)
from apps.catalog.models import Item
from apps.chat.models import Conversation
from apps.rentals.services import (
    ajukan_sewa,
    setujui_sewa,
    tolak_sewa,
    batalkan_sewa,
    RentalError,
    RentalValidationError,
    RentalPermissionError,
    RentalStateError,
)


@login_required(login_url='/masuk/')
@require_POST
def rental_request_view(request, slug):
    """
    POST /sewa/ajukan/<slug>/
    Mengajukan sewa barang dari halaman detail barang.
    """
    item = get_object_or_404(Item, slug=slug)

    # Validasi awal hak akun
    if not request.user.is_verified_student:
        messages.error(request, "Verifikasi KTM dulu untuk memasang barang atau menyewa.")
        return redirect('catalog:item_detail', slug=slug)

    if getattr(request.user, 'is_suspended', False):
        messages.error(request, "Akun Anda sedang dibekukan sehingga tidak dapat mengajukan sewa.")
        return redirect('catalog:item_detail', slug=slug)

    if item.owner_id == request.user.id:
        messages.error(request, "Anda tidak dapat menyewa barang milik Anda sendiri.")
        return redirect('catalog:item_detail', slug=slug)

    # Ambil input form
    start_date_str = request.POST.get('start_date', '').strip()
    end_date_str = request.POST.get('end_date', '').strip()
    use_protection_raw = request.POST.get('use_protection', '')
    use_protection = use_protection_raw in ['true', 'True', '1', 'on']
    terms_accepted = request.POST.get('terms_accepted') in ['true', 'True', '1', 'on']

    if not start_date_str or not end_date_str:
        messages.error(request, "Tanggal mulai dan selesai sewa wajib diisi.")
        return redirect('catalog:item_detail', slug=slug)

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Format tanggal tidak valid. Gunakan format YYYY-MM-DD.")
        return redirect('catalog:item_detail', slug=slug)

    if not terms_accepted:
        messages.error(request, "Anda wajib mencentang persetujuan syarat dan ketentuan sewa.")
        return redirect('catalog:item_detail', slug=slug)

    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        rental = ajukan_sewa(
            item=item,
            renter=request.user,
            start_date=start_date,
            end_date=end_date,
            use_protection=use_protection,
            terms_accepted=terms_accepted,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        messages.success(
            request,
            f"Permintaan sewa berhasil diajukan dengan kode {rental.code}! Menunggu persetujuan pemilik."
        )
        return redirect('rentals:rental_detail', code=rental.code)
    except RentalError as e:
        messages.error(request, str(e))
        return redirect('catalog:item_detail', slug=slug)


@login_required(login_url='/masuk/')
def rental_detail_view(request, code):
    """
    GET /sewa/<kode>/
    Halaman detail sewa: timeline status, aksi pengguna sesuai peran,
    kuitansi rincian biaya, syarat sewa digital, dan tautan chat internal.
    Hanya peserta transaksi (penyewa & pemilik) atau staff yang boleh melihat (Anti-IDOR).
    """
    rental = get_object_or_404(
        Rental.objects.select_related(
            'item', 'item__owner', 'renter', 'owner', 'agreement', 'cancelled_by',
            'renter__student_profile', 'owner__student_profile'
        ),
        code=code
    )

    # Validasi IDOR: hanya penyewa atau pemilik (atau staff) yang berhak melihat
    is_renter = (request.user.id == rental.renter_id)
    is_owner = (request.user.id == rental.owner_id)
    if not (is_renter or is_owner or request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("Anda tidak memiliki izin untuk melihat data sewa ini.")

    # Timeline status
    timeline_steps = [
        {'key': 'diajukan', 'label': 'Diajukan'},
        {'key': 'disetujui', 'label': 'Disetujui'},
        {'key': 'dibayar', 'label': 'Dibayar'},
        {'key': 'diserahkan', 'label': 'Diserahkan'},
        {'key': 'dikembalikan', 'label': 'Dikembalikan'},
        {'key': 'selesai', 'label': 'Selesai'},
    ]

    is_terminal_failed = rental.status in [
        Rental.Status.DITOLAK,
        Rental.Status.DIBATALKAN,
        Rental.Status.KEDALUWARSA,
    ]

    if rental.status == Rental.Status.MENUNGGU_PERSETUJUAN:
        active_step_index = 1
    elif rental.status == Rental.Status.MENUNGGU_PEMBAYARAN:
        active_step_index = 2
    elif rental.status == Rental.Status.DIBAYAR:
        active_step_index = 3
    elif rental.status == Rental.Status.SEDANG_DISEWA:
        active_step_index = 4
    elif rental.status == Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN:
        active_step_index = 5
    elif rental.status == Rental.Status.SELESAI:
        active_step_index = 6
    elif is_terminal_failed:
        if getattr(rental, 'paid_at', None) or rental.payments.filter(status='settlement').exists():
            active_step_index = 3
        elif rental.approved_at:
            active_step_index = 2
        else:
            active_step_index = 1
    else:
        active_step_index = 0

    # Hak aksi saat ini
    can_approve = is_owner and (rental.status == Rental.Status.MENUNGGU_PERSETUJUAN)
    can_reject = is_owner and (rental.status == Rental.Status.MENUNGGU_PERSETUJUAN)
    can_cancel = (is_renter or is_owner) and (
        rental.status in [
            Rental.Status.MENUNGGU_PERSETUJUAN,
            Rental.Status.MENUNGGU_PEMBAYARAN,
            Rental.Status.DIBAYAR,
        ]
    )
    show_pay_button = is_renter and (rental.status == Rental.Status.MENUNGGU_PEMBAYARAN)

    # Hubungkan Conversation dengan rental ini sebagai jalur komunikasi utama
    conversation, _ = Conversation.objects.get_or_create(
        item=rental.item,
        renter=rental.renter,
        defaults={'owner': rental.owner, 'rental': rental}
    )
    if conversation.rental_id != rental.id:
        conversation.rental = rental
        conversation.save(update_fields=['rental'])

    # Logika visibilitas WhatsApp serah terima (hanya lawan bicara, dalam jendela waktu)
    whatsapp_handover_enabled = getattr(settings, 'WHATSAPP_HANDOVER_ENABLED', True)
    show_whatsapp = False
    counterpart = rental.owner if is_renter else rental.renter
    counterpart_role = "Pemilik barang" if is_renter else "Penyewa"

    allowed_handover_statuses = [Rental.Status.DIBAYAR, Rental.Status.SEDANG_DISEWA]
    if whatsapp_handover_enabled and (rental.status in allowed_handover_statuses):
        current_tz = timezone.get_current_timezone()
        start_datetime = timezone.make_aware(
            datetime.combine(rental.start_date, time_module.min),
            current_tz
        )
        window_start = start_datetime - timedelta(hours=24)
        if timezone.now() >= window_start:
            show_whatsapp = True

    agreement_data = getattr(rental, 'agreement', None)
    terms_snapshot = agreement_data.terms_snapshot if agreement_data else {}
    max_loss_compensation = terms_snapshot.get('max_loss_compensation') or rental.item.estimated_value

    from apps.payments.services import (
        is_midtrans_configured,
        get_midtrans_keys,
        get_midtrans_snap_mode,
    )
    midtrans_ready = is_midtrans_configured()
    server_key, midtrans_client_key = get_midtrans_keys()
    midtrans_snap_mode = get_midtrans_snap_mode()

    ledger_entries = rental.ledger_entries.all().order_by('created_at')
    deposit_hold = getattr(rental, 'deposit_hold', None)
    latest_payment = rental.payments.order_by('-created_at').first()

    # Sinkronisasi otomatis dari Midtrans jika status masih menunggu pembayaran dan ada payment pending
    if rental.status == Rental.Status.MENUNGGU_PEMBAYARAN and latest_payment and latest_payment.status == 'pending':
        try:
            from apps.payments.services import sync_payment_status
            sync_payment_status(latest_payment.order_id)
            rental.refresh_from_db()
            latest_payment.refresh_from_db()
            deposit_hold = getattr(rental, 'deposit_hold', None)
            ledger_entries = rental.ledger_entries.all().order_by('created_at')
        except Exception:
            pass

    is_paid = rental.status in [
        Rental.Status.DIBAYAR,
        Rental.Status.SEDANG_DISEWA,
        Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN,
        Rental.Status.SELESAI,
    ]

    # Data Fase 5B: Foto Kondisi
    photos = rental.condition_photos.all().order_by('created_at')
    photos_sebelum = [p for p in photos if p.phase == ConditionPhoto.Phase.SEBELUM]
    photos_serah_terima = [p for p in photos if p.phase == ConditionPhoto.Phase.SERAH_TERIMA]
    photos_sesudah = [p for p in photos if p.phase == ConditionPhoto.Phase.SESUDAH]

    # Jadwal Serah Terima & Titik Temu
    from apps.accounts.models import MeetingPoint
    from django.db.models import Q

    latest_schedule = rental.handover_schedules.order_by('-created_at').first()
    renter_campus = getattr(getattr(rental.renter, 'student_profile', None), 'campus', None)
    owner_campus = getattr(getattr(rental.owner, 'student_profile', None), 'campus', None)
    is_cross_campus = bool(renter_campus and owner_campus and renter_campus.id != owner_campus.id)

    if is_cross_campus:
        meeting_points = MeetingPoint.objects.filter(is_public=True).select_related('campus')
    elif owner_campus:
        meeting_points = MeetingPoint.objects.filter(
            Q(campus=owner_campus) | Q(is_public=True)
        ).select_related('campus').distinct()
    else:
        meeting_points = MeetingPoint.objects.all().select_related('campus')

    dispute = getattr(rental, 'dispute', None)

    # Estimasi denda dan sisa deposit
    today = timezone.localdate()
    if rental.status == Rental.Status.SEDANG_DISEWA:
        current_late_days = max(0, (today - rental.end_date).days)
        current_late_fee = min(round(rental.price_per_day_snapshot * 0.5 * current_late_days), rental.deposit_total)
    else:
        current_late_days = rental.late_days
        current_late_fee = rental.late_fee

    sisa_deposit = max(0, rental.deposit_total - current_late_fee)

    # Ulasan
    my_review = rental.reviews.filter(reviewer=request.user).first()
    counterpart_review = rental.reviews.filter(reviewer=counterpart).first()
    can_review = (rental.status == Rental.Status.SELESAI) and (my_review is None)

    # Izin aksi spesifik Fase 5B
    can_propose_schedule = (rental.status in [Rental.Status.MENUNGGU_PEMBAYARAN, Rental.Status.DIBAYAR]) and (is_owner or is_renter)
    can_confirm_schedule = bool(
        latest_schedule and
        latest_schedule.status == HandoverSchedule.Status.DIUSULKAN and
        latest_schedule.proposed_by_id != request.user.id and
        rental.status in [Rental.Status.MENUNGGU_PEMBAYARAN, Rental.Status.DIBAYAR]
    )
    can_consent_photo = is_renter and not rental.handover_photo_consent_at and (rental.status == Rental.Status.DIBAYAR)
    can_confirm_ktm = (
        rental.item.require_ktm_held and
        not rental.ktm_held_confirmed_at and
        rental.status == Rental.Status.DIBAYAR and
        (is_owner or is_renter)
    )
    can_upload_sebelum = is_owner and (rental.status in [Rental.Status.MENUNGGU_PEMBAYARAN, Rental.Status.DIBAYAR])
    can_upload_serah_terima = (rental.status == Rental.Status.DIBAYAR) and bool(rental.handover_photo_consent_at)
    can_confirm_handover = (rental.status == Rental.Status.DIBAYAR)
    my_handover_confirmed = bool(rental.handed_over_owner_at if is_owner else rental.handed_over_renter_at)
    other_handover_confirmed = bool(rental.handed_over_renter_at if is_owner else rental.handed_over_owner_at)

    can_upload_sesudah = is_renter and (rental.status == Rental.Status.SEDANG_DISEWA)
    can_request_return = is_renter and (rental.status == Rental.Status.SEDANG_DISEWA)
    can_confirm_return = is_owner and (rental.status == Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN)
    can_agree_deduction = is_renter and (rental.status == Rental.Status.SENGKETA) and bool(dispute) and (dispute.status == Dispute.Status.TERBUKA)

    return render(request, 'rentals/rental_detail.html', {
        'rental': rental,
        'item': rental.item,
        'is_renter': is_renter,
        'is_owner': is_owner,
        'can_approve': can_approve,
        'can_reject': can_reject,
        'can_cancel': can_cancel,
        'show_pay_button': show_pay_button,
        'timeline_steps': timeline_steps,
        'active_step_index': active_step_index,
        'current_status_index': active_step_index,
        'is_terminal_failed': is_terminal_failed,
        'conversation': conversation,
        'show_whatsapp': show_whatsapp,
        'counterpart': counterpart,
        'counterpart_role': counterpart_role,
        'terms_snapshot': terms_snapshot,
        'max_loss_compensation': max_loss_compensation,
        'midtrans_ready': midtrans_ready,
        'midtrans_client_key': midtrans_client_key,
        'midtrans_snap_mode': midtrans_snap_mode,
        'ledger_entries': ledger_entries,
        'deposit_hold': deposit_hold,
        'latest_payment': latest_payment,
        'is_paid': is_paid,
        'midtrans_is_production': getattr(settings, 'MIDTRANS_IS_PRODUCTION', False),
        # Fase 5B context
        'photos_sebelum': photos_sebelum,
        'photos_serah_terima': photos_serah_terima,
        'photos_sesudah': photos_sesudah,
        'latest_schedule': latest_schedule,
        'meeting_points': meeting_points,
        'is_cross_campus': is_cross_campus,
        'dispute': dispute,
        'current_late_days': current_late_days,
        'current_late_fee': current_late_fee,
        'sisa_deposit': sisa_deposit,
        'my_review': my_review,
        'counterpart_review': counterpart_review,
        'can_review': can_review,
        'can_propose_schedule': can_propose_schedule,
        'can_confirm_schedule': can_confirm_schedule,
        'can_consent_photo': can_consent_photo,
        'can_confirm_ktm': can_confirm_ktm,
        'can_upload_sebelum': can_upload_sebelum,
        'can_upload_serah_terima': can_upload_serah_terima,
        'can_confirm_handover': can_confirm_handover,
        'my_handover_confirmed': my_handover_confirmed,
        'other_handover_confirmed': other_handover_confirmed,
        'can_upload_sesudah': can_upload_sesudah,
        'can_request_return': can_request_return,
        'can_confirm_return': can_confirm_return,
        'can_agree_deduction': can_agree_deduction,
    })


@login_required(login_url='/masuk/')
@require_POST
def rental_approve_view(request, code):
    """
    POST /sewa/<kode>/setujui/
    Pemilik menyetujui permintaan sewa.
    """
    rental = get_object_or_404(Rental, code=code)
    try:
        setujui_sewa(rental, request.user)
        messages.success(
            request,
            f"Permintaan sewa {rental.code} berhasil disetujui. Menunggu penyelesaian pembayaran oleh penyewa."
        )
    except RentalError as e:
        messages.error(request, str(e))
    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
@require_POST
def rental_reject_view(request, code):
    """
    POST /sewa/<kode>/tolak/
    Pemilik menolak permintaan sewa.
    """
    rental = get_object_or_404(Rental, code=code)
    reason = request.POST.get('reason', '').strip()
    try:
        tolak_sewa(rental, request.user, reason=reason)
        messages.info(request, f"Permintaan sewa {rental.code} telah ditolak.")
    except RentalError as e:
        messages.error(request, str(e))
    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
@require_POST
def rental_cancel_view(request, code):
    """
    POST /sewa/<kode>/batal/
    Penyewa atau pemilik membatalkan sewa sebelum pembayaran.
    """
    rental = get_object_or_404(Rental, code=code)
    reason = request.POST.get('reason', '').strip()
    if not reason:
        messages.error(request, "Alasan pembatalan wajib dicantumkan.")
        return redirect('rentals:rental_detail', code=code)

    try:
        batalkan_sewa(rental, request.user, reason=reason)
        messages.info(request, f"Sewa {rental.code} telah dibatalkan.")
    except (RentalError, ValueError) as e:
        messages.error(request, str(e))
    return redirect('rentals:rental_detail', code=code)


# ==============================================================================
# VIEW FASE 5B: AKSES FOTO PRIVAT, JADWAL, SERAH TERIMA, PENGEMBALIAN, ULASAN
# ==============================================================================

@login_required(login_url='/masuk/')
def rental_photo_serve_view(request, code, photo_id):
    """
    GET /sewa/<kode>/foto/<int:photo_id>/
    Melayani foto kondisi privat hanya untuk peserta sewa atau staf.
    Dilengkapi header Cache-Control: no-store, private (Anti-IDOR & proteksi privasi).
    """
    from django.http import FileResponse, Http404

    rental = get_object_or_404(Rental, code=code)
    is_participant = (
        request.user.id in [rental.renter_id, rental.owner_id] or
        request.user.is_staff or request.user.is_superuser
    )
    if not is_participant:
        return HttpResponseForbidden("Anda tidak berhak mengakses foto kondisi sewa ini.")

    from apps.rentals.models import ConditionPhoto
    photo = get_object_or_404(ConditionPhoto, id=photo_id, rental=rental)
    file_path = photo.private_file_path

    if not file_path or not file_path.exists():
        raise Http404("Berkas foto tidak ditemukan di penyimpanan privat.")

    response = FileResponse(open(file_path, 'rb'), content_type='image/jpeg')
    response['Cache-Control'] = 'no-store, private'
    return response


@login_required(login_url='/masuk/')
@require_POST
def handover_schedule_propose_view(request, code):
    """
    POST /sewa/<kode>/jadwal/usul/
    Peserta sewa mengusulkan jadwal serah terima barang.
    """
    from apps.accounts.models import MeetingPoint
    from apps.rentals.services import usulkan_jadwal_serah_terima

    rental = get_object_or_404(Rental, code=code)
    meet_at_raw = request.POST.get('meet_at', '').strip()
    meeting_point_id = request.POST.get('meeting_point_id', '').strip()
    note = request.POST.get('note', '').strip()

    if not meet_at_raw:
        messages.error(request, "Waktu pertemuan wajib diisi.")
        return redirect('rentals:rental_detail', code=code)

    try:
        # Format HTML datetime-local: YYYY-MM-DDTHH:MM
        current_tz = timezone.get_current_timezone()
        parsed_dt = datetime.fromisoformat(meet_at_raw)
        if timezone.is_naive(parsed_dt):
            meet_at = timezone.make_aware(parsed_dt, current_tz)
        else:
            meet_at = parsed_dt
    except ValueError:
        messages.error(request, "Format waktu tidak valid. Gunakan pemilih tanggal dan waktu yang disediakan.")
        return redirect('rentals:rental_detail', code=code)

    meeting_point = None
    if meeting_point_id:
        meeting_point = get_object_or_404(MeetingPoint, id=meeting_point_id)

    try:
        usulkan_jadwal_serah_terima(rental, request.user, meet_at, meeting_point, note)
        messages.success(request, "Usulan jadwal serah terima berhasil dikirimkan.")
    except (RentalError, ValueError) as e:
        messages.error(request, str(e))

    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
@require_POST
def handover_schedule_confirm_view(request, code):
    """
    POST /sewa/<kode>/jadwal/konfirmasi/
    Pihak lawan mengonfirmasi usulan jadwal serah terima terkini.
    """
    from apps.rentals.services import konfirmasi_jadwal_serah_terima

    rental = get_object_or_404(Rental, code=code)
    try:
        konfirmasi_jadwal_serah_terima(rental, request.user)
        messages.success(request, "Jadwal serah terima berhasil disepakati bersama.")
    except (RentalError, ValueError) as e:
        messages.error(request, str(e))

    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
@require_POST
def handover_photo_consent_view(request, code):
    """
    POST /sewa/<kode>/persetujuan-foto/
    Penyewa memberikan persetujuan dokumentasi foto serah terima.
    """
    from apps.rentals.services import setujui_foto_serah_terima

    rental = get_object_or_404(Rental, code=code)
    try:
        setujui_foto_serah_terima(rental, request.user)
        messages.success(request, "Persetujuan dokumentasi serah terima berhasil dicatat.")
    except (RentalError, ValueError) as e:
        messages.error(request, str(e))

    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
@require_POST
def handover_ktm_confirm_view(request, code):
    """
    POST /sewa/<kode>/konfirmasi-ktm/
    Peserta sewa mengonfirmasi penyerahan fisik KTM (jika require_ktm_held).
    """
    from apps.rentals.services import konfirmasi_ktm_ditahan

    rental = get_object_or_404(Rental, code=code)
    try:
        konfirmasi_ktm_ditahan(rental, request.user)
        messages.success(request, "Konfirmasi penyerahan fisik jaminan KTM berhasil dicatat.")
    except (RentalError, ValueError) as e:
        messages.error(request, str(e))

    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
@require_POST
def condition_photo_upload_view(request, code, phase):
    """
    POST /sewa/<kode>/foto/unggah/<str:phase>/
    Mengunggah foto kondisi barang (sebelum, serah_terima, sesudah).
    Mendukung upload file biasa dan jepretan kamera in-app via base64 canvas.
    """
    from apps.rentals.models import ConditionPhoto
    from apps.rentals.photos import save_condition_photo

    rental = get_object_or_404(Rental, code=code)
    if phase not in ConditionPhoto.Phase.values:
        messages.error(request, f"Fase foto '{phase}' tidak valid.")
        return redirect('rentals:rental_detail', code=code)

    # Validasi hak per fase
    if phase == ConditionPhoto.Phase.SEBELUM:
        if request.user.id != rental.owner_id and not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "Hanya pemilik barang yang dapat mengunggah foto kondisi sebelum sewa.")
            return redirect('rentals:rental_detail', code=code)
    elif phase == ConditionPhoto.Phase.SERAH_TERIMA:
        if not rental.handover_photo_consent_at:
            messages.error(request, "Pengambilan foto serah terima diblokir sebelum penyewa memberikan persetujuan.")
            return redirect('rentals:rental_detail', code=code)
    elif phase == ConditionPhoto.Phase.SESUDAH:
        if request.user.id != rental.renter_id and not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "Hanya penyewa yang dapat mengunggah foto kondisi sesudah sewa.")
            return redirect('rentals:rental_detail', code=code)

    photo_file = request.FILES.get('photo_file')
    photo_base64 = request.POST.get('photo_base64', '').strip()
    note = request.POST.get('note', '').strip()

    image_input = photo_file or (photo_base64 if photo_base64 else None)
    if not image_input:
        messages.error(request, "Pilih berkas foto atau ambil foto menggunakan kamera terlebih dahulu.")
        return redirect('rentals:rental_detail', code=code)

    try:
        save_condition_photo(rental, request.user, phase, image_input, note=note)
        messages.success(request, f"Foto kondisi ({phase}) berhasil disimpan.")
    except Exception as e:
        messages.error(request, f"Gagal memproses foto: {e}")

    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
@require_POST
def rental_handover_confirm_view(request, code):
    """
    POST /sewa/<kode>/serah-terima/
    Konfirmasi serah terima barang oleh salah satu pihak.
    Jika kedua pihak selesai dan semua prasyarat terpenuhi, status berubah ke sedang_disewa.
    """
    from apps.rentals.services import konfirmasi_serah_terima

    rental = get_object_or_404(Rental, code=code)
    try:
        updated_rental = konfirmasi_serah_terima(rental, request.user)
        if updated_rental.status == Rental.Status.SEDANG_DISEWA:
            messages.success(request, "Serah terima berhasil diselesaikan oleh kedua pihak! Masa sewa resmi dimulai.")
        else:
            messages.info(request, "Konfirmasi serah terima Anda telah disimpan. Menunggu konfirmasi dari pihak lawan.")
    except RentalError as e:
        messages.error(request, str(e))

    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
@require_POST
def rental_return_request_view(request, code):
    """
    POST /sewa/<kode>/kembalikan/
    Penyewa menekan 'Barang dikembalikan' dengan minimal 2 foto sesudah.
    """
    from apps.rentals.services import ajukan_pengembalian

    rental = get_object_or_404(Rental, code=code)
    try:
        ajukan_pengembalian(rental, request.user)
        messages.success(
            request,
            "Pengembalian barang berhasil diajukan. Pemilik barang akan memeriksa kondisi fisik sebelum menyelesaikan sewa."
        )
    except RentalError as e:
        messages.error(request, str(e))

    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
@require_POST
def rental_return_confirm_view(request, code):
    """
    POST /sewa/<kode>/konfirmasi-kembali/
    Pemilik memilih:
    1. 'baik': konfirmasi kondisi baik -> sewa selesai, dana diselesaikan.
    2. 'sengketa': laporkan masalah fisik dengan alasan dan potongan deposit -> status sengketa.
    """
    from apps.rentals.services import konfirmasi_pengembalian_baik, laporkan_masalah_sengketa

    rental = get_object_or_404(Rental, code=code)
    action_type = request.POST.get('action_type', 'baik').strip()

    if action_type == 'baik':
        try:
            konfirmasi_pengembalian_baik(rental, request.user)
            messages.success(
                request,
                f"Pengembalian barang dikonfirmasi dalam kondisi baik. Transaksi sewa {rental.code} resmi selesai!"
            )
        except RentalError as e:
            messages.error(request, str(e))
    elif action_type == 'sengketa':
        reason = request.POST.get('reason', '').strip()
        raw_deduction = request.POST.get('deduction_amount', '0').strip()
        try:
            deduction_amount = int(raw_deduction or 0)
        except ValueError:
            messages.error(request, "Nominal potongan harus berupa angka valid.")
            return redirect('rentals:rental_detail', code=code)

        try:
            laporkan_masalah_sengketa(rental, request.user, reason=reason, deduction_amount=deduction_amount)
            messages.warning(
                request,
                "Laporan masalah telah diajukan. Status sewa kini berada dalam 'Sengketa'."
            )
        except RentalError as e:
            messages.error(request, str(e))
    else:
        messages.error(request, "Jenis tindakan tidak dikenali.")

    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
@require_POST
def rental_dispute_agree_view(request, code):
    """
    POST /sewa/<kode>/setujui-potongan/
    Penyewa menyetujui nominal potongan deposit yang diajukan pemilik agar sengketa langsung selesai.
    """
    from apps.rentals.services import penyewa_setujui_potongan

    rental = get_object_or_404(Rental, code=code)
    try:
        penyewa_setujui_potongan(rental, request.user)
        messages.success(
            request,
            "Anda telah menyetujui potongan deposit. Transaksi sewa resmi selesai dan dana telah dicairkan."
        )
    except RentalError as e:
        messages.error(request, str(e))

    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
@require_POST
def rental_review_submit_view(request, code):
    """
    POST /sewa/<kode>/ulasan/
    Peserta sewa mengirimkan ulasan (1-5 bintang, komentar maks 300 karakter).
    Tidak dapat diubah setelah dikirim.
    """
    from apps.rentals.services import buat_ulasan

    rental = get_object_or_404(Rental, code=code)
    rating_raw = request.POST.get('rating', '').strip()
    comment = request.POST.get('comment', '').strip()

    try:
        rating = int(rating_raw)
    except ValueError:
        messages.error(request, "Silakan pilih rating bintang antara 1 dan 5.")
        return redirect('rentals:rental_detail', code=code)

    try:
        buat_ulasan(rental, request.user, rating=rating, comment=comment)
        messages.success(request, "Ulasan Anda berhasil dikirimkan. Terima kasih atas partisipasi Anda!")
    except RentalError as e:
        messages.error(request, str(e))

    return redirect('rentals:rental_detail', code=code)


@login_required(login_url='/masuk/')
def rental_agreement_view(request, code):
    """
    GET /sewa/<kode>/perjanjian/
    Halaman surat perjanjian sewa-menyewa digital yang dapat dicetak (printable).
    Memuat versi S&K, hash SHA-256, waktu persetujuan, identitas lengkap kedua pihak,
    IP address, user agent, dan klausul persetujuan resmi.
    Hanya peserta transaksi (penyewa & pemilik) atau staff/admin yang boleh mengakses.
    """
    rental = get_object_or_404(
        Rental.objects.select_related(
            'item', 'item__owner', 'renter', 'owner', 'agreement',
            'renter__student_profile__campus', 'owner__student_profile__campus'
        ),
        code=code
    )

    # Validasi Anti-IDOR
    is_renter = (request.user.id == rental.renter_id)
    is_owner = (request.user.id == rental.owner_id)
    if not (is_renter or is_owner or request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("Anda tidak berhak mengakses dokumen perjanjian sewa ini.")

    agreement = getattr(rental, 'agreement', None)
    terms_hash = ""
    if agreement:
        terms_hash = agreement.terms_hash
        if not terms_hash and isinstance(agreement.terms_snapshot, dict):
            terms_hash = agreement.terms_snapshot.get('terms_hash', '')
        if not terms_hash and agreement.terms_version:
            terms_hash = agreement.terms_version.calculate_sha256()
        if not terms_hash and getattr(agreement, 'terms_text_snapshot', None):
            terms_hash = hashlib.sha256(agreement.terms_text_snapshot.encode('utf-8')).hexdigest()
        if not terms_hash:
            terms_hash = hashlib.sha256(f"KampusRent-DigitalAgreement-{rental.code}".encode('utf-8')).hexdigest()

    return render(request, 'rentals/rental_agreement.html', {
        'rental': rental,
        'agreement': agreement,
        'terms_hash': terms_hash,
        'item': rental.item,
        'renter': rental.renter,
        'owner': rental.owner,
        'is_renter': is_renter,
        'is_owner': is_owner,
    })

