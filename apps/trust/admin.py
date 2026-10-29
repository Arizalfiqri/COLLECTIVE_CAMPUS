from django.contrib import admin, messages
from django import forms
from django.utils import timezone
from .models import TrustScore, TrustTrainingExample, TrustModelVersion


class TrustScoreAdminForm(forms.ModelForm):
    class Meta:
        model = TrustScore
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        override_score = cleaned_data.get('override_score')
        override_note = cleaned_data.get('override_note', '').strip()

        if override_score is not None:
            if override_score < 0 or override_score > 100:
                self.add_error('override_score', "Skor override harus berada di antara 0 dan 100.")
            if not override_note:
                self.add_error('override_note', "Catatan wajib diisi jika skor override manual ditentukan.")

        return cleaned_data


@admin.register(TrustScore)
class TrustScoreAdmin(admin.ModelAdmin):
    form = TrustScoreAdminForm
    list_display = (
        'user', 'display_score', 'override_score', 'is_new_user',
        'risk_probability', 'model_version', 'computed_at'
    )
    list_filter = ('is_new_user', 'model_version')
    search_fields = ('user__username', 'user__full_name', 'user__email')
    raw_id_fields = ('user', 'override_by')
    readonly_fields = ('computed_at', 'created_at', 'updated_at', 'features', 'top_factors')
    actions = ['reset_override_action']

    fieldsets = (
        ("Pengguna & Skor", {
            'fields': ('user', 'score', 'risk_probability', 'is_new_user', 'model_version', 'computed_at')
        }),
        ("Intervensi / Override Manual Admin", {
            'fields': ('override_score', 'override_note', 'override_by', 'override_at'),
            'description': "Gunakan jika diperlukan penyesuaian khusus oleh admin. Catatan wajib diisi."
        }),
        ("Penjelasan & Fitur ML", {
            'fields': ('top_factors', 'features'),
            'classes': ('collapse',)
        }),
        ("Waktu Sistem", {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description="Skor Aktif")
    def display_score(self, obj):
        effective = obj.effective_score
        label = obj.get_label()
        if obj.override_score is not None:
            return f"{effective} (Override: {label})"
        return f"{effective} ({label})"

    def save_model(self, request, obj, form, change):
        if obj.override_score is not None:
            obj.override_by = request.user
            obj.override_at = timezone.now()
        else:
            obj.override_by = None
            obj.override_at = None
        super().save_model(request, obj, form, change)

    @admin.action(description="Hapus override manual (kembali ke skor sistem)")
    def reset_override_action(self, request, queryset):
        updated = queryset.update(
            override_score=None,
            override_note='',
            override_by=None,
            override_at=None
        )
        self.message_user(request, f"{updated} skor berhasil direset ke perhitungan otomatis.", messages.SUCCESS)


@admin.register(TrustTrainingExample)
class TrustTrainingExampleAdmin(admin.ModelAdmin):
    list_display = ('rental', 'user', 'source', 'label_display', 'risk_pct', 'model_version', 'created_at')
    list_filter = ('source', 'label_problem', 'model_version')
    search_fields = ('rental__code', 'user__username', 'user__full_name')
    ordering = ['-created_at']

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Label Masalah")
    def label_display(self, obj):
        if obj.label_problem == 1:
            return "Bermasalah (1)"
        elif obj.label_problem == 0:
            return "Normal (0)"
        return "Belum Dilabeli"

    @admin.display(description="Risiko")
    def risk_pct(self, obj):
        if obj.predicted_risk is not None:
            return f"{obj.predicted_risk * 100:.1f}%"
        return "-"


@admin.register(TrustModelVersion)
class TrustModelVersionAdmin(admin.ModelAdmin):
    list_display = ('version', 'is_active', 'n_real', 'n_synthetic', 'trained_at')
    list_filter = ('is_active',)
    search_fields = ('version', 'notes')
    ordering = ['-trained_at']

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
