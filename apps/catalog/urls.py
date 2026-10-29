from django.urls import path
from apps.catalog import views

app_name = 'catalog'

urlpatterns = [
    path('barang/', views.item_list_view, name='item_list'),
    path('barang/hasil/', views.item_list_partial_view, name='item_list_partial'),
    path('barang/baru/', views.item_create_view, name='item_create'),
    path('barang/saya/', views.my_items_view, name='my_items'),
    path('barang/<slug:slug>/', views.item_detail_view, name='item_detail'),
    path('barang/<slug:slug>/ubah/', views.item_update_view, name='item_update'),
    path('barang/<slug:slug>/toggle-status/', views.item_toggle_active_view, name='item_toggle_active'),
    path('barang/<slug:slug>/ringkasan/', views.item_price_summary_htmx_view, name='item_price_summary'),
]
