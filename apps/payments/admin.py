from django.contrib import admin
from django.utils import timezone
from .models import (
    Payment, DepositHold, Payout, LedgerEntry,
    WalletTransaction, WithdrawalRequest, WithdrawalAccountAccessLog,
    ExtraCharge
)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'rental', 'sale_order', 'gross_amount', 'status', 'payment_type', 'paid_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('order_id', 'rental__code', 'sale_order__code', 'transaction_id')
    raw_id_fields = ('rental', 'sale_order')
    readonly_fields = ('raw_response',)
    actions = ['sync_from_midtrans']

    @admin.action(description="Sinkronkan status dari Midtrans API")
    def sync_from_midtrans(self, request, queryset):
        from .services import sync_payment_status
        success_count = 0
        error_count = 0
        for payment in queryset:
            try:
                sync_payment_status(payment.order_id)
                success_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(request, f"Gagal sinkron {payment.order_id}: {e}", level='warning')
        if success_count > 0:
            self.message_user(request, f"Berhasil sinkronisasi {success_count} transaksi dari Midtrans.")


@admin.register(DepositHold)
class DepositHoldAdmin(admin.ModelAdmin):
    list_display = ('rental', 'amount', 'status', 'released_amount', 'deducted_amount', 'released_at')
    list_filter = ('status',)
    search_fields = ('rental__code',)
    raw_id_fields = ('rental',)


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('rental', 'owner', 'gross_rent', 'commission', 'net_amount', 'status', 'paid_at')
    list_filter = ('status',)
    search_fields = ('rental__code', 'owner__username')
    raw_id_fields = ('rental', 'owner')


from django.utils.html import format_html


from apps.core.admin_utils import generate_csv_export_action

export_ledger_csv = generate_csv_export_action(
    description="Ekspor entri buku besar terpilih ke CSV",
    filename_prefix="ledger_entries",
    columns=[
        ("ID", "id"),
        ("Kode Referensi", lambda obj: obj.rental.code if obj.rental else (obj.sale_order.code if obj.sale_order else "-")),
        ("Jenis Entri", "kind"),
        ("Jumlah (Rp)", "amount"),
        ("Catatan", "note"),
        ("Waktu Dibuat", "created_at"),
    ]
)

export_wallet_csv = generate_csv_export_action(
    description="Ekspor mutasi dompet terpilih ke CSV",
    filename_prefix="wallet_transactions",
    columns=[
        ("ID", "id"),
        ("Pengguna", lambda obj: obj.user.username if obj.user else "-"),
        ("Jenis Mutasi", "kind"),
        ("Jumlah (Rp)", "amount"),
        ("Kode Referensi", lambda obj: obj.rental.code if obj.rental else (obj.sale_order.code if obj.sale_order else "-")),
        ("Sumber", "source"),
        ("Catatan", "note"),
        ("Waktu Dibuat", "created_at"),
    ]
)

export_withdrawal_csv = generate_csv_export_action(
    description="Ekspor permintaan penarikan terpilih ke CSV (Rekening Tersamar)",
    filename_prefix="withdrawal_requests",
    columns=[
        ("ID", "id"),
        ("Pengguna", lambda obj: obj.user.username if obj.user else "-"),
        ("Jumlah (Rp)", "amount"),
        ("Metode", "method"),
        ("Nomor Rekening (Masked)", "masked_account_number"),
        ("Atas Nama", "account_name"),
        ("Status", "status"),
        ("Referensi Transfer", "transfer_reference"),
        ("Catatan Admin", "admin_note"),
        ("Waktu Pengajuan", "requested_at"),
        ("Waktu Diproses", "processed_at"),
    ]
)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        'reference_code', 'kind', 'display_amount', 'total_masuk_parent',
        'total_keluar_parent', 'status_invarian', 'note', 'created_at'
    )
    list_filter = ('kind', 'created_at')
    search_fields = ('rental__code', 'sale_order__code', 'note')
    raw_id_fields = ('rental', 'sale_order')
    actions = [export_ledger_csv]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def reference_code(self, obj):
        if obj.rental:
            return f"Sewa {obj.rental.code}"
        if obj.sale_order:
            return f"Jual {obj.sale_order.code}"
        return "-"
    reference_code.short_description = "Referensi"

    def display_amount(self, obj):
        return f"Rp{obj.amount:,}"
    display_amount.short_description = "Jumlah"

    def total_masuk_parent(self, obj):
        parent = obj.rental or obj.sale_order
        if parent:
            total = sum(
                parent.ledger_entries.filter(kind__startswith='masuk_').values_list('amount', flat=True)
            )
            return f"Rp{total:,}"
        return "-"
    total_masuk_parent.short_description = "Total Masuk"

    def total_keluar_parent(self, obj):
        parent = obj.rental or obj.sale_order
        if parent:
            total = sum(
                parent.ledger_entries.filter(kind__startswith='keluar_').values_list('amount', flat=True)
            )
            return f"Rp{total:,}"
        return "-"
    total_keluar_parent.short_description = "Total Keluar"

    def status_invarian(self, obj):
        parent = obj.rental or obj.sale_order
        if not parent:
            return "-"
        total_masuk = sum(
            parent.ledger_entries.filter(kind__startswith='masuk_').values_list('amount', flat=True)
        )
        total_keluar = sum(
            parent.ledger_entries.filter(kind__startswith='keluar_').values_list('amount', flat=True)
        )
        if total_masuk == total_keluar and total_masuk > 0:
            return format_html(
                '<span style="background-color: #DDF1E8; color: #0A5C43; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 11px;">'
                'Seimbang'
                '</span>'
            )
        elif total_masuk > total_keluar:
            return format_html(
                '<span style="background-color: #FFF0D1; color: #9A5B00; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 11px;">'
                'Escrow Ditahan'
                '</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #FDE7E4; color: #B42318; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 11px;">'
                'Tidak Seimbang'
                '</span>'
            )
    status_invarian.short_description = "Invarian Buku Besar"


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'kind', 'amount', 'rental', 'sale_order', 'source', 'created_at', 'note')
    list_filter = ('kind', 'source', 'created_at')
    search_fields = ('user__username', 'rental__code', 'sale_order__code', 'note')
    raw_id_fields = ('user', 'rental', 'sale_order')
    readonly_fields = ('user', 'rental', 'sale_order', 'kind', 'amount', 'source', 'created_at', 'note')
    actions = [export_wallet_csv]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'amount', 'method', 'masked_account_number',
        'account_name', 'status', 'requested_at', 'processed_by', 'processed_at'
    )
    list_filter = ('status', 'method', 'requested_at')
    search_fields = ('user__username', 'account_name', 'transfer_reference')
    raw_id_fields = ('user', 'processed_by')
    readonly_fields = (
        'user', 'amount', 'method', 'masked_account_number',
        'account_name', 'account_number', 'requested_at', 'processed_at'
    )
    actions = [export_withdrawal_csv]

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.user_id == request.user.id:
                from django.contrib import messages
                self.message_user(request, "Staf dilarang memproses penarikan dananya sendiri demi kepatuhan pemisahan tugas (segregation of duties).", level=messages.ERROR)
                return
            from apps.payments.services import process_withdrawal
            try:
                process_withdrawal(
                    withdrawal=obj,
                    new_status=obj.status,
                    admin_user=request.user,
                    transfer_reference=obj.transfer_reference,
                    admin_note=obj.admin_note
                )
            except ValueError as e:
                from django.contrib import messages
                self.message_user(request, str(e), level=messages.ERROR)
        else:
            super().save_model(request, obj, form, change)


@admin.register(WithdrawalAccountAccessLog)
class WithdrawalAccountAccessLogAdmin(admin.ModelAdmin):
    list_display = ('withdrawal', 'accessed_by', 'accessed_at', 'ip_address', 'reason')
    list_filter = ('accessed_at',)
    search_fields = ('withdrawal__id', 'accessed_by__username', 'ip_address', 'reason')
    raw_id_fields = ('withdrawal', 'accessed_by')
    readonly_fields = ('withdrawal', 'accessed_by', 'accessed_at', 'ip_address', 'reason')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ExtraCharge)
class ExtraChargeAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'rental', 'renter', 'owner', 'charge_type',
        'amount', 'status', 'settled_by', 'paid_at', 'created_at'
    )
    list_filter = ('charge_type', 'status', 'created_at')
    search_fields = ('rental__code', 'renter__username', 'owner__username', 'reason', 'settled_by')
    raw_id_fields = ('rental', 'renter', 'owner', 'payment')
    actions = ['mark_as_paid_manual']

    @admin.action(description="Tandai lunas manual (kreditkan ke saldo dompet pemilik)")
    def mark_as_paid_manual(self, request, queryset):
        from .services import settle_extra_charge
        success = 0
        for charge in queryset.filter(status=ExtraCharge.Status.TERUTANG):
            ref = f"Pelunasan manual oleh admin {request.user.username} pada {timezone.now().strftime('%d/%m/%Y %H:%M')}"
            settle_extra_charge(charge, reference=ref, reason="Persetujuan/pembayaran manual diverifikasi staf admin")
            success += 1
        if success > 0:
            self.message_user(request, f"Berhasil menandai lunas {success} tagihan tambahan dan mengkredit saldo pemilik.")


