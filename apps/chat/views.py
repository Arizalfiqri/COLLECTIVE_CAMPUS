from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import models
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import verified_student_required
from apps.catalog.models import Item
from apps.chat.models import Conversation, Message


@login_required(login_url='/masuk/')
def inbox_view(request):
    """
    Halaman Kotak Masuk (/pesan/).
    Menampilkan daftar percakapan pengguna baik sebagai penyewa maupun pemilik.
    Mendukung filter: semua, sewa, jual_beli, belum_dibaca.
    Percakapan tanpa pesan diringkas menjadi satu baris terpisah.
    """
    conversations = (
        Conversation.objects
        .filter(models.Q(renter=request.user) | models.Q(owner=request.user))
        .select_related('item', 'sale_item', 'renter', 'owner', 'rental')
        .prefetch_related('messages')
        .order_by('-last_message_at')
    )

    tab = request.GET.get('tab', 'semua')
    if tab not in ['semua', 'sewa', 'jual_beli', 'belum_dibaca']:
        tab = 'semua'

    active_conversations = []
    empty_conversations = []
    total_unread_count = 0
    sewa_count = 0
    jual_count = 0
    unread_conversations_count = 0

    for conv in conversations:
        other_user = conv.owner if request.user == conv.renter else conv.renter
        unread = conv.unread_count_for(request.user)
        total_unread_count += unread
        last_msg = conv.messages.last()
        is_sale = bool(conv.sale_item)
        if is_sale:
            jual_count += 1
        else:
            sewa_count += 1
        if unread > 0:
            unread_conversations_count += 1

        conv_dict = {
            'conversation': conv,
            'other_user': other_user,
            'unread_count': unread,
            'last_message': last_msg,
            'is_sale': is_sale,
        }

        if last_msg:
            active_conversations.append(conv_dict)
        else:
            empty_conversations.append(conv_dict)

    if tab == 'sewa':
        filtered_conversations = [c for c in active_conversations if not c['is_sale']]
        filtered_empty = [c for c in empty_conversations if not c['is_sale']]
    elif tab == 'jual_beli':
        filtered_conversations = [c for c in active_conversations if c['is_sale']]
        filtered_empty = [c for c in empty_conversations if c['is_sale']]
    elif tab == 'belum_dibaca':
        filtered_conversations = [c for c in active_conversations if c['unread_count'] > 0]
        filtered_empty = []
    else:  # 'semua'
        filtered_conversations = active_conversations
        filtered_empty = empty_conversations

    return render(request, 'chat/inbox.html', {
        'conversations': filtered_conversations,
        'empty_conversations': filtered_empty,
        'empty_count': len(filtered_empty),
        'active_tab': tab,
        'total_unread_count': total_unread_count,
        'unread_conversations_count': unread_conversations_count,
        'sewa_count': sewa_count,
        'jual_count': jual_count,
        'total_active_count': len(active_conversations),
    })


@login_required(login_url='/masuk/')
def conversation_view(request, conversation_id):
    """
    Halaman Ruang Percakapan (/pesan/<id>/).
    Hanya peserta percakapan (renter & owner) yang berhak membaca.
    """
    conv = get_object_or_404(
        Conversation.objects.select_related(
            'item', 'item__owner', 'sale_item', 'sale_item__owner', 'renter', 'owner', 'rental'
        ),
        pk=conversation_id
    )

    # Validasi hak akses peserta percakapan
    if request.user != conv.renter and request.user != conv.owner:
        return HttpResponseForbidden("Anda tidak memiliki akses ke percakapan ini.")

    # Tandai pesan lawan bicara sebagai telah dibaca
    conv.messages.exclude(sender=request.user).filter(read_at__isnull=True).update(read_at=timezone.now())

    other_user = conv.owner if request.user == conv.renter else conv.renter
    has_paid = conv.has_successful_payment()

    chat_messages = conv.messages.select_related('sender').order_by('created_at')

    return render(request, 'chat/conversation.html', {
        'conversation': conv,
        'other_user': other_user,
        'has_paid': has_paid,
        'chat_messages': chat_messages,
    })


@login_required(login_url='/masuk/')
def messages_partial_view(request, conversation_id):
    """
    Endpoint partial HTMX untuk pembaruan polling pesan setiap 5 detik.
    """
    conv = get_object_or_404(Conversation, pk=conversation_id)

    if request.user != conv.renter and request.user != conv.owner:
        return HttpResponseForbidden("Akses ditolak.")

    # Tandai pesan lawan bicara sebagai telah dibaca saat di-poll
    conv.messages.exclude(sender=request.user).filter(read_at__isnull=True).update(read_at=timezone.now())

    chat_messages = conv.messages.select_related('sender').order_by('created_at')

    return render(request, 'chat/partials/message_list.html', {
        'conversation': conv,
        'chat_messages': chat_messages,
    })


@login_required(login_url='/masuk/')
def send_message_view(request, conversation_id):
    """
    Kirim pesan baru (/pesan/<id>/kirim/).
    Memeriksa:
    - Hak peserta
    - Pembatasan laju 20 pesan per menit
    - Maksimal 500 karakter
    """
    if request.method != 'POST':
        return HttpResponseForbidden("Metode tidak diizinkan.")

    conv = get_object_or_404(Conversation, pk=conversation_id)

    if request.user != conv.renter and request.user != conv.owner:
        return HttpResponseForbidden("Akses ditolak.")

    # 1. Pembatasan laju (Rate limit): 20 pesan / menit / user
    rate_key = f"chat_ratelimit_{request.user.id}"
    now_ts = timezone.now().timestamp()
    timestamps = cache.get(rate_key, [])
    # Filter hanya 60 detik terakhir
    timestamps = [t for t in timestamps if now_ts - t < 60]

    if len(timestamps) >= 20:
        error_msg = "Batas pengiriman pesan tercapai (maksimal 20 pesan per menit). Silakan tunggu sejenak."
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="p-3 my-2 rounded-xl bg-brick-tint border border-brick/30 text-brick text-xs font-semibold">{error_msg}</div>',
                status=429
            )
        messages.error(request, error_msg)
        return redirect('chat:conversation', conversation_id=conv.id)

    # 2. Ambil dan validasi isi pesan (maks 500 karakter)
    raw_body = request.POST.get('body', '').strip()
    if not raw_body:
        if request.headers.get('HX-Request'):
            return messages_partial_view(request, conversation_id)
        return redirect('chat:conversation', conversation_id=conv.id)

    body = raw_body[:500]

    # 3. Simpan pesan
    Message.objects.create(
        conversation=conv,
        sender=request.user,
        body=body
    )
    conv.last_message_at = timezone.now()
    conv.save(update_fields=['last_message_at'])

    # Catat riwayat laju pengiriman
    timestamps.append(now_ts)
    cache.set(rate_key, timestamps, timeout=65)

    if request.headers.get('HX-Request'):
        return messages_partial_view(request, conversation_id)

    return redirect('chat:conversation', conversation_id=conv.id)


@verified_student_required
def start_conversation_view(request, item_slug):
    """
    Mulai percakapan dari tombol 'Tanya Pemilik' di detail barang (/pesan/mulai/<slug>/).
    Aturan SPEC v2 Bagian E:
    - Hanya penyewa yang boleh memulai (mencegah spam ke pemilik)
    - Wajib akun terverifikasi KTM
    """
    item = get_object_or_404(Item, slug=item_slug, is_active=True)

    if request.user == item.owner:
        messages.warning(request, "Anda adalah pemilik barang ini.")
        return redirect('catalog:item_detail', slug=item.slug)

    conv, created = Conversation.objects.get_or_create(
        item=item,
        renter=request.user,
        defaults={'owner': item.owner}
    )

    return redirect('chat:conversation', conversation_id=conv.id)


@verified_student_required
def start_sale_conversation_view(request, sale_slug):
    """
    Mulai percakapan dari tombol 'Tanya Penjual' di detail barang jualan (/pesan/mulai-jual/<slug>/).
    """
    from apps.sales.models import SaleItem
    sale_item = get_object_or_404(SaleItem, slug=sale_slug, status=SaleItem.Status.AKTIF)

    if request.user == sale_item.owner:
        messages.warning(request, "Anda adalah penjual barang ini.")
        return redirect('sales:item_detail', slug=sale_item.slug)

    conv, created = Conversation.objects.get_or_create(
        sale_item=sale_item,
        renter=request.user,
        defaults={'owner': sale_item.owner}
    )

    return redirect('chat:conversation', conversation_id=conv.id)

