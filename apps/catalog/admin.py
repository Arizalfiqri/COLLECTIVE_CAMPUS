from django.contrib import admin
from .models import Category, Item, ItemPhoto


from django.utils.html import format_html


class ItemPhotoInline(admin.TabularInline):
    model = ItemPhoto
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'order')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order',)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        'title_display', 'owner', 'category',
        'harga_display', 'deposit_display',
        'tier_display', 'tahan_ktm_display', 'status_aktif_display',
        'dibuat_display'
    )
    list_filter = ('is_active', 'min_renter_tier', 'require_ktm_held', 'condition', 'category')
    search_fields = ('title', 'description', 'owner__username', 'owner__full_name')
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ('owner',)
    inlines = [ItemPhotoInline]
    list_per_page = 20
    actions = ['turunkan_barang_dengan_alasan']

    def title_display(self, obj):
        short = obj.title if len(obj.title) <= 32 else f"{obj.title[:30]}..."
        return format_html('<span title="{}">{}</span>', obj.title, short)
    title_display.short_description = "Barang"
    title_display.admin_order_field = 'title'

    def harga_display(self, obj):
        return f"Rp{int(obj.price_per_day):,}".replace(',', '.') + "/hr"
    harga_display.short_description = "Harga/hari"
    harga_display.admin_order_field = 'price_per_day'

    def deposit_display(self, obj):
        return f"Rp{int(obj.deposit_amount):,}".replace(',', '.')
    deposit_display.short_description = "Deposit"
    deposit_display.admin_order_field = 'deposit_amount'

    def tier_display(self, obj):
        label = obj.get_min_renter_tier_display()
        return format_html(
            '<span style="background:#E6ECFB; color:#1F45C4; padding:2px 8px; border-radius:10px; font-weight:600; font-size:11px; white-space:nowrap;">{}</span>',
            label
        )
    tier_display.short_description = "Min. tier"
    tier_display.admin_order_field = 'min_renter_tier'

    def tahan_ktm_display(self, obj):
        if obj.require_ktm_held:
            return format_html('<span style="background:#FFF0D1; color:#9A5B00; padding:2px 8px; border-radius:10px; font-weight:600; font-size:11px;">Wajib</span>')
        return format_html('<span style="color:#566074; font-size:11px;">Tidak</span>')
    tahan_ktm_display.short_description = "Tahan KTM"
    tahan_ktm_display.admin_order_field = 'require_ktm_held'

    def status_aktif_display(self, obj):
        if obj.is_active:
            return format_html('<span style="background:#DDF1E8; color:#0A5C43; padding:2px 8px; border-radius:10px; font-weight:600; font-size:11px;">Aktif</span>')
        return format_html('<span style="background:#FDE7E4; color:#B42318; padding:2px 8px; border-radius:10px; font-weight:600; font-size:11px;">Nonaktif</span>')
    status_aktif_display.short_description = "Status"
    status_aktif_display.admin_order_field = 'is_active'

    def dibuat_display(self, obj):
        if not obj.created_at:
            return '-'
        from django.utils import dateformat, timezone
        return dateformat.format(timezone.localtime(obj.created_at), 'd M Y')
    dibuat_display.short_description = "Dibuat"
    dibuat_display.admin_order_field = 'created_at'

    @admin.action(description="Turunkan barang terpilih dengan alasan wajib")
    def turunkan_barang_dengan_alasan(self, request, queryset):
        if request.POST.get('confirm') == 'yes':
            reason = request.POST.get('reason', '').strip()
            if not reason:
                from django.contrib import messages
                self.message_user(request, "Alasan penurunan barang wajib diisi!", level=messages.ERROR)
                from django.template.response import TemplateResponse
                return TemplateResponse(request, 'admin/catalog/item/take_down_intermediate.html', {
                    'items': queryset,
                    'title': 'Konfirmasi Penurunan Barang',
                })
            from apps.core.models import Notification
            count = 0
            for item in queryset:
                item.is_active = False
                item.save(update_fields=['is_active'])
                Notification.notify(
                    user=item.owner,
                    title="Barang Diturunkan oleh Moderator",
                    message=f"Barang Anda '{item.title}' telah dinonaktifkan oleh moderator platform. Alasan: {reason}",
                    url=f"/katalog/{item.slug}/"
                )
                count += 1
            from django.contrib import messages
            self.message_user(request, f"{count} barang berhasil diturunkan dan pemilik telah diberi notifikasi.", level=messages.SUCCESS)
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(request.get_full_path())

        from django.template.response import TemplateResponse
        return TemplateResponse(request, 'admin/catalog/item/take_down_intermediate.html', {
            'items': queryset,
            'title': 'Konfirmasi Penurunan Barang',
        })


@admin.register(ItemPhoto)
class ItemPhotoAdmin(admin.ModelAdmin):
    list_display = ('item', 'order', 'created_at')
    raw_id_fields = ('item',)
