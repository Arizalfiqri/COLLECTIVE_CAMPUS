from django.db.models import Q


def unread_messages_count(request):
    """Menyediakan jumlah pesan belum dibaca untuk user yang login."""
    if not request.user.is_authenticated:
        return {'unread_messages_count': 0}
    try:
        from apps.chat.models import Message
        count = Message.objects.filter(
            Q(conversation__renter=request.user) | Q(conversation__owner=request.user),
            read_at__isnull=True
        ).exclude(sender=request.user).distinct().count()
        return {'unread_messages_count': count}
    except Exception:
        return {'unread_messages_count': 0}
