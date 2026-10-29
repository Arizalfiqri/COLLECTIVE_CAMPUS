from django.urls import path
from .views import (
    rental_request_view,
    rental_detail_view,
    rental_approve_view,
    rental_reject_view,
    rental_cancel_view,
    rental_photo_serve_view,
    handover_schedule_propose_view,
    handover_schedule_confirm_view,
    handover_photo_consent_view,
    handover_ktm_confirm_view,
    condition_photo_upload_view,
    rental_handover_confirm_view,
    rental_return_request_view,
    rental_return_confirm_view,
    rental_dispute_agree_view,
    rental_review_submit_view,
    rental_agreement_view,
)
from apps.payments.views import (
    rental_pay_view,
    rental_sync_payment_view,
    rental_payment_finish_view,
)

app_name = 'rentals'

urlpatterns = [
    path('ajukan/<slug:slug>/', rental_request_view, name='rental_request'),
    path('<str:code>/', rental_detail_view, name='rental_detail'),
    path('<str:code>/perjanjian/', rental_agreement_view, name='rental_agreement'),
    path('<str:code>/setujui/', rental_approve_view, name='rental_approve'),
    path('<str:code>/tolak/', rental_reject_view, name='rental_reject'),
    path('<str:code>/batal/', rental_cancel_view, name='rental_cancel'),
    path('<str:code>/bayar/', rental_pay_view, name='rental_pay'),
    path('<str:code>/sinkron-pembayaran/', rental_sync_payment_view, name='rental_sync_payment'),
    path('<str:code>/selesai-bayar/', rental_payment_finish_view, name='rental_payment_finish'),
    # Phase 5B patterns
    path('<str:code>/foto/<int:photo_id>/', rental_photo_serve_view, name='rental_photo_serve'),
    path('<str:code>/jadwal/usul/', handover_schedule_propose_view, name='handover_schedule_propose'),
    path('<str:code>/jadwal/konfirmasi/', handover_schedule_confirm_view, name='handover_schedule_confirm'),
    path('<str:code>/persetujuan-foto/', handover_photo_consent_view, name='handover_photo_consent'),
    path('<str:code>/konfirmasi-ktm/', handover_ktm_confirm_view, name='handover_ktm_confirm'),
    path('<str:code>/foto/unggah/<str:phase>/', condition_photo_upload_view, name='condition_photo_upload'),
    path('<str:code>/serah-terima/', rental_handover_confirm_view, name='rental_handover_confirm'),
    path('<str:code>/kembalikan/', rental_return_request_view, name='rental_return_request'),
    path('<str:code>/konfirmasi-kembali/', rental_return_confirm_view, name='rental_return_confirm'),
    path('<str:code>/setujui-potongan/', rental_dispute_agree_view, name='rental_dispute_agree'),
    path('<str:code>/ulasan/', rental_review_submit_view, name='rental_review_submit'),
]

