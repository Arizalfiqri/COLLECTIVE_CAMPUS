from functools import wraps
from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect
from django.urls import reverse


def verified_student_required(view_func):
    """
    Decorator untuk view yang mewajibkan status mahasiswa terverifikasi KTM.
    Jika belum login: diarahkan ke halaman login.
    Jika belum terverifikasi: pesan peringatan spesifik dan diarahkan ke /verifikasi-ktm/.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Silakan masuk terlebih dahulu.")
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        
        if not request.user.is_verified_student:
            messages.warning(request, "Verifikasi KTM dulu untuk memasang barang atau menyewa.")
            return redirect('verification:ktm_stepper')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


class VerifiedStudentRequiredMixin(AccessMixin):
    """Mixin untuk Class-Based View yang mewajibkan status mahasiswa terverifikasi."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Silakan masuk terlebih dahulu.")
            return redirect(f"{reverse('accounts:login')}?next={request.path}")

        if not request.user.is_verified_student:
            messages.warning(request, "Verifikasi KTM dulu untuk memasang barang atau menyewa.")
            return redirect('verification:ktm_stepper')

        return super().dispatch(request, *args, **kwargs)
