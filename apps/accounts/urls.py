from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from apps.accounts import views

app_name = 'accounts'

urlpatterns = [
    # Autentikasi dasar
    path('daftar/', views.register_view, name='register'),
    path('masuk/', views.login_view, name='login'),
    path('keluar/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profil/<str:username>/', views.user_profile_view, name='user_profile'),

    # Verifikasi email akun & kampus (.ac.id)
    path('verifikasi-email/<str:uidb64>/<str:token>/', views.verify_email_view, name='verify_email'),
    path('kirim-ulang-verifikasi/', views.resend_verification_email_view, name='resend_verification'),
    path('verifikasi-email-kampus/<str:uidb64>/<str:token>/', views.verify_campus_email_view, name='verify_campus_email'),

    # Alur Lupa & Atur Ulang Kata Sandi
    path(
        'lupa-kata-sandi/',
        views.RateLimitedPasswordResetView.as_view(
            success_url=reverse_lazy('accounts:password_reset_done'),
        ),
        name='password_reset'
    ),
    path(
        'lupa-kata-sandi/terkirim/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html'
        ),
        name='password_reset_done'
    ),
    path(
        'atur-ulang-kata-sandi/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete'),
        ),
        name='password_reset_confirm'
    ),
    path(
        'atur-ulang-kata-sandi/selesai/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),
]

