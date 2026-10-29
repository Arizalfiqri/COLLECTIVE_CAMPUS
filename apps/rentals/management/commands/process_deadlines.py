import logging
from datetime import datetime, time as time_module, timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.rentals.models import Rental, HandoverSchedule
from apps.core.models import Notification
from apps.rentals.services import (
    kedaluwarsa_sewa,
    konfirmasi_pengembalian_baik,
    proses_barang_tidak_dikembalikan,
)
from apps.rentals.photos import purge_handover_photos

logger = logging.getLogger(__name__)


def run_process_deadlines():
    """
    Fungsi logika inti pemrosesan batas waktu sewa:
    1. Mengubah status 'menunggu_persetujuan' menjadi 'kedaluwarsa' jika melewati APPROVAL_DEADLINE_HOURS.
    2. Mengubah status 'menunggu_pembayaran' menjadi 'kedaluwarsa' jika melewati PAYMENT_DEADLINE_HOURS.
    3. Mengirimkan pengingat serah terima H-1 untuk jadwal terkonfirmasi.
    4. Mengonfirmasi pengembalian baik otomatis setelah AUTO_CONFIRM_RETURN_HOURS.
    5. Menangani barang tidak dikembalikan setelah end_date + NON_RETURN_GRACE_HOURS terlewati.
    6. Menghapus foto serah terima setelah masa retensi HANDOVER_PHOTO_RETENTION_DAYS (purge_handover_photos).
    Aman dijalankan berulang (idempoten).
    """
    now = timezone.now()
    approval_hours = int(getattr(settings, 'APPROVAL_DEADLINE_HOURS', 24))
    payment_hours = int(getattr(settings, 'PAYMENT_DEADLINE_HOURS', 6))
    auto_confirm_hours = int(getattr(settings, 'AUTO_CONFIRM_RETURN_HOURS', 48))
    non_return_grace_hours = int(getattr(settings, 'NON_RETURN_GRACE_HOURS', 48))

    cutoff_approval = now - timedelta(hours=approval_hours)
    cutoff_payment = now - timedelta(hours=payment_hours)
    cutoff_auto_confirm = now - timedelta(hours=auto_confirm_hours)

    expired_approval_count = 0
    expired_payment_count = 0
    h1_reminder_count = 0
    auto_confirmed_return_count = 0
    non_return_count = 0

    # 1. Menunggu persetujuan yang melebihi batas waktu
    pending_approval_qs = Rental.objects.filter(
        status=Rental.Status.MENUNGGU_PERSETUJUAN
    ).filter(
        Q(requested_at__lte=cutoff_approval) |
        Q(requested_at__isnull=True, created_at__lte=cutoff_approval)
    )

    for rental in pending_approval_qs:
        reason = f"Batas waktu persetujuan pemilik ({approval_hours} jam) telah berakhir."
        kedaluwarsa_sewa(rental, reason=reason)
        expired_approval_count += 1

    # 2. Menunggu pembayaran yang melebihi batas waktu (dihitung dari approved_at)
    pending_payment_qs = Rental.objects.filter(
        status=Rental.Status.MENUNGGU_PEMBAYARAN
    ).filter(
        Q(approved_at__lte=cutoff_payment) |
        Q(approved_at__isnull=True, status_changed_at__lte=cutoff_payment) |
        Q(approved_at__isnull=True, status_changed_at__isnull=True, updated_at__lte=cutoff_payment)
    )

    for rental in pending_payment_qs:
        reason = f"Batas waktu pembayaran penyewa ({payment_hours} jam) telah berakhir."
        kedaluwarsa_sewa(rental, reason=reason)
        expired_payment_count += 1

    # 3. Pengingat serah terima H-1 untuk jadwal terkonfirmasi
    h1_window_end = now + timedelta(hours=24)
    upcoming_schedules = HandoverSchedule.objects.filter(
        status=HandoverSchedule.Status.DIKONFIRMASI,
        rental__status=Rental.Status.DIBAYAR,
        meet_at__gte=now,
        meet_at__lte=h1_window_end,
    ).select_related('rental', 'rental__renter', 'rental__owner', 'meeting_point')

    for schedule in upcoming_schedules:
        rental = schedule.rental
        title = "Pengingat Serah Terima (H-1)"
        # Cek apakah notifikasi pengingat sudah pernah dikirim agar idempoten
        already_notified = Notification.objects.filter(
            user=rental.renter,
            title=title,
            message__icontains=rental.code
        ).exists()

        if not already_notified:
            point_name = schedule.meeting_point.name if schedule.meeting_point else "titik temu yang disepakati"
            time_str = schedule.meet_at.strftime("%d %b %Y, %H:%M")
            msg = (
                f"Pengingat: Serah terima barang '{rental.item.title}' dijadwalkan besok pada {time_str} "
                f"di {point_name}. Pastikan membawa KTM dan memeriksa kondisi barang bersama."
            )
            Notification.notify(user=rental.renter, title=title, message=msg, url=f"/sewa/{rental.code}/")
            Notification.notify(user=rental.owner, title=title, message=msg, url=f"/sewa/{rental.code}/")
            h1_reminder_count += 1

    # 4. Konfirmasi otomatis pengembalian setelah AUTO_CONFIRM_RETURN_HOURS
    pending_returns = Rental.objects.filter(
        status=Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN
    ).filter(
        Q(return_requested_at__lte=cutoff_auto_confirm) |
        Q(return_requested_at__isnull=True, status_changed_at__lte=cutoff_auto_confirm)
    )

    for rental in pending_returns:
        try:
            konfirmasi_pengembalian_baik(rental, user=None)
            auto_confirmed_return_count += 1
            logger.info(f"Rental {rental.code} auto-confirmed return after {auto_confirm_hours} hours.")
        except Exception as e:
            logger.error(f"Gagal auto-confirm return {rental.code}: {e}")

    # 5. Barang tidak dikembalikan (SEDANG_DISEWA lewat end_date + NON_RETURN_GRACE_HOURS)
    active_rentals = Rental.objects.filter(status=Rental.Status.SEDANG_DISEWA)
    current_tz = timezone.get_current_timezone()

    for rental in active_rentals:
        # Batas akhir sewa adalah pukul 23:59:59 dari tanggal end_date
        end_datetime = timezone.make_aware(
            datetime.combine(rental.end_date, time_module.max),
            current_tz
        )
        non_return_deadline = end_datetime + timedelta(hours=non_return_grace_hours)

        if now > non_return_deadline:
            try:
                proses_barang_tidak_dikembalikan(rental)
                non_return_count += 1
                logger.info(f"Rental {rental.code} processed for non-return after grace period.")
            except Exception as e:
                logger.error(f"Gagal memproses non-return untuk {rental.code}: {e}")

    # 6. Pembersihan berkala foto serah terima (retensi HANDOVER_PHOTO_RETENTION_DAYS)
    purged_photos = purge_handover_photos()

    # 7. Kedaluwarsa otomatis listing jual beli setelah 60 hari (Fase 8A)
    expired_sale_items_count = 0
    try:
        from apps.sales.models import SaleItem
        from apps.core.models import Notification

        expired_sales_qs = SaleItem.objects.filter(
            status=SaleItem.Status.AKTIF,
            expires_at__lte=now
        )
        for s_item in expired_sales_qs:
            s_item.status = SaleItem.Status.KEDALUWARSA
            s_item.save(update_fields=['status', 'updated_at'])
            expired_sale_items_count += 1
            notif_msg = f"Listing barang jualan '{s_item.title}' telah kedaluwarsa setelah 60 hari. Anda dapat memperpanjang masa tayang melalui menu Barang Jualan Saya."
            if not Notification.objects.filter(user=s_item.owner, message=notif_msg).exists():
                Notification.notify(
                    user=s_item.owner,
                    title="Listing jualan kedaluwarsa",
                    message=notif_msg,
                    url="/jual/saya/?tab=nonaktif"
                )
    except Exception as e:
        logger.error(f"Gagal memproses kedaluwarsa listing jual: {e}")

    # 7. Fase 8B: Batas waktu pesanan jual beli
    expired_sale_orders_count = 0
    expired_sale_meetups_count = 0
    auto_completed_sales_count = 0

    try:
        from apps.sales.models import SaleOrder
        from apps.sales.services import expire_sale_order, cancel_sale_order, settle_sale_order

        # 7a. Kedaluwarsa bayar (menunggu_pembayaran lewat reserved_until)
        unpaid_orders = SaleOrder.objects.filter(
            status=SaleOrder.Status.MENUNGGU_PEMBAYARAN,
            reserved_until__lte=now
        )
        for order in unpaid_orders:
            expire_sale_order(order)
            expired_sale_orders_count += 1

        # 7b. Batal otomatis plus refund bila pertemuan lewat 7 hari tanpa serah terima
        meetup_days = getattr(settings, 'SALE_MEETUP_DEADLINE_DAYS', 7)
        meetup_deadline = now - timedelta(days=meetup_days)
        unmet_orders = SaleOrder.objects.filter(
            status=SaleOrder.Status.DIBAYAR,
            handed_over_at__isnull=True,
            paid_at__lte=meetup_deadline
        )
        for order in unmet_orders:
            cancel_sale_order(
                order,
                user=None,
                reason=f"Pertemuan serah terima melewati batas waktu {meetup_days} hari tanpa serah terima."
            )
            expired_sale_meetups_count += 1

        # 7c. Selesai otomatis setelah masa pemeriksaan (diserahkan lewat SALE_INSPECTION_HOURS)
        inspection_hours = getattr(settings, 'SALE_INSPECTION_HOURS', 48)
        inspection_deadline = now - timedelta(hours=inspection_hours)
        uninspected_orders = SaleOrder.objects.filter(
            status=SaleOrder.Status.DISERAHKAN,
            handed_over_at__lte=inspection_deadline
        )
        for order in uninspected_orders:
            settle_sale_order(order, actor=None)
            auto_completed_sales_count += 1

    except Exception as e:
        logger.error(f"Gagal memproses batas waktu pesanan jual beli: {e}")

    return {
        'expired_approval': expired_approval_count,
        'expired_payment': expired_payment_count,
        'h1_reminders': h1_reminder_count,
        'auto_confirmed_returns': auto_confirmed_return_count,
        'non_returns': non_return_count,
        'purged_photos': purged_photos,
        'expired_sale_items': expired_sale_items_count,
        'expired_sale_orders': expired_sale_orders_count,
        'expired_sale_meetups': expired_sale_meetups_count,
        'auto_completed_sales': auto_completed_sales_count,
        'total': expired_approval_count + expired_payment_count,
    }


class Command(BaseCommand):
    help = "Memproses batas waktu sewa: kedaluwarsa, pengingat H-1, konfirmasi pengembalian, barang tidak kembali, dan retensi foto."

    def handle(self, *args, **options):
        self.stdout.write("Memulai pemrosesan batas waktu sewa (process_deadlines)...")
        results = run_process_deadlines()
        self.stdout.write(
            self.style.SUCCESS(
                f"Selesai: {results['expired_approval']} pengajuan kedaluwarsa, "
                f"{results['expired_payment']} pembayaran kedaluwarsa, "
                f"{results['h1_reminders']} pengingat H-1, "
                f"{results['auto_confirmed_returns']} konfirmasi otomatis, "
                f"{results['non_returns']} barang tidak kembali, "
                f"{results['purged_photos']} foto dibersihkan."
            )
        )

