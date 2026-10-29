from django.utils import timezone
from django.db.models import Sum, Q
from django.contrib.auth import get_user_model
from apps.payments.models import (
    Payment,
    DepositHold,
    Payout,
    LedgerEntry,
    WalletTransaction,
    WithdrawalRequest,
    ExtraCharge,
)
from apps.rentals.models import Rental
from apps.sales.models import SaleOrder

User = get_user_model()

def run_financial_reconciliation():
    """
    Melakukan rekonsiliasi keuangan menyeluruh:
    1. Total dana masuk dari pembayaran Midtrans (settlement sewa & pesanan jual beli).
    2. Total dana yang sedang ditahan di escrow platform (DepositHold ditahan + sewa berjalan + pesanan jual beli berjalan).
    3. Total saldo dompet pengguna aktif saat ini.
    4. Total penarikan dana aktif (status diminta/diproses) dan yang sudah selesai ditransfer.
    5. Total pendapatan komisi platform dari buku besar (sewa & jual beli).
    6. Total saldo cadangan Dana Gotong Royong platform.
    7. Status seimbang per sewa, per pesanan jual beli, dan secara global.
    """
    # 1. Total Pembayaran Masuk (Inflow dari Midtrans)
    total_payment_settled = (
        Payment.objects.filter(status=Payment.Status.SETTLEMENT)
        .aggregate(total=Sum('gross_amount'))['total'] or 0
    )

    # Total dari buku besar masuk (sewa + jual beli)
    ledger_masuk_aggr = LedgerEntry.objects.filter(
        kind__in=[
            LedgerEntry.Kind.MASUK_SEWA,
            LedgerEntry.Kind.MASUK_DEPOSIT,
            LedgerEntry.Kind.MASUK_PROTEKSI,
            LedgerEntry.Kind.MASUK_DANA_PROTEKSI,
            LedgerEntry.Kind.MASUK_PENJUALAN,
        ]
    ).aggregate(total=Sum('amount'))['total'] or 0

    # 2. Dana Ditahan di Escrow
    # a. DepositHold DITAHAN
    escrow_deposit_held = (
        DepositHold.objects.filter(status=DepositHold.Status.DITAHAN)
        .aggregate(total=Sum('amount'))['total'] or 0
    )

    # b. Dana sewa pokok yang sedang berjalan yang belum diselesaikan
    unsettled_rentals = Rental.objects.filter(
        status__in=[
            Rental.Status.DIBAYAR,
            Rental.Status.SEDANG_DISEWA,
            Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN,
            Rental.Status.SENGKETA,
        ]
    )
    escrow_rent_held = sum(r.rent_total for r in unsettled_rentals)

    # c. Dana jual beli yang sedang berjalan di escrow (dibayar, diserahkan, sengketa)
    unsettled_sales = SaleOrder.objects.filter(
        status__in=[
            SaleOrder.Status.DIBAYAR,
            SaleOrder.Status.DISERAHKAN,
            SaleOrder.Status.SENGKETA,
        ]
    )
    escrow_sales_held = sum(s.price_snapshot for s in unsettled_sales)

    total_escrow_held = escrow_deposit_held + escrow_rent_held + escrow_sales_held

    # 3. Total Saldo Dompet Seluruh Pengguna
    # Kredit (+)
    wallet_credits = (
        WalletTransaction.objects.filter(
            kind__in=[
                WalletTransaction.Kind.KREDIT_PAYOUT,
                WalletTransaction.Kind.KREDIT_REFUND_DEPOSIT,
                WalletTransaction.Kind.KREDIT_DENDA_ATAU_POTONGAN,
                WalletTransaction.Kind.KREDIT_KLAIM_PROTEKSI,
                WalletTransaction.Kind.DEBIT_PENARIKAN_BATAL,
                WalletTransaction.Kind.KREDIT_TAGIHAN_TAMBAHAN,
                WalletTransaction.Kind.KREDIT_PENJUALAN,
                WalletTransaction.Kind.KREDIT_REFUND_PENJUALAN,
            ]
        ).aggregate(total=Sum('amount'))['total'] or 0
    )
    # Debit (-)
    wallet_debits = (
        WalletTransaction.objects.filter(
            kind__in=[WalletTransaction.Kind.DEBIT_PENARIKAN]
        ).aggregate(total=Sum('amount'))['total'] or 0
    )
    total_user_wallets = max(0, wallet_credits - wallet_debits)

    # Tagihan Tambahan (ExtraCharge)
    total_extra_charges_unpaid = (
        ExtraCharge.objects.filter(status=ExtraCharge.Status.TERUTANG)
        .aggregate(total=Sum('amount'))['total'] or 0
    )
    total_extra_charges_paid = (
        ExtraCharge.objects.filter(status=ExtraCharge.Status.LUNAS)
        .aggregate(total=Sum('amount'))['total'] or 0
    )
    manual_settled_extra_charges = (
        ExtraCharge.objects.filter(status=ExtraCharge.Status.LUNAS, payment__isnull=True)
        .aggregate(total=Sum('amount'))['total'] or 0
    )

    # 4. Permintaan Penarikan Dana
    pending_withdrawals = (
        WithdrawalRequest.objects.filter(
            status__in=[WithdrawalRequest.Status.DIMINTA, WithdrawalRequest.Status.DIPROSES]
        ).aggregate(total=Sum('amount'))['total'] or 0
    )
    completed_withdrawals = (
        WithdrawalRequest.objects.filter(
            status=WithdrawalRequest.Status.SELESAI
        ).aggregate(total=Sum('amount'))['total'] or 0
    )

    # 5. Pendapatan Komisi Platform (Sewa + Jual Beli)
    total_commission = (
        LedgerEntry.objects.filter(
            kind__in=[
                LedgerEntry.Kind.KELUAR_KOMISI_PLATFORM,
                LedgerEntry.Kind.KELUAR_KOMISI_PENJUALAN,
            ]
        ).aggregate(total=Sum('amount'))['total'] or 0
    )

    # 6. Saldo Cadangan Dana Gotong Royong
    protection_inflow = (
        LedgerEntry.objects.filter(
            kind__in=[LedgerEntry.Kind.MASUK_DANA_PROTEKSI, LedgerEntry.Kind.MASUK_PROTEKSI]
        ).aggregate(total=Sum('amount'))['total'] or 0
    )
    protection_claims_paid = (
        LedgerEntry.objects.filter(kind=LedgerEntry.Kind.KELUAR_KOMPENSASI_PEMILIK)
        .aggregate(total=Sum('amount'))['total'] or 0
    )
    total_protection_fund = max(0, protection_inflow - protection_claims_paid)

    # 7. Rekonsiliasi Sumber-Sumber Saling Bebas:
    # A. Ledger User Outflow Sewa vs Wallet Rental Credits
    ledger_user_outflow_total = (
        LedgerEntry.objects.filter(
            rental__isnull=False,
            kind__in=[
                LedgerEntry.Kind.KELUAR_PAYOUT_PEMILIK,
                LedgerEntry.Kind.KELUAR_DENDA_KE_PEMILIK,
                LedgerEntry.Kind.KELUAR_DEPOSIT_KE_PEMILIK,
                LedgerEntry.Kind.KELUAR_DEPOSIT_DIKEMBALIKAN,
                LedgerEntry.Kind.KELUAR_KOMPENSASI_PEMILIK,
                LedgerEntry.Kind.KELUAR_REFUND_PENYEWA,
            ]
        ).aggregate(total=Sum('amount'))['total'] or 0
    )

    wallet_rental_credits_total = (
        WalletTransaction.objects.filter(
            rental__isnull=False,
            kind__in=[
                WalletTransaction.Kind.KREDIT_PAYOUT,
                WalletTransaction.Kind.KREDIT_REFUND_DEPOSIT,
                WalletTransaction.Kind.KREDIT_DENDA_ATAU_POTONGAN,
                WalletTransaction.Kind.KREDIT_KLAIM_PROTEKSI,
            ]
        ).aggregate(total=Sum('amount'))['total'] or 0
    )
    wallet_ledger_mismatch = abs(ledger_user_outflow_total - wallet_rental_credits_total)

    # B. DepositHold Selesai vs Ledger Deposit Outflows
    dh_settled = DepositHold.objects.filter(
        status__in=[DepositHold.Status.DIRILIS, DepositHold.Status.DIPOTONG_SEBAGIAN, DepositHold.Status.DIPOTONG_PENUH]
    ).aggregate(rel=Sum('released_amount'), ded=Sum('deducted_amount'))
    dh_settled_total = (dh_settled['rel'] or 0) + (dh_settled['ded'] or 0)

    ledger_deposit_outflow_total = (
        LedgerEntry.objects.filter(
            kind__in=[
                LedgerEntry.Kind.KELUAR_DEPOSIT_DIKEMBALIKAN,
                LedgerEntry.Kind.KELUAR_DEPOSIT_KE_PEMILIK,
                LedgerEntry.Kind.KELUAR_DENDA_KE_PEMILIK,
                LedgerEntry.Kind.KELUAR_REFUND_DEPOSIT,
            ]
        ).aggregate(total=Sum('amount'))['total'] or 0
    )
    deposithold_ledger_mismatch = abs(dh_settled_total - ledger_deposit_outflow_total)

    # C. WithdrawalRequest Valid vs Wallet Debits
    valid_withdrawals_total = pending_withdrawals + completed_withdrawals
    withdrawal_mismatch = abs(valid_withdrawals_total - wallet_debits)

    # D. Midtrans Sale Payments Settled vs Ledger masuk_penjualan
    sale_payments_settled = (
        Payment.objects.filter(sale_order__isnull=False, status=Payment.Status.SETTLEMENT)
        .aggregate(total=Sum('gross_amount'))['total'] or 0
    )
    ledger_masuk_penjualan = (
        LedgerEntry.objects.filter(sale_order__isnull=False, kind=LedgerEntry.Kind.MASUK_PENJUALAN)
        .aggregate(total=Sum('amount'))['total'] or 0
    )
    sale_payment_ledger_mismatch = abs(sale_payments_settled - ledger_masuk_penjualan)

    # E. Ledger Sales Payout vs Wallet Sales Credits
    ledger_sales_payout_total = (
        LedgerEntry.objects.filter(sale_order__isnull=False, kind=LedgerEntry.Kind.KELUAR_PAYOUT_PENJUAL)
        .aggregate(total=Sum('amount'))['total'] or 0
    )
    wallet_sales_credits_total = (
        WalletTransaction.objects.filter(sale_order__isnull=False, kind=WalletTransaction.Kind.KREDIT_PENJUALAN)
        .aggregate(total=Sum('amount'))['total'] or 0
    )
    sale_payout_wallet_mismatch = abs(ledger_sales_payout_total - wallet_sales_credits_total)

    # F. Ledger Sales Refund vs Wallet Sales Refund
    ledger_sales_refund_total = (
        LedgerEntry.objects.filter(sale_order__isnull=False, kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA)
        .aggregate(total=Sum('amount'))['total'] or 0
    )
    wallet_sales_refund_total = (
        WalletTransaction.objects.filter(sale_order__isnull=False, kind=WalletTransaction.Kind.KREDIT_REFUND_PENJUALAN)
        .aggregate(total=Sum('amount'))['total'] or 0
    )
    sale_refund_wallet_mismatch = abs(ledger_sales_refund_total - wallet_sales_refund_total)

    # 8. Pemeriksaan Per-Sewa
    rentals_data = []
    per_rental_mismatches = 0

    all_rentals_with_ledger = Rental.objects.filter(
        ledger_entries__isnull=False
    ).distinct().order_by('-created_at')

    for rental in all_rentals_with_ledger:
        masuk = sum(l.amount for l in rental.ledger_entries.all() if l.kind.startswith('masuk_'))
        keluar = sum(l.amount for l in rental.ledger_entries.all() if l.kind.startswith('keluar_'))

        # Periksa juga kesesuaian Ledger keluar pengguna vs WalletTransaction kredit sewa ini
        r_ledger_user_outflow = sum(
            l.amount for l in rental.ledger_entries.all()
            if l.kind in [
                LedgerEntry.Kind.KELUAR_PAYOUT_PEMILIK,
                LedgerEntry.Kind.KELUAR_DENDA_KE_PEMILIK,
                LedgerEntry.Kind.KELUAR_DEPOSIT_KE_PEMILIK,
                LedgerEntry.Kind.KELUAR_DEPOSIT_DIKEMBALIKAN,
                LedgerEntry.Kind.KELUAR_KOMPENSASI_PEMILIK,
                LedgerEntry.Kind.KELUAR_REFUND_PENYEWA,
            ]
        )
        r_wallet_credits = (
            WalletTransaction.objects.filter(
                rental=rental,
                kind__in=[
                    WalletTransaction.Kind.KREDIT_PAYOUT,
                    WalletTransaction.Kind.KREDIT_REFUND_DEPOSIT,
                    WalletTransaction.Kind.KREDIT_DENDA_ATAU_POTONGAN,
                    WalletTransaction.Kind.KREDIT_KLAIM_PROTEKSI,
                ]
            ).aggregate(total=Sum('amount'))['total'] or 0
        )
        
        is_rental_balanced = True
        status_note = "Seimbang"
        if rental.status in [Rental.Status.SELESAI, Rental.Status.DIBATALKAN]:
            if masuk != keluar:
                is_rental_balanced = False
                per_rental_mismatches += 1
                status_note = f"Selisih Masuk({masuk}) vs Keluar({keluar})"
            elif r_ledger_user_outflow != r_wallet_credits:
                is_rental_balanced = False
                per_rental_mismatches += 1
                status_note = f"Selisih Buku Besar ({r_ledger_user_outflow}) vs Kredit Dompet ({r_wallet_credits})"
        else:
            # Masih berjalan, masuk ada, keluar belum dicatat
            status_note = f"Berjalan (Escrow Rp{masuk:,})"

        item_title = getattr(rental.item, 'title', str(rental.item)) if hasattr(rental, 'item') and rental.item else '-'
        discrepancy = (masuk - keluar) if rental.status in [Rental.Status.SELESAI, Rental.Status.DIBATALKAN] else 0
        if is_rental_balanced and (masuk == keluar and masuk > 0):
            status_label = 'Seimbang'
        elif masuk > keluar:
            status_label = 'Escrow Ditahan'
        else:
            status_label = 'Tidak Seimbang'

        rentals_data.append({
            'rental': rental,
            'code': rental.code,
            'item_title': item_title,
            'status': rental.status,
            'status_display': rental.get_status_display(),
            'masuk': masuk,
            'keluar': keluar,
            'inflow': masuk,
            'outflow': keluar,
            'discrepancy': discrepancy,
            'status_label': status_label,
            'is_balanced': is_rental_balanced,
            'note': status_note,
        })

    # 8.2 Pemeriksaan Per-Pesanan Jual Beli
    sales_data = []
    per_sale_order_mismatches = 0

    all_sales_with_ledger = SaleOrder.objects.filter(
        ledger_entries__isnull=False
    ).distinct().order_by('-created_at')

    for sale_order in all_sales_with_ledger:
        masuk = sum(l.amount for l in sale_order.ledger_entries.all() if l.kind.startswith('masuk_'))
        keluar = sum(l.amount for l in sale_order.ledger_entries.all() if l.kind.startswith('keluar_'))

        # Periksa kesesuaian Ledger keluar pengguna vs WalletTransaction kredit pesanan jual beli ini
        s_ledger_user_outflow = sum(
            l.amount for l in sale_order.ledger_entries.all()
            if l.kind in [
                LedgerEntry.Kind.KELUAR_PAYOUT_PENJUAL,
                LedgerEntry.Kind.KELUAR_REFUND_PENYEWA,
            ]
        )
        s_wallet_credits = (
            WalletTransaction.objects.filter(
                sale_order=sale_order,
                kind__in=[
                    WalletTransaction.Kind.KREDIT_PENJUALAN,
                    WalletTransaction.Kind.KREDIT_REFUND_PENJUALAN,
                ]
            ).aggregate(total=Sum('amount'))['total'] or 0
        )

        is_sale_balanced = True
        status_note = "Seimbang"
        if sale_order.status in [SaleOrder.Status.SELESAI, SaleOrder.Status.DIBATALKAN]:
            if masuk != keluar:
                is_sale_balanced = False
                per_sale_order_mismatches += 1
                status_note = f"Selisih Masuk({masuk}) vs Keluar({keluar})"
            elif s_ledger_user_outflow != s_wallet_credits:
                is_sale_balanced = False
                per_sale_order_mismatches += 1
                status_note = f"Selisih Buku Besar ({s_ledger_user_outflow}) vs Kredit Dompet ({s_wallet_credits})"
        else:
            # Masih berjalan (dibayar, diserahkan, sengketa), masuk ada, keluar belum dicatat
            status_note = f"Berjalan (Escrow Rp{masuk:,})"

        item_title = getattr(sale_order.item, 'title', str(sale_order.item)) if hasattr(sale_order, 'item') and sale_order.item else '-'
        discrepancy = (masuk - keluar) if sale_order.status in [SaleOrder.Status.SELESAI, SaleOrder.Status.DIBATALKAN] else 0
        if is_sale_balanced and (masuk == keluar and masuk > 0):
            status_label = 'Seimbang'
        elif masuk > keluar:
            status_label = 'Escrow Ditahan'
        else:
            status_label = 'Tidak Seimbang'

        sales_data.append({
            'sale_order': sale_order,
            'code': sale_order.code,
            'item_title': item_title,
            'status': sale_order.status,
            'status_display': sale_order.get_status_display(),
            'masuk': masuk,
            'keluar': keluar,
            'inflow': masuk,
            'outflow': keluar,
            'discrepancy': discrepancy,
            'status_label': status_label,
            'is_balanced': is_sale_balanced,
            'note': status_note,
        })

    # 9. Keseimbangan Global
    # Total Dana Masuk Riil = Total Escrow + Total Saldo Pengguna + Total Penarikan Aktif + Total Penarikan Selesai + Total Komisi Platform + Total Dana Gotong Royong
    total_accounted = (
        total_escrow_held +
        total_user_wallets +
        pending_withdrawals +
        completed_withdrawals +
        total_commission +
        total_protection_fund
    )
    
    total_effective_inflow = total_payment_settled + manual_settled_extra_charges
    global_diff = total_effective_inflow - total_accounted if total_effective_inflow > 0 else 0
    is_global_balanced = (
        per_rental_mismatches == 0 and
        per_sale_order_mismatches == 0 and
        abs(global_diff) == 0 and
        wallet_ledger_mismatch == 0 and
        deposithold_ledger_mismatch == 0 and
        withdrawal_mismatch == 0 and
        sale_payment_ledger_mismatch == 0 and
        sale_payout_wallet_mismatch == 0 and
        sale_refund_wallet_mismatch == 0
    )

    independent_checks = {
        'ledger_user_outflow_total': ledger_user_outflow_total,
        'wallet_rental_credits_total': wallet_rental_credits_total,
        'wallet_ledger_mismatch': wallet_ledger_mismatch,
        'dh_settled_total': dh_settled_total,
        'ledger_deposit_outflow_total': ledger_deposit_outflow_total,
        'deposithold_ledger_mismatch': deposithold_ledger_mismatch,
        'valid_withdrawals_total': valid_withdrawals_total,
        'wallet_debits_total': wallet_debits,
        'withdrawal_mismatch': withdrawal_mismatch,
        'sale_payments_settled': sale_payments_settled,
        'ledger_masuk_penjualan': ledger_masuk_penjualan,
        'sale_payment_ledger_mismatch': sale_payment_ledger_mismatch,
        'ledger_sales_payout_total': ledger_sales_payout_total,
        'wallet_sales_credits_total': wallet_sales_credits_total,
        'sale_payout_wallet_mismatch': sale_payout_wallet_mismatch,
        'ledger_sales_refund_total': ledger_sales_refund_total,
        'wallet_sales_refund_total': wallet_sales_refund_total,
        'sale_refund_wallet_mismatch': sale_refund_wallet_mismatch,
        'all_independent_balanced': (
            wallet_ledger_mismatch == 0 and
            deposithold_ledger_mismatch == 0 and
            withdrawal_mismatch == 0 and
            sale_payment_ledger_mismatch == 0 and
            sale_payout_wallet_mismatch == 0 and
            sale_refund_wallet_mismatch == 0
        )
    }

    summary = {
        'global_balanced': is_global_balanced,
        'discrepancy': global_diff,
        'total_inflow': total_effective_inflow,
        'total_held_escrow': total_escrow_held,
        'escrow_sales_held': escrow_sales_held,
        'total_user_wallets': total_user_wallets,
        'total_pending_withdrawals': pending_withdrawals,
        'total_completed_withdrawals': completed_withdrawals,
        'total_platform_commission': total_commission,
        'total_protection_pool': total_protection_fund,
        'total_extra_charges_unpaid': total_extra_charges_unpaid,
        'total_extra_charges_paid': total_extra_charges_paid,
        'mismatched_rentals_count': per_rental_mismatches,
        'total_rentals_checked': len(rentals_data),
        'mismatched_sales_count': per_sale_order_mismatches,
        'total_sales_checked': len(sales_data),
        'independent_checks': independent_checks,
    }

    return {
        'summary': summary,
        'rentals': rentals_data,
        'sales': sales_data,
        'sales_data': sales_data,
        'escrow_sales_held': escrow_sales_held,
        'per_sale_order_mismatches': per_sale_order_mismatches,
        'generated_at': timezone.now(),
        # Flat keys for compatibility:
        'total_payment_settled': total_payment_settled,
        'total_effective_inflow': total_effective_inflow,
        'ledger_masuk_aggr': ledger_masuk_aggr,
        'total_escrow_held': total_escrow_held,
        'escrow_deposit_held': escrow_deposit_held,
        'escrow_rent_held': escrow_rent_held,
        'total_user_wallets': total_user_wallets,
        'pending_withdrawals': pending_withdrawals,
        'completed_withdrawals': completed_withdrawals,
        'total_commission': total_commission,
        'total_protection_fund': total_protection_fund,
        'total_extra_charges_unpaid': total_extra_charges_unpaid,
        'total_extra_charges_paid': total_extra_charges_paid,
        'is_global_balanced': is_global_balanced,
        'global_diff': global_diff,
        'per_rental_mismatches': per_rental_mismatches,
        'rentals_data': rentals_data,
        'independent_checks': independent_checks,
    }
