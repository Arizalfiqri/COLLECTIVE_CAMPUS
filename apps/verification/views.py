import os
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.models import Notification
from apps.verification.forms import KtmUploadForm
from apps.verification.models import KtmVerification
from ml.ktm_ocr import extract_ktm_data


@login_required(login_url='/masuk/')
def ktm_stepper_view(request):
    """
    Halaman verifikasi KTM dengan stepper 3 langkah sesuai design.md 5.8:
    1. Data Diri
    2. Unggah KTM (JPG/PNG maks 5 MB, validasi Pillow, simpan privat)
    3. Menunggu Tinjauan / Status & Hasil Pembacaan OCR
    """
    user = request.user
    profile = getattr(user, 'student_profile', None)
    latest_verification = KtmVerification.objects.filter(user=user).order_by('-created_at').first()

    # Tentukan langkah aktif (1, 2, atau 3)
    requested_step = request.GET.get('step')
    if requested_step in ['1', '2', '3']:
        current_step = int(requested_step)
    elif user.is_verified_student:
        current_step = 3
    elif latest_verification and latest_verification.status in [
        KtmVerification.Status.MENUNGGU,
        KtmVerification.Status.PERLU_TINJAUAN,
        KtmVerification.Status.DITOLAK,
        KtmVerification.Status.DISETUJUI,
    ]:
        current_step = 3
    else:
        current_step = 1

    form = KtmUploadForm()

    if request.method == 'POST':
        form = KtmUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data['ktm_image']
            
            # Buat nama berkas UUID yang aman
            extension = Path(uploaded_file.name).suffix.lower()
            if extension not in ['.jpg', '.jpeg', '.png']:
                extension = '.jpg'
            unique_filename = f"{uuid.uuid4().hex}{extension}"

            # Simpan berkas ke private_media/ktm/
            private_ktm_dir = settings.PRIVATE_MEDIA_ROOT / 'ktm'
            private_ktm_dir.mkdir(parents=True, exist_ok=True)
            saved_file_path = private_ktm_dir / unique_filename

            with open(saved_file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            # Jalankan pipeline OCR di ml/ktm_ocr.py
            target_nim = profile.nim if profile else ''
            target_name = user.full_name or user.username
            target_campus = profile.campus_name if profile else ''
            target_campus_keywords = profile.campus.ktm_keywords if (profile and profile.campus) else []
            nim_pattern = profile.campus.nim_pattern if (profile and profile.campus) else ''

            ocr_result = extract_ktm_data(
                saved_file_path,
                target_nim=target_nim,
                target_name=target_name,
                target_campus=target_campus,
                target_campus_keywords=target_campus_keywords,
                nim_pattern=nim_pattern
            )

            # Buat entri verifikasi baru
            verification = KtmVerification.objects.create(
                user=user,
                ktm_image=f"ktm/{unique_filename}",
                ocr_text=ocr_result.get('ocr_raw_text', ''),
                ocr_nim=ocr_result.get('extracted_nim', ''),
                ocr_name=ocr_result.get('extracted_name', ''),
                ocr_campus=ocr_result.get('extracted_campus', ''),
                nim_match=ocr_result.get('nim_match', False),
                name_similarity=ocr_result.get('name_similarity', 0),
                campus_match=ocr_result.get('campus_match', False),
                quality_score=ocr_result.get('quality_score', 0),
                match_score=ocr_result.get('match_score', 0),
                recommendation=ocr_result.get('recommendation', KtmVerification.Recommendation.TINJAU),
                status=ocr_result.get('status', KtmVerification.Status.MENUNGGU),
                admin_note=ocr_result.get('admin_note', '')
            )

            # Periksa auto-approve jika diaktifkan di konfigurasi
            auto_approve = getattr(settings, 'KTM_AUTO_APPROVE', False)
            if auto_approve and verification.recommendation == KtmVerification.Recommendation.SETUJU:
                verification.status = KtmVerification.Status.DISETUJUI
                verification.reviewed_at = timezone.now()
                verification.admin_note = "Disetujui otomatis oleh sistem berdasarkan skor OCR tinggi."
                verification.save(update_fields=['status', 'reviewed_at', 'admin_note'])

                user.is_verified_student = True
                user.save(update_fields=['is_verified_student'])

                # Hapus gambar jika KTM_DELETE_AFTER_DECISION=True
                if getattr(settings, 'KTM_DELETE_AFTER_DECISION', True):
                    verification.delete_image_file()

                Notification.objects.create(
                    user=user,
                    message="KTM Anda berhasil diverifikasi otomatis! Anda sekarang dapat memasang barang dan menyewa.",
                    url="/dashboard/"
                )
                messages.success(request, "Verifikasi KTM Anda telah berhasil dan disetujui otomatis oleh sistem!")
            else:
                messages.success(
                    request,
                    "Foto KTM berhasil diunggah! Sistem sedang memproses peninjauan."
                )

            return redirect('/verifikasi-ktm/?step=3')

    return render(request, 'verification/ktm_stepper.html', {
        'user': user,
        'profile': profile,
        'current_step': current_step,
        'latest_verification': latest_verification,
        'form': form,
    })


@staff_member_required(login_url='/admin/login/')
def admin_ktm_image_view(request, pk):
    """
    View privat khusus staf admin untuk melihat berkas foto KTM.
    - Dilindungi login staf
    - Disajikan dengan header Cache-Control: no-store
    - Mengembalikan 404 jika berkas telah dihapus demi privasi
    """
    ktm = get_object_or_404(KtmVerification, pk=pk)

    if not ktm.has_image_file:
        return HttpResponseNotFound(
            "Berkas foto KTM ini telah dihapus permanen demi menjaga privasi data "
            "setelah keputusan verifikasi diambil."
        )

    file_path = ktm.private_file_path
    if not file_path or not file_path.exists():
        return HttpResponseNotFound("Berkas fisik foto KTM tidak ditemukan di penyimpanan privat.")

    # Tentukan MIME type berdasarkan ekstensi
    extension = file_path.suffix.lower()
    content_type = 'image/png' if extension == '.png' else 'image/jpeg'

    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['Content-Disposition'] = f'inline; filename="ktm_private_{pk}{extension}"'
    return response
