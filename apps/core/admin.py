from django.contrib import admin
from .models import Notification, TermsVersion


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'url', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('user__username', 'message')
    raw_id_fields = ('user',)


@admin.register(TermsVersion)
class TermsVersionAdmin(admin.ModelAdmin):
    list_display = ('term_type', 'version', 'valid_from', 'is_active', 'sha256_display', 'created_at')
    list_filter = ('term_type', 'is_active')
    search_fields = ('version', 'content')
    ordering = ('term_type', '-valid_from')

    def sha256_display(self, obj):
        h = obj.calculate_sha256()
        return f"{h[:10]}...{h[-8:]}"
    sha256_display.short_description = "Hash SHA-256"

