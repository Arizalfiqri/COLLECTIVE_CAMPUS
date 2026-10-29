from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('sender', 'body', 'created_at', 'read_at')
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('item', 'renter', 'owner', 'rental', 'last_message_at', 'created_at')
    search_fields = ('item__title', 'renter__username', 'owner__username')
    raw_id_fields = ('item', 'renter', 'owner', 'rental')
    inlines = [MessageInline]
    ordering = ['-last_message_at']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'short_body', 'created_at', 'read_at')
    search_fields = ('conversation__item__title', 'sender__username', 'body')
    raw_id_fields = ('conversation', 'sender')
    ordering = ['-created_at']

    def short_body(self, obj):
        display = obj.get_display_body()
        return display[:60]
    short_body.short_description = "Isi Pesan (Masked)"
