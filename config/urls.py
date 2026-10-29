from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from apps.core.views import (
    home, handler404, handler500, handler403,
    admin_broadcast_announcement_view,
    admin_rental_chart_htmx,
    admin_recent_transactions_htmx,
)

admin.site.site_header = f"{getattr(settings, 'SITE_SHORT_NAME', 'Collective')} Admin"
admin.site.site_title = f"{getattr(settings, 'SITE_SHORT_NAME', 'Collective')} Admin"
admin.site.index_title = "Pusat Operasional Platform"


urlpatterns = [
    path('admin/pengumuman/', admin_broadcast_announcement_view, name='admin_broadcast_announcement'),
    path('admin/htmx/rental-chart/', admin_rental_chart_htmx, name='admin_rental_chart_root'),
    path('admin/htmx/recent-transactions/', admin_recent_transactions_htmx, name='admin_recent_transactions_root'),
    path('', include('apps.trust.urls', namespace='trust')),
    path('', include('apps.verification.urls')),
    path('', include('apps.payments.urls', namespace='payments')),
    path(getattr(settings, 'ADMIN_URL', 'admin/'), admin.site.urls),
    path('', home, name='home'),
    path('', include('apps.core.urls', namespace='core')),
    path('', include('apps.accounts.urls')),
    path('', include('apps.catalog.urls')),
    path('sewa/', include('apps.rentals.urls', namespace='rentals')),
    path('pesan/', include('apps.chat.urls', namespace='chat')),
    path('', include('apps.sales.urls', namespace='sales')),
]

# Layani berkas media publik (foto barang dsb) saat DEBUG atau jika SERVE_MEDIA_LOCAL aktif (misal waitress lokal).
# CATATAN PRODUKSI: Pada hosting publik sesungguhnya (Nginx/Caddy/S3), berkas /media/ dilayani langsung oleh web server / object storage.
# Berkas privat (KTM dsb di PRIVATE_MEDIA_ROOT) TIDAK PERNAH memiliki pola URL publik dan tidak boleh dilayani publik.
if settings.DEBUG or getattr(settings, 'SERVE_MEDIA_LOCAL', True):
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

handler404 = 'apps.core.views.handler404'
handler500 = 'apps.core.views.handler500'
handler403 = 'apps.core.views.handler403'

