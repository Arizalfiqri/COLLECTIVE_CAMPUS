from django.urls import path
from . import views

app_name = 'trust'

urlpatterns = [
    path('admin/model-skor/', views.admin_model_score_view, name='admin_model_score'),
    path('admin/model-skor/simulasi/', views.trust_score_simulation_htmx_view, name='simulation_htmx'),
    path('skor-kepercayaan/', views.public_trust_score_redirect_view, name='public_trust_score'),
    path('admin/ringkasan/', views.admin_summary_view, name='admin_summary'),
]
