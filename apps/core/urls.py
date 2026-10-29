from django.urls import path
from .views import (
    home,
    notifications_view,
    notification_panel_view,
    notification_click_view,
    mark_all_notifications_read_htmx,
    rental_calculator_view,
    tentang_view,
    bantuan_view,
    syarat_ketentuan_view,
    kebijakan_privasi_view,
    panduan_komunitas_view,
    kontak_view,
    robots_txt_view,
    sitemap_xml_view,
    preview_card_fallback_view,
    dev_login_as_view,
    handler404,
    admin_broadcast_announcement_view,
    admin_rental_chart_htmx,
    admin_recent_transactions_htmx,
)

app_name = 'core'

urlpatterns = [
    path('admin/pengumuman/', admin_broadcast_announcement_view, name='admin_broadcast_announcement'),
    path('admin/htmx/rental-chart/', admin_rental_chart_htmx, name='admin_rental_chart'),
    path('admin/htmx/recent-transactions/', admin_recent_transactions_htmx, name='admin_recent_transactions'),
    path('tentang/', tentang_view, name='tentang'),
    path('bantuan/', bantuan_view, name='bantuan'),
    path('syarat-ketentuan/', syarat_ketentuan_view, name='syarat_ketentuan'),
    path('kebijakan-privasi/', kebijakan_privasi_view, name='kebijakan_privasi'),
    path('panduan-komunitas/', panduan_komunitas_view, name='panduan_komunitas'),
    path('kontak/', kontak_view, name='kontak'),
    path('robots.txt', robots_txt_view, name='robots_txt'),
    path('sitemap.xml', sitemap_xml_view, name='sitemap_xml'),
    path('kalkulator-sewa/', rental_calculator_view, name='rental_calculator'),
    path('dev/preview-card-fallback/', preview_card_fallback_view, name='dev_card_fallback'),
    path('dev/preview-404/', handler404, name='dev_preview_404'),
    path('dev/login-as/<str:username>/', dev_login_as_view, name='dev_login_as'),
    path('notifikasi/', notifications_view, name='notifications'),
    path('notifikasi/panel/', notification_panel_view, name='notification_panel'),
    path('notifikasi/tandai-semua-dibaca/', mark_all_notifications_read_htmx, name='mark_all_read_htmx'),
    path('notifikasi/tandai-semua-dibaca/action/', mark_all_notifications_read_htmx, name='mark_all_read'),
    path('notifikasi/<int:pk>/', notification_click_view, name='notification_click'),
]

