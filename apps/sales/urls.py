from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('jual/baru/', views.sale_item_create_view, name='item_create'),
    path('jual/saya/', views.my_sale_items_view, name='my_items'),
    path('jual/<slug:slug>/ubah/', views.sale_item_edit_view, name='item_edit'),
    path('jual/<slug:slug>/toggle-status/', views.sale_item_toggle_status_view, name='item_toggle_status'),
    path('jual/<slug:slug>/perpanjang/', views.sale_item_extend_view, name='item_extend'),
    path('jual-beli/', views.sale_item_list_view, name='item_list'),
    path('jual-beli/hasil/', views.sale_item_results_partial, name='item_results_partial'),
    path('jual-beli/<slug:slug>/', views.sale_item_detail_view, name='item_detail'),
    path('jual-beli/<slug:slug>/lapor/', views.sale_item_report_view, name='item_report'),
    path('jual-beli/<slug:slug>/tawar/', views.sale_item_offer_view, name='item_offer'),
    path('jual-beli/tawaran/<int:offer_id>/terima/', views.sale_offer_accept_view, name='offer_accept'),
    path('jual-beli/tawaran/<int:offer_id>/tolak/', views.sale_offer_reject_view, name='offer_reject'),
    path('jual-beli/<slug:slug>/beli/', views.buy_sale_item_view, name='item_buy'),
    path('pesanan/<str:code>/', views.sale_order_detail_view, name='order_detail'),
    path('pesanan/<str:code>/perjanjian/', views.sale_agreement_print_view, name='order_agreement'),
    path('pesanan/<str:code>/jadwal-temu/', views.sale_order_set_meetup_view, name='order_set_meetup'),
    path('pesanan/<str:code>/serah-terima/', views.sale_order_handover_view, name='order_handover'),
    path('pesanan/<str:code>/konfirmasi/', views.sale_order_confirm_received_view, name='order_confirm_received'),
    path('pesanan/<str:code>/sengketa/', views.sale_order_dispute_view, name='order_dispute'),
    path('pesanan/<str:code>/foto-sengketa/<int:idx>/', views.sale_order_dispute_photo_view, name='order_dispute_photo'),
    path('pesanan/<str:code>/ulasan/', views.sale_order_review_view, name='order_review'),
    path('pesanan/<str:code>/batal/', views.sale_order_cancel_view, name='order_cancel'),
]
