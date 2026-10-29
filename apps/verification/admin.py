from django.contrib import admin, messages
from django.conf import settings
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse

from apps.core.models import Notification
from apps.verification.models import KtmVerification


@admin.register(KtmVerification)
class KtmVerificationAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'user_nim', 'user_campus',
        'skor_display', 'rekomendasi_display', 'status_badge',
        'diajukan_display'
    )
    list_filter = ('status', 'recommendation', 'nim_match', 'campus_match')
    search_fields = ('user__username', 'user__full_name', 'ocr_nim', 'ocr_name', 'user__student_profile__nim', 'user__student_profile__campus_email')
    readonly_fields = (
        'user', 'sinyal_email_kampus', 'tautan_gambar', 'ocr_text', 'ocr_nim', 'ocr_name', 'ocr_campus',
        'nim_match', 'name_similarity', 'campus_match', 'quality_score', 'match_score',
        'recommendation', 'image_deleted_at', 'created_at', 'updated_at'
    )
    raw_id_fields = ('user', 'reviewed_by')
    list_per_page = 20
    actions = ['setujui_ktm_action', 'tolak_ktm_action']

    fieldsets = (
        ("Identitas Pengguna & Status", {
            'fields': ('user', 'sinyal_email_kampus', 'status', 'tautan_gambar', 'admin_note')
        }),
        ("Peninjau Admin", {
            'fields': ('reviewed_by', 'reviewed_at', 'image_deleted_at')
        }),
        ("Hasil Ekstraksi OCR", {
            'fields': ('ocr_nim', 'ocr_name', 'ocr_campus', 'ocr_text')
        }),
        ("Skor & Rekomendasi Sistem", {
            'fields': (
                'nim_match', 'name_similarity', 'campus_match',
                'quality_score', 'match_score', 'recommendation'
            )
        }),
        ("Metadata", {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_nim(self, obj):
        profile = getattr(obj.user, 'student_profile', None)
        return profile.nim if profile else '-'
    user_nim.short_description = "NIM"

    def user_campus(self, obj):
        profile = getattr(obj.user, 'student_profile', None)
        return profile.campus_name if profile else '-'
    user_campus.short_description = "Kampus"

    def skor_display(self, obj):
        score = obj.match_score or 0
        if score >= 75:
            color = "#0A5C43"
            bg = "#DDF1E8"
        elif score >= 50:
            color = "#9A5B00"
            bg = "#FFF0D1"
        else:
            color = "#B42318"
            bg = "#FDE7E4"
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 8px; border-radius:6px; font-weight:700; font-size:12px; font-variant-numeric:tabular-nums; display:inline-block;">{}%</span>',
            bg, color, score
        )
    skor_display.short_description = "Skor"
    skor_display.admin_order_field = 'match_score'

    def rekomendasi_display(self, obj):
        colors = {
            'setuju': ('#DDF1E8', '#0A5C43'),
            'tinjau': ('#FFF0D1', '#9A5B00'),
            'tolak': ('#FDE7E4', '#B42318'),
        }
        bg, text = colors.get(obj.recommendation, ('#F0EBDD', '#141B34'))
        label = (obj.get_recommendation_display() or '-').capitalize()
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 10px; border-radius:12px; font-weight:600; font-size:11px; display:inline-block;">{}</span>',
            bg, text, label
        )
    rekomendasi_display.short_description = "Rekomendasi"

    def status_badge(self, obj):
        colors = {
            'disetujui': ('#DDF1E8', '#0A5C43'),
            'menunggu': ('#FFF0D1', '#9A5B00'),
            'perlu_tinjauan': ('#FFF0D1', '#9A5B00'),
            'ditolak': ('#FDE7E4', '#B42318'),
        }
        bg, text = colors.get(obj.status, ('#F0EBDD', '#141B34'))
        label = (obj.get_status_display() or '-').capitalize()
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 10px; border-radius:12px; font-weight:600; font-size:11px; display:inline-block;">{}</span>',
            bg, text, label
        )
    status_badge.short_description = "Status"

    def diajukan_display(self, obj):
        if not obj.created_at:
            return '-'
        from django.utils import dateformat
        return dateformat.format(timezone.localtime(obj.created_at), 'd M Y, H:i')
    diajukan_display.short_description = "Diajukan"
    diajukan_display.admin_order_field = 'created_at'

    def sinyal_email_kampus(self, obj):
        profile = getattr(obj.user, 'student_profile', None)
        if profile and profile.is_campus_email_verified and profile.campus_email.endswith('.ac.id'):
            return format_html(
                '<span style="background:#DDF1E8; color:#0A5C43; padding:2px 8px; border-radius:4px; font-weight:600; font-size:11px;" title="Email kampus .ac.id diverifikasi via link">'
                '✓ Terverifikasi (.ac.id)</span><br><small style="color:#566074;">{}</small>',
                profile.campus_email
            )
        elif profile and profile.campus_email:
            return format_html(
                '<span style="background:#FFF0D1; color:#9A5B00; padding:2px 8px; border-radius:4px; font-size:11px;" title="Belum verifikasi tautan">'
                'Belum diverifikasi</span><br><small style="color:#566074;">{}</small>',
                profile.campus_email
            )
        return format_html('<span style="color:#8A92A6; font-size:11px;">Tidak ada</span>')
    sinyal_email_kampus.short_description = "Sinyal Email Kampus"

    def tautan_gambar(self, obj):
        if obj.image_deleted_at or not obj.has_image_file:
            return format_html('<span style="color:#566074; font-style:italic;">Dihapus (Privasi)</span>')
        url = reverse('verification:admin_ktm_image', args=[obj.pk])
        return format_html(
            '<a href="{}" target="_blank" style="color:#1F45C4; font-weight:600; text-decoration:underline;">Buka Foto KTM (Privat)</a>',
            url
        )
    tautan_gambar.short_description = "Berkas KTM"

    @admin.action(description="Setujui verifikasi KTM terpilih")
    def setujui_ktm_action(self, request, queryset):
        count = 0
        delete_after = getattr(settings, 'KTM_DELETE_AFTER_DECISION', True)
        now = timezone.now()

        for ktm in queryset:
            ktm.status = KtmVerification.Status.DISETUJUI
            ktm.reviewed_by = request.user
            ktm.reviewed_at = now
            if not ktm.admin_note:
                ktm.admin_note = "Disetujui oleh admin."
            
            # Verifikasi user
            ktm.user.is_verified_student = True
            ktm.user.save(update_fields=['is_verified_student'])

            # Hapus file gambar jika pengaturan privasi aktif
            if delete_after:
                ktm.delete_image_file()

            ktm.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_note'])

            # Notifikasi pengguna
            Notification.objects.create(
                user=ktm.user,
                message="Selamat! Verifikasi KTM Anda telah disetujui admin. Anda sekarang dapat memasang dan menyewa barang.",
                url="/dashboard/"
            )
            count += 1

        self.message_user(
            request,
            f"{count} verifikasi KTM berhasil disetujui. Akun mahasiswa telah diverifikasi.",
            level=messages.SUCCESS
        )

    @admin.action(description="Tolak verifikasi KTM terpilih")
    def tolak_ktm_action(self, request, queryset):
        count = 0
        now = timezone.now()

        for ktm in queryset:
            ktm.status = KtmVerification.Status.DITOLAK
            ktm.reviewed_by = request.user
            ktm.reviewed_at = now
            if not ktm.admin_note:
                ktm.admin_note = "Ditolak oleh admin. Foto tidak jelas atau data tidak sesuai."

            ktm.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_note'])

            # Notifikasi pengguna
            Notification.objects.create(
                user=ktm.user,
                message="Verifikasi KTM Anda ditolak oleh admin. Silakan periksa kembali foto KTM dan data kemahasiswaan Anda.",
                url="/verifikasi-ktm/?step=3"
            )
            count += 1

        self.message_user(
            request,
            f"{count} verifikasi KTM ditolak.",
            level=messages.WARNING
        )
