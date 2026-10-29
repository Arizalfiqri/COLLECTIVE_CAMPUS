import re
from django.db import models
from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe


class Conversation(models.Model):
    item = models.ForeignKey(
        'catalog.Item', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='conversations', verbose_name="Barang Sewa"
    )
    sale_item = models.ForeignKey(
        'sales.SaleItem', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='conversations', verbose_name="Barang Jualan"
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='conversations_as_renter', verbose_name="Penyewa atau Pembeli"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='conversations_as_owner', verbose_name="Pemilik atau Penjual"
    )
    rental = models.ForeignKey(
        'rentals.Rental', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversations', verbose_name="Sewa Terkait"
    )
    last_message_at = models.DateTimeField(auto_now=True, verbose_name="Pesan Terakhir Pada")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")

    class Meta:
        verbose_name = "Percakapan"
        verbose_name_plural = "Percakapan"
        constraints = [
            models.CheckConstraint(
                check=(
                    (models.Q(item__isnull=False) & models.Q(sale_item__isnull=True)) |
                    (models.Q(item__isnull=True) & models.Q(sale_item__isnull=False))
                ),
                name='check_conversation_one_item_type'
            ),
            models.UniqueConstraint(
                fields=['item', 'renter'],
                condition=models.Q(item__isnull=False),
                name='unique_conversation_per_item_renter'
            ),
            models.UniqueConstraint(
                fields=['sale_item', 'renter'],
                condition=models.Q(sale_item__isnull=False),
                name='unique_conversation_per_sale_item_renter'
            ),
        ]
        ordering = ['-last_message_at']

    def __str__(self):
        title = self.item.title if self.item else (self.sale_item.title if self.sale_item else '')
        return f"Chat: {self.renter.username} & {self.owner.username} – {title}"

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if bool(self.item_id) == bool(self.sale_item_id):
            raise ValidationError("Percakapan harus terhubung tepat ke salah satu: barang sewa atau barang jualan.")

    def has_successful_payment(self):
        """
        Cek apakah ada transaksi sewa/beli yang berstatus dibayar atau lebih lanjut
        yang terikat dengan percakapan ini.
        """
        if self.rental:
            paid_statuses = ['dibayar', 'sedang_disewa', 'menunggu_konfirmasi_pengembalian', 'selesai']
            return self.rental.status in paid_statuses

        if self.sale_item:
            from apps.sales.models import SaleOrder
            return SaleOrder.objects.filter(
                item=self.sale_item,
                buyer=self.renter,
                status__in=['dibayar', 'diserahkan', 'selesai', 'sengketa']
            ).exists()

        if self.item:
            from apps.rentals.models import Rental
            # Jika belum ada rental terikat pada percakapan, periksa hanya jika ada rental AKTIF
            # (bukan transaksi lama yang sudah selesai atau dibatalkan)
            return Rental.objects.filter(
                item=self.item,
                renter=self.renter,
                status__in=['dibayar', 'sedang_disewa', 'menunggu_konfirmasi_pengembalian']
            ).exists()

        return False

    @property
    def target_title(self):
        if self.item:
            return self.item.title
        if self.sale_item:
            return self.sale_item.title
        return ''

    @property
    def item_type(self):
        return 'jual' if self.sale_item else 'sewa'

    @property
    def item_type_label(self):
        return 'Dijual' if self.sale_item else 'Disewa'

    def unread_count_for(self, user):
        """Menghitung jumlah pesan yang belum dibaca oleh user tertentu."""
        return self.messages.exclude(sender=user).filter(read_at__isnull=True).count()


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE,
        related_name='messages', verbose_name="Percakapan"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sent_messages', verbose_name="Pengirim"
    )
    body = models.CharField(max_length=500, verbose_name="Isi Pesan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Dibaca")

    class Meta:
        verbose_name = "Pesan percakapan"
        verbose_name_plural = "Pesan percakapan"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username}: {self.body[:30]}"

    @classmethod
    def mask_contact_info(cls, text):
        """
        Menyamarkan nomor telepon, tautan, dan email menjadi '[disamarkan sampai pembayaran]'.
        Aturan SPEC v2 bagian E:
        - nomor telepon (pola 08..., +62..., 8 digit berurutan atau lebih)
        - tautan (http, https, www., wa.me, t.me)
        - alamat email
        """
        if not text:
            return text

        masked_notice = "[disamarkan sampai pembayaran]"

        # 1. Mask URL / links (http://, https://, www., wa.me, t.me)
        url_pattern = r'(https?://[^\s]+|www\.[^\s]+|wa\.me/[^\s]+|t\.me/[^\s]+)'
        text = re.sub(url_pattern, masked_notice, text, flags=re.IGNORECASE)

        # 2. Mask email
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        text = re.sub(email_pattern, masked_notice, text)

        # 3. Mask phone numbers: 08..., +62..., 62..., or 8+ consecutive digits with optional spaces/dashes
        phone_patterns = [
            r'(\+62|62|08)[0-9\-\s]{5,24}[0-9]',
            r'\b0\d{2,4}[\-\s]?\d{5,10}\b',
            r'\b\d{8,}\b',
        ]
        for p in phone_patterns:
            text = re.sub(p, masked_notice, text)

        return text

    def get_display_body(self):
        """
        Mengembalikan teks pesan yang aman (escaped) dan tersamar jika sewa belum dibayar.
        """
        # 1. Cek apakah sewa sudah dibayar
        is_paid = self.conversation.has_successful_payment()
        content = self.body

        if not is_paid:
            content = self.mask_contact_info(content)

        # 2. Escape teks agar aman dari XSS
        return escape(content)
