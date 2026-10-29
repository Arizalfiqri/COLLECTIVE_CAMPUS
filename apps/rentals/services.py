import logging
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.rentals.models import (
    Rental,
    RentalAgreement,
    ConditionPhoto,
    Review,
    Dispute,
    HandoverSchedule,
)
from apps.catalog.models import Item
from apps.accounts.models import User, BlacklistedNim
from apps.chat.models import Conversation
from apps.core.models import Notification
from apps.trust.services import (
    get_renter_tier,
    calculate_minimum_deposit,
    calculate_protection_fee,
    is_renter_eligible_for_item,
)

logger = logging.getLogger(__name__)


class RentalError(Exception):
    """Base exception untuk operasi sewa."""
    pass


class RentalStateError(RentalError):
    """Pengecualian saat transisi status tidak valid menurut state machine."""
    pass


class RentalPermissionError(RentalError):
    """Pengecualian saat pengguna tidak memiliki hak memicu transisi."""
    pass


class RentalValidationError(RentalError):
    """Pengecualian saat validasi parameter sewa gagal."""
    pass


# ==============================================================================
# 1. PENGAJUAN SEWA (RENTER -> MENUNGGU_PERSETUJUAN)
# ==============================================================================

def validate_rental_dates(item, start_date, end_date):
    """
    Validasi tanggal sewa sesuai spesifikasi:
    - start_date >= today
    - start_date <= today + 60 hari
    - end_date >= start_date
    - days = (end_date - start_date).days + 1
    - days di antara item.min_days dan item.max_days
    """
    today = timezone.localdate()
    if start_date < today:
        raise RentalValidationError("Tanggal mulai sewa tidak boleh sebelum hari ini.")

    max_future_start = today + timedelta(days=60)
    if start_date > max_future_start:
        raise RentalValidationError("Tanggal mulai sewa maksimal 60 hari ke depan.")

    if end_date < start_date:
        raise RentalValidationError("Tanggal selesai sewa tidak boleh sebelum tanggal mulai.")

    days = (end_date - start_date).days + 1
    if days < item.min_days or days > item.max_days:
        raise RentalValidationError(
            f"Durasi sewa harus antara {item.min_days} dan {item.max_days} hari (pilihan Anda: {days} hari)."
        )
    return days


def check_date_collision(item, start_date, end_date, exclude_rental_id=None):
    """
    Memeriksa tabrakan tanggal dengan sewa berstatus pemblokir:
    menunggu_pembayaran, dibayar, sedang_disewa, menunggu_konfirmasi_pengembalian, sengketa.
    """
    qs = Rental.objects.filter(
        item=item,
        status__in=Rental.BLOCKING_STATUSES,
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    if exclude_rental_id:
        qs = qs.exclude(id=exclude_rental_id)
    return qs.exists()


@transaction.atomic
def ajukan_sewa(item, renter, start_date, end_date, use_protection=False, terms_accepted=False, ip_address=None, user_agent=None):
    """
    Alur pengajuan sewa oleh penyewa:
    - Validasi akun penyewa (terverifikasi, tidak dibekukan, tidak memiliki tagihan tambahan terutang)
    - Validasi barang aktif & bukan milik sendiri
    - Validasi tanggal dan anti double-booking
    - Validasi tangga kepercayaan (tingkat penyewa & batas nilai barang)
    - Hanya satu permintaan aktif per barang per penyewa
    - Perhitungan deposit_total (nilai tertinggi barang vs kalkulasi tangga/lintas kampus)
    - Perhitungan rent_total, protection_fee, grand_total & simpan snapshot
    - Pembuatan RentalAgreement (terms_snapshot, hash SHA-256, identitas lengkap kedua pihak, IP, UA)
    - Hubungkan Conversation.rental
    - Kirim notifikasi ke pemilik
    """
    # 1. Validasi hak penyewa
    if not renter.is_authenticated:
        raise RentalPermissionError("Silakan masuk akun terlebih dahulu.")

    if not renter.is_verified_student:
        raise RentalPermissionError("Verifikasi KTM dulu untuk memasang barang atau menyewa.")

    if getattr(renter, 'is_suspended', False):
        raise RentalPermissionError("Akun Anda sedang dibekukan sehingga tidak dapat mengajukan sewa.")

    from apps.payments.models import ExtraCharge
    if ExtraCharge.objects.filter(renter=renter, status=ExtraCharge.Status.TERUTANG).exists():
        raise RentalValidationError("Anda memiliki tagihan denda atau ganti rugi yang belum diselesaikan (tagihan tambahan terutang). Harap lunasi tagihan terlebih dahulu sebelum mengajukan sewa baru.")

    # 2. Validasi barang
    if not item.is_active:
        raise RentalValidationError("Barang ini sedang tidak aktif dan tidak dapat disewa.")

    if item.owner_id == renter.id:
        raise RentalValidationError("Anda tidak dapat menyewa barang milik Anda sendiri.")

    if not terms_accepted:
        raise RentalValidationError("Anda wajib mencentang persetujuan syarat dan ketentuan sewa.")

    # 3. Validasi tanggal dan durasi
    days = validate_rental_dates(item, start_date, end_date)

    # 4. Validasi tangga kepercayaan & batas nilai barang
    eligible, reason = is_renter_eligible_for_item(renter, item)
    if not eligible:
        raise RentalValidationError(reason)

    # 5. Kunci item untuk mencegah race condition
    locked_item = Item.objects.select_for_update().get(id=item.id)

    # 6. Hanya satu permintaan aktif per barang per penyewa
    active_statuses = [
        Rental.Status.MENUNGGU_PERSETUJUAN,
        Rental.Status.MENUNGGU_PEMBAYARAN,
        Rental.Status.DIBAYAR,
        Rental.Status.SEDANG_DISEWA,
        Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN,
        Rental.Status.SENGKETA,
    ]
    if Rental.objects.filter(item=locked_item, renter=renter, status__in=active_statuses).exists():
        raise RentalValidationError("Anda sudah memiliki pengajuan sewa aktif untuk barang ini.")

    # 7. Validasi tabrakan tanggal dengan pesanan yang memblokir
    if check_date_collision(locked_item, start_date, end_date):
        raise RentalValidationError("Barang ini tidak tersedia pada rentang tanggal yang dipilih karena sudah dipesan penyewa lain.")

    # 8. Kalkulasi biaya dan deposit
    renter_tier = get_renter_tier(renter)
    renter_profile = getattr(renter, 'student_profile', None)
    owner_profile = getattr(locked_item.owner, 'student_profile', None)
    is_cross_campus = bool(
        renter_profile and owner_profile and
        renter_profile.campus_id and owner_profile.campus_id and
        renter_profile.campus_id != owner_profile.campus_id
    )

    deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
    if deposit_mode == 'off':
        deposit_total = 0
    elif deposit_mode == 'optional':
        deposit_total = locked_item.deposit_amount or 0
    else:
        min_dep_renter = calculate_minimum_deposit(locked_item.estimated_value, renter_tier, is_cross_campus)
        deposit_total = max(locked_item.deposit_amount, min_dep_renter)

    price_per_day = locked_item.price_per_day
    rent_total = price_per_day * days

    prot_calc = calculate_protection_fee(rent_total, locked_item.estimated_value)
    if prot_calc['is_mandatory']:
        use_protection = True
    protection_fee = prot_calc['fee'] if use_protection else 0

    grand_total = rent_total + deposit_total + protection_fee

    # 9. Buat instance Rental
    now = timezone.now()
    rental = Rental(
        item=locked_item,
        renter=renter,
        owner=locked_item.owner,
        start_date=start_date,
        end_date=end_date,
        days=days,
        price_per_day_snapshot=price_per_day,
        rent_total=rent_total,
        deposit_total=deposit_total,
        protection_fee=protection_fee,
        grand_total=grand_total,
        use_protection=use_protection,
        status=Rental.Status.MENUNGGU_PERSETUJUAN,
        requested_at=now,
        status_changed_at=now,
        handover_photo_consent_at=now,  # Persetujuan foto serah terima dicatat saat pengajuan (SPEC v2 C.3)
    )
    rental.save()

    # 10. Buat RentalAgreement digital dengan versi, hash, dan identitas lengkap kedua pihak
    from apps.core.models import TermsVersion
    active_terms = TermsVersion.objects.filter(
        term_type=TermsVersion.TermType.PENYEWA,
        is_active=True
    ).order_by('-valid_from', '-created_at').first()

    terms_version_str = active_terms.version if active_terms else 'v1.0'
    terms_hash = active_terms.calculate_sha256() if active_terms else ''
    terms_content = active_terms.content if active_terms else ''

    renter_name = getattr(renter, 'full_name', '') or renter.get_full_name() or renter.username
    renter_nim = renter_profile.nim if renter_profile else ''
    renter_campus = (renter_profile.campus.name if renter_profile and renter_profile.campus else '') or ''

    owner_user = locked_item.owner
    owner_name = getattr(owner_user, 'full_name', '') or owner_user.get_full_name() or owner_user.username
    owner_nim = owner_profile.nim if owner_profile else ''
    owner_campus = (owner_profile.campus.name if owner_profile and owner_profile.campus else '') or ''

    terms_snapshot = {
        'rental_code': rental.code,
        'item_title': locked_item.title,
        'estimated_value': locked_item.estimated_value,
        'price_per_day': price_per_day,
        'days': days,
        'rent_total': rent_total,
        'deposit_total': deposit_total,
        'protection_fee': protection_fee,
        'grand_total': grand_total,
        'use_protection': use_protection,
        'require_ktm_held': locked_item.require_ktm_held,
        'late_fee_per_day_percent': 50,
        'max_loss_compensation': locked_item.estimated_value,
        'accepted_by': renter.username,
        'accepted_at': now.isoformat(),
        'handover_photo_consent': True,
        'handover_photo_consent_at': now.isoformat(),
        'terms_version': terms_version_str,
        'terms_hash': terms_hash,
        'renter_name': renter_name,
        'renter_nim': renter_nim,
        'renter_campus': renter_campus,
        'owner_name': owner_name,
        'owner_nim': owner_nim,
        'owner_campus': owner_campus,
        'ip_address': str(ip_address) if ip_address else None,
        'user_agent': str(user_agent) if user_agent else '',
        'terms_text': terms_content or (
            "Penyewa menyetujui ketentuan sewa platform KampusRent: "
            "identitas yang diberikan benar, barang dipakai secara wajar dan tidak dipindahtangankan atau disewakan ulang, "
            "wajib dikembalikan sesuai jadwal, tanggung jawab penuh atas kehilangan dan kerusakan "
            f"(ganti rugi sebesar nilai taksiran Rp{locked_item.estimated_value:,} atau biaya perbaikan yang wajar), "
            "denda keterlambatan 50%/hari, tagihan tambahan dan konsekuensinya, persetujuan foto serah terima, "
            "persetujuan identitas dibagikan ke pemilik untuk tindak lanjut, penyelesaian sengketa melalui admin, dan platform sebagai perantara."
        ),
    }

    RentalAgreement.objects.create(
        rental=rental,
        terms_version=active_terms,
        terms_version_string=terms_version_str,
        terms_hash=terms_hash,
        terms_text_snapshot=terms_content,
        renter_name=renter_name,
        renter_nim=renter_nim,
        renter_campus=renter_campus,
        owner_name=owner_name,
        owner_nim=owner_nim,
        owner_campus=owner_campus,
        ip_address=ip_address,
        user_agent=user_agent or '',
        terms_snapshot=terms_snapshot,
    )

    # 10b. Catat snapshot fitur pelatihan ML skor kepercayaan (Fase 7C Bagian B)
    try:
        from apps.trust.services import record_training_snapshot
        record_training_snapshot(rental, renter)
    except Exception as e:
        logger.warning(f"Gagal mencatat snapshot pelatihan ML untuk sewa {rental.code}: {e}")

    # 11. Hubungkan atau buat percakapan chat
    conversation, _ = Conversation.objects.get_or_create(
        item=locked_item,
        renter=renter,
        defaults={'owner': locked_item.owner}
    )
    conversation.rental = rental
    conversation.save(update_fields=['rental'])

    # 12. Notifikasi ke pemilik
    Notification.notify(
        user=locked_item.owner,
        title="Permintaan Sewa Baru",
        message=f"Permintaan sewa baru untuk '{locked_item.title}' ({days} hari) dari {renter.full_name or renter.username}.",
        url=f"/sewa/{rental.code}/"
    )

    logger.info(f"Rental created: {rental.code} by {renter.username} for item {locked_item.id}")
    return rental


# ==============================================================================
# 2. PERSETUJUAN PEMILIK (MENUNGGU_PERSETUJUAN -> MENUNGGU_PEMBAYARAN)
# ==============================================================================

@transaction.atomic
def setujui_sewa(rental, user):
    """
    Pemilik menyetujui permintaan sewa:
    - Hanya pemilik (atau superuser) yang boleh memicu
    - Status awal wajib menunggu_persetujuan
    - Cek ulang tabrakan dengan select_for_update()
    - Ubah status menjadi menunggu_pembayaran & catat approved_at
    - Otomatis tolak permintaan lain yang bertabrakan dengan alasan "tanggal sudah dipesan"
    - Kirim notifikasi ke penyewa yang disetujui & penyewa yang ditolak otomatis
    """
    if not (user.id == rental.owner_id or user.is_staff or user.is_superuser):
        raise RentalPermissionError("Hanya pemilik barang yang dapat menyetujui permintaan sewa.")

    # Kunci baris rental dan item
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    locked_item = Item.objects.select_for_update().get(id=locked_rental.item_id)

    if locked_rental.status != Rental.Status.MENUNGGU_PERSETUJUAN:
        raise RentalStateError(
            f"Permintaan sewa tidak dapat disetujui dari status '{locked_rental.get_status_display()}'."
        )

    # Cek ulang tabrakan dengan sewa yang memblokir
    if check_date_collision(locked_item, locked_rental.start_date, locked_rental.end_date, exclude_rental_id=locked_rental.id):
        raise RentalValidationError("Tanggal sewa bertabrakan dengan pesanan lain yang sudah aktif.")

    now = timezone.now()
    locked_rental.status = Rental.Status.MENUNGGU_PEMBAYARAN
    locked_rental.approved_at = now
    locked_rental.status_changed_at = now
    locked_rental.save(update_fields=['status', 'approved_at', 'status_changed_at', 'updated_at'])

    # Otomatis tolak permintaan sewa lain yang bertabrakan
    conflicting_requests = Rental.objects.filter(
        item=locked_item,
        status=Rental.Status.MENUNGGU_PERSETUJUAN,
        start_date__lte=locked_rental.end_date,
        end_date__gte=locked_rental.start_date,
    ).exclude(id=locked_rental.id).select_for_update()

    auto_rejected_count = 0
    for other in conflicting_requests:
        other.status = Rental.Status.DITOLAK
        other.cancel_reason = "Tanggal sudah dipesan"
        other.status_changed_at = now
        other.save(update_fields=['status', 'cancel_reason', 'status_changed_at', 'updated_at'])
        auto_rejected_count += 1

        Notification.notify(
            user=other.renter,
            title="Permintaan Sewa Ditolak",
            message=f"Permintaan sewa Anda untuk '{other.item.title}' ditolak secara otomatis karena tanggal sudah dipesan penyewa lain.",
            url=f"/sewa/{other.code}/"
        )

    # Notifikasi ke penyewa utama
    Notification.notify(
        user=locked_rental.renter,
        title="Permintaan Sewa Disetujui",
        message=f"Permintaan sewa Anda untuk '{locked_rental.item.title}' telah disetujui pemilik. Silakan selesaikan pembayaran.",
        url=f"/sewa/{locked_rental.code}/"
    )

    logger.info(
        f"Rental {locked_rental.code} approved by {user.username}. Auto-rejected {auto_rejected_count} overlapping requests."
    )
    return locked_rental


# ==============================================================================
# 3. PENOLAKAN PEMILIK (MENUNGGU_PERSETUJUAN -> DITOLAK)
# ==============================================================================

@transaction.atomic
def tolak_sewa(rental, user, reason=""):
    """
    Pemilik menolak permintaan sewa:
    - Hanya pemilik (atau superuser) yang boleh memicu
    - Status awal wajib menunggu_persetujuan
    - Catat cancel_reason & status_changed_at
    - Kirim notifikasi ke penyewa
    """
    if not (user.id == rental.owner_id or user.is_staff or user.is_superuser):
        raise RentalPermissionError("Hanya pemilik barang yang dapat menolak permintaan sewa.")

    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    if locked_rental.status != Rental.Status.MENUNGGU_PERSETUJUAN:
        raise RentalStateError(
            f"Permintaan sewa tidak dapat ditolak dari status '{locked_rental.get_status_display()}'."
        )

    final_reason = reason.strip() if reason and reason.strip() else "Permintaan ditolak oleh pemilik."
    now = timezone.now()
    locked_rental.status = Rental.Status.DITOLAK
    locked_rental.cancel_reason = final_reason
    locked_rental.status_changed_at = now
    locked_rental.save(update_fields=['status', 'cancel_reason', 'status_changed_at', 'updated_at'])

    Notification.notify(
        user=locked_rental.renter,
        title="Permintaan Sewa Ditolak",
        message=f"Permintaan sewa Anda untuk '{locked_rental.item.title}' ditolak oleh pemilik: {final_reason}",
        url=f"/sewa/{locked_rental.code}/"
    )

    logger.info(f"Rental {locked_rental.code} rejected by owner {user.username}: {final_reason}")
    return locked_rental


# ==============================================================================
# 4. PEMBATALAN SEWA (SEBELUM BAYAR / SETELAH DIBAYAR -> DIBATALKAN)
# ==============================================================================

@transaction.atomic
def batalkan_sewa(rental, user, reason):
    """
    Pembatalan sewa:
    - Boleh dipicu oleh penyewa atau pemilik (atau admin)
    - Wajib mencantumkan alasan
    - Status awal: menunggu_persetujuan, menunggu_pembayaran, atau dibayar
    - Jika status dibayar: menjalankan simulasi refund di buku besar (process_cancellation_after_payment)
    - Catat cancelled_by, cancel_reason, dan status_changed_at
    - Kirim notifikasi ke pihak lawan
    """
    if not reason or not reason.strip():
        raise RentalValidationError("Alasan pembatalan wajib dicantumkan.")

    is_participant = (user.id == rental.renter_id or user.id == rental.owner_id or user.is_staff or user.is_superuser)
    if not is_participant:
        raise RentalPermissionError("Hanya penyewa atau pemilik yang berhak membatalkan sewa ini.")

    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    allowed_statuses = [
        Rental.Status.MENUNGGU_PERSETUJUAN,
        Rental.Status.MENUNGGU_PEMBAYARAN,
        Rental.Status.DIBAYAR,
    ]
    if locked_rental.status not in allowed_statuses:
        raise RentalStateError(
            f"Sewa dengan status '{locked_rental.get_status_display()}' tidak dapat dibatalkan."
        )

    clean_reason = reason.strip()

    # Jika sudah dibayar, proses refund simulasi di buku besar sesuai aturan SPEC
    if locked_rental.status == Rental.Status.DIBAYAR:
        from apps.payments.services import process_cancellation_after_payment
        process_cancellation_after_payment(locked_rental, cancelled_by=user, reason=clean_reason)

    now = timezone.now()
    locked_rental.status = Rental.Status.DIBATALKAN
    locked_rental.cancelled_by = user
    locked_rental.cancel_reason = clean_reason
    locked_rental.status_changed_at = now
    locked_rental.save(update_fields=['status', 'cancelled_by', 'cancel_reason', 'status_changed_at', 'updated_at'])

    # Kirim notifikasi ke pihak lain
    if user.id == locked_rental.renter_id:
        target_user = locked_rental.owner
        party_label = "Penyewa"
    else:
        target_user = locked_rental.renter
        party_label = "Pemilik"

    Notification.notify(
        user=target_user,
        title="Sewa Dibatalkan",
        message=f"{party_label} membatalkan sewa '{locked_rental.item.title}' ({locked_rental.code}): {clean_reason}",
        url=f"/sewa/{locked_rental.code}/"
    )

    logger.info(f"Rental {locked_rental.code} cancelled by {user.username}: {clean_reason}")
    return locked_rental


# ==============================================================================
# 5. KEDALUWARSA BATAS WAKTU (MENUNGGU_PERSETUJUAN / MENUNGGU_PEMBAYARAN -> KEDALUWARSA)
# ==============================================================================

@transaction.atomic
def kedaluwarsa_sewa(rental, reason=""):
    """
    Sewa kedaluwarsa otomatis oleh sistem:
    - Status awal: menunggu_persetujuan atau menunggu_pembayaran
    - Catat cancel_reason & status_changed_at
    - Kirim notifikasi ke kedua belah pihak
    """
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    allowed_statuses = [
        Rental.Status.MENUNGGU_PERSETUJUAN,
        Rental.Status.MENUNGGU_PEMBAYARAN,
    ]
    if locked_rental.status not in allowed_statuses:
        # Jika sudah bukan status menunggu, abaikan secara idempoten
        return locked_rental

    now = timezone.now()
    old_status = locked_rental.status
    if not reason:
        if old_status == Rental.Status.MENUNGGU_PERSETUJUAN:
            reason = "Batas waktu persetujuan pemilik telah berakhir (24 jam)."
        else:
            pay_deadline = getattr(settings, 'PAYMENT_DEADLINE_HOURS', 6)
            reason = f"Batas waktu pembayaran penyewa telah berakhir ({pay_deadline} jam)."

    locked_rental.status = Rental.Status.KEDALUWARSA
    locked_rental.cancel_reason = reason
    locked_rental.status_changed_at = now
    locked_rental.save(update_fields=['status', 'cancel_reason', 'status_changed_at', 'updated_at'])

    # Notifikasi ke kedua pihak
    Notification.notify(
        user=locked_rental.renter,
        title="Sewa Kedaluwarsa",
        message=f"Permintaan sewa '{locked_rental.item.title}' ({locked_rental.code}) kedaluwarsa: {reason}",
        url=f"/sewa/{locked_rental.code}/"
    )
    Notification.notify(
        user=locked_rental.owner,
        title="Sewa Kedaluwarsa",
        message=f"Permintaan sewa '{locked_rental.item.title}' ({locked_rental.code}) kedaluwarsa: {reason}",
        url=f"/sewa/{locked_rental.code}/"
    )

    logger.info(f"Rental {locked_rental.code} marked as expired: {reason}")
    return locked_rental


# ==============================================================================
# 6. TRANSISI FASE 5B: SIKLUS SERAH TERIMA, PENGEMBALIAN, SENGKETA & ULASAN
# ==============================================================================

@transaction.atomic
def konfirmasi_pembayaran(rental, payment_record=None):
    """
    Transisi: menunggu_pembayaran -> dibayar.
    Dipanggil saat webhook Midtrans atau sinkronisasi status pembayaran berhasil.
    """
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    if locked_rental.status == Rental.Status.DIBAYAR:
        return locked_rental
    if locked_rental.status != Rental.Status.MENUNGGU_PEMBAYARAN:
        raise RentalStateError(f"Tidak dapat mengubah ke 'dibayar' dari status '{locked_rental.get_status_display()}'.")
    now = timezone.now()
    locked_rental.status = Rental.Status.DIBAYAR
    locked_rental.status_changed_at = now
    locked_rental.save(update_fields=['status', 'status_changed_at', 'updated_at'])

    Notification.notify(
        user=locked_rental.owner,
        title="Pembayaran Sewa Diterima",
        message=f"Penyewa telah membayar sewa '{locked_rental.item.title}'. Dana aman di platform (Escrow). Silakan jadwalkan serah terima.",
        url=f"/sewa/{locked_rental.code}/"
    )
    Notification.notify(
        user=locked_rental.renter,
        title="Pembayaran Berhasil",
        message=f"Pembayaran sewa '{locked_rental.item.title}' berhasil diverifikasi. Dana ditahan di platform.",
        url=f"/sewa/{locked_rental.code}/"
    )
    return locked_rental


@transaction.atomic
def usulkan_jadwal_serah_terima(rental, user, meet_at, meeting_point, note=""):
    """
    Mengusulkan jadwal serah terima (HandoverSchedule):
    - Dilakukan oleh pemilik atau penyewa pada status DIBAYAR (atau MENUNGGU_PEMBAYARAN)
    - Validasi: penyewa lintas kampus hanya boleh memilih titik temu publik (is_public=True)
    - Mencatat HandoverSchedule dengan status DIUSULKAN
    - Mengirim notifikasi ke pihak lawan
    """
    if user.id not in [rental.renter_id, rental.owner_id] and not (user.is_staff or user.is_superuser):
        raise RentalPermissionError("Hanya peserta sewa yang dapat mengusulkan jadwal serah terima.")

    allowed_statuses = [Rental.Status.MENUNGGU_PEMBAYARAN, Rental.Status.DIBAYAR]
    if rental.status not in allowed_statuses:
        raise RentalStateError("Jadwal serah terima hanya dapat diatur sebelum barang diserahterimakan.")

    # Validasi lintas kampus
    renter_campus_id = User.objects.filter(id=rental.renter_id).values_list('student_profile__campus_id', flat=True).first()
    owner_campus_id = User.objects.filter(id=rental.owner_id).values_list('student_profile__campus_id', flat=True).first()
    if renter_campus_id and owner_campus_id and renter_campus_id != owner_campus_id:
        if meeting_point and not meeting_point.is_public:
            raise RentalValidationError("Penyewa lintas kampus hanya dapat memilih titik temu publik yang ramai.")

    schedule = HandoverSchedule.objects.create(
        rental=rental,
        proposed_by=user,
        meet_at=meet_at,
        meeting_point=meeting_point,
        status=HandoverSchedule.Status.DIUSULKAN,
        note=note.strip() if note else "",
    )

    counterpart = rental.owner if user.id == rental.renter_id else rental.renter
    party_label = "Penyewa" if user.id == rental.renter_id else "Pemilik"
    Notification.notify(
        user=counterpart,
        title="Usulan Jadwal Serah Terima",
        message=f"{party_label} mengusulkan jadwal serah terima barang '{rental.item.title}' pada {meet_at.strftime('%d %b %Y, %H:%M')}.",
        url=f"/sewa/{rental.code}/"
    )
    return schedule


@transaction.atomic
def konfirmasi_jadwal_serah_terima(rental, user):
    """Pihak lawan mengonfirmasi usulan jadwal serah terima terkini."""
    schedule = rental.handover_schedules.order_by('-created_at').first()
    if not schedule:
        raise RentalValidationError("Belum ada jadwal serah terima yang diusulkan.")

    if user.id not in [rental.renter_id, rental.owner_id] and not (user.is_staff or user.is_superuser):
        raise RentalPermissionError("Hanya peserta sewa yang dapat mengonfirmasi jadwal.")

    if schedule.proposed_by_id == user.id and not (user.is_staff or user.is_superuser):
        raise RentalValidationError("Anda tidak dapat mengonfirmasi jadwal yang Anda usulkan sendiri.")

    schedule.status = HandoverSchedule.Status.DIKONFIRMASI
    schedule.save(update_fields=['status', 'updated_at'])

    counterpart = rental.owner if user.id == rental.renter_id else rental.renter
    Notification.notify(
        user=counterpart,
        title="Jadwal Serah Terima Dikonfirmasi",
        message=f"Jadwal serah terima barang '{rental.item.title}' telah disepakati untuk {schedule.meet_at.strftime('%d %b %Y, %H:%M')}.",
        url=f"/sewa/{rental.code}/"
    )
    return schedule


@transaction.atomic
def setujui_foto_serah_terima(rental, user):
    """Penyewa menyetujui dokumentasi serah terima di aplikasi."""
    if user.id != rental.renter_id and not (user.is_staff or user.is_superuser):
        raise RentalPermissionError("Hanya penyewa yang dapat menyetujui dokumentasi serah terima.")

    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    now = timezone.now()
    locked_rental.handover_photo_consent_at = now
    locked_rental.save(update_fields=['handover_photo_consent_at', 'updated_at'])
    return locked_rental


@transaction.atomic
def konfirmasi_ktm_ditahan(rental, user):
    """Kedua pihak mengonfirmasi penyerahan fisik KTM (jika require_ktm_held)."""
    if not rental.item.require_ktm_held:
        raise RentalValidationError("Sewa barang ini tidak mensyaratkan penahanan fisik KTM.")

    if user.id not in [rental.renter_id, rental.owner_id] and not (user.is_staff or user.is_superuser):
        raise RentalPermissionError("Hanya peserta sewa yang dapat mengonfirmasi penahanan KTM.")

    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    now = timezone.now()
    locked_rental.ktm_held_confirmed_at = now
    locked_rental.save(update_fields=['ktm_held_confirmed_at', 'updated_at'])

    Notification.notify(
        user=rental.owner if user.id == rental.renter_id else rental.renter,
        title="Konfirmasi KTM Ditahan",
        message=f"Penyerahan fisik jaminan KTM untuk sewa '{rental.code}' telah dikonfirmasi.",
        url=f"/sewa/{rental.code}/"
    )
    return locked_rental


@transaction.atomic
def konfirmasi_serah_terima(rental, user):
    """
    Transisi: dibayar -> sedang_disewa.
    Prasyarat wajib:
    1. Pemilik unggah minimal 2 foto kondisi sebelum (phase='sebelum')
    2. Foto serah terima di aplikasi minimal 1 foto (phase='serah_terima')
    3. Persetujuan dokumentasi foto penyewa (handover_photo_consent_at)
    4. Jika require_ktm_held: konfirmasi KTM diserahkan (ktm_held_confirmed_at)
    5. Kedua belah pihak mengonfirmasi serah terima (handed_over_owner_at dan handed_over_renter_at)
    """
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    if locked_rental.status != Rental.Status.DIBAYAR:
        raise RentalStateError(f"Tidak dapat melakukan serah terima dari status '{locked_rental.get_status_display()}'.")

    now = timezone.now()
    if user.id == locked_rental.owner_id:
        locked_rental.handed_over_owner_at = now
    elif user.id == locked_rental.renter_id:
        locked_rental.handed_over_renter_at = now
    elif user.is_staff or user.is_superuser:
        locked_rental.handed_over_owner_at = locked_rental.handed_over_owner_at or now
        locked_rental.handed_over_renter_at = locked_rental.handed_over_renter_at or now
    else:
        raise RentalPermissionError("Hanya peserta sewa yang dapat mengonfirmasi serah terima.")

    # Evaluasi prasyarat
    missing = []
    before_count = locked_rental.condition_photos.filter(phase=ConditionPhoto.Phase.SEBELUM).count()
    if before_count < 2:
        missing.append("Pemilik wajib mengunggah minimal 2 foto kondisi sebelum sewa")

    handover_count = locked_rental.condition_photos.filter(phase=ConditionPhoto.Phase.SERAH_TERIMA).count()
    if handover_count < 1:
        missing.append("Wajib mengambil minimal 1 foto serah terima barang di aplikasi")

    if not locked_rental.handover_photo_consent_at:
        missing.append("Penyewa belum memberikan persetujuan dokumentasi serah terima")

    if locked_rental.item.require_ktm_held and not locked_rental.ktm_held_confirmed_at:
        missing.append("Konfirmasi fisik penyerahan KTM belum dilakukan")

    # Jika kedua belah pihak sudah mengonfirmasi:
    if locked_rental.handed_over_owner_at and locked_rental.handed_over_renter_at:
        if missing:
            # Simpan timestamp konfirmasi pihak yang bersangkutan, namun tolak transisi status
            locked_rental.save(update_fields=['handed_over_owner_at', 'handed_over_renter_at', 'updated_at'])
            raise RentalValidationError("Serah terima belum dapat diselesaikan: " + "; ".join(missing) + ".")

        # Semua prasyarat lengkap -> SEDANG_DISEWA
        locked_rental.status = Rental.Status.SEDANG_DISEWA
        locked_rental.status_changed_at = now
        locked_rental.save(update_fields=[
            'status', 'handed_over_owner_at', 'handed_over_renter_at',
            'status_changed_at', 'updated_at'
        ])

        Notification.notify(
            user=locked_rental.renter,
            title="Masa Sewa Dimulai",
            message=f"Serah terima barang '{locked_rental.item.title}' selesai. Selamat menggunakan barang! Jaga kondisi hingga batas waktu pengembalian.",
            url=f"/sewa/{locked_rental.code}/"
        )
        Notification.notify(
            user=locked_rental.owner,
            title="Masa Sewa Dimulai",
            message=f"Barang '{locked_rental.item.title}' telah aktif disewa oleh {locked_rental.renter.full_name or locked_rental.renter.username}.",
            url=f"/sewa/{locked_rental.code}/"
        )
    else:
        # Hanya satu pihak yang baru mengonfirmasi
        locked_rental.save(update_fields=['handed_over_owner_at', 'handed_over_renter_at', 'updated_at'])
        party = "Pemilik" if user.id == locked_rental.owner_id else "Penyewa"
        counterpart = locked_rental.renter if user.id == locked_rental.owner_id else locked_rental.owner
        Notification.notify(
            user=counterpart,
            title="Menunggu Konfirmasi Serah Terima",
            message=f"{party} telah mengonfirmasi serah terima barang '{locked_rental.item.title}'. Mohon segera konfirmasi dari akun Anda.",
            url=f"/sewa/{locked_rental.code}/"
        )

    return locked_rental


@transaction.atomic
def ajukan_pengembalian(rental, user):
    """
    Transisi: sedang_disewa -> menunggu_konfirmasi_pengembalian.
    Penyewa mengonfirmasi barang telah dikembalikan:
    - Wajib mengunggah minimal 2 foto kondisi sesudah (phase='sesudah')
    - Mencatat returned_date = localdate()
    - Menghitung late_days dan late_fee (maksimal sisa deposit)
    """
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    if locked_rental.status != Rental.Status.SEDANG_DISEWA:
        raise RentalStateError(f"Tidak dapat mengajukan pengembalian dari status '{locked_rental.get_status_display()}'.")

    if user.id != locked_rental.renter_id and not (user.is_staff or user.is_superuser):
        raise RentalPermissionError("Hanya penyewa yang dapat mengajukan pengembalian barang.")

    # Validasi foto sesudah minimal 2
    after_count = locked_rental.condition_photos.filter(phase=ConditionPhoto.Phase.SESUDAH).count()
    if after_count < 2:
        raise RentalValidationError("Minimal 2 foto kondisi barang sesudah sewa wajib diunggah sebelum mengajukan pengembalian.")

    now = timezone.now()
    returned_date = timezone.localdate()

    # Hitung keterlambatan sesuai PROJECT_SPEC.md 7.2
    late_days = max(0, (returned_date - locked_rental.end_date).days)
    full_late_fee = round(locked_rental.price_per_day_snapshot * 0.5 * late_days)

    deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
    if deposit_mode == 'off':
        late_fee = 0
        if full_late_fee > 0:
            from apps.payments.models import ExtraCharge
            ExtraCharge.objects.update_or_create(
                rental=locked_rental,
                charge_type=ExtraCharge.ChargeType.KETERLAMBATAN,
                defaults={
                    'renter': locked_rental.renter,
                    'owner': locked_rental.owner,
                    'amount': full_late_fee,
                    'reason': f"Denda keterlambatan pengembalian {late_days} hari (50%/hari x Rp{locked_rental.price_per_day_snapshot:,})",
                    'status': ExtraCharge.Status.TERUTANG,
                }
            )
            Notification.notify(
                user=locked_rental.renter,
                title="Denda Keterlambatan Pengembalian",
                message=f"Pengembalian barang terlambat {late_days} hari. Denda keterlambatan sebesar Rp{full_late_fee:,} telah dicatat sebagai tagihan tambahan.",
                url=f"/sewa/{locked_rental.code}/"
            )
    else:
        late_fee = min(full_late_fee, locked_rental.deposit_total)

    locked_rental.status = Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN
    locked_rental.return_requested_at = now
    locked_rental.returned_date = returned_date
    locked_rental.late_days = late_days
    locked_rental.late_fee = late_fee
    locked_rental.status_changed_at = now
    locked_rental.save(update_fields=[
        'status', 'return_requested_at', 'returned_date', 'late_days',
        'late_fee', 'status_changed_at', 'updated_at'
    ])

    Notification.notify(
        user=locked_rental.owner,
        title="Barang Telah Dikembalikan",
        message=f"Penyewa telah mengembalikan barang '{locked_rental.item.title}'. Mohon periksa fisik barang dan konfirmasi kondisi.",
        url=f"/sewa/{locked_rental.code}/"
    )
    return locked_rental


@transaction.atomic
def konfirmasi_pengembalian_baik(rental, user=None):
    """
    Transisi: menunggu_konfirmasi_pengembalian -> selesai (kondisi baik).
    - Jika require_ktm_held: wajib konfirmasi pengembalian KTM fisik (ktm_returned_confirmed_at)
    - Menyelesaikan sewa dan memanggil settle_rental_funds(late_fee=rental.late_fee, damage_fee=0)
    - Menghitung ulang skor kepercayaan (recompute_trust_score) kedua pihak
    """
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    if locked_rental.status != Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN:
        raise RentalStateError(f"Tidak dapat menyelesaikan sewa dari status '{locked_rental.get_status_display()}'.")

    if user and user.id != locked_rental.owner_id and not (user.is_staff or user.is_superuser):
        raise RentalPermissionError("Hanya pemilik barang yang dapat mengonfirmasi pengembalian barang.")

    now = timezone.now()
    if locked_rental.item.require_ktm_held:
        locked_rental.ktm_returned_confirmed_at = now

    locked_rental.status = Rental.Status.SELESAI
    locked_rental.status_changed_at = now
    locked_rental.save(update_fields=[
        'status', 'ktm_returned_confirmed_at', 'status_changed_at', 'updated_at'
    ])

    # Selesaikan dana escrow dan buku besar
    from apps.payments.services import settle_rental_funds
    settle_rental_funds(locked_rental, late_fee=locked_rental.late_fee, damage_fee=0)

    # Hitung ulang skor kepercayaan dan labeli data latih
    from apps.trust.services import recompute_trust_score, label_training_example_for_rental
    label_training_example_for_rental(locked_rental)
    recompute_trust_score(locked_rental.renter)
    recompute_trust_score(locked_rental.owner)

    Notification.notify(
        user=locked_rental.renter,
        title="Sewa Selesai",
        message=f"Pemilik telah mengonfirmasi barang '{locked_rental.item.title}' kembali dalam kondisi baik. Sisa deposit Anda telah dikembalikan ke saldo dompet akun Anda.",
        url=f"/sewa/{locked_rental.code}/"
    )
    Notification.notify(
        user=locked_rental.owner,
        title="Sewa Selesai",
        message=f"Transaksi sewa '{locked_rental.item.title}' ({locked_rental.code}) telah selesai dan dana sewa bersih telah dicairkan ke saldo dompet akun Anda.",
        url=f"/sewa/{locked_rental.code}/"
    )
    return locked_rental


@transaction.atomic
def laporkan_masalah_sengketa(rental, user, reason, deduction_amount=0):
    """
    Transisi: menunggu_konfirmasi_pengembalian -> sengketa.
    Pemilik melaporkan masalah fisik/kehilangan barang:
    - deduction_amount maksimal adalah sisa deposit (deposit_total - late_fee)
    - Membuka objek Dispute baru berstatus TERBUKA
    """
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    if locked_rental.status != Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN:
        raise RentalStateError(f"Tidak dapat membuka sengketa dari status '{locked_rental.get_status_display()}'.")

    if user.id != locked_rental.owner_id and not (user.is_staff or user.is_superuser):
        raise RentalPermissionError("Hanya pemilik barang yang dapat melaporkan kendala sewa.")

    if not reason or not reason.strip():
        raise RentalValidationError("Alasan pelaporan masalah wajib diisi.")

    deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
    deduction = int(deduction_amount or 0)
    if deposit_mode == 'off':
        max_allowed = locked_rental.item.estimated_value
        if deduction > max_allowed:
            raise RentalValidationError(
                f"Nominal ganti rugi (Rp{deduction:,}) tidak boleh melebihi nilai taksiran barang (Rp{max_allowed:,})."
            )
    else:
        sisa_deposit = max(0, locked_rental.deposit_total - locked_rental.late_fee)
        if deduction > sisa_deposit:
            raise RentalValidationError(
                f"Nominal potongan (Rp{deduction:,}) tidak boleh melebihi sisa deposit jaminan (Rp{sisa_deposit:,})."
            )

    now = timezone.now()
    locked_rental.damage_fee = deduction
    locked_rental.status = Rental.Status.SENGKETA
    locked_rental.status_changed_at = now
    locked_rental.save(update_fields=['status', 'damage_fee', 'status_changed_at', 'updated_at'])

    dispute, _ = Dispute.objects.update_or_create(
        rental=locked_rental,
        defaults={
            'opened_by': user,
            'reason': reason.strip(),
            'deduction_amount': deduction,
            'status': Dispute.Status.TERBUKA,
        }
    )

    Notification.notify(
        user=locked_rental.renter,
        title="Laporan Masalah Sewa (Sengketa)",
        message=f"Pemilik melaporkan kendala pada sewa '{locked_rental.item.title}': {reason.strip()}. Anda dapat menyetujui potongan atau menunggu keputusan admin.",
        url=f"/sewa/{locked_rental.code}/"
    )
    return locked_rental


@transaction.atomic
def penyewa_setujui_potongan(rental, user):
    """
    Penyewa menyetujui nominal potongan yang diajukan pemilik:
    - Status langsung menjadi SELESAI tanpa campur tangan admin
    - Saat DEPOSIT_MODE=off: dicatat sebagai ExtraCharge(kerusakan) terutang, tanpa potongan deposit
    - Saat legacy: dipotong dari deposit
    - Dana sewa diselesaikan dan diteruskan ke pemilik seperti biasa
    """
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    if locked_rental.status != Rental.Status.SENGKETA:
        raise RentalStateError("Hanya sewa berstatus sengketa yang dapat disetujui potongannya.")

    if user.id != locked_rental.renter_id and not (user.is_staff or user.is_superuser):
        raise RentalPermissionError("Hanya penyewa yang berhak menyetujui potongan deposit.")

    dispute = getattr(locked_rental, 'dispute', None)
    if not dispute or dispute.status != Dispute.Status.TERBUKA:
        raise RentalValidationError("Tidak ada sengketa terbuka yang memerlukan persetujuan.")

    now = timezone.now()
    deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
    if deposit_mode == 'off':
        if dispute.deduction_amount > 0:
            from apps.payments.models import ExtraCharge
            ExtraCharge.objects.update_or_create(
                rental=locked_rental,
                charge_type=ExtraCharge.ChargeType.KERUSAKAN,
                defaults={
                    'renter': locked_rental.renter,
                    'owner': locked_rental.owner,
                    'amount': dispute.deduction_amount,
                    'reason': f"Ganti rugi kerusakan disetujui penyewa: {dispute.reason}",
                    'status': ExtraCharge.Status.TERUTANG,
                }
            )
            Notification.notify(
                user=locked_rental.renter,
                title="Tagihan Ganti Rugi Kerusakan",
                message=f"Tagihan ganti rugi sebesar Rp{dispute.deduction_amount:,} telah dicatat untuk sewa '{locked_rental.code}'. Harap segera lakukan pelunasan.",
                url=f"/sewa/{locked_rental.code}/"
            )
        damage_fee_to_settle = 0
        decision = Dispute.Decision.POTONG_PENUH if dispute.deduction_amount >= locked_rental.item.estimated_value else Dispute.Decision.POTONG_SEBAGIAN
    else:
        sisa_deposit = max(0, locked_rental.deposit_total - locked_rental.late_fee)
        decision = Dispute.Decision.POTONG_PENUH if dispute.deduction_amount >= sisa_deposit else Dispute.Decision.POTONG_SEBAGIAN
        damage_fee_to_settle = dispute.deduction_amount

    dispute.decision = decision
    dispute.status = Dispute.Status.DIPUTUSKAN
    dispute.decided_by = user
    dispute.decision_note = "Disetujui langsung oleh penyewa tanpa campur tangan admin."
    dispute.save()

    if locked_rental.item.require_ktm_held and not locked_rental.ktm_returned_confirmed_at:
        locked_rental.ktm_returned_confirmed_at = now

    locked_rental.status = Rental.Status.SELESAI
    locked_rental.damage_fee = damage_fee_to_settle
    locked_rental.status_changed_at = now
    locked_rental.save(update_fields=[
        'status', 'damage_fee', 'ktm_returned_confirmed_at', 'status_changed_at', 'updated_at'
    ])

    from apps.payments.services import settle_rental_funds
    settle_rental_funds(locked_rental, late_fee=locked_rental.late_fee, damage_fee=damage_fee_to_settle)

    from apps.trust.services import recompute_trust_score, label_training_example_for_rental
    label_training_example_for_rental(locked_rental)
    recompute_trust_score(locked_rental.renter)
    recompute_trust_score(locked_rental.owner)

    Notification.notify(
        user=locked_rental.owner,
        title="Potongan Sengketa Disetujui",
        message=f"Penyewa menyetujui ganti rugi Rp{dispute.deduction_amount:,}. Sewa '{locked_rental.code}' resmi selesai.",
        url=f"/sewa/{locked_rental.code}/"
    )
    return locked_rental


@transaction.atomic
def selesaikan_sengketa_admin(rental, admin_user, decision, deduction_amount=0, decision_note=""):
    """
    Keputusan resmi admin untuk menyelesaikan sengketa sewa:
    - decision: kembalikan_penuh, potong_sebagian, potong_penuh
    - Saat DEPOSIT_MODE=off: dicatat sebagai ExtraCharge(kerusakan) terutang
    - Menjalankan settle_rental_funds dan menyelesaikan sewa
    - Buku besar dan invarian tetap seimbang
    """
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    if locked_rental.status != Rental.Status.SENGKETA:
        raise RentalStateError(f"Tidak dapat memutuskan sengketa dari status '{locked_rental.get_status_display()}'.")

    if not (admin_user.is_staff or admin_user.is_superuser):
        raise RentalPermissionError("Hanya staf admin yang berhak memutuskan sengketa.")

    deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
    if deposit_mode == 'off':
        if decision == Dispute.Decision.KEMBALIKAN_PENUH:
            charge_amount = 0
        elif decision == Dispute.Decision.POTONG_PENUH:
            charge_amount = locked_rental.item.estimated_value
        else:
            charge_amount = min(int(deduction_amount or 0), locked_rental.item.estimated_value)

        if charge_amount > 0:
            from apps.payments.models import ExtraCharge
            ExtraCharge.objects.update_or_create(
                rental=locked_rental,
                charge_type=ExtraCharge.ChargeType.KERUSAKAN,
                defaults={
                    'renter': locked_rental.renter,
                    'owner': locked_rental.owner,
                    'amount': charge_amount,
                    'reason': f"Ganti rugi kerusakan diputuskan admin: {decision_note or dispute.reason}",
                    'status': ExtraCharge.Status.TERUTANG,
                }
            )
            Notification.notify(
                user=locked_rental.renter,
                title="Tagihan Ganti Rugi Diputuskan Admin",
                message=f"Admin menetapkan tagihan ganti rugi sebesar Rp{charge_amount:,} untuk sewa '{locked_rental.item.title}'.",
                url=f"/sewa/{locked_rental.code}/"
            )
        damage_fee_to_settle = 0
        dispute_damage_fee = charge_amount
    else:
        sisa_deposit = max(0, locked_rental.deposit_total - locked_rental.late_fee)
        if decision == Dispute.Decision.KEMBALIKAN_PENUH:
            damage_fee = 0
        elif decision == Dispute.Decision.POTONG_PENUH:
            damage_fee = sisa_deposit
        else:  # POTONG_SEBAGIAN
            damage_fee = min(int(deduction_amount or 0), sisa_deposit)
        damage_fee_to_settle = damage_fee
        dispute_damage_fee = damage_fee

    dispute = getattr(locked_rental, 'dispute', None)
    if not dispute:
        dispute = Dispute.objects.create(
            rental=locked_rental,
            opened_by=locked_rental.owner,
            reason="Penyelesaian sengketa administratif."
        )

    dispute.decision = decision
    dispute.deduction_amount = dispute_damage_fee
    dispute.status = Dispute.Status.DIPUTUSKAN
    dispute.decided_by = admin_user
    dispute.decision_note = decision_note.strip() if decision_note else ""
    dispute.save()

    now = timezone.now()
    if locked_rental.item.require_ktm_held and not locked_rental.ktm_returned_confirmed_at:
        locked_rental.ktm_returned_confirmed_at = now

    locked_rental.status = Rental.Status.SELESAI
    locked_rental.damage_fee = damage_fee_to_settle
    locked_rental.status_changed_at = now
    locked_rental.save(update_fields=[
        'status', 'damage_fee', 'ktm_returned_confirmed_at', 'status_changed_at', 'updated_at'
    ])

    from apps.payments.services import settle_rental_funds
    settle_rental_funds(locked_rental, late_fee=locked_rental.late_fee, damage_fee=damage_fee_to_settle)

    from apps.trust.services import recompute_trust_score, label_training_example_for_rental
    label_training_example_for_rental(locked_rental)
    recompute_trust_score(locked_rental.renter)
    recompute_trust_score(locked_rental.owner)

    msg = f"Sengketa untuk sewa '{locked_rental.item.title}' telah diputuskan oleh Admin: {dispute.get_decision_display()}."
    Notification.notify(user=locked_rental.renter, title="Keputusan Sengketa", message=msg, url=f"/sewa/{locked_rental.code}/")
    Notification.notify(user=locked_rental.owner, title="Keputusan Sengketa", message=msg, url=f"/sewa/{locked_rental.code}/")
    return locked_rental


@transaction.atomic
def proses_barang_tidak_dikembalikan(rental):
    """
    Penanganan kasus darurat barang tidak dikembalikan sesuai SPEC v2 Bagian G:
    - Saat DEPOSIT_MODE=off: dicatat sebagai ExtraCharge(kehilangan) sebesar nilai taksiran barang
      Sewa selesai dan pembayaran sewa pokok diteruskan ke pemilik seperti biasa
    - Saat legacy: Seluruh deposit dialihkan ke pemilik
    - Membekukan akun penyewa (User.is_suspended = True)
    - Mendaftarkan NIM penyewa ke BlacklistedNim
    - Notifikasi kedua pihak
    """
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    if locked_rental.status != Rental.Status.SEDANG_DISEWA:
        return locked_rental

    now = timezone.now()
    deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()

    if deposit_mode == 'off':
        loss_amount = locked_rental.item.estimated_value
        from apps.payments.models import ExtraCharge
        ExtraCharge.objects.update_or_create(
            rental=locked_rental,
            charge_type=ExtraCharge.ChargeType.KEHILANGAN,
            defaults={
                'renter': locked_rental.renter,
                'owner': locked_rental.owner,
                'amount': loss_amount,
                'reason': f"Ganti rugi kehilangan barang tidak dikembalikan ({locked_rental.item.title})",
                'status': ExtraCharge.Status.TERUTANG,
            }
        )
        locked_rental.status = Rental.Status.SELESAI
        locked_rental.damage_fee = 0
        locked_rental.status_changed_at = now
        locked_rental.save(update_fields=['status', 'damage_fee', 'status_changed_at', 'updated_at'])
        from apps.payments.services import settle_rental_funds
        settle_rental_funds(locked_rental, late_fee=0, damage_fee=0)
    else:
        dispute, _ = Dispute.objects.update_or_create(
            rental=locked_rental,
            defaults={
                'opened_by': locked_rental.owner,
                'reason': "Barang tidak dikembalikan melewati batas waktu tenggang (grace period).",
                'deduction_amount': locked_rental.deposit_total,
                'status': Dispute.Status.TERBUKA,
            }
        )
        locked_rental.status = Rental.Status.SENGKETA
        locked_rental.damage_fee = locked_rental.deposit_total
        locked_rental.status_changed_at = now
        locked_rental.save(update_fields=['status', 'damage_fee', 'status_changed_at', 'updated_at'])
        from apps.payments.services import settle_rental_funds
        settle_rental_funds(locked_rental, late_fee=0, damage_fee=locked_rental.deposit_total)

    # 4. Bekukan akun penyewa
    renter = locked_rental.renter
    renter.is_suspended = True
    renter.save(update_fields=['is_suspended'])

    # 5. Masukkan NIM ke BlacklistedNim
    from apps.accounts.models import BlacklistedNim
    profile = getattr(renter, 'student_profile', None)
    if profile and profile.nim:
        BlacklistedNim.objects.get_or_create(
            nim=profile.nim,
            defaults={'reason': f"Barang tidak dikembalikan pada sewa {locked_rental.code} ({locked_rental.item.title})"}
        )

    # 6. Hitung ulang skor kepercayaan penyewa & pemilik dan labeli data latih
    from apps.trust.services import recompute_trust_score, label_training_example_for_rental
    label_training_example_for_rental(locked_rental)
    recompute_trust_score(renter)
    recompute_trust_score(locked_rental.owner)

    # 7. Notifikasi
    Notification.notify(
        user=locked_rental.owner,
        title="Sengketa: Barang Tidak Dikembalikan",
        message=f"Batas waktu pengembalian sewa '{locked_rental.code}' telah habis. Seluruh deposit (Rp{locked_rental.deposit_total:,}) telah dialihkan ke saldo Anda. Anda dapat mengajukan klaim Dana Gotong Royong kepada admin.",
        url=f"/sewa/{locked_rental.code}/"
    )
    Notification.notify(
        user=renter,
        title="Akun Dibekukan: Barang Tidak Dikembalikan",
        message=f"Akun Anda dibekukan dan NIM didaftarkan hitam karena barang sewa '{locked_rental.code}' tidak dikembalikan tepat waktu.",
        url=f"/sewa/{locked_rental.code}/"
    )
    return locked_rental


@transaction.atomic
def proses_klaim_dana_proteksi_admin(rental, admin_user, note=""):
    """
    Admin memutuskan pencairan klaim dana proteksi untuk pemilik barang:
    - Maksimal 50% nilai barang dikurangi deposit yang sudah diterima
    - Dicatat di buku besar sewa (masuk_klaim_proteksi & keluar_kompensasi_pemilik) agar tetap seimbang
    """
    if not (admin_user.is_staff or admin_user.is_superuser):
        raise RentalPermissionError("Hanya staf admin yang dapat memutuskan klaim proteksi.")

    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    max_claim = max(0, round(locked_rental.item.estimated_value * 0.5) - locked_rental.deposit_total)
    if max_claim <= 0:
        raise RentalValidationError("Nilai klaim proteksi adalah Rp0 karena deposit sudah mencukupi 50% nilai barang.")

    from apps.payments.models import LedgerEntry
    from apps.payments.services import record_ledger_entry, validate_ledger_invariant

    # Catat mutasi masuk dan keluar kompensasi pada buku besar sewa
    record_ledger_entry(
        rental=locked_rental,
        kind=LedgerEntry.Kind.MASUK_KLAIM_PROTEKSI,
        amount=max_claim,
        note=f"Pencairan cadangan Dana Gotong Royong platform untuk {locked_rental.code} ({note})"
    )
    record_ledger_entry(
        rental=locked_rental,
        kind=LedgerEntry.Kind.KELUAR_KOMPENSASI_PEMILIK,
        amount=max_claim,
        note=f"Kompensasi Dana Gotong Royong diteruskan ke pemilik ({locked_rental.code})"
    )

    from apps.payments.models import WalletTransaction
    from apps.payments.services import create_wallet_transaction
    create_wallet_transaction(
        user=locked_rental.owner,
        rental=locked_rental,
        kind=WalletTransaction.Kind.KREDIT_KLAIM_PROTEKSI,
        amount=max_claim,
        note=f"Kompensasi cadangan Dana Gotong Royong ke dompet pemilik ({locked_rental.code})"
    )

    validate_ledger_invariant(locked_rental)

    Notification.notify(
        user=locked_rental.owner,
        title="Klaim Dana Gotong Royong Dicairkan",
        message=f"Admin telah menyetujui klaim ganti rugi Dana Gotong Royong sebesar Rp{max_claim:,} untuk sewa '{locked_rental.code}'. Dana kompensasi telah ditambahkan ke saldo dompet akun Anda.",
        url=f"/sewa/{locked_rental.code}/"
    )
    return max_claim


@transaction.atomic
def buat_ulasan(rental, reviewer, rating, comment=""):
    """
    Membuat ulasan (Review) setelah transaksi sewa SELESAI:
    - Rating 1-5, komentar maksimal 300 karakter
    - Satu ulasan per peran per sewa (tidak bisa diubah)
    - Memperbarui skor kepercayaan reviewee
    """
    if rental.status != Rental.Status.SELESAI:
        raise RentalStateError("Ulasan hanya dapat diberikan setelah sewa berstatus selesai.")

    if reviewer.id not in [rental.renter_id, rental.owner_id]:
        raise RentalPermissionError("Hanya peserta sewa yang dapat memberikan ulasan.")

    if Review.objects.filter(rental=rental, reviewer=reviewer).exists():
        raise RentalValidationError("Anda sudah memberikan ulasan untuk transaksi sewa ini.")

    clean_comment = comment.strip() if comment else ""
    if len(clean_comment) > 300:
        raise RentalValidationError("Komentar ulasan maksimal 300 karakter.")

    rating = int(rating)
    if rating < 1 or rating > 5:
        raise RentalValidationError("Rating harus berada antara 1 dan 5 bintang.")

    as_role = Review.AsRole.PENYEWA if reviewer.id == rental.renter_id else Review.AsRole.PEMILIK
    reviewee = rental.owner if as_role == Review.AsRole.PENYEWA else rental.renter

    review = Review.objects.create(
        rental=rental,
        reviewer=reviewer,
        reviewee=reviewee,
        as_role=as_role,
        rating=rating,
        comment=clean_comment,
    )

    # Perbarui skor kepercayaan pihak yang diulas
    from apps.trust.services import recompute_trust_score
    recompute_trust_score(reviewee)

    Notification.notify(
        user=reviewee,
        title="Ulasan Baru Diterima",
        message=f"{reviewer.full_name or reviewer.username} memberikan ulasan {rating}★ untuk sewa '{rental.item.title}'.",
        url=f"/sewa/{rental.code}/"
    )
    return review

