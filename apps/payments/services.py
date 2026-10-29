import hashlib
import hmac
import logging
import uuid
from datetime import datetime, time, timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
import requests

import midtransclient

from apps.core.models import Notification
from apps.payments.models import (
    Payment,
    DepositHold,
    Payout,
    LedgerEntry,
    WalletTransaction,
    WithdrawalRequest,
    WithdrawalAccountAccessLog,
)
from apps.rentals.models import Rental

logger = logging.getLogger(__name__)


class MidtransError(Exception):
    """Base error untuk integrasi Midtrans."""
    pass


class MidtransConfigError(MidtransError):
    """Error konfigurasi kunci Midtrans belum diatur."""
    pass


def get_midtrans_keys():
    """Mengambil server key dan client key dari settings atau langsung dari .env jika belum di-reload."""
    server_key = getattr(settings, 'MIDTRANS_SERVER_KEY', '').strip()
    client_key = getattr(settings, 'MIDTRANS_CLIENT_KEY', '').strip()
    placeholder_vals = ['', 'isi-dari-dashboard-sandbox']

    if server_key in placeholder_vals or client_key in placeholder_vals:
        env_path = getattr(settings, 'BASE_DIR', None)
        if env_path:
            env_file = env_path / '.env'
            if env_file.exists():
                import environ
                _env = environ.Env()
                _env.read_env(str(env_file), overwrite=True)
                s_key = _env('MIDTRANS_SERVER_KEY', default='').strip()
                c_key = _env('MIDTRANS_CLIENT_KEY', default='').strip()
                if s_key not in placeholder_vals and c_key not in placeholder_vals:
                    server_key = s_key
                    client_key = c_key
                    # Perbarui settings di memori
                    settings.MIDTRANS_SERVER_KEY = server_key
                    settings.MIDTRANS_CLIENT_KEY = client_key
    return server_key, client_key


def is_midtrans_configured():
    """Memeriksa apakah server key dan client key Midtrans telah terisi."""
    server_key, client_key = get_midtrans_keys()
    placeholder_vals = ['', 'isi-dari-dashboard-sandbox']
    return server_key not in placeholder_vals and client_key not in placeholder_vals


def get_midtrans_enabled_payments():
    """
    Mengambil daftar metode pembayaran yang diizinkan dari settings atau .env.
    Mengembalikan list of string (misalnya ['dana', 'seabank_va', 'echannel', 'other_qris']),
    atau empty list [] jika tidak dibatasi (semua metode diizinkan).
    """
    raw = getattr(settings, 'MIDTRANS_ENABLED_PAYMENTS_RAW', '')
    env_path = getattr(settings, 'BASE_DIR', None)
    if env_path:
        env_file = env_path / '.env'
        if env_file.exists():
            import environ
            _env = environ.Env()
            _env.read_env(str(env_file), overwrite=True)
            val = _env('MIDTRANS_ENABLED_PAYMENTS', default=None)
            if val is not None:
                raw = val
    if isinstance(raw, list):
        return [p.strip() for p in raw if p.strip()]
    return [p.strip() for p in str(raw).split(',') if p.strip()]


def get_midtrans_snap_mode():
    """Mengambil mode tampilan Snap ('popup' atau 'embed')."""
    mode = getattr(settings, 'MIDTRANS_SNAP_MODE', 'popup')
    env_path = getattr(settings, 'BASE_DIR', None)
    if env_path:
        env_file = env_path / '.env'
        if env_file.exists():
            import environ
            _env = environ.Env()
            _env.read_env(str(env_file), overwrite=True)
            val = _env('MIDTRANS_SNAP_MODE', default=None)
            if val is not None:
                mode = val
    return str(mode).strip().lower() or 'popup'



def get_midtrans_snap_client():
    """Menginisialisasi objek Midtrans Snap client."""
    server_key, client_key = get_midtrans_keys()
    if not is_midtrans_configured():
        raise MidtransConfigError("Kunci Midtrans belum diisi pada pengaturan server (.env).")
    return midtransclient.Snap(
        is_production=getattr(settings, 'MIDTRANS_IS_PRODUCTION', False),
        server_key=server_key,
        client_key=client_key,
    )


def get_midtrans_core_api_client():
    """Menginisialisasi objek Midtrans CoreApi client untuk pengecekan status transaksi."""
    server_key, client_key = get_midtrans_keys()
    if not is_midtrans_configured():
        raise MidtransConfigError("Kunci Midtrans belum diisi pada pengaturan server (.env).")
    return midtransclient.CoreApi(
        is_production=getattr(settings, 'MIDTRANS_IS_PRODUCTION', False),
        server_key=server_key,
        client_key=client_key,
    )


def verify_midtrans_signature(order_id, status_code, gross_amount, signature_key):
    """
    Memverifikasi SHA-512 signature key dari notifikasi webhook Midtrans:
    signature_key = SHA512(order_id + status_code + gross_amount + server_key)
    """
    server_key = getattr(settings, 'MIDTRANS_SERVER_KEY', '').strip()
    if not server_key or not signature_key:
        return False

    # Format gross_amount: pastikan string tanpa desimal jika bilangan bulat
    raw_str = f"{order_id}{status_code}{gross_amount}{server_key}"
    calculated = hashlib.sha512(raw_str.encode('utf-8')).hexdigest()
    return hmac.compare_digest(calculated.lower(), signature_key.lower())


def record_ledger_entry(rental, kind, amount, note=""):
    """Mencatat satu baris mutasi ke buku besar (LedgerEntry)."""
    return LedgerEntry.objects.create(
        rental=rental,
        kind=kind,
        amount=amount,
        note=note
    )


@transaction.atomic
def record_payment_settlement(rental, payment, raw_response=None):
    """
    Mencatat penerimaan pembayaran escrow dan buku besar secara idempoten:
    - DepositHold berstatus DITAHAN
    - LedgerEntry: masuk_sewa, masuk_deposit, masuk_dana_proteksi (bila ada)
    """
    # 1. DepositHold (hanya dibuat jika deposit_total > 0)
    hold = None
    if rental.deposit_total > 0:
        hold, _ = DepositHold.objects.get_or_create(
            rental=rental,
            defaults={
                'amount': rental.deposit_total,
                'status': DepositHold.Status.DITAHAN,
            }
        )

    # 2. LedgerEntry masuk (periksa agar tidak membuat catatan ganda)
    existing_kinds = set(rental.ledger_entries.filter(kind__startswith='masuk_').values_list('kind', flat=True))

    if LedgerEntry.Kind.MASUK_SEWA not in existing_kinds:
        record_ledger_entry(
            rental=rental,
            kind=LedgerEntry.Kind.MASUK_SEWA,
            amount=rental.rent_total,
            note=f"Penerimaan dana sewa {rental.days} hari ({rental.code})"
        )

    if rental.deposit_total > 0 and LedgerEntry.Kind.MASUK_DEPOSIT not in existing_kinds:
        record_ledger_entry(
            rental=rental,
            kind=LedgerEntry.Kind.MASUK_DEPOSIT,
            amount=rental.deposit_total,
            note=f"Penahanan deposit jaminan sewa ({rental.code})"
        )

    if rental.protection_fee > 0 and LedgerEntry.Kind.MASUK_DANA_PROTEKSI not in existing_kinds:
        record_ledger_entry(
            rental=rental,
            kind=LedgerEntry.Kind.MASUK_DANA_PROTEKSI,
            amount=rental.protection_fee,
            note=f"Penerimaan iuran dana proteksi kerusakan ringan ({rental.code})"
        )

    return hold


@transaction.atomic
def create_or_get_payment_token(rental, user, force_new=False, finish_url=None):
    """
    Membuat atau mengambil kembali Snap token pembayaran untuk sewa:
    - Memeriksa hak akses (hanya penyewa)
    - Status wajib menunggu_pembayaran
    - Menggunakan ulang Payment berstatus PENDING jika masih berlaku dan tidak force_new
    - Menghasilkan token Snap Midtrans
    - Meneruskan finish_url sebagai callbacks.finish agar Midtrans redirect ke halaman profesional kita
    """
    if user.id != rental.renter_id:
        raise PermissionError("Hanya penyewa yang dapat melakukan pembayaran sewa ini.")

    if rental.status != Rental.Status.MENUNGGU_PEMBAYARAN:
        raise ValueError(f"Sewa berstatus '{rental.get_status_display()}' tidak dalam posisi menunggu pembayaran.")

    # Periksa batas waktu pembayaran
    from apps.rentals.services import kedaluwarsa_sewa
    payment_hours = int(getattr(settings, 'PAYMENT_DEADLINE_HOURS', 6))
    if rental.approved_at:
        deadline = rental.approved_at + timedelta(hours=payment_hours)
        if timezone.now() > deadline:
            kedaluwarsa_sewa(rental, reason=f"Batas waktu pembayaran penyewa ({payment_hours} jam) telah berakhir.")
            raise ValueError("Batas waktu pembayaran telah kedaluwarsa.")

    if not is_midtrans_configured():
        raise MidtransConfigError("Kunci Midtrans belum diisi")

    # Pakai ulang Payment PENDING yang sudah ada bila snap_token tersedia dan bukan force_new
    if not force_new:
        existing_payment = Payment.objects.filter(
            rental=rental,
            status=Payment.Status.PENDING
        ).order_by('-created_at').first()

        if existing_payment and existing_payment.snap_token:
            return existing_payment

    # Buat order_id unik: KR-<kode>-<nomor urut>
    counter = rental.payments.count() + 1
    order_id = f"KR-{rental.code}-{counter:02d}"

    # Item details
    item_details = [
        {
            'id': f"RENT-{rental.code}",
            'price': rental.rent_total,
            'quantity': 1,
            'name': f"Sewa: {rental.item.title[:40]}",
        }
    ]
    if rental.deposit_total > 0:
        item_details.append({
            'id': f"DEP-{rental.code}",
            'price': rental.deposit_total,
            'quantity': 1,
            'name': "Deposit Jaminan Sewa",
        })
    if rental.protection_fee > 0:
        item_details.append({
            'id': f"PROT-{rental.code}",
            'price': rental.protection_fee,
            'quantity': 1,
            'name': "Iuran Dana Gotong Royong",
        })

    customer_phone = rental.renter.phone_whatsapp or '08123456789'

    params = {
        'transaction_details': {
            'order_id': order_id,
            'gross_amount': rental.grand_total,
        },
        'item_details': item_details,
        'customer_details': {
            'first_name': rental.renter.first_name or rental.renter.username,
            'last_name': rental.renter.last_name or '',
            'email': rental.renter.email or f"{rental.renter.username}@kampusrent.id",
            'phone': customer_phone,
        },
        'expiry': {
            'unit': 'hours',
            'duration': payment_hours,
        }
    }

    if finish_url:
        params['callbacks'] = {
            'finish': finish_url
        }

    enabled_payments = get_midtrans_enabled_payments()
    if enabled_payments:
        params['enabled_payments'] = enabled_payments

    snap_client = get_midtrans_snap_client()
    try:
        snap_response = snap_client.create_transaction(params)
        snap_token = snap_response.get('token', '')
    except Exception as e:
        logger.error(f"Gagal membuat transaksi Midtrans Snap untuk sewa {rental.code}: {e}")
        raise MidtransError(f"Gagal menghubungi gateway pembayaran: {e}")

    payment = Payment.objects.create(
        rental=rental,
        order_id=order_id,
        gross_amount=rental.grand_total,
        snap_token=snap_token,
        status=Payment.Status.PENDING
    )
    return payment


@transaction.atomic
def create_or_get_sale_payment_token(order, user, force_new=False, finish_url=None):
    """
    Membuat atau mengambil kembali Snap token pembayaran untuk pesanan jual beli:
    - Hak akses: hanya pembeli
    - Status wajib menunggu_pembayaran
    - order_id berawalan KJ- (misal KJ-XXXXXX-01)
    - MIDTRANS_ENABLED_PAYMENTS tetap berlaku
    """
    from apps.sales.models import SaleOrder
    if user.id != order.buyer_id:
        raise PermissionError("Hanya pembeli yang dapat melakukan pembayaran pesanan ini.")

    if order.status != SaleOrder.Status.MENUNGGU_PEMBAYARAN:
        raise ValueError(f"Pesanan berstatus '{order.get_status_display()}' tidak dalam posisi menunggu pembayaran.")

    if order.reserved_until and timezone.now() > order.reserved_until:
        from apps.sales.services import expire_sale_order
        expire_sale_order(order)
        raise ValueError("Batas waktu pembayaran pesanan telah kedaluwarsa.")

    if not is_midtrans_configured():
        raise MidtransConfigError("Kunci Midtrans belum diisi")

    if not force_new:
        existing_payment = Payment.objects.filter(
            sale_order=order,
            status=Payment.Status.PENDING
        ).order_by('-created_at').first()

        if existing_payment and existing_payment.snap_token:
            return existing_payment

    counter = order.payments.count() + 1
    order_id = f"{order.code}-{counter:02d}"

    item_details = [
        {
            'id': f"SALE-{order.code}",
            'price': order.price_snapshot,
            'quantity': 1,
            'name': f"Beli: {order.item.title[:40]}",
        }
    ]

    customer_phone = getattr(order.buyer, 'phone_whatsapp', '') or getattr(getattr(order.buyer, 'student_profile', None), 'phone_number', '') or '08123456789'
    payment_hours = int(getattr(settings, 'SALE_PAYMENT_DEADLINE_HOURS', 6))

    params = {
        'transaction_details': {
            'order_id': order_id,
            'gross_amount': order.price_snapshot,
        },
        'item_details': item_details,
        'customer_details': {
            'first_name': order.buyer.first_name or order.buyer.username,
            'last_name': order.buyer.last_name or '',
            'email': order.buyer.email or f"{order.buyer.username}@kampusrent.id",
            'phone': customer_phone,
        },
        'expiry': {
            'unit': 'hours',
            'duration': payment_hours,
        }
    }

    if finish_url:
        params['callbacks'] = {
            'finish': finish_url
        }

    enabled_payments = get_midtrans_enabled_payments()
    if enabled_payments:
        params['enabled_payments'] = enabled_payments

    snap_client = get_midtrans_snap_client()
    try:
        snap_response = snap_client.create_transaction(params)
        snap_token = snap_response.get('token', '')
    except Exception as e:
        logger.error(f"Gagal membuat transaksi Midtrans Snap untuk pesanan {order.code}: {e}")
        raise MidtransError(f"Gagal menghubungi gateway pembayaran: {e}")

    payment = Payment.objects.create(
        sale_order=order,
        order_id=order_id,
        gross_amount=order.price_snapshot,
        snap_token=snap_token,
        status=Payment.Status.PENDING
    )
    return payment


@transaction.atomic
def sync_payment_status(order_id, external_status_data=None):
    """
    Sinkronisasi status transaksi dari Midtrans API:
    - SATU-SATUNYA sumber kebenaran adalah API Midtrans (atau payload webhook yang terverifikasi signature-nya).
    - Menangani settlement/capture accept -> state machine sewa / pesanan jual beli idempoten.
    - Idempoten: aman dipanggil berkali-kali tanpa duplikasi data.
    """
    try:
        payment = Payment.objects.select_for_update().filter(
            Q(order_id=order_id) | Q(transaction_id=order_id)
        ).first()
        if not payment:
            raise Payment.DoesNotExist()
    except Payment.DoesNotExist:
        raise ValueError(f"Transaksi dengan order_id '{order_id}' tidak ditemukan.")

    rental = None
    sale_order = None
    if payment.rental_id:
        rental = Rental.objects.select_for_update().get(id=payment.rental_id)
    elif payment.sale_order_id:
        from apps.sales.models import SaleOrder
        sale_order = SaleOrder.objects.select_for_update().get(id=payment.sale_order_id)

    # Ambil status dari Midtrans API jika tidak dioper data terverifikasi
    if external_status_data:
        status_resp = external_status_data
    else:
        core_api = get_midtrans_core_api_client()
        status_resp = None
        last_error = None

        # 1. Coba verifikasi lewat transaction_id jika sudah tersimpan
        if payment.transaction_id:
            try:
                status_resp = core_api.transactions.status(payment.transaction_id)
            except Exception as e:
                last_error = e

        # 2. Coba verifikasi lewat order_id
        if not status_resp:
            try:
                status_resp = core_api.transactions.status(payment.order_id)
            except Exception as e:
                last_error = e

        # 3. Fallback jika Core API 404
        if not status_resp and payment.snap_token:
            try:
                is_prod = getattr(settings, 'MIDTRANS_IS_PRODUCTION', False)
                snap_base_url = "https://app.midtrans.com" if is_prod else "https://app.sandbox.midtrans.com"
                snap_status_url = f"{snap_base_url}/snap/v1/transactions/{payment.snap_token}/status"
                r = requests.get(snap_status_url, timeout=10)
                if r.status_code == 200:
                    snap_data = r.json()
                    tid = snap_data.get('transaction_id')
                    if tid:
                        payment.transaction_id = tid
                        try:
                            status_resp = core_api.transactions.status(tid)
                        except Exception:
                            status_resp = snap_data
                    else:
                        status_resp = snap_data
            except Exception as snap_err:
                logger.warning(f"Gagal query snap status token {payment.snap_token}: {snap_err}")

        if not status_resp:
            logger.error(f"Gagal mengecek status Midtrans order {order_id}: {last_error}")
            raise MidtransError(f"Gagal mengecek status transaksi ke Midtrans: {last_error}")

    transaction_status = status_resp.get('transaction_status', '')
    fraud_status = status_resp.get('fraud_status', '')

    logger.info(f"Sync Midtrans order {order_id}: status={transaction_status}, fraud={fraud_status}")

    # Settlement atau capture accept = Berhasil
    is_settlement = (
        transaction_status == 'settlement' or
        (transaction_status == 'capture' and fraud_status == 'accept')
    )

    if is_settlement:
        if sale_order:
            from apps.sales.models import SaleOrder
            if payment.status == Payment.Status.SETTLEMENT and sale_order.status in (
                SaleOrder.Status.DIBAYAR, SaleOrder.Status.DISERAHKAN, SaleOrder.Status.SELESAI
            ):
                return payment, sale_order

            now = timezone.now()
            payment.status = Payment.Status.SETTLEMENT
            payment.paid_at = now
            payment.payment_type = status_resp.get('payment_type', payment.payment_type)
            payment.transaction_id = status_resp.get('transaction_id', payment.transaction_id)
            payment.raw_response = status_resp
            payment.save()

            from apps.sales.services import mark_sale_order_paid
            sale_order = mark_sale_order_paid(
                sale_order,
                payment_type=payment.payment_type,
                transaction_id=payment.transaction_id,
                raw_response=status_resp
            )
            return payment, sale_order

        # Rental settlement
        if payment.status == Payment.Status.SETTLEMENT and rental.status == Rental.Status.DIBAYAR:
            # Idempoten: pembayaran sudah tercatat penuh sebelumnya
            return payment, rental

        now = timezone.now()
        payment.status = Payment.Status.SETTLEMENT
        payment.paid_at = now
        payment.payment_type = status_resp.get('payment_type', payment.payment_type)
        payment.transaction_id = status_resp.get('transaction_id', payment.transaction_id)
        payment.raw_response = status_resp
        payment.save()

        # Update status sewa melalui state machine
        from apps.rentals.services import konfirmasi_pembayaran
        rental = konfirmasi_pembayaran(rental, payment_record=payment)

        # Catat penahanan deposit dan buku besar
        record_payment_settlement(rental, payment, raw_response=status_resp)

        # Kirim notifikasi konfirmasi ke kedua pihak
        Notification.notify(
            user=rental.renter,
            title="Pembayaran Berhasil",
            message=f"Pembayaran untuk sewa '{rental.item.title}' ({rental.code}) telah berhasil diverifikasi.",
            url=f"/sewa/{rental.code}/"
        )
        Notification.notify(
            user=rental.owner,
            title="Dana Sewa Masuk ke Escrow",
            message=f"Penyewa telah membayar sewa '{rental.item.title}' ({rental.code}). Silakan jadwalkan serah terima barang.",
            url=f"/sewa/{rental.code}/"
        )
        return payment, rental

    elif transaction_status == 'pending':
        payment.status = Payment.Status.PENDING
        payment.raw_response = status_resp
        payment.save()

    elif transaction_status in ['expire', 'cancel', 'deny']:
        status_map = {
            'expire': Payment.Status.EXPIRE,
            'cancel': Payment.Status.CANCEL,
            'deny': Payment.Status.DENY,
        }
        payment.status = status_map.get(transaction_status, Payment.Status.CANCEL)
        payment.raw_response = status_resp
        payment.save()
        if sale_order and transaction_status == 'expire':
            from apps.sales.services import expire_sale_order
            expire_sale_order(sale_order)

    return payment, (rental or sale_order)


@transaction.atomic
def settle_rental_funds(rental, late_fee=0, damage_fee=0):
    """
    Fungsi penyelesaian dana escrow dan buku besar (dipanggil saat sewa selesai di Fase 5B / testing):
    - Rumus 7.2 & SPEC v2:
      commission = round(rent_total * PLATFORM_COMMISSION_PERCENT / 100)
      owner_net = rent_total - commission
      late_fee = min(late_fee, deposit_total)
      damage_fee = min(damage_fee, deposit_total - late_fee)
      deposit_refund = deposit_total - late_fee - damage_fee
    - LedgerEntry:
      keluar_komisi_platform, keluar_payout_pemilik, keluar_deposit_dikembalikan,
      keluar_denda_ke_pemilik (bila ada), keluar_deposit_ke_pemilik (bila ada),
      keluar_ke_dana_proteksi (pemindahan ke dana bersama bila ada iuran proteksi).
    - Payout berstatus dicairkan_simulasi.
    - Invarian wajib: Total Masuk == Total Keluar.
    """
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)

    # Idempoten: periksa apakah sudah pernah diselesaikan
    if locked_rental.ledger_entries.filter(kind=LedgerEntry.Kind.KELUAR_PAYOUT_PEMILIK).exists():
        payout = getattr(locked_rental, 'payout', None)
        return payout

    commission_pct = int(getattr(settings, 'PLATFORM_COMMISSION_PERCENT', 8))
    rent_total = locked_rental.rent_total
    deposit_total = locked_rental.deposit_total

    commission = round(rent_total * commission_pct / 100)
    owner_net = rent_total - commission

    late_fee = min(int(late_fee or 0), deposit_total)
    damage_fee = min(int(damage_fee or 0), deposit_total - late_fee)
    deposit_refund = max(0, deposit_total - late_fee - damage_fee)

    # 1. Komisi platform
    record_ledger_entry(
        rental=locked_rental,
        kind=LedgerEntry.Kind.KELUAR_KOMISI_PLATFORM,
        amount=commission,
        note=f"Komisi platform {commission_pct}% dari sewa pokok ({locked_rental.code})"
    )

    # 2. Payout pokok pemilik
    record_ledger_entry(
        rental=locked_rental,
        kind=LedgerEntry.Kind.KELUAR_PAYOUT_PEMILIK,
        amount=owner_net,
        note=f"Pencairan pokok sewa bersih ke pemilik ({locked_rental.code})"
    )
    create_wallet_transaction(
        user=locked_rental.owner,
        rental=locked_rental,
        kind=WalletTransaction.Kind.KREDIT_PAYOUT,
        amount=owner_net,
        note=f"Pencairan pokok sewa bersih ke dompet pemilik ({locked_rental.code})"
    )

    # 3. Denda keterlambatan ke pemilik (bila ada)
    if late_fee > 0:
        record_ledger_entry(
            rental=locked_rental,
            kind=LedgerEntry.Kind.KELUAR_DENDA_KE_PEMILIK,
            amount=late_fee,
            note=f"Denda keterlambatan diteruskan ke pemilik ({locked_rental.code})"
        )
        create_wallet_transaction(
            user=locked_rental.owner,
            rental=locked_rental,
            kind=WalletTransaction.Kind.KREDIT_DENDA_ATAU_POTONGAN,
            amount=late_fee,
            note=f"Denda keterlambatan diteruskan ke dompet pemilik ({locked_rental.code})"
        )

    # 4. Ganti rugi kerusakan dari deposit ke pemilik (bila ada)
    if damage_fee > 0:
        record_ledger_entry(
            rental=locked_rental,
            kind=LedgerEntry.Kind.KELUAR_DEPOSIT_KE_PEMILIK,
            amount=damage_fee,
            note=f"Ganti rugi kerusakan barang dari deposit ke pemilik ({locked_rental.code})"
        )
        create_wallet_transaction(
            user=locked_rental.owner,
            rental=locked_rental,
            kind=WalletTransaction.Kind.KREDIT_DENDA_ATAU_POTONGAN,
            amount=damage_fee,
            note=f"Ganti rugi kerusakan barang dari deposit ke dompet pemilik ({locked_rental.code})"
        )

    # 5. Pengembalian sisa deposit ke penyewa
    if deposit_refund > 0:
        record_ledger_entry(
            rental=locked_rental,
            kind=LedgerEntry.Kind.KELUAR_DEPOSIT_DIKEMBALIKAN,
            amount=deposit_refund,
            note=f"Pengembalian deposit jaminan ke penyewa ({locked_rental.code})"
        )
        create_wallet_transaction(
            user=locked_rental.renter,
            rental=locked_rental,
            kind=WalletTransaction.Kind.KREDIT_REFUND_DEPOSIT,
            amount=deposit_refund,
            note=f"Pengembalian deposit jaminan ke dompet penyewa ({locked_rental.code})"
        )

    # 6. Pemindahan dana proteksi ke dana bersama (bila ada)
    if locked_rental.protection_fee > 0:
        record_ledger_entry(
            rental=locked_rental,
            kind=LedgerEntry.Kind.KELUAR_KE_DANA_PROTEKSI,
            amount=locked_rental.protection_fee,
            note=f"Pemindahan iuran proteksi ke rekening cadangan dana proteksi ({locked_rental.code})"
        )

    # 7. Update status DepositHold
    hold = getattr(locked_rental, 'deposit_hold', None)
    if not hold:
        hold = DepositHold.objects.filter(rental=locked_rental).first()

    if hold:
        hold.released_amount = deposit_refund
        hold.deducted_amount = late_fee + damage_fee
        if hold.deducted_amount == 0:
            hold.status = DepositHold.Status.DIRILIS
        elif hold.released_amount == 0:
            hold.status = DepositHold.Status.DIPOTONG_PENUH
        else:
            hold.status = DepositHold.Status.DIPOTONG_SEBAGIAN
        hold.released_at = timezone.now()
        hold.save()

    # 8. Buat catatan Payout pemilik (simulasi)
    total_owner_payout = owner_net + late_fee + damage_fee
    total_owner_gross = rent_total + late_fee + damage_fee
    payout, _ = Payout.objects.get_or_create(
        rental=locked_rental,
        defaults={
            'owner': locked_rental.owner,
            'gross_rent': total_owner_gross,
            'commission': commission,
            'net_amount': total_owner_payout,
            'status': Payout.Status.DICAIRKAN_SIMULASI,
            'paid_at': timezone.now(),
        }
    )

    # 9. Verifikasi Invarian Buku Besar: Total Masuk == Total Keluar
    validate_ledger_invariant(locked_rental)

    return payout


@transaction.atomic
def process_cancellation_after_payment(rental, cancelled_by, reason=""):
    """
    Simulasi refund di buku besar untuk pembatalan setelah pembayaran berhasil:
    Kasus 1: Dibatalkan pemilik -> refund penuh (sewa + deposit + proteksi).
    Kasus 2: Dibatalkan penyewa > 24 jam sebelum start_date -> refund penuh.
    Kasus 3: Dibatalkan penyewa <= 24 jam sebelum start_date -> 20% dari rent_total menjadi hak pemilik, sisanya refund.
    Invarian: Total Masuk == Total Keluar.
    """
    locked_rental = Rental.objects.select_for_update().get(id=rental.id)
    if LedgerEntry.objects.filter(rental=locked_rental, kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA).exists():
        logger.info(f"Pembatalan buku besar untuk {locked_rental.code} sudah pernah diproses. Lewati (idempoten).")
        return locked_rental

    if locked_rental.status != Rental.Status.DIBAYAR:
        raise ValueError(f"Pembatalan berbayar hanya dapat dilakukan dari status DIBAYAR, bukan '{locked_rental.get_status_display()}'.")

    now = timezone.now()
    rent_total = locked_rental.rent_total
    deposit_total = locked_rental.deposit_total
    protection_fee = locked_rental.protection_fee
    grand_total = locked_rental.grand_total

    is_owner = (cancelled_by.id == locked_rental.owner_id)

    # Hitung selisih waktu terhadap awal tanggal sewa (start_date pukul 00:00 lokal)
    start_dt = timezone.make_aware(datetime.combine(locked_rental.start_date, time.min))
    hours_before_start = (start_dt - now).total_seconds() / 3600.0

    if is_owner or hours_before_start > 24:
        # Refund penuh ke penyewa
        record_ledger_entry(
            rental=locked_rental,
            kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA,
            amount=grand_total,
            note=f"Pengembalian dana penuh kepada penyewa akibat pembatalan ({locked_rental.code})"
        )
        create_wallet_transaction(
            user=locked_rental.renter,
            rental=locked_rental,
            kind=WalletTransaction.Kind.KREDIT_REFUND_DEPOSIT,
            amount=grand_total,
            note=f"Pengembalian dana penuh pembatalan sewa ({locked_rental.code})"
        )
    else:
        # Penyewa membatalkan <= 24 jam sebelum mulai: 20% rent_total untuk pemilik, sisanya refund
        compensation_owner = round(rent_total * 0.20)
        refund_renter = grand_total - compensation_owner

        record_ledger_entry(
            rental=locked_rental,
            kind=LedgerEntry.Kind.KELUAR_PAYOUT_PEMILIK,
            amount=compensation_owner,
            note=f"Kompensasi pembatalan mendadak (20% sewa) ke pemilik ({locked_rental.code})"
        )
        create_wallet_transaction(
            user=locked_rental.owner,
            rental=locked_rental,
            kind=WalletTransaction.Kind.KREDIT_PAYOUT,
            amount=compensation_owner,
            note=f"Kompensasi pembatalan sewa ke dompet pemilik ({locked_rental.code})"
        )

        record_ledger_entry(
            rental=locked_rental,
            kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA,
            amount=refund_renter,
            note=f"Pengembalian sisa dana sewa & deposit ke penyewa setelah potongan kompensasi ({locked_rental.code})"
        )
        create_wallet_transaction(
            user=locked_rental.renter,
            rental=locked_rental,
            kind=WalletTransaction.Kind.KREDIT_REFUND_DEPOSIT,
            amount=refund_renter,
            note=f"Pengembalian sisa dana sewa & deposit pembatalan sewa ({locked_rental.code})"
        )

        # Buat catatan Payout kompensasi pemilik
        Payout.objects.get_or_create(
            rental=locked_rental,
            defaults={
                'owner': locked_rental.owner,
                'gross_rent': compensation_owner,
                'commission': 0,
                'net_amount': compensation_owner,
                'status': Payout.Status.DICAIRKAN_SIMULASI,
                'paid_at': now,
            }
        )

    # Perbarui DepositHold
    hold = getattr(locked_rental, 'deposit_hold', None)
    if hold:
        hold.status = DepositHold.Status.DIRILIS
        hold.released_amount = deposit_total
        hold.deducted_amount = 0
        hold.released_at = now
        hold.save()

    # Verifikasi Invarian Buku Besar
    validate_ledger_invariant(locked_rental)

    return locked_rental


def validate_ledger_invariant(rental):
    """
    Memvalidasi invarian wajib buku besar:
    Jumlah seluruh 'masuk_*' HARUS PERSIS SAMA dengan jumlah seluruh 'keluar_*'.
    """
    total_masuk = sum(
        rental.ledger_entries.filter(kind__startswith='masuk_').values_list('amount', flat=True)
    )
    total_keluar = sum(
        rental.ledger_entries.filter(kind__startswith='keluar_').values_list('amount', flat=True)
    )
    if total_masuk != total_keluar:
        raise ValueError(
            f"Pelanggaran Invarian Buku Besar pada rental {rental.code}! "
            f"Total Masuk: Rp{total_masuk:,} != Total Keluar: Rp{total_keluar:,}"
        )
    return True


# ==============================================================================
# Layanan Dompet Pengguna dan Penarikan Dana (Fase 7C)
# ==============================================================================

def get_user_wallet_balance(user) -> int:
    """
    Menghitung saldo dompet pengguna saat ini dari riwayat WalletTransaction.
    Kredit (+) menambah saldo, penarikan (-) mengurangi saldo, penarikan batal (+) mengembalikan saldo.
    """
    from django.db.models import Sum, Q

    if not user or not user.is_authenticated:
        return 0

    res = WalletTransaction.objects.filter(user=user).aggregate(
        credits=Sum(
            'amount',
            filter=Q(kind__in=[
                WalletTransaction.Kind.KREDIT_PAYOUT,
                WalletTransaction.Kind.KREDIT_REFUND_DEPOSIT,
                WalletTransaction.Kind.KREDIT_DENDA_ATAU_POTONGAN,
                WalletTransaction.Kind.KREDIT_KLAIM_PROTEKSI,
                WalletTransaction.Kind.KREDIT_TAGIHAN_TAMBAHAN,
                WalletTransaction.Kind.DEBIT_PENARIKAN_BATAL,
            ])
        ),
        debits=Sum(
            'amount',
            filter=Q(kind__in=[WalletTransaction.Kind.DEBIT_PENARIKAN])
        ),
    )
    credits = res['credits'] or 0
    debits = res['debits'] or 0
    return max(0, credits - debits)


def validate_wallet_balance(user) -> int:
    """Memvalidasi integritas saldo pengguna (tidak boleh bernilai negatif)."""
    balance = get_user_wallet_balance(user)
    if balance < 0:
        raise ValueError(f"Integritas saldo tidak valid: Saldo pengguna '{user.username}' negatif ({balance}).")
    return balance


def create_wallet_transaction(user, kind, amount, rental=None, extra_charge=None, note="", source="live"):
    """
    Mencatat transaksi mutasi saldo dompet secara aman dan idempoten.
    Jika extra_charge atau rental ditentukan, tidak akan membuat mutasi duplikat untuk jenis yang sama.
    """
    if amount <= 0:
        return None

    if extra_charge:
        existing = WalletTransaction.objects.filter(
            user=user,
            extra_charge=extra_charge,
            kind=kind
        ).first()
        if existing:
            return existing
    elif rental:
        existing = WalletTransaction.objects.filter(
            user=user,
            rental=rental,
            kind=kind,
            amount=amount
        ).first()
        if existing:
            return existing

    tx = WalletTransaction.objects.create(
        user=user,
        rental=rental,
        extra_charge=extra_charge,
        kind=kind,
        amount=amount,
        source=source,
        note=note or f"Mutasi saldo {kind}"
    )
    return tx


@transaction.atomic
def request_withdrawal(user, amount, method, account_name, account_number, ip_address="", admin_note=""):
    """
    Mengajukan permintaan penarikan dana dompet pengguna:
    1. Validasi batas minimal (WITHDRAWAL_MIN, default Rp20.000).
    2. Validasi saldo mencukupi.
    3. Maksimal satu permintaan aktif (diminta / diproses) per pengguna.
    4. Nomor rekening dienkripsi Fernet (tidak pernah tercatat mentah di log).
    5. Saldo pengguna langsung dipotong (debit_penarikan).
    6. Mengirim notifikasi dalam aplikasi.
    """
    min_amount = int(getattr(settings, 'WITHDRAWAL_MIN', 20000))
    if amount < min_amount:
        raise ValueError(f"Jumlah penarikan minimal adalah Rp{min_amount:,}. Anda mengajukan Rp{amount:,}.")

    current_balance = get_user_wallet_balance(user)
    if amount > current_balance:
        raise ValueError(f"Saldo dompet tidak mencukupi (Saldo saat ini: Rp{current_balance:,}, diajukan: Rp{amount:,}).")

    has_active = WithdrawalRequest.objects.filter(
        user=user,
        status__in=[WithdrawalRequest.Status.DIMINTA, WithdrawalRequest.Status.DIPROSES]
    ).exists()
    if has_active:
        raise ValueError("Anda masih memiliki permintaan penarikan dana aktif yang sedang diproses. Harap tunggu hingga selesai.")

    valid_methods = WithdrawalRequest.Method.values
    if method not in valid_methods:
        raise ValueError(f"Metode penarikan '{method}' tidak valid. Pilihan yang tersedia: {', '.join(valid_methods)}.")

    if not account_name or not account_name.strip():
        raise ValueError("Nama pemilik rekening atau akun dompet digital wajib diisi.")

    if not account_number or not account_number.strip():
        raise ValueError("Nomor rekening atau akun dompet digital wajib diisi.")

    w = WithdrawalRequest(
        user=user,
        amount=amount,
        method=method,
        account_name=account_name.strip(),
        status=WithdrawalRequest.Status.DIMINTA,
        admin_note=admin_note.strip() if admin_note else "",
    )
    w.set_account_number(account_number.strip())
    w.save()

    # Langsung kurangi saldo dompet (debit_penarikan)
    create_wallet_transaction(
        user=user,
        kind=WalletTransaction.Kind.DEBIT_PENARIKAN,
        amount=amount,
        note=f"Pengajuan penarikan dana #{w.id} ke {method} ({w.masked_account_number})"
    )

    Notification.notify(
        user=user,
        title="Permintaan Penarikan Dana Diajukan",
        message=f"Permintaan penarikan saldo Rp{amount:,} ke rekening {method} ({w.masked_account_number}) berhasil diajukan dan sedang menunggu verifikasi admin.",
        url="/dompet/"
    )

    return w


@transaction.atomic
def process_withdrawal(withdrawal, new_status, admin_user, transfer_reference="", admin_note=""):
    """
    Memproses status permintaan penarikan dana oleh admin:
    - Status diproses: tandai diproses & kirim notifikasi.
    - Status selesai: catat transfer_reference & kirim notifikasi.
    - Status ditolak: kembalikan saldo lewat debit_penarikan_batal & kirim notifikasi.
    """
    locked_w = WithdrawalRequest.objects.select_for_update().get(id=withdrawal.id)
    if admin_user and locked_w.user_id == admin_user.id:
        raise ValueError("Staf dilarang memproses penarikan dananya sendiri demi kepatuhan pemisahan tugas (segregation of duties).")

    if locked_w.status in [WithdrawalRequest.Status.SELESAI, WithdrawalRequest.Status.DITOLAK]:
        raise ValueError(f"Permintaan penarikan #{locked_w.id} sudah berstatus final '{locked_w.get_status_display()}'.")

    now = timezone.now()

    if new_status == WithdrawalRequest.Status.DITOLAK:
        locked_w.status = WithdrawalRequest.Status.DITOLAK
        locked_w.processed_by = admin_user
        locked_w.processed_at = now
        locked_w.admin_note = admin_note.strip() if admin_note else "Ditolak oleh admin"
        locked_w.save()

        # Kembalikan saldo pengguna lewat debit_penarikan_batal
        create_wallet_transaction(
            user=locked_w.user,
            kind=WalletTransaction.Kind.DEBIT_PENARIKAN_BATAL,
            amount=locked_w.amount,
            note=f"Pengembalian saldo: Penarikan dana #{locked_w.id} ditolak admin. Alasan: {locked_w.admin_note}"
        )

        Notification.notify(
            user=locked_w.user,
            title="Penarikan Dana Ditolak",
            message=f"Permintaan penarikan dana Rp{locked_w.amount:,} ditolak admin. Alasan: {locked_w.admin_note}. Saldo telah dikembalikan penuh ke dompet Anda.",
            url="/dompet/"
        )

    elif new_status == WithdrawalRequest.Status.DIPROSES:
        locked_w.status = WithdrawalRequest.Status.DIPROSES
        locked_w.processed_by = admin_user
        locked_w.processed_at = now
        if admin_note:
            locked_w.admin_note = admin_note.strip()
        locked_w.save()

        Notification.notify(
            user=locked_w.user,
            title="Penarikan Dana Sedang Diproses",
            message=f"Permintaan penarikan dana Rp{locked_w.amount:,} sedang diverifikasi dan diproses transfer oleh tim admin.",
            url="/dompet/"
        )

    elif new_status == WithdrawalRequest.Status.SELESAI:
        locked_w.status = WithdrawalRequest.Status.SELESAI
        locked_w.processed_by = admin_user
        locked_w.processed_at = now
        locked_w.transfer_reference = transfer_reference.strip() if transfer_reference else ""
        if admin_note:
            locked_w.admin_note = admin_note.strip()
        locked_w.save()

        ref_str = f" (Ref: {locked_w.transfer_reference})" if locked_w.transfer_reference else ""
        Notification.notify(
            user=locked_w.user,
            title="Penarikan Dana Berhasil",
            message=f"Dana penarikan sebesar Rp{locked_w.amount:,} telah berhasil ditransfer ke {locked_w.method} ({locked_w.masked_account_number}){ref_str}.",
            url="/dompet/"
        )

    return locked_w


def log_account_number_access(withdrawal, accessed_by, ip_address="", reason=""):
    """Mencatat audit log saat staf/admin mengakses nomor rekening terenkripsi."""
    if not accessed_by or not (accessed_by.is_staff or accessed_by.is_superuser):
        raise PermissionError("Hanya staf admin yang memiliki wewenang melihat nomor rekening terenkripsi.")

    log_entry = WithdrawalAccountAccessLog.objects.create(
        withdrawal=withdrawal,
        accessed_by=accessed_by,
        ip_address=ip_address or "",
        reason=reason or ""
    )
    logger.info("Audit: Staf '%s' mengakses nomor rekening penarikan #%s (alasan: %s)", accessed_by.username, withdrawal.id, reason)
    return log_entry


@transaction.atomic
def settle_extra_charge(extra_charge, reference=None, reason="", settled_by=None, admin_user=None):
    """
    Menandai pelunasan tagihan tambahan (ExtraCharge) secara idempoten:
    - Status diubah menjadi LUNAS
    - Mengkredit saldo dompet pemilik barang via WalletTransaction (KREDIT_TAGIHAN_TAMBAHAN)
    - Mengirimkan notifikasi ke penyewa dan pemilik
    """
    from apps.payments.models import ExtraCharge
    from apps.core.models import Notification

    locked_charge = ExtraCharge.objects.select_for_update().get(id=extra_charge.id)
    if locked_charge.status == ExtraCharge.Status.LUNAS:
        return locked_charge

    now = timezone.now()
    ref_str = (reference or "").strip()
    if not ref_str:
        if admin_user:
            ref_str = f"Admin {getattr(admin_user, 'username', str(admin_user))}"
        elif settled_by:
            ref_str = f"Pelunasan oleh {settled_by}"
        else:
            ref_str = "Pelunasan sistem"

    locked_charge.status = ExtraCharge.Status.LUNAS
    locked_charge.paid_at = now
    locked_charge.settled_by = ref_str[:255]
    locked_charge.save(update_fields=['status', 'paid_at', 'settled_by'])

    # Kredit dompet pemilik barang dalam transaksi yang sama secara idempoten
    create_wallet_transaction(
        user=locked_charge.owner,
        rental=locked_charge.rental,
        extra_charge=locked_charge,
        kind=WalletTransaction.Kind.KREDIT_TAGIHAN_TAMBAHAN,
        amount=locked_charge.amount,
        note=f"Pelunasan {locked_charge.get_charge_type_display()} sewa {locked_charge.rental.code} (Ref: {locked_charge.settled_by})"
    )

    Notification.notify(
        user=locked_charge.owner,
        title="Tagihan Tambahan Dilunasi",
        message=f"Tagihan {locked_charge.get_charge_type_display()} sebesar Rp{locked_charge.amount:,} untuk sewa '{locked_charge.rental.code}' telah dilunasi dan dikreditkan ke saldo dompet Anda.",
        url=f"/sewa/{locked_charge.rental.code}/"
    )
    Notification.notify(
        user=locked_charge.renter,
        title="Pelunasan Tagihan Berhasil",
        message=f"Tagihan {locked_charge.get_charge_type_display()} sebesar Rp{locked_charge.amount:,} untuk sewa '{locked_charge.rental.code}' telah berhasil dilunasi.",
        url=f"/sewa/{locked_charge.rental.code}/"
    )

    return locked_charge



