from django.urls import path
from apps.verification import views

app_name = 'verification'

urlpatterns = [
    path('verifikasi-ktm/', views.ktm_stepper_view, name='ktm_stepper'),
    path('admin/ktm/<int:pk>/gambar/', views.admin_ktm_image_view, name='admin_ktm_image'),
]
