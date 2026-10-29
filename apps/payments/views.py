import json
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.payments.models import Payment
from apps.payments.services import (
    create_or_get_payment_token,
    sync_payment_status,
    verify_midtrans_signature,
    is_midtrans_configured,
    MidtransConfigError,
    MidtransError,
)
from apps.rentals.models import Rental

logger = logging.getLogger(__name__)


@login_required
@require_POST
def rental_pay_view(request, code):
    """
    POST /sewa/<kode>/bayar/
    - Hanya penyewa sah dari sewa tersebut
    - Status wajib menunggu_pembayaran
    - Menghasilkan atau menggunakan kembali Snap Token Midtrans
    - Mengembalikan JSON {status, snap_token, order_id, client_key}
    """
    rental = get_object_or_404(
        Rental.objects.select_related('item', 'renter', 'owner'),
        code=code
    )

    # 1. Proteksi IDOR: Hanya penyewa sah
    if request.user.id != rental.renter_id:
        return JsonResponse({
            'status': 'error',
            'message': 'Hanya penyewa yang dapat melakukan pembayaran untuk pesanan ini.'
        }, status=403)

    # 2. Validasi status sewa
    if rental.status != Rental.Status.MENUNGGU_PEMBAYARAN:
        return JsonResponse({
            'status': 'error',
            'message': f"Pembayaran tidak dapat diproses karena status sewa saat ini adalah '{rental.get_status_display()}'."
        }, status=400)

    # 3. Validasi konfigurasi kunci Midtrans
    if not is_midtrans_configured():
        return JsonResponse({
            'status': 'error',
            'message': 'Kunci Midtrans belum diisi'
        }, status=400)

    # 4. Buat atau ambil Snap token
    force_new = False
    if request.body:
        try:
            body_json = json.loads(request.body.decode('utf-8'))
            force_new = bool(body_json.get('force_new'))
        except Exception:
            pass
    if not force_new:
        force_new = request.POST.get('force_new') in ['1', 'true', 'True']

    try:
        finish_url = request.build_absolute_uri(
            reverse('rentals:rental_payment_finish', kwargs={'code': rental.code})
        )
        payment = create_or_get_payment_token(
            rental, request.user, force_new=force_new, finish_url=finish_url
        )
    except MidtransConfigError:
        return JsonResponse({
            'status': 'error',
            'message': 'Kunci Midtrans belum diisi'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in rental_pay_view for {code}: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

    from apps.payments.services import get_midtrans_snap_mode
    return JsonResponse({
        'status': 'success',
        'snap_token': payment.snap_token,
        'order_id': payment.order_id,
        'gross_amount': payment.gross_amount,
        'client_key': getattr(settings, 'MIDTRANS_CLIENT_KEY', ''),
        'snap_mode': get_midtrans_snap_mode(),
    })


@login_required
@require_POST
def rental_sync_payment_view(request, code):
    """
    POST /sewa/<kode>/sinkron-pembayaran/
    - Dipanggil setelah popup Snap selesai (onSuccess, onPending, onClose)
    - Server mengecek langsung status transaksi ke API Midtrans (SATU-SATUNYA SUMBER KEBENARAN)
    - Tidak pernah mempercayai payload status mentah yang dikirim browser
    - Idempoten
    """
    rental = get_object_or_404(Rental, code=code)

    # Proteksi IDOR: hanya peserta sewa
    if request.user.id not in [rental.renter_id, rental.owner_id] and not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({
            'status': 'error',
            'message': 'Anda tidak berhak mengakses informasi sewa ini.'
        }, status=403)

    # Ambil order_id atau transaction_id dari POST data atau cari pembayaran pending terakhir
    order_id = request.POST.get('order_id')
    transaction_id = request.POST.get('transaction_id')
    if not order_id and transaction_id:
        order_id = transaction_id
    elif not order_id:
        try:
            body_data = json.loads(request.body)
            order_id = body_data.get('order_id') or body_data.get('transaction_id')
            if not transaction_id:
                transaction_id = body_data.get('transaction_id')
        except Exception:
            pass

    if not order_id:
        latest_payment = rental.payments.order_by('-created_at').first()
        if latest_payment:
            order_id = latest_payment.order_id

    if not order_id:
        return JsonResponse({
            'status': 'error',
            'message': 'Data transaksi pembayaran tidak ditemukan.'
        }, status=404)

    try:
        payment, updated_rental = sync_payment_status(order_id)
    except MidtransError as e:
        logger.warning(f"Midtrans sync error for order {order_id}: {e}")
        err_msg = str(e)
        if "404" in err_msg or "doesn't exist" in err_msg:
            friendly_msg = "Transaksi belum aktif di Midtrans (metode pembayaran belum dipilih di popup atau belum diproses di simulator)."
        else:
            friendly_msg = f"Gagal mengecek status pembayaran ke Midtrans: {e}"
        return JsonResponse({
            'status': 'error',
            'message': friendly_msg
        }, status=502)
    except Exception as e:
        logger.error(f"Unexpected error in rental_sync_payment_view for {order_id}: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

    is_paid_status = updated_rental.status in [
        Rental.Status.DIBAYAR,
        Rental.Status.SEDANG_DISEWA,
        Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN,
        Rental.Status.SELESAI,
    ]
    return JsonResponse({
        'status': 'success',
        'order_id': payment.order_id,
        'payment_status': payment.status,
        'rental_status': updated_rental.status,
        'rental_status_display': updated_rental.get_status_display(),
        'is_paid': is_paid_status,
    })


@login_required
def rental_payment_finish_view(request, code):
    """
    GET /sewa/<kode>/selesai-bayar/
    - Halaman profesional status penyelesaian pembayaran sewa KampusRent.
    - Menangani kembalian (finish redirect) dari Midtrans Snap / Simulator.
    - Sinkronisasi otomatis ke Midtrans API (idempoten) menggunakan order_id dari query params atau pembayaran rental.
    - Menampilkan tanda terima resmi terverifikasi, penjelasan perlindungan escrow, dan langkah selanjutnya.
    """
    rental = get_object_or_404(
        Rental.objects.select_related('item', 'renter', 'owner', 'item__owner'),
        code=code
    )

    # Proteksi IDOR: hanya peserta sewa atau staf
    if request.user.id not in [rental.renter_id, rental.owner_id] and not (request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied("Anda tidak berhak mengakses informasi pembayaran sewa ini.")

    order_id = request.GET.get('order_id') or request.GET.get('transaction_id')
    if not order_id:
        latest = rental.payments.order_by('-created_at').first()
        if latest:
            order_id = latest.order_id

    if order_id:
        try:
            sync_payment_status(order_id)
            rental.refresh_from_db()
        except MidtransError as e:
            logger.warning(f"Midtrans sync warning pada selesai-bayar {order_id}: {e}")
        except Exception as e:
            logger.error(f"Error tidak terduga saat sync pembayaran {order_id}: {e}")

    latest_payment = rental.payments.order_by('-created_at').first()
    is_settled = rental.status in [
        Rental.Status.DIBAYAR,
        Rental.Status.SEDANG_DISEWA,
        Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN,
        Rental.Status.SELESAI
    ]

    context = {
        'rental': rental,
        'payment': latest_payment,
        'is_settled': is_settled,
        'order_id': order_id or (latest_payment.order_id if latest_payment else f"KR-{rental.code}"),
    }
    return render(request, 'rentals/rental_payment_finish.html', context)


@login_required
@require_POST
def sale_order_pay_view(request, code):
    """
    POST /pesanan/<kode>/bayar/
    - Hanya pembeli sah dari pesanan jual beli tersebut
    - Status wajib menunggu_pembayaran
    - Menghasilkan atau menggunakan kembali Snap Token Midtrans (order_id berawalan KJ-)
    - Mengembalikan JSON {status, snap_token, order_id, client_key, snap_mode}
    """
    from apps.sales.models import SaleOrder
    from apps.payments.services import create_or_get_sale_payment_token, get_midtrans_snap_mode

    order = get_object_or_404(
        SaleOrder.objects.select_related('item', 'buyer', 'seller'),
        code=code
    )

    # 1. Proteksi IDOR: Hanya pembeli sah
    if request.user.id != order.buyer_id:
        return JsonResponse({
            'status': 'error',
            'message': 'Hanya pembeli yang dapat melakukan pembayaran untuk pesanan ini.'
        }, status=403)

    # 2. Validasi status pesanan
    if order.status != SaleOrder.Status.MENUNGGU_PEMBAYARAN:
        return JsonResponse({
            'status': 'error',
            'message': f"Pembayaran tidak dapat diproses karena status pesanan saat ini adalah '{order.get_status_display()}'."
        }, status=400)

    # 3. Validasi konfigurasi kunci Midtrans
    if not is_midtrans_configured():
        return JsonResponse({
            'status': 'error',
            'message': 'Kunci Midtrans belum diisi'
        }, status=400)

    force_new = False
    if request.body:
        try:
            body_json = json.loads(request.body.decode('utf-8'))
            force_new = bool(body_json.get('force_new'))
        except Exception:
            pass
    if not force_new:
        force_new = request.POST.get('force_new') in ['1', 'true', 'True']

    try:
        finish_url = request.build_absolute_uri(
            reverse('sales:order_detail', kwargs={'code': order.code})
        )
        payment = create_or_get_sale_payment_token(
            order, request.user, force_new=force_new, finish_url=finish_url
        )
    except MidtransConfigError:
        return JsonResponse({
            'status': 'error',
            'message': 'Kunci Midtrans belum diisi'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in sale_order_pay_view for {code}: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

    return JsonResponse({
        'status': 'success',
        'snap_token': payment.snap_token,
        'order_id': payment.order_id,
        'gross_amount': payment.gross_amount,
        'client_key': getattr(settings, 'MIDTRANS_CLIENT_KEY', ''),
        'snap_mode': get_midtrans_snap_mode(),
    })


@login_required
@require_POST
def sale_order_sync_payment_view(request, code):
    """
    POST /pesanan/<kode>/sinkron-pembayaran/
    Sinkronisasi status pembayaran Midtrans untuk pesanan jual beli secara manual/idempoten.
    """
    from apps.sales.models import SaleOrder
    order = get_object_or_404(SaleOrder, code=code)

    if request.user.id not in (order.buyer_id, order.seller_id) and not request.user.is_staff:
        return JsonResponse({
            'status': 'error',
            'message': 'Anda tidak berhak mengakses informasi pesanan ini.'
        }, status=403)

    latest_payment = order.payments.order_by('-created_at').first()
    if not latest_payment:
        return JsonResponse({
            'status': 'error',
            'message': 'Belum ada transaksi pembayaran yang tercatat untuk pesanan ini.'
        }, status=400)

    try:
        payment, updated_order = sync_payment_status(latest_payment.order_id)
        return JsonResponse({
            'status': 'success',
            'payment_status': payment.status,
            'order_status': updated_order.status,
            'message': f"Status pesanan berhasil disinkronkan: {updated_order.get_status_display()}."
        })
    except Exception as e:
        logger.error(f"Error in sale_order_sync_payment_view for {code}: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)



@csrf_exempt
@require_POST
def midtrans_notification_webhook(request):
    """
    POST /midtrans/notifikasi/
    - Webhook resmi dari Midtrans server
    - Memverifikasi signature_key (SHA-512)
    - Memanggil sync_payment_status
    - Hanya berfungsi bila memakai tunnel (mis. Cloudflare Tunnel / ngrok)
    """
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON body")

    order_id = payload.get('order_id')
    status_code = payload.get('status_code')
    gross_amount = payload.get('gross_amount')
    signature_key = payload.get('signature_key')

    if not order_id or not status_code or not gross_amount or not signature_key:
        return HttpResponseBadRequest("Missing required parameters in notification")

    # Verifikasi signature key
    if not verify_midtrans_signature(order_id, status_code, gross_amount, signature_key):
        logger.warning(f"Invalid webhook signature for order {order_id}")
        return HttpResponse("Signature verification failed", status=403)

    try:
        payment, rental = sync_payment_status(order_id, external_status_data=payload)
        logger.info(f"Webhook processed for order {order_id}: payment={payment.status}, rental={rental.status}")
    except Exception as e:
        logger.error(f"Webhook processing error for order {order_id}: {e}")
        return HttpResponse(f"Error: {e}", status=500)

    return JsonResponse({'status': 'ok'})


# ==============================================================================
# Tampilan Dompet Pengguna dan Penarikan Dana (Fase 7C)
# ==============================================================================

from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from apps.core.ratelimit import get_client_ip
from apps.payments.models import WalletTransaction, WithdrawalRequest
from apps.payments.services import (
    get_user_wallet_balance,
    request_withdrawal,
    process_withdrawal,
    log_account_number_access,
)
from apps.payments.reconciliation import run_financial_reconciliation


@login_required(login_url='/masuk/')
def wallet_view(request):
    """Halaman dompet mahasiswa (/dompet/): menampilkan saldo, mutasi, dan riwayat penarikan."""
    user = request.user
    balance = get_user_wallet_balance(user)

    transactions = (
        WalletTransaction.objects
        .filter(user=user)
        .select_related('rental', 'rental__item')
        .order_by('-created_at')[:50]
    )

    withdrawals_qs = (
        WithdrawalRequest.objects
        .filter(user=user)
        .order_by('-requested_at')
    )

    pending_withdrawal = withdrawals_qs.filter(
        status__in=[WithdrawalRequest.Status.DIMINTA, WithdrawalRequest.Status.DIPROSES]
    ).first()

    withdrawals = withdrawals_qs[:20]

    min_withdrawal = int(getattr(settings, 'WITHDRAWAL_MIN', 20000))

    return render(request, 'payments/wallet.html', {
        'balance': balance,
        'transactions': transactions,
        'withdrawals': withdrawals,
        'pending_withdrawal': pending_withdrawal,
        'min_withdrawal': min_withdrawal,
    })


@login_required(login_url='/masuk/')
def withdrawal_request_view(request):
    """Halaman pengajuan penarikan dana (/dompet/tarik/): wajib konfirmasi kata sandi."""
    user = request.user
    balance = get_user_wallet_balance(user)
    min_withdrawal = int(getattr(settings, 'WITHDRAWAL_MIN', 20000))

    # Cek apakah sudah ada penarikan aktif
    active_withdrawal = WithdrawalRequest.objects.filter(
        user=user,
        status__in=[WithdrawalRequest.Status.DIMINTA, WithdrawalRequest.Status.DIPROSES]
    ).first()
    if active_withdrawal:
        messages.warning(
            request,
            f"Anda memiliki permintaan penarikan dana aktif sebesar Rp{active_withdrawal.amount:,} "
            f"yang sedang diproses. Anda belum dapat mengajukan penarikan baru."
        )
        return redirect('payments:wallet')

    if request.method == 'POST':
        password = request.POST.get('password', '')
        if not user.check_password(password):
            messages.error(request, "Konfirmasi kata sandi akun salah. Permintaan penarikan dana dibatalkan demi keamanan.")
            return render(request, 'payments/withdrawal_form.html', {
                'balance': balance,
                'min_withdrawal': min_withdrawal,
                'methods': WithdrawalRequest.Method.choices,
                'selected_method': request.POST.get('method', '').strip(),
                'account_name': request.POST.get('account_name', '').strip(),
                'account_number': request.POST.get('account_number', '').strip(),
                'amount': request.POST.get('amount', '').strip(),
            })

        method = request.POST.get('method', '').strip()
        account_name = request.POST.get('account_name', '').strip()
        account_number = request.POST.get('account_number', '').strip()
        amount_raw = request.POST.get('amount', '').replace('.', '').replace(',', '').strip()

        try:
            amount = int(amount_raw)
        except (ValueError, TypeError):
            messages.error(request, "Nominal penarikan harus berupa angka rupiah yang valid.")
            return render(request, 'payments/withdrawal_form.html', {
                'balance': balance,
                'min_withdrawal': min_withdrawal,
                'methods': WithdrawalRequest.Method.choices,
                'selected_method': method,
                'account_name': account_name,
                'account_number': account_number,
                'amount': amount_raw,
            })

        ip = get_client_ip(request)
        try:
            w = request_withdrawal(
                user=user,
                amount=amount,
                method=method,
                account_name=account_name,
                account_number=account_number,
                ip_address=ip
            )
            messages.success(
                request,
                f"Permintaan penarikan dana sebesar Rp{w.amount:,} ke {w.method} ({w.masked_account_number}) "
                f"berhasil diajukan dan sedang menunggu verifikasi admin."
            )
            return redirect('payments:wallet')
        except ValueError as e:
            messages.error(request, str(e))

    return render(request, 'payments/withdrawal_form.html', {
        'balance': balance,
        'min_withdrawal': min_withdrawal,
        'methods': WithdrawalRequest.Method.choices,
    })


@staff_member_required
def admin_reconciliation_view(request):
    """Halaman admin (/admin/rekonsiliasi/): audit saldo dompet, escrow, penarikan, komisi, dan dana gotong royong."""
    data = run_financial_reconciliation()
    return render(request, 'payments/admin_reconciliation.html', {
        'recon': data,
    })


@staff_member_required
def admin_withdrawals_view(request):
    """Halaman antrean penarikan dana admin (/admin/penarikan/)."""
    status_filter = request.GET.get('status', '').strip()
    withdrawals = (
        WithdrawalRequest.objects
        .select_related('user', 'processed_by')
        .order_by('-requested_at')
    )

    if status_filter:
        withdrawals = withdrawals.filter(status=status_filter)

    counts = {
        'semua': WithdrawalRequest.objects.count(),
        'diminta': WithdrawalRequest.objects.filter(status=WithdrawalRequest.Status.DIMINTA).count(),
        'diproses': WithdrawalRequest.objects.filter(status=WithdrawalRequest.Status.DIPROSES).count(),
        'selesai': WithdrawalRequest.objects.filter(status=WithdrawalRequest.Status.SELESAI).count(),
        'ditolak': WithdrawalRequest.objects.filter(status=WithdrawalRequest.Status.DITOLAK).count(),
    }

    return render(request, 'payments/admin_withdrawals.html', {
        'withdrawals': withdrawals,
        'status_filter': status_filter,
        'counts': counts,
    })


@staff_member_required
@require_POST
def admin_withdrawal_reveal_account_view(request, pk):
    """
    Tindakan staf melihat nomor rekening asli:
    - Wajib request POST dengan CSRF token
    - Wajib mencantumkan alasan operasional (min. 5 karakter)
    - Dibatasi laju (maks. 10x per menit per staf)
    - Dicatat ke WithdrawalAccountAccessLog
    """
    from apps.core.ratelimit import is_rate_limited
    rate_key = f"reveal_account:{request.user.id}"
    limited, remaining = is_rate_limited(rate_key, max_attempts=10, window_seconds=60, request=request, user_id=request.user.id)
    if limited:
        return JsonResponse({
            'status': 'error',
            'message': f"Batas laju pembukaan nomor rekening terlampaui. Silakan tunggu {remaining} detik."
        }, status=429)

    reason = request.POST.get('reason', '').strip()
    if not reason or len(reason) < 5:
        return JsonResponse({
            'status': 'error',
            'message': "Alasan operasional pembukaan nomor rekening wajib diisi minimal 5 karakter."
        }, status=400)

    w = get_object_or_404(WithdrawalRequest, pk=pk)
    ip = get_client_ip(request)
    log_account_number_access(withdrawal=w, accessed_by=request.user, ip_address=ip, reason=reason)

    plain_number = w.get_decrypted_account_number()
    return JsonResponse({
        'status': 'success',
        'account_number': plain_number,
        'masked': w.masked_account_number,
        'account_name': w.account_name,
        'method': w.method,
    })


@staff_member_required
@require_POST
def admin_withdrawal_process_view(request, pk):
    """Tindakan staf memproses penarikan: tandai diproses, selesai, atau ditolak."""
    w = get_object_or_404(WithdrawalRequest, pk=pk)

    if w.user_id == request.user.id:
        messages.error(request, "Staf dilarang memproses permintaan penarikan dananya sendiri demi kepatuhan pemisahan tugas (segregation of duties).")
        return redirect('payments:admin_withdrawals')

    new_status = request.POST.get('status', '').strip()
    transfer_ref = request.POST.get('transfer_reference', '').strip()
    admin_note = request.POST.get('admin_note', '').strip()

    valid_targets = [
        WithdrawalRequest.Status.DIPROSES,
        WithdrawalRequest.Status.SELESAI,
        WithdrawalRequest.Status.DITOLAK,
    ]
    if new_status not in valid_targets:
        messages.error(request, f"Status target '{new_status}' tidak valid.")
        return redirect('payments:admin_withdrawals')

    if new_status == WithdrawalRequest.Status.DITOLAK and not admin_note:
        messages.error(request, "Alasan penolakan wajib diisi saat menolak penarikan dana.")
        return redirect('payments:admin_withdrawals')

    try:
        process_withdrawal(
            withdrawal=w,
            new_status=new_status,
            admin_user=request.user,
            transfer_reference=transfer_ref,
            admin_note=admin_note
        )
        messages.success(request, f"Permintaan penarikan #{w.id} berhasil diubah statusnya menjadi {w.get_status_display()}.")
    except Exception as e:
        messages.error(request, f"Gagal memperbarui penarikan: {e}")

    return redirect('payments:admin_withdrawals')

