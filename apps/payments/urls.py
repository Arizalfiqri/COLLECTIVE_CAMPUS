from django.urls import path
from .views import (
    rental_pay_view,
    rental_sync_payment_view,
    sale_order_pay_view,
    sale_order_sync_payment_view,
    midtrans_notification_webhook,
    wallet_view,
    withdrawal_request_view,
    admin_reconciliation_view,
    admin_withdrawals_view,
    admin_withdrawal_reveal_account_view,
    admin_withdrawal_process_view,
)

app_name = 'payments'

urlpatterns = [
    # Dompet Pengguna & Penarikan Dana (Fase 7C)
    path('dompet/', wallet_view, name='wallet'),
    path('dompet/tarik/', withdrawal_request_view, name='withdrawal_request'),

    # Admin Penarikan & Rekonsiliasi (Fase 7C)
    path('admin/rekonsiliasi/', admin_reconciliation_view, name='admin_reconciliation'),
    path('admin/penarikan/', admin_withdrawals_view, name='admin_withdrawals'),
    path('admin/penarikan/<int:pk>/lihat-rekening/', admin_withdrawal_reveal_account_view, name='admin_withdrawal_reveal_account'),
    path('admin/penarikan/<int:pk>/proses/', admin_withdrawal_process_view, name='admin_withdrawal_process'),

    # Transaksi Sewa & Midtrans Webhook
    path('midtrans/notifikasi/', midtrans_notification_webhook, name='webhook_notification'),
    path('midtrans/sewa/<str:code>/bayar/', rental_pay_view, name='rental_pay'),
    path('midtrans/sewa/<str:code>/sinkron-pembayaran/', rental_sync_payment_view, name='rental_sync_payment'),

    # Transaksi Jual Beli Midtrans (Fase 8B)
    path('midtrans/pesanan/<str:code>/bayar/', sale_order_pay_view, name='sale_order_pay'),
    path('midtrans/pesanan/<str:code>/sinkron-pembayaran/', sale_order_sync_payment_view, name='sale_order_sync_payment'),
]

