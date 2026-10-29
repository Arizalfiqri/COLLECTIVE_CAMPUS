import json
from django.contrib import admin
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from .models import Rental, ConditionPhoto, Review, Dispute, RentalAgreement, HandoverSchedule
from apps.rentals.services import (
    selesaikan_sengketa_admin,
    proses_klaim_dana_proteksi_admin,
    RentalError,
)


class ConditionPhotoInline(admin.TabularInline):
    model = ConditionPhoto
    extra = 0
    readonly_fields = ('uploaded_by', 'phase', 'photo_preview', 'note', 'created_at')

    def photo_preview(self, obj):
        if obj.id:
            url = obj.get_serve_url()
            return format_html('<a href="{}" target="_blank">Buka Foto ({})</a>', url, obj.phase)
        return "-"
    photo_preview.short_description = "Pratinjau Foto"


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    readonly_fields = ('reviewer', 'reviewee', 'as_role', 'rating', 'comment', 'created_at')


class RentalAgreementInline(admin.StackedInline):
    model = RentalAgreement
    extra = 0
    readonly_fields = ('accepted_at', 'formatted_terms')

    def formatted_terms(self, obj):
        if obj and obj.terms_snapshot:
            return format_html('<pre style="max-height: 200px; overflow: auto;">{}</pre>', json.dumps(obj.terms_snapshot, indent=2))
        return "-"
    formatted_terms.short_description = "Snapshot Syarat & Ketentuan"


class HandoverScheduleInline(admin.TabularInline):
    model = HandoverSchedule
    extra = 0


from apps.core.admin_utils import generate_csv_export_action

export_rental_csv = generate_csv_export_action(
    description="Ekspor transaksi sewa terpilih ke CSV",
    filename_prefix="rentals",
    columns=[
        ("Kode Sewa", "code"),
        ("Barang", lambda obj: obj.item.title if obj.item else "-"),
        ("Penyewa", lambda obj: obj.renter.username if obj.renter else "-"),
        ("Pemilik", lambda obj: obj.owner.username if obj.owner else "-"),
        ("Status", "status"),
        ("Tanggal Mulai", "start_date"),
        ("Tanggal Selesai", "end_date"),
        ("Total Biaya (Rp)", "grand_total"),
        ("Waktu Dibuat", "created_at"),
    ]
)


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = ('code', 'item', 'renter', 'owner', 'status', 'start_date', 'end_date', 'grand_total', 'created_at')
    list_filter = ('status',)
    search_fields = ('code', 'item__title', 'renter__username', 'owner__username')
    raw_id_fields = ('item', 'renter', 'owner', 'cancelled_by')
    readonly_fields = ('code', 'created_at', 'updated_at', 'requested_at', 'approved_at', 'status_changed_at')
    inlines = [ConditionPhotoInline, ReviewInline, RentalAgreementInline, HandoverScheduleInline]
    list_per_page = 20
    actions = ['process_deadlines_action', 'action_klaim_dana_proteksi', export_rental_csv]

    @admin.action(description="Jalankan process_deadlines (Proses batas waktu sewa)")
    def process_deadlines_action(self, request, queryset):
        from .management.commands.process_deadlines import run_process_deadlines
        results = run_process_deadlines()
        self.message_user(
            request,
            f"Process deadlines selesai: {results['expired_approval']} pengajuan kedaluwarsa, "
            f"{results['expired_payment']} pembayaran kedaluwarsa, "
            f"{results['auto_confirmed_returns']} konfirmasi pengembalian, "
            f"{results['non_returns']} barang tidak kembali (Total kedaluwarsa: {results['total']})."
        )

    @admin.action(description="Putuskan Klaim Dana Gotong Royong ke Pemilik (Maks. 50 persen Nilai Barang - Deposit)")
    def action_klaim_dana_proteksi(self, request, queryset):
        count = 0
        for rental in queryset:
            try:
                nominal = proses_klaim_dana_proteksi_admin(rental, request.user, note="Admin action via RentalAdmin")
                count += 1
                self.message_user(request, f"Klaim Dana Gotong Royong sebesar Rp{nominal:,} berhasil dicairkan untuk {rental.code}.")
            except Exception as e:
                self.message_user(request, f"Gagal mencairkan klaim proteksi untuk {rental.code}: {e}", level='error')


@admin.register(ConditionPhoto)
class ConditionPhotoAdmin(admin.ModelAdmin):
    list_display = ('rental', 'uploaded_by', 'phase', 'photo_link', 'created_at')
    list_filter = ('phase',)
    raw_id_fields = ('rental', 'uploaded_by')

    def photo_link(self, obj):
        url = obj.get_serve_url()
        return format_html('<a href="{}" target="_blank">Lihat Berkas Privat</a>', url)
    photo_link.short_description = "Berkas Privat"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('rental', 'reviewer', 'reviewee', 'as_role', 'rating', 'created_at')
    list_filter = ('as_role', 'rating')
    search_fields = ('rental__code', 'reviewer__username', 'reviewee__username')
    raw_id_fields = ('rental', 'reviewer', 'reviewee')


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ('rental', 'opened_by', 'status_badge', 'decision_badge', 'deduction_amount_display', 'dibuat_display')
    list_filter = ('status', 'decision')
    search_fields = ('rental__code', 'opened_by__username')
    raw_id_fields = ('rental', 'opened_by', 'decided_by')

    def status_badge(self, obj):
        colors = {
            'terbuka': ('#FFF0D1', '#9A5B00'),
            'dimediasi': ('#E6ECFB', '#1F45C4'),
            'diputuskan': ('#DDF1E8', '#0A5C43'),
            'dibatalkan': ('#FDE7E4', '#B42318'),
        }
        bg, text = colors.get(obj.status, ('#F0EBDD', '#141B34'))
        label = (obj.get_status_display() or '-').capitalize()
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 10px; border-radius:12px; font-weight:600; font-size:11px; display:inline-block;">{}</span>',
            bg, text, label
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = 'status'

    def decision_badge(self, obj):
        if not obj.decision:
            return format_html('<span style="color:#566074; font-size:11px;">Belum diputus</span>')
        colors = {
            'kembalikan_penuh': ('#DDF1E8', '#0A5C43'),
            'potong_sebagian': ('#FFF0D1', '#9A5B00'),
            'potong_penuh': ('#FDE7E4', '#B42318'),
            'klaim_proteksi': ('#E6ECFB', '#1F45C4'),
        }
        bg, text = colors.get(obj.decision, ('#F0EBDD', '#141B34'))
        label = (obj.get_decision_display() or '-').title()
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 10px; border-radius:12px; font-weight:600; font-size:11px; display:inline-block; white-space:nowrap;">{}</span>',
            bg, text, label
        )
    decision_badge.short_description = "Keputusan"
    decision_badge.admin_order_field = 'decision'

    def deduction_amount_display(self, obj):
        val = obj.deduction_amount or 0
        if val > 0:
            return format_html(
                '<span style="font-weight:600; font-variant-numeric:tabular-nums; color:#B42318;">Rp{}</span>',
                f"{int(val):,}".replace(',', '.')
            )
        return format_html('<span style="color:#566074;">Rp0</span>')
    deduction_amount_display.short_description = "Potongan"
    deduction_amount_display.admin_order_field = 'deduction_amount'

    def dibuat_display(self, obj):
        if not obj.created_at:
            return '-'
        from django.utils import dateformat, timezone
        return dateformat.format(timezone.localtime(obj.created_at), 'd M Y, H:i')
    dibuat_display.short_description = "Dibuat"
    dibuat_display.admin_order_field = 'created_at'
    readonly_fields = (
        'rental', 'opened_by', 'created_at', 'updated_at',
        'rental_overview_display', 'chat_history_display',
        'photos_display', 'agreement_display', 'schedules_display',
        'decided_by'
    )
    fieldsets = (
        ("Status & Informasi Sengketa", {
            'fields': ('rental', 'opened_by', 'status', 'reason', 'evidence_note', 'created_at')
        }),
        ("Bukti & Riwayat Transaksi", {
            'fields': (
                'rental_overview_display',
                'photos_display',
                'chat_history_display',
                'agreement_display',
                'schedules_display',
            )
        }),
        ("Keputusan Admin", {
            'fields': ('decision', 'deduction_amount', 'decision_note', 'decided_by')
        }),
    )
    actions = ['action_kembalikan_penuh', 'action_potong_penuh', 'action_klaim_dana_proteksi']

    def rental_overview_display(self, obj):
        r = obj.rental
        sisa = max(0, r.deposit_total - r.late_fee)
        html = f"""
        <div style="background:#f8f9fa; padding:12px; border-radius:6px; border:1px solid #dee2e6;">
            <strong>Kode Sewa:</strong> {r.code}<br>
            <strong>Barang:</strong> {escape(r.item.title)} (Nilai Estimasi: Rp{r.item.estimated_value:,})<br>
            <strong>Penyewa:</strong> {escape(r.renter.username)} ({escape(r.renter.get_full_name() or '')})<br>
            <strong>Pemilik:</strong> {escape(r.owner.username)} ({escape(r.owner.get_full_name() or '')})<br>
            <strong>Status Sewa:</strong> {r.get_status_display()}<br>
            <strong>Total Biaya Sewa:</strong> Rp{r.rent_total:,}<br>
            <strong>Deposit Ditahan:</strong> Rp{r.deposit_total:,}<br>
            <strong>Denda Keterlambatan ({r.late_days} hari):</strong> Rp{r.late_fee:,}<br>
            <strong>Sisa Deposit Maksimal untuk Potongan:</strong> Rp{sisa:,}
        </div>
        """
        return mark_safe(html)
    rental_overview_display.short_description = "Ringkasan Sewa"

    def chat_history_display(self, obj):
        rental = obj.rental
        conv = rental.conversations.first()
        if not conv:
            return "Tidak ada riwayat percakapan untuk sewa ini."
        messages = conv.messages.all().order_by('created_at')
        if not messages.exists():
            return "Belum ada pesan dalam percakapan."

        items = []
        for m in messages:
            sender_name = m.sender.username
            is_renter = (m.sender_id == rental.renter_id)
            role_label = "Penyewa" if is_renter else "Pemilik"
            time_str = m.created_at.strftime("%d %b %Y, %H:%M")
            items.append(
                f"<div style='margin-bottom:6px; padding:6px 10px; background:#f1f5f9; border-radius:4px;'>"
                f"<strong>{escape(sender_name)}</strong> ({role_label}) "
                f"<span style='color:#64748b; font-size:11px;'>{time_str}</span><br>"
                f"<span>{escape(m.body)}</span>"
                f"</div>"
            )
        html = f"<div style='max-height:240px; overflow-y:auto; border:1px solid #cbd5e1; padding:8px; border-radius:4px;'>{''.join(items)}</div>"
        return mark_safe(html)
    chat_history_display.short_description = "Riwayat Chat Internal"

    def photos_display(self, obj):
        rental = obj.rental
        photos = rental.condition_photos.all().order_by('created_at')
        if not photos.exists():
            return "Belum ada foto kondisi yang diunggah."

        blocks = []
        for p in photos:
            url = p.get_serve_url()
            blocks.append(
                f"<div style='display:inline-block; margin:6px; text-align:center; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:8px;'>"
                f"<div><strong>{p.get_phase_display()}</strong></div>"
                f"<div style='font-size:11px; color:#64748b; margin-bottom:4px;'>Oleh: {escape(p.uploaded_by.username)}</div>"
                f"<a href='{url}' target='_blank' style='display:inline-block; background:#0284c7; color:#fff; padding:4px 8px; border-radius:4px; text-decoration:none; font-size:12px;'>Lihat Foto</a>"
                f"</div>"
            )
        return mark_safe("".join(blocks))
    photos_display.short_description = "Dokumentasi Foto Kondisi (Sebelum, Serah Terima, Sesudah)"

    def agreement_display(self, obj):
        agreement = getattr(obj.rental, 'agreement', None)
        if not agreement or not agreement.terms_snapshot:
            return "Tidak ada perjanjian sewa digital tersimpan."
        return format_html('<pre style="max-height: 180px; overflow: auto; background:#f8fafc; padding:8px; border:1px solid #e2e8f0;">{}</pre>', json.dumps(agreement.terms_snapshot, indent=2))
    agreement_display.short_description = "Perjanjian Sewa Digital"

    def schedules_display(self, obj):
        schedules = obj.rental.handover_schedules.all().order_by('-created_at')
        if not schedules.exists():
            return "Belum ada usulan jadwal serah terima."
        items = []
        for s in schedules:
            point = s.meeting_point.name if s.meeting_point else "Tanpa titik temu khusus"
            items.append(
                f"<li><strong>{s.meet_at.strftime('%d %b %Y %H:%M')}</strong> di {escape(point)} "
                f"({s.get_status_display()} oleh {escape(s.proposed_by.username)})</li>"
            )
        return mark_safe(f"<ul>{''.join(items)}</ul>")
    schedules_display.short_description = "Jadwal Serah Terima"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.decision and obj.rental.status == Rental.Status.SENGKETA:
            try:
                selesaikan_sengketa_admin(
                    rental=obj.rental,
                    admin_user=request.user,
                    decision=obj.decision,
                    deduction_amount=obj.deduction_amount,
                    decision_note=obj.decision_note,
                )
            except Exception as e:
                self.message_user(request, f"Penyelesaian sengketa gagal: {e}", level='error')

    @admin.action(description="Putuskan Sengketa: Kembalikan Penuh Deposit ke Penyewa")
    def action_kembalikan_penuh(self, request, queryset):
        for dispute in queryset:
            try:
                selesaikan_sengketa_admin(
                    rental=dispute.rental,
                    admin_user=request.user,
                    decision=Dispute.Decision.KEMBALIKAN_PENUH,
                    deduction_amount=0,
                    decision_note="Diputuskan kembalikan penuh melalui tindakan admin."
                )
                self.message_user(request, f"Sengketa {dispute.rental.code} berhasil diselesaikan: Deposit dikembalikan penuh.")
            except Exception as e:
                self.message_user(request, f"Gagal menyelesaikan sengketa {dispute.rental.code}: {e}", level='error')

    @admin.action(description="Putuskan Sengketa: Potong Penuh Deposit ke Pemilik")
    def action_potong_penuh(self, request, queryset):
        for dispute in queryset:
            try:
                selesaikan_sengketa_admin(
                    rental=dispute.rental,
                    admin_user=request.user,
                    decision=Dispute.Decision.POTONG_PENUH,
                    deduction_amount=dispute.rental.deposit_total,
                    decision_note="Diputuskan potong penuh melalui tindakan admin."
                )
                self.message_user(request, f"Sengketa {dispute.rental.code} berhasil diselesaikan: Deposit dipotong penuh untuk pemilik.")
            except Exception as e:
                self.message_user(request, f"Gagal menyelesaikan sengketa {dispute.rental.code}: {e}", level='error')

    @admin.action(description="Putuskan Klaim Dana Gotong Royong ke Pemilik Barang")
    def action_klaim_dana_proteksi(self, request, queryset):
        for dispute in queryset:
            try:
                nominal = proses_klaim_dana_proteksi_admin(dispute.rental, request.user, note="Admin action via DisputeAdmin")
                self.message_user(request, f"Klaim Dana Gotong Royong sebesar Rp{nominal:,} berhasil dicairkan untuk {dispute.rental.code}.")
            except Exception as e:
                self.message_user(request, f"Gagal mencairkan klaim proteksi untuk {dispute.rental.code}: {e}", level='error')


@admin.register(RentalAgreement)
class RentalAgreementAdmin(admin.ModelAdmin):
    list_display = ('rental', 'accepted_at')
    raw_id_fields = ('rental',)


@admin.register(HandoverSchedule)
class HandoverScheduleAdmin(admin.ModelAdmin):
    list_display = ('rental', 'proposed_by', 'meet_at', 'meeting_point', 'status', 'created_at')
    list_filter = ('status',)
    raw_id_fields = ('rental', 'proposed_by')

