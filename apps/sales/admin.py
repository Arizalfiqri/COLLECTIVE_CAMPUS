from django.contrib import admin
from django.contrib import messages
from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect
from django.utils import timezone
from .models import (
    SaleItem,
    SaleItemPhoto,
    SellerTermsAcceptance,
    SaleOrder,
    SaleAgreement,
    SaleDispute,
    SaleReview,
    SaleItemReport,
    SaleOffer,
)


class SaleItemPhotoInline(admin.TabularInline):
    model = SaleItemPhoto
    extra = 1
    fields = ('image', 'order', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'category', 'price', 'condition', 'status', 'expires_at', 'created_at')
    list_filter = ('status', 'condition', 'category', 'created_at')
    search_fields = ('title', 'description', 'owner__username', 'owner__email', 'pickup_area')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [SaleItemPhotoInline]
    readonly_fields = ('created_at', 'updated_at', 'takedown_by', 'takedown_at', 'takedown_reason')
    actions = ['turunkan_listing_dengan_alasan']

    @admin.action(description="Turunkan listing terpilih dengan alasan wajib")
    def turunkan_listing_dengan_alasan(self, request, queryset):
        if request.POST.get('confirm') == 'yes':
            reason = request.POST.get('reason', '').strip()
            if not reason:
                self.message_user(request, "Alasan penurunan listing wajib diisi!", level=messages.ERROR)
                return TemplateResponse(request, 'admin/sales/saleitem/take_down_intermediate.html', {
                    'items': queryset,
                    'title': 'Konfirmasi Penurunan Listing Jual Beli',
                })
            from apps.sales.services import takedown_sale_item
            count = 0
            for item in queryset:
                takedown_sale_item(item, request.user, reason)
                count += 1
            self.message_user(request, f"{count} barang jualan berhasil diturunkan dan penjual telah diberi notifikasi.", level=messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())

        return TemplateResponse(request, 'admin/sales/saleitem/take_down_intermediate.html', {
            'items': queryset,
            'title': 'Konfirmasi Penurunan Listing Jual Beli',
        })


@admin.register(SaleItemPhoto)
class SaleItemPhotoAdmin(admin.ModelAdmin):
    list_display = ('sale_item', 'order', 'image', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('sale_item__title', 'sale_item__owner__username')
    readonly_fields = ('created_at',)


@admin.register(SellerTermsAcceptance)
class SellerTermsAcceptanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'terms_version', 'terms_hash', 'accepted_at', 'ip_address')
    list_filter = ('terms_version', 'accepted_at')
    search_fields = ('user__username', 'user__email', 'terms_hash', 'ip_address')
    readonly_fields = ('user', 'terms_version', 'terms_hash', 'text_snapshot', 'accepted_at', 'ip_address', 'user_agent')


class SaleAgreementInline(admin.StackedInline):
    model = SaleAgreement
    extra = 0
    can_delete = False
    readonly_fields = ('buyer', 'terms_version', 'terms_hash', 'text_snapshot', 'agreed_at', 'ip_address', 'user_agent')


@admin.register(SaleOrder)
class SaleOrderAdmin(admin.ModelAdmin):
    list_display = ('code', 'item', 'buyer', 'seller', 'price_snapshot', 'status', 'paid_at', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('code', 'item__title', 'buyer__username', 'seller__username')
    raw_id_fields = ('item', 'buyer', 'seller', 'meeting_point', 'cancelled_by')
    readonly_fields = ('code', 'created_at', 'updated_at', 'listing_snapshot')
    inlines = [SaleAgreementInline]


@admin.register(SaleAgreement)
class SaleAgreementAdmin(admin.ModelAdmin):
    list_display = ('order', 'buyer', 'terms_version', 'terms_hash', 'agreed_at', 'ip_address')
    list_filter = ('terms_version', 'agreed_at')
    search_fields = ('order__code', 'buyer__username', 'terms_hash', 'ip_address')
    readonly_fields = ('order', 'buyer', 'terms_version', 'terms_hash', 'text_snapshot', 'agreed_at', 'ip_address', 'user_agent')


from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe
from django.utils import dateformat, timezone
from .models import (
    SaleItem,
    SaleItemPhoto,
    SellerTermsAcceptance,
    SaleOrder,
    SaleAgreement,
    SaleDispute,
)
from .services import resolve_sale_dispute


@admin.register(SaleDispute)
class SaleDisputeAdmin(admin.ModelAdmin):
    list_display = (
        'order_code_display',
        'opened_by',
        'seller_display',
        'dispute_type_badge',
        'status_badge',
        'decision_badge',
        'nominal_display',
        'seller_violation_badge',
        'created_at_display',
    )
    list_filter = ('status', 'dispute_type', 'decision', 'seller_violation_recorded', 'created_at')
    search_fields = ('order__code', 'opened_by__username', 'order__seller__username', 'reason', 'notes')
    raw_id_fields = ('order', 'opened_by', 'decided_by')
    readonly_fields = (
        'order', 'opened_by', 'dispute_type', 'reason',
        'created_at', 'resolved_at', 'decided_by',
        'seller_violation_recorded', 'seller_violation_notes',
        'snapshot_comparison_display',
        'evidence_photos_display',
        'chat_transcript_display',
        'agreement_display',
        'timeline_display',
    )
    fieldsets = (
        ("Informasi Sengketa", {
            'fields': (
                'order',
                'opened_by',
                'dispute_type',
                'reason',
                'status',
                'seller_violation_recorded',
                'seller_violation_notes',
                'created_at',
            )
        }),
        ("Bukti & Perbandingan Listing", {
            'fields': (
                'snapshot_comparison_display',
                'evidence_photos_display',
                'chat_transcript_display',
                'agreement_display',
                'timeline_display',
            )
        }),
        ("Keputusan & Mediasi Admin", {
            'fields': (
                'decision',
                'nominal',
                'notes',
                'decided_by',
                'resolved_at',
            )
        }),
    )
    actions = ['action_putuskan_refund_pembeli', 'action_putuskan_lepas_ke_penjual']

    def order_code_display(self, obj):
        url = f"/admin/sales/saleorder/{obj.order.id}/change/"
        return format_html('<a href="{}" style="font-weight:700; color:#1F45C4;">#{}</a>', url, obj.order.code)
    order_code_display.short_description = "Pesanan"
    order_code_display.admin_order_field = 'order__code'

    def seller_display(self, obj):
        return obj.order.seller.username
    seller_display.short_description = "Penjual"

    def dispute_type_badge(self, obj):
        label = obj.get_dispute_type_display()
        return format_html(
            '<span style="background:#F0EBDD; color:#141B34; padding:3px 8px; border-radius:6px; font-weight:600; font-size:11px;">{}</span>',
            label
        )
    dispute_type_badge.short_description = "Jenis Sengketa"
    dispute_type_badge.admin_order_field = 'dispute_type'

    def status_badge(self, obj):
        colors = {
            'terbuka': ('#FFF0D1', '#9A5B00'),
            'diproses': ('#E6ECFB', '#1F45C4'),
            'selesai': ('#DDF1E8', '#0A5C43'),
            'ditolak': ('#FDE7E4', '#B42318'),
        }
        bg, text = colors.get(obj.status, ('#F0EBDD', '#141B34'))
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 10px; border-radius:12px; font-weight:600; font-size:11px;">{}</span>',
            bg, text, obj.get_status_display()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = 'status'

    def decision_badge(self, obj):
        if not obj.decision:
            return format_html('<span style="color:#566074; font-size:11px;">Belum diputus</span>')
        colors = {
            'refund_pembeli': ('#DDF1E8', '#0A5C43'),
            'lepas_ke_penjual': ('#E6ECFB', '#1F45C4'),
            'sebagian': ('#FFF0D1', '#9A5B00'),
        }
        bg, text = colors.get(obj.decision, ('#F0EBDD', '#141B34'))
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 10px; border-radius:12px; font-weight:600; font-size:11px;">{}</span>',
            bg, text, obj.get_decision_display()
        )
    decision_badge.short_description = "Keputusan"
    decision_badge.admin_order_field = 'decision'

    def nominal_display(self, obj):
        if obj.nominal:
            return format_html('<span style="font-weight:700; font-variant-numeric:tabular-nums; color:#1F45C4;">Rp{:,}</span>'.replace(',', '.'))
        return format_html('<span style="color:#566074;">-</span>')
    nominal_display.short_description = "Nominal Putusan"
    nominal_display.admin_order_field = 'nominal'

    def seller_violation_badge(self, obj):
        if obj.seller_violation_recorded:
            return format_html('<span style="background:#FDE7E4; color:#B42318; padding:2px 8px; border-radius:6px; font-size:10px; font-weight:700;">Pelanggaran</span>')
        return format_html('<span style="color:#566074; font-size:11px;">Bersih</span>')
    seller_violation_badge.short_description = "Pelanggaran Penjual"
    seller_violation_badge.admin_order_field = 'seller_violation_recorded'

    def created_at_display(self, obj):
        return dateformat.format(timezone.localtime(obj.created_at), 'd M Y, H:i')
    created_at_display.short_description = "Waktu Lapor"
    created_at_display.admin_order_field = 'created_at'

    def snapshot_comparison_display(self, obj):
        order = obj.order
        item = order.item
        snap = order.listing_snapshot or {}

        fields_to_compare = [
            ("Judul", snap.get('title', '-'), item.title),
            ("Harga", f"Rp{snap.get('price', order.price_snapshot):,}".replace(',', '.'), f"Rp{item.price:,}".replace(',', '.')),
            ("Kondisi", snap.get('condition', '-'), item.get_condition_display()),
            ("Minus / Cacat", snap.get('flaws', '-') or '-', item.flaws or '-'),
            ("Kelengkapan", snap.get('included_items', '-') or '-', item.included_items or '-'),
            ("Deskripsi", snap.get('description', '-'), item.description),
        ]

        rows = []
        for name, val_snap, val_curr in fields_to_compare:
            is_diff = str(val_snap).strip() != str(val_curr).strip()
            diff_style = "background:#FFF0D1;" if is_diff else ""
            rows.append(
                f"<tr style='border-bottom:1px solid #E4DECF; {diff_style}'>"
                f"<td style='padding:8px 12px; font-weight:600; color:#141B34; width:140px;'>{escape(name)}</td>"
                f"<td style='padding:8px 12px; color:#141B34; width:45%;'>{escape(str(val_snap))}</td>"
                f"<td style='padding:8px 12px; color:#566074; width:45%;'>{escape(str(val_curr))}</td>"
                f"</tr>"
            )

        html = f"""
        <div style="border:1px solid #E4DECF; border-radius:12px; overflow:hidden; background:#FFFFFF;">
            <table style="width:100%; border-collapse:collapse; font-size:12px; text-align:left;">
                <thead>
                    <tr style="background:#F0EBDD; border-bottom:1px solid #E4DECF; color:#141B34;">
                        <th style="padding:8px 12px;">Atribut</th>
                        <th style="padding:8px 12px;">Snapshot Saat Dipesan (Resmi)</th>
                        <th style="padding:8px 12px;">Data Listing Terkini</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """
        return mark_safe(html)
    snapshot_comparison_display.short_description = "Perbandingan Snapshot vs Kondisi Listing"

    def evidence_photos_display(self, obj):
        photos = obj.evidence_photos or []
        if not photos:
            return format_html('<span style="color:#566074; font-size:12px;">Tidak ada bukti foto yang dilampirkan.</span>')

        blocks = []
        for idx, p_rel in enumerate(photos):
            url = f"/pesanan/{obj.order.code}/foto-sengketa/{idx}/"
            blocks.append(
                f"<div style='display:inline-block; margin:6px; text-align:center; background:#F8F5EE; border:1px solid #E4DECF; border-radius:8px; padding:8px;'>"
                f"<div style='font-size:11px; font-weight:600; color:#141B34; margin-bottom:6px;'>Bukti #{idx + 1}</div>"
                f"<a href='{url}' target='_blank' style='display:inline-block; background:#1F45C4; color:#ffffff; padding:4px 10px; border-radius:6px; text-decoration:none; font-size:11px; font-weight:600;'>"
                f"Buka Foto Bukti"
                f"</a>"
                f"</div>"
            )
        return mark_safe(f"<div style='padding:6px 0;'>{''.join(blocks)}</div>")
    evidence_photos_display.short_description = "Bukti Foto Sengketa (Privat)"

    def chat_transcript_display(self, obj):
        from apps.chat.models import Conversation
        order = obj.order
        conv = Conversation.objects.filter(
            sale_item=order.item,
            renter=order.buyer,
            owner=order.seller
        ).first()

        if not conv:
            return format_html('<span style="color:#566074; font-size:12px;">Belum ada percakapan internal antara pembeli dan penjual untuk barang ini.</span>')

        messages = conv.messages.all().order_by('created_at')
        if not messages.exists():
            return format_html('<span style="color:#566074; font-size:12px;">Percakapan belum memiliki pesan.</span>')

        items = []
        for m in messages:
            is_buyer = (m.sender_id == order.buyer_id)
            sender_name = m.sender.full_name or m.sender.username
            role_label = "Pembeli" if is_buyer else "Penjual"
            bg_color = "#E6ECFB" if is_buyer else "#F8F5EE"
            time_str = dateformat.format(timezone.localtime(m.created_at), 'd M Y, H:i')
            items.append(
                f"<div style='margin-bottom:8px; padding:8px 12px; background:{bg_color}; border-radius:8px; border:1px solid #E4DECF;'>"
                f"<div style='display:flex; justify-content:space-between; margin-bottom:4px; font-size:11px;'>"
                f"<strong>{escape(sender_name)} ({role_label})</strong>"
                f"<span style='color:#566074;'>{time_str}</span>"
                f"</div>"
                f"<div style='font-size:12px; color:#141B34; line-height:1.4;'>{escape(m.body)}</div>"
                f"</div>"
            )

        html = f"<div style='max-height:280px; overflow-y:auto; border:1px solid #E4DECF; padding:10px; border-radius:8px; background:#FFFFFF;'>{''.join(items)}</div>"
        return mark_safe(html)
    chat_transcript_display.short_description = "Transkrip Chat Pembeli & Penjual"

    def agreement_display(self, obj):
        agreement = getattr(obj.order, 'agreement', None)
        if not agreement:
            return format_html('<span style="color:#566074; font-size:12px;">Perjanjian pembelian digital belum tercatat.</span>')

        print_url = f"/pesanan/{obj.order.code}/perjanjian/"
        time_str = dateformat.format(timezone.localtime(agreement.agreed_at), 'd M Y, H:i')
        html = f"""
        <div style="background:#F8F5EE; border:1px solid #E4DECF; border-radius:8px; padding:10px 14px; font-size:12px; line-height:1.6;">
            <div><strong>Versi S&K:</strong> Versi {escape(str(agreement.terms_version.version if agreement.terms_version else '1.0'))}</div>
            <div><strong>Hash SHA-256:</strong> <code style="font-family:monospace; font-size:11px;">{escape(agreement.terms_hash)}</code></div>
            <div><strong>Waktu Persetujuan:</strong> {time_str} WIB</div>
            <div><strong>Alamat IP Pembeli:</strong> {escape(str(agreement.ip_address or '-'))}</div>
            <div style="margin-top:6px;">
                <a href="{print_url}" target="_blank" style="background:#1F45C4; color:#ffffff; padding:4px 10px; border-radius:6px; text-decoration:none; font-weight:600; font-size:11px; display:inline-block;">
                    Buka Dokumen Perjanjian Resmi &rarr;
                </a>
            </div>
        </div>
        """
        return mark_safe(html)
    agreement_display.short_description = "Perjanjian Pembelian Digital Resmi"

    def timeline_display(self, obj):
        order = obj.order
        events = [
            ("Pesanan Dibuat", order.created_at, True),
            ("Pembayaran Midtrans Escrow", order.paid_at, bool(order.paid_at)),
            ("Jadwal Temu Kampus Disepakati", order.meetup_at, bool(order.meetup_at)),
            ("Serah Terima Fisik Barang", order.handed_over_at, bool(order.handed_over_at)),
            ("Sengketa Diajukan", obj.created_at, True),
            ("Putusan Admin", obj.resolved_at, bool(obj.resolved_at)),
        ]

        steps = []
        for title, dt, done in events:
            color = "#0E7C5A" if done else "#8E98A8"
            icon = "✓" if done else "○"
            dt_str = dateformat.format(timezone.localtime(dt), 'd M Y, H:i') if dt else "Belum tercatat"
            steps.append(
                f"<div style='display:flex; align-items:flex-start; gap:8px; margin-bottom:6px;'>"
                f"<span style='color:{color}; font-weight:bold; font-size:13px;'>{icon}</span>"
                f"<div>"
                f"<div style='font-weight:600; font-size:12px; color:#141B34;'>{escape(title)}</div>"
                f"<div style='font-size:11px; color:#566074;'>{dt_str}</div>"
                f"</div>"
                f"</div>"
            )

        html = f"<div style='background:#FFFFFF; border:1px solid #E4DECF; border-radius:8px; padding:12px;'>{''.join(steps)}</div>"
        return mark_safe(html)
    timeline_display.short_description = "Garis Waktu Siklus Transaksi"

    def save_model(self, request, obj, form, change):
        if obj.decision and obj.status != SaleDispute.Status.SELESAI:
            resolve_sale_dispute(
                obj,
                decision=obj.decision,
                nominal=obj.nominal,
                notes=obj.notes,
                admin_user=request.user
            )
        else:
            super().save_model(request, obj, form, change)

    def action_putuskan_refund_pembeli(self, request, queryset):
        success_count = 0
        for dispute in queryset:
            try:
                resolve_sale_dispute(
                    dispute,
                    decision=SaleDispute.Decision.REFUND_PEMBELI,
                    notes="Diputuskan via aksi admin: Pengembalian dana penuh ke pembeli",
                    admin_user=request.user
                )
                success_count += 1
            except Exception as e:
                self.message_user(request, f"Gagal menyelesaikan sengketa {dispute.order.code}: {e}", level='error')
        if success_count:
            self.message_user(request, f"{success_count} sengketa berhasil diputuskan dengan refund penuh ke pembeli.")
    action_putuskan_refund_pembeli.short_description = "Putuskan: Refund Penuh ke Pembeli"

    def action_putuskan_lepas_ke_penjual(self, request, queryset):
        success_count = 0
        for dispute in queryset:
            try:
                resolve_sale_dispute(
                    dispute,
                    decision=SaleDispute.Decision.LEPAS_KE_PENJUAL,
                    notes="Diputuskan via aksi admin: Pencairan dana penuh ke penjual",
                    admin_user=request.user
                )
                success_count += 1
            except Exception as e:
                self.message_user(request, f"Gagal menyelesaikan sengketa {dispute.order.code}: {e}", level='error')
        if success_count:
            self.message_user(request, f"{success_count} sengketa berhasil diputuskan dengan pencairan penuh ke penjual.")
    action_putuskan_lepas_ke_penjual.short_description = "Putuskan: Lepas Penuh ke Penjual"


@admin.register(SaleReview)
class SaleReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'reviewer', 'reviewee', 'role', 'rating', 'comment_snippet', 'created_at')
    list_filter = ('role', 'rating', 'created_at')
    search_fields = ('order__code', 'reviewer__username', 'reviewee__username', 'comment')
    readonly_fields = ('created_at', 'updated_at')

    def comment_snippet(self, obj):
        if not obj.comment:
            return '-'
        return (obj.comment[:45] + '...') if len(obj.comment) > 45 else obj.comment
    comment_snippet.short_description = "Komentar"


@admin.register(SaleItemReport)
class SaleItemReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'item_title_display', 'reporter', 'reason', 'status', 'reviewed_by', 'created_at', 'resolved_at')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('item__title', 'reporter__username', 'reporter__email', 'notes', 'action_taken')
    readonly_fields = ('created_at', 'resolved_at')
    raw_id_fields = ('item', 'reporter', 'reviewed_by')
    actions = ['tandai_ditindaklanjuti', 'tandai_diabaikan', 'turunkan_listing_terkait']

    def item_title_display(self, obj):
        return f"{obj.item.title} (Rp{obj.item.price:,})"
    item_title_display.short_description = "Barang Jualan"

    @admin.action(description="Tandai laporan terpilih sebagai Ditindaklanjuti")
    def tandai_ditindaklanjuti(self, request, queryset):
        now = timezone.now()
        updated = queryset.update(
            status=SaleItemReport.Status.DITINDAKLANJUTI,
            reviewed_by=request.user,
            action_taken="Ditandai ditindaklanjuti oleh staf",
            resolved_at=now
        )
        self.message_user(request, f"{updated} laporan berhasil ditandai sebagai ditindaklanjuti.", level=messages.SUCCESS)

    @admin.action(description="Tandai laporan terpilih sebagai Diabaikan")
    def tandai_diabaikan(self, request, queryset):
        now = timezone.now()
        updated = queryset.update(
            status=SaleItemReport.Status.DIABAIKAN,
            reviewed_by=request.user,
            action_taken="Laporan diabaikan setelah evaluasi",
            resolved_at=now
        )
        self.message_user(request, f"{updated} laporan berhasil ditandai sebagai diabaikan.", level=messages.SUCCESS)

    @admin.action(description="Turunkan barang terkait dari laporan terpilih")
    def turunkan_listing_terkait(self, request, queryset):
        from apps.sales.services import takedown_sale_item
        count = 0
        for report in queryset:
            if report.item.status != SaleItem.Status.NONAKTIF:
                takedown_sale_item(
                    report.item,
                    request.user,
                    f"Diturunkan dari laporan pengguna: {report.get_reason_display()} ({report.notes})"
                )
                count += 1
        self.message_user(request, f"{count} barang jualan terkait berhasil dinonaktifkan.", level=messages.SUCCESS)


@admin.register(SaleOffer)
class SaleOfferAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'buyer', 'offered_price', 'status', 'created_at', 'expires_at')
    list_filter = ('status', 'created_at', 'expires_at')
    search_fields = ('item__title', 'buyer__username', 'buyer__email')
    raw_id_fields = ('item', 'buyer', 'order')
    readonly_fields = ('created_at',)




