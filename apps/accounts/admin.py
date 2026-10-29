from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from .models import User, StudentProfile, Campus, MeetingPoint, BlacklistedNim, SuspensionRecord


from django.utils.html import format_html


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    verbose_name_plural = 'Profil Mahasiswa'


class SuspensionRecordInline(admin.TabularInline):
    model = SuspensionRecord
    fk_name = 'user'
    extra = 0
    readonly_fields = ('started_at', 'created_at')
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (StudentProfileInline, SuspensionRecordInline)
    list_display = ('username', 'email', 'full_name', 'status_email', 'status_verifikasi', 'status_suspensi', 'status_staf')
    list_filter = ('is_email_verified', 'is_verified_student', 'is_suspended', 'is_staff', 'is_active')
    actions = ['aktivasi_email_manual', 'bekukan_pengguna', 'pulihkan_pengguna']

    def status_email(self, obj):
        if obj.is_email_verified:
            return format_html('<span style="background:#DDF1E8; color:#0A5C43; padding:2px 8px; border-radius:10px; font-weight:600; font-size:11px;">Terverifikasi</span>')
        return format_html('<span style="background:#FDE7E4; color:#B42318; padding:2px 8px; border-radius:10px; font-weight:600; font-size:11px;">Belum</span>')
    status_email.short_description = "Status email"
    status_email.admin_order_field = 'is_email_verified'

    def status_verifikasi(self, obj):
        if obj.is_verified_student:
            return format_html('<span style="background:#DDF1E8; color:#0A5C43; padding:2px 8px; border-radius:10px; font-weight:600; font-size:11px;">Terverifikasi</span>')
        return format_html('<span style="background:#F0EBDD; color:#566074; padding:2px 8px; border-radius:10px; font-weight:600; font-size:11px;">Belum</span>')
    status_verifikasi.short_description = "Verifikasi"
    status_verifikasi.admin_order_field = 'is_verified_student'

    def status_suspensi(self, obj):
        if obj.is_suspended:
            return format_html('<span style="background:#FDE7E4; color:#B42318; padding:2px 8px; border-radius:10px; font-weight:600; font-size:11px;">Dibekukan</span>')
        return format_html('<span style="color:#0A5C43; font-weight:600; font-size:11px;">Aktif</span>')
    status_suspensi.short_description = "Status akun"
    status_suspensi.admin_order_field = 'is_suspended'

    def status_staf(self, obj):
        if obj.is_staff:
            return format_html('<span style="background:#E6ECFB; color:#1F45C4; padding:2px 8px; border-radius:10px; font-weight:600; font-size:11px;">Staf</span>')
        return format_html('<span style="color:#566074; font-size:11px;">Biasa</span>')
    status_staf.short_description = "Peran"
    status_staf.admin_order_field = 'is_staff'

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informasi Tambahan', {
            'fields': ('full_name', 'phone_whatsapp', 'avatar', 'is_email_verified', 'is_verified_student', 'is_suspended')
        }),
    )

    @admin.action(description="Aktifkan / Verifikasi email pengguna terpilih")
    def aktivasi_email_manual(self, request, queryset):
        count = queryset.filter(is_email_verified=False).update(is_email_verified=True)
        self.message_user(request, f"{count} akun pengguna berhasil diverifikasi emailnya secara manual.", level=messages.SUCCESS)

    @admin.action(description="Bekukan pengguna terpilih dengan alasan wajib")
    def bekukan_pengguna(self, request, queryset):
        if request.POST.get('confirm') == 'yes':
            reason = request.POST.get('reason', '').strip()
            if not reason:
                self.message_user(request, "Alasan pembekuan pengguna wajib diisi!", level=messages.ERROR)
                from django.template.response import TemplateResponse
                return TemplateResponse(request, 'admin/accounts/user/suspend_intermediate.html', {
                    'users': queryset,
                    'title': 'Konfirmasi Pembekuan Pengguna',
                })
            from apps.core.models import Notification
            count = 0
            for user in queryset:
                user.is_suspended = True
                user.save(update_fields=['is_suspended'])
                SuspensionRecord.objects.create(
                    user=user,
                    reason=reason,
                    suspended_by=request.user,
                    is_permanent=True
                )
                Notification.notify(
                    user=user,
                    title="Akun Anda Dibekukan",
                    message=f"Akun Anda telah dibekukan oleh staf/moderator platform. Alasan: {reason}"
                )
                count += 1
            self.message_user(request, f"{count} akun pengguna berhasil dibekukan dan riwayat telah dicatat.", level=messages.SUCCESS)
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(request.get_full_path())

        from django.template.response import TemplateResponse
        return TemplateResponse(request, 'admin/accounts/user/suspend_intermediate.html', {
            'users': queryset,
            'title': 'Konfirmasi Pembekuan Pengguna',
        })

    @admin.action(description="Pulihkan pengguna terpilih (batalkan pembekuan)")
    def pulihkan_pengguna(self, request, queryset):
        from apps.core.models import Notification
        count = 0
        now = timezone.now()
        for user in queryset:
            user.is_suspended = False
            user.save(update_fields=['is_suspended'])
            user.suspension_records.filter(ended_at__isnull=True).update(ended_at=now)
            Notification.notify(
                user=user,
                title="Akun Anda Telah Dipulihkan",
                message="Akun Anda telah dipulihkan oleh administrator. Anda dapat kembali menggunakan fitur platform KampusRent."
            )
            count += 1
        self.message_user(request, f"{count} akun pengguna berhasil dipulihkan dari pembekuan.", level=messages.SUCCESS)


@admin.register(SuspensionRecord)
class SuspensionRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'reason', 'suspended_by', 'started_at', 'ended_at', 'is_permanent')
    list_filter = ('is_permanent', 'started_at')
    search_fields = ('user__username', 'user__full_name', 'reason')
    raw_id_fields = ('user', 'suspended_by')


class MeetingPointInline(admin.TabularInline):
    model = MeetingPoint
    extra = 1


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'city', 'is_active', 'created_at')
    list_filter = ('is_active', 'city')
    search_fields = ('name', 'short_name', 'city')
    inlines = [MeetingPointInline]
    actions = ['aktifkan_kampus', 'nonaktifkan_kampus', 'merge_campuses']

    @admin.action(description="Aktifkan kampus terpilih")
    def aktifkan_kampus(self, request, queryset):
        count = queryset.update(is_active=True)
        if request:
            self.message_user(request, f"{count} kampus berhasil diaktifkan.", level=messages.SUCCESS)

    @admin.action(description="Nonaktifkan kampus terpilih")
    def nonaktifkan_kampus(self, request, queryset):
        count = queryset.update(is_active=False)
        if request:
            self.message_user(request, f"{count} kampus berhasil dinonaktifkan.", level=messages.SUCCESS)

    @admin.action(description="Gabungkan kampus terpilih (pindahkan semua profil dan barang)")
    def merge_campuses(self, request, queryset):
        if queryset.count() < 2:
            if request:
                self.message_user(
                    request,
                    "Pilih minimal 2 kampus untuk digabungkan.",
                    level=messages.WARNING
                )
            return


        target = queryset.order_by('id').first()
        sources = queryset.exclude(id=target.id)

        total_profiles = 0
        total_mps = 0
        source_names = []

        for src in sources:
            source_names.append(src.name)
            # Pindahkan profil mahasiswa beserta barang terkait
            p_count = StudentProfile.objects.filter(campus=src).update(campus=target)
            total_profiles += p_count
            # Pindahkan titik temu
            mp_count = MeetingPoint.objects.filter(campus=src).update(campus=target)
            total_mps += mp_count
            src.delete()

        self.message_user(
            request,
            f"Berhasil menggabungkan kampus {', '.join(source_names)} ke '{target.name}'. "
            f"{total_profiles} profil mahasiswa dan {total_mps} titik temu telah dipindahkan."
        )


@admin.register(MeetingPoint)
class MeetingPointAdmin(admin.ModelAdmin):
    list_display = ('name', 'campus', 'is_public', 'created_at')
    list_filter = ('is_public', 'campus')
    search_fields = ('name', 'campus__name')


@admin.register(BlacklistedNim)
class BlacklistedNimAdmin(admin.ModelAdmin):
    list_display = ('nim', 'reason', 'blacklisted_at')
    search_fields = ('nim', 'reason')


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('nim', 'user', 'campus', 'major', 'entry_year', 'student_status')
    search_fields = ('nim', 'user__username', 'user__full_name', 'campus__name')
    list_filter = ('campus', 'student_status', 'entry_year')
