import hashlib
import logging
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Avg
from django.utils import timezone

logger = logging.getLogger(__name__)


class SaleOrderError(Exception):
    """Base exception untuk operasi pesanan jual beli."""
    pass


class SaleOrderStateError(SaleOrderError):
    """Pengecualian saat transisi status pesanan jual beli tidak valid."""
    pass


class SaleOrderPermissionError(SaleOrderError):
    """Pengecualian saat pengguna tidak memiliki izin memicu aksi."""
    pass


class SaleOrderValidationError(SaleOrderError):
    """Pengecualian saat validasi parameter pesanan gagal."""
    pass


SELLER_TIER_LABELS = {
    'baru': 'Penjual baru',
    'tepercaya': 'Penjual tepercaya',
    'sangat_tepercaya': 'Penjual sangat tepercaya',
}

SELLER_TIER_CHIP_CLASSES = {
    'baru': 'bg-paper-deep text-ink-muted border border-line',
    'tepercaya': 'bg-amber-tint text-amber-text border border-line',
    'sangat_tepercaya': 'bg-pine-tint text-pine-dark border border-line',
}


def get_seller_tier(user):
    """
    Menghitung tingkat penjual sesuai Fase 8A Butir 3:
    - Sebelum ada penjualan: semua penjual berstatus 'baru'.
    - 'tepercaya': 5 penjualan selesai tanpa sengketa dan rating rata-rata >= 4.5.
    - 'sangat_tepercaya': 15 penjualan selesai tanpa sengketa dan rating rata-rata >= 4.7.
    - Default/lainnya: 'baru'.
    """
    if not user or not user.is_authenticated:
        return 'baru'

    # Dukungan override/mock langsung pada user (berguna untuk testing atau kebijakan staf)
    explicit_tier = getattr(user, 'seller_tier', None) or getattr(user, '_seller_tier', None)
    if explicit_tier in ('baru', 'tepercaya', 'sangat_tepercaya'):
        return explicit_tier

    # 1. Jumlah penjualan selesai
    completed_sales = getattr(user, '_seller_completed_sales', None)
    if completed_sales is None:
        from apps.sales.models import SaleItem
        completed_sales = SaleItem.objects.filter(
            owner=user,
            status=SaleItem.Status.TERJUAL
        ).count()

    # 2. Jumlah sengketa penjualan
    disputes_count = getattr(user, '_seller_disputes_count', None)
    if disputes_count is None:
        from apps.sales.models import SaleDispute
        disputes_count = (
            SaleDispute.objects.filter(
                order__seller=user,
                status=SaleDispute.Status.SELESAI
            ).exclude(
                decision=SaleDispute.Decision.LEPAS_KE_PENJUAL
            ).count()
            + SaleDispute.objects.filter(
                order__seller=user,
                seller_violation_recorded=True
            ).count()
        )

    # 3. Rating rata-rata ulasan yang diterima
    # 3. Rating rata-rata ulasan yang diterima (gabungan ulasan jual beli & sewa)
    avg_rating = getattr(user, '_seller_rating', None)
    if avg_rating is None:
        from apps.sales.models import SaleReview
        from apps.rentals.models import Review

        sale_ratings = list(
            SaleReview.objects.filter(
                reviewee=user,
                role=SaleReview.Role.PENJUAL
            ).values_list('rating', flat=True)
        )
        rental_ratings = list(
            Review.objects.filter(
                reviewee=user,
                as_role='pemilik'
            ).values_list('rating', flat=True)
        )
        all_ratings = sale_ratings + rental_ratings
        if all_ratings:
            avg_rating = sum(all_ratings) / len(all_ratings)
        else:
            avg_rating = None

    if completed_sales >= 15 and disputes_count == 0 and avg_rating is not None and avg_rating >= 4.7:
        return 'sangat_tepercaya'
    elif completed_sales >= 5 and disputes_count == 0 and avg_rating is not None and avg_rating >= 4.5:
        return 'tepercaya'
    return 'baru'



def get_seller_max_price(user_or_tier):
    """
    Mendapatkan batas harga maksimum sesuai tingkat penjual:
    - baru: SALE_MAX_PRICE_NEW (default Rp1.000.000)
    - tepercaya: SALE_MAX_PRICE_TRUSTED (default Rp3.000.000)
    - sangat_tepercaya: SALE_MAX_PRICE_TOP (default Rp8.000.000)
    """
    if isinstance(user_or_tier, str):
        tier = user_or_tier
    else:
        tier = get_seller_tier(user_or_tier)

    if tier == 'sangat_tepercaya':
        return getattr(settings, 'SALE_MAX_PRICE_TOP', 8000000)
    elif tier == 'tepercaya':
        return getattr(settings, 'SALE_MAX_PRICE_TRUSTED', 3000000)
    return getattr(settings, 'SALE_MAX_PRICE_NEW', 1000000)


def check_prohibited_keywords(*texts):
    """
    Memeriksa teks terhadap daftar kata kunci terlarang dari pengaturan.
    Mengembalikan (is_prohibited, matched_keyword).
    """
    prohibited_list = getattr(settings, 'SALE_PROHIBITED_KEYWORDS', [
        'obat resep', 'obat keras', 'miras', 'minuman keras', 'alkohol',
        'rokok', 'vape', 'pod', 'liquid vape', 'senjata', 'senjata tajam',
        'senapan', 'hewan', 'binatang', 'kucing', 'anjing',
        'makanan olahan', 'makanan basah', 'barang palsu', 'barang curian',
        'kw super', 'clone', 'akun digital', 'akun game', 'topup game',
    ])
    combined_text = ' '.join(str(t or '').lower() for t in texts)
    for kw in prohibited_list:
        kw_clean = kw.lower().strip()
        if not kw_clean:
            continue
        if kw_clean in combined_text:
            return True, kw_clean
    return False, None


def get_active_seller_terms():
    """Mengambil versi aktif terbaru Syarat & Ketentuan Penjual."""
    from apps.core.models import TermsVersion
    return TermsVersion.get_active_terms(term_type='jual_penjual')


def record_seller_terms_acceptance(user, terms_version, ip_address=None, user_agent=''):
    """Mencatat persetujuan S&K Penjual lengkap dengan hash SHA-256 dan snapshot teks."""
    from apps.sales.models import SellerTermsAcceptance
    terms_hash = terms_version.calculate_sha256()
    return SellerTermsAcceptance.objects.create(
        user=user,
        terms_version=terms_version,
        terms_hash=terms_hash,
        text_snapshot=terms_version.content,
        ip_address=ip_address,
        user_agent=str(user_agent)[:500] if user_agent else '',
    )


def extend_sale_item_listing(sale_item):
    """
    Memperpanjang listing barang jualan selama 60 hari.
    Bila sebelumnya kedaluwarsa, aktifkan kembali.
    """
    import datetime
    from django.utils import timezone
    now = timezone.now()
    base_time = sale_item.expires_at if (sale_item.expires_at and sale_item.expires_at > now) else now
    sale_item.expires_at = base_time + datetime.timedelta(days=60)
    if sale_item.status == sale_item.Status.KEDALUWARSA:
        sale_item.status = sale_item.Status.AKTIF
    sale_item.save(update_fields=['expires_at', 'status', 'updated_at'])
    return sale_item


def calculate_sale_commission(price):
    """Menghitung komisi platform untuk penjualan barang: 5% dengan batas minimal Rp2.000."""
    percent = getattr(settings, 'SALE_COMMISSION_PERCENT', 5)
    min_amount = getattr(settings, 'SALE_COMMISSION_MIN', 2000)
    calculated = int(round(price * (percent / 100.0)))
    commission = max(calculated, min_amount)
    return min(commission, price)


def get_active_buyer_terms():
    """Mengambil versi aktif terbaru Syarat & Ketentuan Pembeli."""
    from apps.core.models import TermsVersion
    return TermsVersion.get_active_terms(term_type='jual_pembeli')


def record_buyer_terms_agreement(order, buyer, terms_version, ip_address=None, user_agent=''):
    """Mencatat persetujuan S&K Pembeli lengkap dengan hash SHA-256 dan snapshot teks."""
    from apps.sales.models import SaleAgreement
    terms_hash = terms_version.calculate_sha256() if terms_version else ''
    content = terms_version.content if terms_version else ''
    return SaleAgreement.objects.create(
        order=order,
        buyer=buyer,
        terms_version=terms_version,
        terms_hash=terms_hash,
        text_snapshot=content,
        ip_address=ip_address,
        user_agent=str(user_agent)[:500] if user_agent else '',
    )


@transaction.atomic
def create_sale_order(item, buyer, terms_accepted=False, ip_address=None, user_agent='', agreed_price=None):
    """
    Membuat pesanan jual beli baru secara atomik:
    - Validasi pembeli: terautentikasi, terverifikasi KTM, bukan barang milik sendiri, akun tidak dibekukan, tanpa tagihan tambahan.
    - Mengunci baris barang dengan select_for_update() untuk mencegah double-order / jual ganda.
    - Status barang berubah menjadi 'dipesan'.
    - Membuat snapshot listing beku (judul, deskripsi, kondisi, foto + hash SHA-256).
    - Menghitung komisi & net_to_seller (menggunakan agreed_price jika disediakan dari tawaran yang diterima).
    - Menetapkan batas waktu bayar: SALE_PAYMENT_DEADLINE_HOURS (default 6 jam).
    - Mencatat perjanjian pembelian (SaleAgreement) dengan verifikasi hash SHA-256 S&K.
    """
    from apps.sales.models import SaleItem, SaleOrder
    from apps.core.models import Notification

    if not buyer or not buyer.is_authenticated:
        raise SaleOrderValidationError("Silakan masuk terlebih dahulu untuk membeli barang.")

    if not getattr(buyer, 'email_verified', True):
        raise SaleOrderValidationError("Email Anda belum terverifikasi.")

    profile = getattr(buyer, 'student_profile', None)
    if not profile or not getattr(buyer, 'is_verified_student', False):
        raise SaleOrderValidationError("Anda wajib memverifikasi KTM terlebih dahulu sebelum membeli barang.")

    if not buyer.is_active:
        raise SaleOrderValidationError("Akun Anda sedang dinonaktifkan.")

    from apps.payments.models import ExtraCharge
    if ExtraCharge.objects.filter(rental__renter=buyer, status='unpaid').exists():
        raise SaleOrderValidationError("Anda memiliki tagihan tambahan yang belum dilunasi. Lunasi terlebih dahulu di dasbor.")

    if buyer == item.owner:
        raise SaleOrderValidationError("Anda tidak dapat membeli barang milik sendiri.")

    if not terms_accepted:
        raise SaleOrderValidationError("Anda wajib mencentang persetujuan Syarat & Ketentuan Pembeli.")

    locked_item = SaleItem.objects.select_for_update().get(id=item.id)
    if locked_item.status != SaleItem.Status.AKTIF or locked_item.is_expired:
        raise SaleOrderValidationError("Barang ini sedang tidak aktif atau sudah dipesan/terjual.")

    locked_item.status = SaleItem.Status.DIPESAN
    locked_item.save(update_fields=['status', 'updated_at'])

    order_price = int(agreed_price) if agreed_price is not None else locked_item.price
    commission = calculate_sale_commission(order_price)
    net_to_seller = order_price - commission

    deadline_hours = getattr(settings, 'SALE_PAYMENT_DEADLINE_HOURS', 6)
    reserved_until = timezone.now() + timedelta(hours=deadline_hours)

    photos_data = []
    for photo in locked_item.photos.all():
        p_hash = ''
        try:
            if photo.image:
                photo.image.open('rb')
                p_hash = hashlib.sha256(photo.image.read()).hexdigest()
        except Exception:
            p_hash = ''
        photos_data.append({
            'url': photo.image.url if photo.image else '',
            'order': photo.order,
            'hash': p_hash,
        })

    snapshot = {
        'title': locked_item.title,
        'description': locked_item.description,
        'condition': locked_item.condition,
        'condition_display': locked_item.get_condition_display(),
        'flaws': locked_item.flaws,
        'included_items': locked_item.included_items,
        'pickup_area': locked_item.pickup_area,
        'category_name': locked_item.category.name if locked_item.category else '',
        'category_slug': locked_item.category.slug if locked_item.category else '',
        'price': locked_item.price,
        'original_price': locked_item.original_price,
        'photos': photos_data,
        'photos_hashes': [p['hash'] for p in photos_data if p['hash']],
    }

    order = SaleOrder.objects.create(
        item=locked_item,
        buyer=buyer,
        seller=locked_item.owner,
        price_snapshot=order_price,
        listing_snapshot=snapshot,
        commission=commission,
        net_to_seller=net_to_seller,
        status=SaleOrder.Status.MENUNGGU_PEMBAYARAN,
        reserved_until=reserved_until,
    )

    terms_version = get_active_buyer_terms()
    record_buyer_terms_agreement(
        order=order,
        buyer=buyer,
        terms_version=terms_version,
        ip_address=ip_address,
        user_agent=user_agent
    )

    Notification.notify(
        user=locked_item.owner,
        title="Pesanan baru masuk",
        message=f"Ada pesanan baru {order.code} untuk '{locked_item.title}'. Menunggu pembayaran dari pembeli.",
        url=f"/pesanan/{order.code}/"
    )

    return order


@transaction.atomic
def mark_sale_order_paid(order, payment_type='', transaction_id='', raw_response=None):
    """
    Menandai pesanan jual beli telah dibayar (settlement dari Midtrans):
    - Idempoten: bila sudah dibayar/diserahkan/selesai, abaikan tanpa error.
    - Status berubah menjadi 'dibayar'.
    - Mencatat buku besar MASUK_PENJUALAN sebesar harga barang.
    - Mengirim notifikasi ke penjual dan pembeli.
    """
    from apps.sales.models import SaleOrder
    from apps.payments.models import LedgerEntry
    from apps.core.models import Notification

    locked_order = SaleOrder.objects.select_for_update().get(id=order.id)
    if locked_order.status != SaleOrder.Status.MENUNGGU_PEMBAYARAN:
        return locked_order  # Idempoten

    locked_order.status = SaleOrder.Status.DIBAYAR
    locked_order.paid_at = timezone.now()
    locked_order.save(update_fields=['status', 'paid_at', 'updated_at'])

    if not locked_order.ledger_entries.filter(kind=LedgerEntry.Kind.MASUK_PENJUALAN).exists():
        LedgerEntry.objects.create(
            sale_order=locked_order,
            kind=LedgerEntry.Kind.MASUK_PENJUALAN,
            amount=locked_order.price_snapshot,
            note=f"Pembayaran masuk pesanan {locked_order.code}"
        )

    Notification.notify(
        user=locked_order.seller,
        title="Pembayaran pesanan diterima",
        message=f"Pembayaran untuk pesanan {locked_order.code} telah diterima. Silakan hubungi pembeli dan atur jadwal temu.",
        url=f"/pesanan/{locked_order.code}/"
    )
    Notification.notify(
        user=locked_order.buyer,
        title="Pembayaran berhasil",
        message=f"Pembayaran untuk pesanan {locked_order.code} berhasil diverifikasi. Kontak penjual telah dibuka.",
        url=f"/pesanan/{locked_order.code}/"
    )
    return locked_order


@transaction.atomic
def set_sale_order_meetup(order, user, meetup_at, meeting_point=None):
    """Mengatur atau memperbarui jadwal temu dan lokasi serah terima."""
    from apps.sales.models import SaleOrder
    from apps.core.models import Notification

    locked_order = SaleOrder.objects.select_for_update().get(id=order.id)
    if user != locked_order.seller and user != locked_order.buyer and not getattr(user, 'is_staff', False):
        raise SaleOrderPermissionError("Anda tidak berhak mengatur jadwal temu pesanan ini.")

    if locked_order.status not in (SaleOrder.Status.DIBAYAR, SaleOrder.Status.MENUNGGU_PEMBAYARAN):
        raise SaleOrderStateError(f"Pesanan berstatus '{locked_order.status}', tidak dapat mengubah jadwal temu.")

    locked_order.meetup_at = meetup_at
    if meeting_point is not None:
        seller_campus = getattr(getattr(locked_order.seller, 'student_profile', None), 'campus', None)
        buyer_campus = getattr(getattr(locked_order.buyer, 'student_profile', None), 'campus', None)
        if seller_campus and buyer_campus and seller_campus != buyer_campus:
            if not getattr(meeting_point, 'is_public', True):
                raise SaleOrderValidationError("Untuk serah terima lintas kampus, wajib memilih titik temu publik kampus.")
        locked_order.meeting_point = meeting_point
    locked_order.save(update_fields=['meetup_at', 'meeting_point', 'updated_at'])

    other_user = locked_order.buyer if user == locked_order.seller else locked_order.seller
    Notification.notify(
        user=other_user,
        title="Jadwal temu diperbarui",
        message=f"Jadwal temu untuk pesanan {locked_order.code} telah diperbarui oleh {user.username}.",
        url=f"/pesanan/{locked_order.code}/"
    )
    return locked_order


@transaction.atomic
def mark_sale_order_handed_over(order, user, notes='', photo_file=None):
    """
    Penjual menandai barang sudah diserahkan:
    - Hanya penjual atau staf yang berhak.
    - Status harus 'dibayar'.
    - Berubah menjadi 'diserahkan', handed_over_at dicatat.
    - Opsional foto serah terima disimpan privat di private_media/sales_handovers/.
    - Pembeli memiliki masa inspeksi SALE_INSPECTION_HOURS (48 jam).
    """
    from pathlib import Path
    import uuid
    from PIL import Image
    import io
    from apps.sales.models import SaleOrder
    from apps.core.models import Notification

    locked_order = SaleOrder.objects.select_for_update().get(id=order.id)
    if user != locked_order.seller and not getattr(user, 'is_staff', False):
        raise SaleOrderPermissionError("Hanya penjual yang dapat menandai serah terima barang.")

    if locked_order.status != SaleOrder.Status.DIBAYAR:
        raise SaleOrderStateError(f"Pesanan berstatus '{locked_order.status}', tidak dapat diserahkan.")

    locked_order.status = SaleOrder.Status.DISERAHKAN
    locked_order.handed_over_at = timezone.now()

    saved_photo_path = None
    if photo_file:
        try:
            target_dir = Path(settings.PRIVATE_MEDIA_ROOT) / 'sales_handovers'
            target_dir.mkdir(parents=True, exist_ok=True)
            img = Image.open(photo_file)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            max_side = 1280
            w, h = img.size
            if w > max_side or h > max_side:
                ratio = min(max_side / w, max_side / h)
                img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=80, optimize=True)
            output.seek(0)

            filename = f"{locked_order.code}_handover_{uuid.uuid4().hex[:8]}.jpg"
            filepath = target_dir / filename
            with open(filepath, 'wb') as f:
                f.write(output.read())
            saved_photo_path = f"sales_handovers/{filename}"
        except Exception as e:
            logger.warning(f"Gagal memproses foto serah terima pesanan {locked_order.code}: {e}")

    snapshot = dict(locked_order.listing_snapshot or {})
    if saved_photo_path:
        snapshot['handover_photo'] = saved_photo_path
    if notes:
        snapshot['handover_notes'] = notes
    locked_order.listing_snapshot = snapshot

    locked_order.save(update_fields=['status', 'handed_over_at', 'listing_snapshot', 'updated_at'])

    inspection_hours = getattr(settings, 'SALE_INSPECTION_HOURS', 48)
    Notification.notify(
        user=locked_order.buyer,
        title="Barang telah diserahkan",
        message=f"Penjual telah menyerahkan barang untuk pesanan {locked_order.code}. Anda memiliki {inspection_hours} jam untuk memeriksa barang dan mengonfirmasi penerimaan.",
        url=f"/pesanan/{locked_order.code}/"
    )
    return locked_order



def confirm_sale_order_received(order, user):
    """Pembeli mengonfirmasi bahwa barang diterima sesuai deskripsi."""
    if user != order.buyer and not getattr(user, 'is_staff', False):
        raise SaleOrderPermissionError("Hanya pembeli yang dapat mengonfirmasi penerimaan barang.")
    if order.status != order.Status.DISERAHKAN:
        raise SaleOrderStateError(f"Pesanan berstatus '{order.status}', belum diserahkan.")
    return settle_sale_order(order, actor=user)


@transaction.atomic
def settle_sale_order(order, actor=None):
    """
    Penyelesaian pesanan jual beli idempoten:
    - Status menjadi 'selesai', completed_at terisi.
    - Barang jualan status menjadi 'terjual'.
    - Buku besar dicatat:
      * keluar_komisi_penjualan (sebesar komisi)
      * keluar_payout_penjual (sebesar net_to_seller)
    - Dompet penjual dikredit kredit_penjualan sebesar net_to_seller.
    - Invarian buku besar diverifikasi: total masuk == total keluar.
    """
    from apps.sales.models import SaleOrder, SaleItem
    from apps.payments.models import LedgerEntry, WalletTransaction
    from apps.core.models import Notification

    locked_order = SaleOrder.objects.select_for_update().get(id=order.id)
    if locked_order.status == SaleOrder.Status.SELESAI:
        return locked_order  # Idempoten

    if locked_order.status not in (SaleOrder.Status.DISERAHKAN, SaleOrder.Status.SENGKETA):
        raise SaleOrderStateError(f"Pesanan berstatus '{locked_order.status}', tidak dapat diselesaikan.")

    commission = locked_order.commission or calculate_sale_commission(locked_order.price_snapshot)
    net_to_seller = locked_order.price_snapshot - commission

    locked_order.status = SaleOrder.Status.SELESAI
    locked_order.completed_at = timezone.now()
    locked_order.commission = commission
    locked_order.net_to_seller = net_to_seller
    locked_order.save(update_fields=['status', 'completed_at', 'commission', 'net_to_seller', 'updated_at'])

    # Update item menjadi terjual
    item = locked_order.item
    item.status = SaleItem.Status.TERJUAL
    item.save(update_fields=['status', 'updated_at'])

    # Pastikan masuk_penjualan ada di buku besar
    if not locked_order.ledger_entries.filter(kind=LedgerEntry.Kind.MASUK_PENJUALAN).exists():
        LedgerEntry.objects.create(
            sale_order=locked_order,
            kind=LedgerEntry.Kind.MASUK_PENJUALAN,
            amount=locked_order.price_snapshot,
            note=f"Pembayaran masuk pesanan {locked_order.code}"
        )

    # Catat buku besar keluar
    if not locked_order.ledger_entries.filter(kind=LedgerEntry.Kind.KELUAR_KOMISI_PENJUALAN).exists():
        LedgerEntry.objects.create(
            sale_order=locked_order,
            kind=LedgerEntry.Kind.KELUAR_KOMISI_PENJUALAN,
            amount=commission,
            note=f"Komisi platform untuk pesanan {locked_order.code}"
        )

    if not locked_order.ledger_entries.filter(kind=LedgerEntry.Kind.KELUAR_PAYOUT_PENJUAL).exists():
        LedgerEntry.objects.create(
            sale_order=locked_order,
            kind=LedgerEntry.Kind.KELUAR_PAYOUT_PENJUAL,
            amount=net_to_seller,
            note=f"Penerusan hasil penjualan pesanan {locked_order.code} ke penjual"
        )

    # Kredit dompet penjual
    if not WalletTransaction.objects.filter(sale_order=locked_order, kind=WalletTransaction.Kind.KREDIT_PENJUALAN).exists():
        WalletTransaction.objects.create(
            user=locked_order.seller,
            sale_order=locked_order,
            kind=WalletTransaction.Kind.KREDIT_PENJUALAN,
            amount=net_to_seller,
            note=f"Hasil penjualan barang '{item.title}' ({locked_order.code})"
        )

    # Invarian check: total_masuk == total_keluar
    total_masuk = sum(locked_order.ledger_entries.filter(kind__startswith='masuk_').values_list('amount', flat=True))
    total_keluar = sum(locked_order.ledger_entries.filter(kind__startswith='keluar_').values_list('amount', flat=True))
    if total_masuk != total_keluar:
        raise SaleOrderError(f"Invarian buku besar tidak seimbang: masuk {total_masuk} != keluar {total_keluar}")

    Notification.notify(
        user=locked_order.seller,
        title="Pesanan selesai - Dana diterima",
        message=f"Pesanan {locked_order.code} telah selesai. Saldo sebesar Rp{net_to_seller:,} telah masuk ke dompet Anda.",
        url="/dompet/"
    )
    Notification.notify(
        user=locked_order.buyer,
        title="Pesanan selesai",
        message=f"Terima kasih telah bertransaksi! Pesanan {locked_order.code} telah selesai.",
        url=f"/pesanan/{locked_order.code}/"
    )
    return locked_order


@transaction.atomic
def cancel_sale_order(order, user=None, reason=''):
    """
    Membatalkan pesanan jual beli:
    - Sebelum bayar: bebas dibatalkan oleh pembeli, penjual, atau sistem. Barang lepas kembali ke status 'aktif'.
    - Setelah bayar (dibayar / diserahkan): hanya boleh dibatalkan oleh penjual, sistem (kedaluwarsa temu 7 hari), atau admin.
      Dana pembeli direfund penuh ke dompet (kredit_refund_penjualan).
      Buku besar dicatat keluar_refund_penyewa / seimbang.
      Barang lepas kembali ke status 'aktif'.
    """
    from apps.sales.models import SaleOrder, SaleItem
    from apps.payments.models import LedgerEntry, WalletTransaction, Payment
    from apps.core.models import Notification

    locked_order = SaleOrder.objects.select_for_update().get(id=order.id)
    if locked_order.status in (SaleOrder.Status.SELESAI, SaleOrder.Status.DIBATALKAN, SaleOrder.Status.KEDALUWARSA):
        return locked_order  # Idempoten

    if locked_order.status == SaleOrder.Status.MENUNGGU_PEMBAYARAN:
        if user and user != locked_order.buyer and user != locked_order.seller and not getattr(user, 'is_staff', False):
            raise SaleOrderPermissionError("Anda tidak berhak membatalkan pesanan ini.")

        locked_order.status = SaleOrder.Status.DIBATALKAN
        locked_order.cancelled_by = user
        locked_order.cancel_reason = reason or "Dibatalkan sebelum pembayaran"
        locked_order.save(update_fields=['status', 'cancelled_by', 'cancel_reason', 'updated_at'])

        locked_item = locked_order.item
        if locked_item.status == SaleItem.Status.DIPESAN:
            locked_item.status = SaleItem.Status.AKTIF
            locked_item.save(update_fields=['status', 'updated_at'])

        Payment.objects.filter(sale_order=locked_order, status=Payment.Status.PENDING).update(status=Payment.Status.CANCEL)

        return locked_order

    if locked_order.status in (SaleOrder.Status.DIBAYAR, SaleOrder.Status.DISERAHKAN, SaleOrder.Status.SENGKETA):
        if user and user != locked_order.seller and not getattr(user, 'is_staff', False):
            raise SaleOrderPermissionError("Setelah pembayaran, pembatalan hanya dapat dilakukan oleh penjual atau keputusan admin.")

        locked_order.status = SaleOrder.Status.DIBATALKAN
        locked_order.cancelled_by = user
        locked_order.cancel_reason = reason or "Dibatalkan setelah pembayaran"
        locked_order.save(update_fields=['status', 'cancelled_by', 'cancel_reason', 'updated_at'])

        locked_item = locked_order.item
        if locked_item.status == SaleItem.Status.DIPESAN:
            locked_item.status = SaleItem.Status.AKTIF
            locked_item.save(update_fields=['status', 'updated_at'])

        if not WalletTransaction.objects.filter(sale_order=locked_order, kind=WalletTransaction.Kind.KREDIT_REFUND_PENJUALAN).exists():
            WalletTransaction.objects.create(
                user=locked_order.buyer,
                sale_order=locked_order,
                kind=WalletTransaction.Kind.KREDIT_REFUND_PENJUALAN,
                amount=locked_order.price_snapshot,
                note=f"Pengembalian dana pembatalan pesanan {locked_order.code}"
            )

        if not locked_order.ledger_entries.filter(kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA).exists():
            LedgerEntry.objects.create(
                sale_order=locked_order,
                kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA,
                amount=locked_order.price_snapshot,
                note=f"Keluar refund pesanan {locked_order.code}"
            )

        total_masuk = sum(locked_order.ledger_entries.filter(kind__startswith='masuk_').values_list('amount', flat=True))
        total_keluar = sum(locked_order.ledger_entries.filter(kind__startswith='keluar_').values_list('amount', flat=True))
        if total_masuk != total_keluar:
            raise SaleOrderError(f"Invarian buku besar refund tidak seimbang: masuk {total_masuk} != keluar {total_keluar}")

        Notification.notify(
            user=locked_order.buyer,
            title="Pesanan dibatalkan & Dana dikembalikan",
            message=f"Pesanan {locked_order.code} telah dibatalkan. Dana sebesar Rp{locked_order.price_snapshot:,} telah dikembalikan ke dompet Anda.",
            url="/dompet/"
        )
        Notification.notify(
            user=locked_order.seller,
            title="Pesanan dibatalkan",
            message=f"Pesanan {locked_order.code} telah dibatalkan. Barang telah dikembalikan ke katalog aktif.",
            url=f"/pesanan/{locked_order.code}/"
        )
        return locked_order

    raise SaleOrderStateError(f"Pesanan berstatus '{locked_order.status}', tidak dapat dibatalkan.")


@transaction.atomic
def expire_sale_order(order):
    """Kedaluwarsa pesanan yang belum dibayar melewati batas waktu."""
    from apps.sales.models import SaleOrder, SaleItem
    from apps.core.models import Notification

    locked_order = SaleOrder.objects.select_for_update().get(id=order.id)
    if locked_order.status != SaleOrder.Status.MENUNGGU_PEMBAYARAN:
        return locked_order

    locked_order.status = SaleOrder.Status.KEDALUWARSA
    locked_order.cancel_reason = "Batas waktu pembayaran telah terlewati."
    locked_order.save(update_fields=['status', 'cancel_reason', 'updated_at'])

    locked_item = locked_order.item
    if locked_item.status == SaleItem.Status.DIPESAN:
        locked_item.status = SaleItem.Status.AKTIF
        locked_item.save(update_fields=['status', 'updated_at'])

    Notification.notify(
        user=locked_order.buyer,
        title="Batas waktu pembayaran habis",
        message=f"Batas waktu pembayaran untuk pesanan {locked_order.code} telah kedaluwarsa. Pesanan dibatalkan otomatis.",
        url=f"/pesanan/{locked_order.code}/"
    )
    Notification.notify(
        user=locked_order.seller,
        title="Pesanan kedaluwarsa",
        message=f"Pembeli tidak menyelesaikan pembayaran untuk pesanan {locked_order.code}. Barang '{locked_item.title}' telah kembali aktif di katalog.",
        url=f"/pesanan/{locked_order.code}/"
    )
    return locked_order


@transaction.atomic
def open_sale_dispute(order, user, reason='', photo_files=None, evidence_notes='', dispute_type='lainnya'):
    """
    Pembeli mengajukan sengketa barang dalam masa pemeriksaan:
    - Status harus 'diserahkan'.
    - Status beralih ke 'sengketa'.
    - Membuat atau memperbarui rekaman SaleDispute resmi.
    - Foto bukti (maks. 3 foto) disimpan secara privat di private_media/sales_disputes/.
    - Bila jenis sengketa adalah 'penjual_tidak_hadir', pelanggaran penjual dicatat seketika.
    """
    from pathlib import Path
    import uuid
    from PIL import Image
    import io
    from apps.sales.models import SaleOrder, SaleDispute
    from apps.core.models import Notification

    # Penanganan fleksibel bila urutan argumen posisi ditukar
    if reason in SaleDispute.Type.values and (not photo_files or isinstance(photo_files, str)):
        actual_type = reason
        actual_reason = str(photo_files or evidence_notes or actual_type)
        photo_files = evidence_notes if isinstance(evidence_notes, list) else None
        reason = actual_reason
        dispute_type = actual_type

    locked_order = SaleOrder.objects.select_for_update().get(id=order.id)
    if user != locked_order.buyer and not getattr(user, 'is_staff', False):
        raise SaleOrderPermissionError("Hanya pembeli yang dapat mengajukan sengketa.")

    if not reason or not str(reason).strip():
        raise SaleOrderValidationError("Alasan pelaporan masalah wajib diisi.")

    if locked_order.status != SaleOrder.Status.DISERAHKAN:
        raise SaleOrderStateError(f"Pesanan berstatus '{locked_order.status}', tidak dapat disengketakan.")

    type_map = {
        'rusak': SaleDispute.Type.RUSAK_SAAT_SERAH_TERIMA,
        'rusak_saat_serah_terima': SaleDispute.Type.RUSAK_SAAT_SERAH_TERIMA,
        'tidak_sesuai': SaleDispute.Type.TIDAK_SESUAI_DESKRIPSI,
        'tidak_sesuai_deskripsi': SaleDispute.Type.TIDAK_SESUAI_DESKRIPSI,
        'penjual_tidak_hadir': SaleDispute.Type.PENJUAL_TIDAK_HADIR,
        'palsu': SaleDispute.Type.PALSU,
        'lainnya': SaleDispute.Type.LAINNYA,
    }
    dispute_type = type_map.get(str(dispute_type).lower(), SaleDispute.Type.LAINNYA)

    saved_photo_paths = []
    if photo_files:
        target_dir = Path(settings.PRIVATE_MEDIA_ROOT) / 'sales_disputes'
        target_dir.mkdir(parents=True, exist_ok=True)
        for p_file in photo_files[:3]:
            try:
                img = Image.open(p_file)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                max_side = 1280
                w, h = img.size
                if w > max_side or h > max_side:
                    ratio = min(max_side / w, max_side / h)
                    img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=80, optimize=True)
                output.seek(0)

                filename = f"{locked_order.code}_dispute_{uuid.uuid4().hex[:8]}.jpg"
                filepath = target_dir / filename
                with open(filepath, 'wb') as f:
                    f.write(output.read())
                saved_photo_paths.append(f"sales_disputes/{filename}")
            except Exception as e:
                logger.warning(f"Gagal memproses foto sengketa pesanan {locked_order.code}: {e}")

    cancel_desc = f"Sengketa [{dispute_type}]: {reason.strip()}"
    if saved_photo_paths:
        cancel_desc += f" [Bukti foto privat: {', '.join(saved_photo_paths)}]"

    snapshot = dict(locked_order.listing_snapshot or {})
    if saved_photo_paths:
        snapshot['dispute_photos'] = saved_photo_paths
    locked_order.listing_snapshot = snapshot

    locked_order.status = SaleOrder.Status.SENGKETA
    locked_order.cancel_reason = cancel_desc
    locked_order.save(update_fields=['status', 'cancel_reason', 'listing_snapshot', 'updated_at'])

    # Rekam objek SaleDispute
    is_seller_absent = (dispute_type == SaleDispute.Type.PENJUAL_TIDAK_HADIR)
    dispute, created = SaleDispute.objects.get_or_create(
        order=locked_order,
        defaults={
            'opened_by': user,
            'dispute_type': dispute_type,
            'reason': reason.strip(),
            'evidence_photos': saved_photo_paths,
            'status': SaleDispute.Status.TERBUKA,
            'seller_violation_recorded': is_seller_absent,
            'seller_violation_notes': 'Penjual tidak hadir pada titik temu kampus yang disepakati' if is_seller_absent else '',
        }
    )
    if not created:
        dispute.dispute_type = dispute_type
        dispute.reason = reason.strip()
        if saved_photo_paths:
            dispute.evidence_photos = saved_photo_paths
        if is_seller_absent:
            dispute.seller_violation_recorded = True
            dispute.seller_violation_notes = 'Penjual tidak hadir pada titik temu kampus yang disepakati'
        dispute.status = SaleDispute.Status.TERBUKA
        dispute.save()

    Notification.notify(
        user=locked_order.seller,
        title="Sengketa diajukan pembeli",
        message=f"Pembeli melaporkan masalah untuk pesanan {locked_order.code}: '{reason}'. Admin akan memediasi penyelesaian.",
        url=f"/pesanan/{locked_order.code}/"
    )
    Notification.notify(
        user=locked_order.buyer,
        title="Laporan masalah diterima",
        message=f"Laporan masalah Anda untuk pesanan {locked_order.code} sedang ditinjau oleh admin.",
        url=f"/pesanan/{locked_order.code}/"
    )
    return locked_order


@transaction.atomic
def resolve_sale_dispute(dispute_or_id, decision, nominal=0, notes='', admin_user=None):
    """
    Menyelesaikan sengketa pesanan jual beli secara atomik dan idempoten oleh admin:
    - decision:
      1. 'refund_pembeli': Refund penuh ke dompet pembeli, pesanan dibatalkan, barang kembali aktif.
      2. 'lepas_ke_penjual': Payout penuh ke dompet penjual (dipotong komisi platform 5%), pesanan selesai, barang terjual.
      3. 'sebagian': Pembeli menerima refund sejumlah nominal, sisa dilepas ke penjual (dipotong komisi).
    - Idempoten: Jika sengketa sudah berstatus 'selesai', kembalikan objek tanpa melakukan mutasi buku besar ganda.
    - Menjaga invarian buku besar secara presisi (total masuk escrow = total keluar).
    """
    from apps.sales.models import SaleOrder, SaleItem, SaleDispute
    from apps.payments.models import LedgerEntry, WalletTransaction
    from apps.core.models import Notification

    if isinstance(dispute_or_id, SaleDispute):
        dispute = SaleDispute.objects.select_for_update().get(id=dispute_or_id.id)
    else:
        dispute = SaleDispute.objects.select_for_update().get(id=dispute_or_id)

    if dispute.status == SaleDispute.Status.SELESAI:
        logger.info(f"Sengketa pesanan {dispute.order.code} sudah berstatus selesai (idempoten).")
        return dispute

    order = SaleOrder.objects.select_for_update().select_related('item', 'seller', 'buyer').get(id=dispute.order_id)
    total = order.total_amount

    valid_decisions = [
        SaleDispute.Decision.REFUND_PEMBELI,
        SaleDispute.Decision.LEPAS_KE_PENJUAL,
        SaleDispute.Decision.SEBAGIAN,
    ]
    if decision not in valid_decisions:
        raise SaleOrderValidationError(f"Keputusan sengketa '{decision}' tidak valid.")

    now = timezone.now()

    if decision == SaleDispute.Decision.REFUND_PEMBELI:
        # 1. Refund penuh ke pembeli
        LedgerEntry.objects.create(
            sale_order=order,
            kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA,
            amount=total,
            note=f"Putusan admin sengketa {order.code}: Refund penuh ke pembeli",
        )
        WalletTransaction.objects.create(
            user=order.buyer,
            amount=total,
            kind=WalletTransaction.Kind.KREDIT_REFUND_PENJUALAN,
            sale_order=order,
            note=f"Pengembalian dana putusan sengketa #{order.code}",
        )
        order.status = SaleOrder.Status.DIBATALKAN
        order.cancelled_by = admin_user
        order.cancel_reason = f"Putusan sengketa: Refund penuh ke pembeli. {notes}".strip()
        order.save(update_fields=['status', 'cancelled_by', 'cancel_reason', 'updated_at'])

        item = order.item
        if item.status == SaleItem.Status.DIPESAN:
            item.status = SaleItem.Status.AKTIF
            item.save(update_fields=['status', 'updated_at'])

        resolved_nominal = total
        if dispute.dispute_type == SaleDispute.Type.PENJUAL_TIDAK_HADIR:
            dispute.seller_violation_recorded = True
            dispute.seller_violation_notes = "Penjual tidak hadir pada waktu dan titik temu serah terima"

    elif decision == SaleDispute.Decision.LEPAS_KE_PENJUAL:
        # 2. Payout penuh ke penjual (komisi platform 5% min Rp 2.000)
        commission = max(int(order.price_snapshot * 0.05), 2000)
        net_to_seller = max(0, order.price_snapshot - commission)

        LedgerEntry.objects.create(
            sale_order=order,
            kind=LedgerEntry.Kind.KELUAR_KOMISI_PENJUALAN,
            amount=commission,
            note=f"Komisi platform putusan sengketa {order.code}",
        )
        LedgerEntry.objects.create(
            sale_order=order,
            kind=LedgerEntry.Kind.KELUAR_PAYOUT_PENJUAL,
            amount=net_to_seller,
            note=f"Pencairan hasil penjualan putusan sengketa {order.code} ke dompet penjual",
        )
        WalletTransaction.objects.create(
            user=order.seller,
            amount=net_to_seller,
            kind=WalletTransaction.Kind.KREDIT_PENJUALAN,
            sale_order=order,
            note=f"Hasil penjualan barang '{order.listing_snapshot.get('title', order.item.title)}' (#{order.code})",
        )
        order.status = SaleOrder.Status.SELESAI
        order.completed_at = now
        order.save(update_fields=['status', 'completed_at', 'updated_at'])

        item = order.item
        item.status = SaleItem.Status.TERJUAL
        item.save(update_fields=['status', 'updated_at'])

        resolved_nominal = 0

    elif decision == SaleDispute.Decision.SEBAGIAN:
        # 3. Split nominal: Pembeli menerima refund 'nominal', sisa ke penjual
        refund_buyer = max(0, min(int(nominal), total))
        seller_share = total - refund_buyer

        if seller_share > 0:
            raw_commission = max(int(seller_share * 0.05), 2000)
            commission = min(raw_commission, seller_share)
            net_to_seller = seller_share - commission
        else:
            commission = 0
            net_to_seller = 0

        # Penyesuaian presisi invarian: total keluar harus tepat sama dengan total masuk
        if refund_buyer + commission + net_to_seller != total:
            commission = total - refund_buyer - net_to_seller

        if refund_buyer > 0:
            LedgerEntry.objects.create(
                sale_order=order,
                kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA,
                amount=refund_buyer,
                note=f"Refund sebagian putusan sengketa {order.code}",
            )
            WalletTransaction.objects.create(
                user=order.buyer,
                amount=refund_buyer,
                kind=WalletTransaction.Kind.KREDIT_REFUND_PENJUALAN,
                sale_order=order,
                note=f"Pengembalian dana sebagian sengketa #{order.code}",
            )

        if commission > 0:
            LedgerEntry.objects.create(
                sale_order=order,
                kind=LedgerEntry.Kind.KELUAR_KOMISI_PENJUALAN,
                amount=commission,
                note=f"Komisi platform putusan sengketa sebagian {order.code}",
            )

        if net_to_seller > 0:
            LedgerEntry.objects.create(
                sale_order=order,
                kind=LedgerEntry.Kind.KELUAR_PAYOUT_PENJUAL,
                amount=net_to_seller,
                note=f"Payout sebagian putusan sengketa {order.code} ke dompet penjual",
            )
            WalletTransaction.objects.create(
                user=order.seller,
                amount=net_to_seller,
                kind=WalletTransaction.Kind.KREDIT_PENJUALAN,
                sale_order=order,
                note=f"Hasil bersih sebagian sengketa barang '{order.listing_snapshot.get('title', order.item.title)}' (#{order.code})",
            )

        order.status = SaleOrder.Status.SELESAI
        order.completed_at = now
        order.save(update_fields=['status', 'completed_at', 'updated_at'])

        item = order.item
        item.status = SaleItem.Status.TERJUAL
        item.save(update_fields=['status', 'updated_at'])

        resolved_nominal = refund_buyer
        dispute.seller_violation_recorded = True
        dispute.seller_violation_notes = f"Sengketa diselesaikan dengan pengembalian sebagian ke pembeli Rp{refund_buyer:,}"

    dispute.status = SaleDispute.Status.SELESAI
    dispute.decision = decision
    dispute.nominal = resolved_nominal
    dispute.decided_by = admin_user
    dispute.notes = notes.strip()
    dispute.resolved_at = now
    dispute.save()

    dec_label = dispute.get_decision_display()
    Notification.notify(
        user=order.buyer,
        title="Sengketa jual beli diputuskan",
        message=f"Sengketa pesanan {order.code} telah diputuskan oleh admin: '{dec_label}'.",
        url=f"/pesanan/{order.code}/"
    )
    Notification.notify(
        user=order.seller,
        title="Sengketa jual beli diputuskan",
        message=f"Sengketa pesanan {order.code} telah diputuskan oleh admin: '{dec_label}'.",
        url=f"/pesanan/{order.code}/"
    )

    return dispute


@transaction.atomic
def create_sale_review(order, reviewer, rating, comment=''):
    """
    Membuat ulasan dua arah setelah pesanan jual beli selesai:
    - Hanya setelah order.status == SaleOrder.Status.SELESAI.
    - Reviewer adalah pembeli atau penjual pada pesanan ini.
    - Rating 1-5, komentar maks 300 karakter.
    - Sekali kirim (menghindari duplikasi per pihak).
    """
    from apps.sales.models import SaleOrder, SaleReview
    from apps.core.models import Notification

    locked_order = SaleOrder.objects.select_for_update().get(id=order.id)
    if locked_order.status != SaleOrder.Status.SELESAI:
        raise SaleOrderStateError("Ulasan hanya dapat dikirimkan setelah pesanan selesai.")

    if reviewer != locked_order.buyer and reviewer != locked_order.seller:
        raise SaleOrderPermissionError("Anda tidak berhak mengulas pesanan ini.")

    if SaleReview.objects.filter(order=locked_order, reviewer=reviewer).exists():
        raise SaleOrderValidationError("Anda sudah memberikan ulasan untuk pesanan ini.")

    try:
        rating_int = int(rating)
    except (ValueError, TypeError):
        raise SaleOrderValidationError("Rating harus berupa angka antara 1 sampai 5.")

    if rating_int < 1 or rating_int > 5:
        raise SaleOrderValidationError("Rating harus berada di antara 1 sampai 5.")

    comment_clean = str(comment or '').strip()
    if len(comment_clean) > 300:
        raise SaleOrderValidationError("Komentar ulasan maksimal 300 karakter.")

    if reviewer == locked_order.buyer:
        reviewee = locked_order.seller
        role = SaleReview.Role.PENJUAL
        role_label = "pembeli"
    else:
        reviewee = locked_order.buyer
        role = SaleReview.Role.PEMBELI
        role_label = "penjual"

    review = SaleReview.objects.create(
        order=locked_order,
        reviewer=reviewer,
        reviewee=reviewee,
        role=role,
        rating=rating_int,
        comment=comment_clean
    )

    Notification.notify(
        user=reviewee,
        title="Ulasan baru diterima",
        message=f"{reviewer.full_name or reviewer.username} (sebagai {role_label}) memberikan ulasan {rating_int}★ untuk pesanan {locked_order.code}.",
        url=f"/pesanan/{locked_order.code}/"
    )

    return review


def create_sale_item_report(item, reporter, reason, notes=''):
    """
    Membuat laporan pelanggaran terhadap barang jualan oleh pengguna terautentikasi.
    """
    from apps.sales.models import SaleItemReport
    from apps.core.models import Notification

    if not reporter or not reporter.is_authenticated:
        raise SaleOrderPermissionError("Anda harus masuk untuk melaporkan barang.")

    if reporter == item.owner:
        raise SaleOrderValidationError("Anda tidak dapat melaporkan barang milik Anda sendiri.")

    if reason not in SaleItemReport.Reason.values:
        raise SaleOrderValidationError("Alasan laporan tidak valid.")

    notes_clean = str(notes or '').strip()

    report = SaleItemReport.objects.create(
        item=item,
        reporter=reporter,
        reason=reason,
        notes=notes_clean,
        status=SaleItemReport.Status.MENUNGGU
    )

    logger.info("Laporan barang #%s dibuat oleh %s (alasan: %s)", item.pk, reporter.username, reason)
    return report


def takedown_sale_item(item, admin_user, reason):
    """
    Aksi admin untuk menurunkan listing barang jualan dengan alasan wajib:
    - Status barang diubah menjadi nonaktif.
    - Catatan dan waktu penurunan disimpan.
    - Notifikasi dikirimkan ke penjual.
    - Laporan terkait yang berstatus menunggu otomatis ditandai ditindaklanjuti.
    """
    from apps.sales.models import SaleItem, SaleItemReport
    from apps.core.models import Notification

    reason_clean = str(reason or '').strip()
    if not reason_clean:
        raise SaleOrderValidationError("Alasan penurunan barang wajib dicantumkan.")

    with transaction.atomic():
        item.status = SaleItem.Status.NONAKTIF
        item.takedown_reason = reason_clean
        item.takedown_by = admin_user
        item.takedown_at = timezone.now()
        item.save(update_fields=['status', 'takedown_reason', 'takedown_by', 'takedown_at', 'updated_at'])

        # Tandai laporan terkait sebagai ditindaklanjuti
        now = timezone.now()
        SaleItemReport.objects.filter(
            item=item,
            status=SaleItemReport.Status.MENUNGGU
        ).update(
            status=SaleItemReport.Status.DITINDAKLANJUTI,
            reviewed_by=admin_user,
            action_taken=f"Barang dinonaktifkan oleh moderator: {reason_clean}",
            resolved_at=now
        )

        # Kirim notifikasi ke pemilik barang
        Notification.notify(
            user=item.owner,
            title="Barang Jualan Diturunkan oleh Moderator",
            message=f"Barang jualan Anda '{item.title}' telah dinonaktifkan oleh moderator platform. Alasan: {reason_clean}",
            url=f"/jual/{item.slug}/"
        )

    logger.info("Barang jualan #%s (%s) diturunkan oleh %s. Alasan: %s", item.pk, item.title, getattr(admin_user, 'username', 'admin'), reason_clean)
    return item


def create_sale_offer(item, buyer, offered_price):
    """
    Membuat tawaran harga baru untuk barang jualan:
    - Saklar SALE_OFFERS_ENABLED wajib aktif.
    - Validasi pembeli: terautentikasi, email terverifikasi, KTM terverifikasi, aktif, tanpa tagihan tertunggak.
    - Pembeli tidak dapat menawar barang miliknya sendiri.
    - Barang harus berstatus aktif dan belum kedaluwarsa.
    - Harga tawaran harus valid, > 0, dan < harga listing barang.
    - Tawaran berlaku selama 24 jam. Jika pembeli punya tawaran menunggu sebelumnya, tawaran lama dibatalkan.
    """
    if not getattr(settings, 'SALE_OFFERS_ENABLED', False):
        raise SaleOrderPermissionError("Fitur penawaran harga dinonaktifkan.")

    from apps.sales.models import SaleOffer, SaleItem
    from apps.core.models import Notification
    from apps.payments.models import ExtraCharge

    if not buyer or not buyer.is_authenticated:
        raise SaleOrderValidationError("Silakan masuk terlebih dahulu untuk menawar harga.")

    if not getattr(buyer, 'email_verified', True):
        raise SaleOrderValidationError("Email Anda belum terverifikasi.")

    profile = getattr(buyer, 'student_profile', None)
    if not profile or not getattr(buyer, 'is_verified_student', False):
        raise SaleOrderValidationError("Anda wajib memverifikasi KTM terlebih dahulu sebelum menawar harga.")

    if not buyer.is_active:
        raise SaleOrderValidationError("Akun Anda sedang dinonaktifkan.")

    if ExtraCharge.objects.filter(rental__renter=buyer, status='unpaid').exists():
        raise SaleOrderValidationError("Anda memiliki tagihan tambahan yang belum dilunasi.")

    if buyer == item.owner:
        raise SaleOrderValidationError("Anda tidak dapat menawar barang milik sendiri.")

    if item.status != SaleItem.Status.AKTIF or item.is_expired:
        raise SaleOrderValidationError("Barang ini sedang tidak aktif atau sudah terjual.")

    try:
        price_val = int(offered_price)
    except (ValueError, TypeError):
        raise SaleOrderValidationError("Harga tawaran tidak valid.")

    if price_val <= 0:
        raise SaleOrderValidationError("Harga tawaran harus lebih besar dari 0.")

    if price_val >= item.price:
        raise SaleOrderValidationError("Harga tawaran harus lebih rendah dari harga listing.")

    # Batalkan tawaran menunggu sebelumnya dari pembeli untuk barang ini jika ada
    existing_pending = SaleOffer.objects.filter(
        item=item,
        buyer=buyer,
        status=SaleOffer.Status.MENUNGGU,
        expires_at__gt=timezone.now()
    ).first()
    if existing_pending:
        existing_pending.status = SaleOffer.Status.DIBATALKAN
        existing_pending.save(update_fields=['status'])

    expires_at = timezone.now() + timedelta(hours=24)
    offer = SaleOffer.objects.create(
        item=item,
        buyer=buyer,
        offered_price=price_val,
        status=SaleOffer.Status.MENUNGGU,
        expires_at=expires_at,
    )

    Notification.notify(
        user=item.owner,
        title="Tawaran harga baru masuk",
        message=f"{buyer.username} menawar Rp{price_val:,} untuk '{item.title}'. Berlaku 24 jam.",
        url=f"/jual-beli/{item.slug}/"
    )

    return offer


@transaction.atomic
def accept_sale_offer(offer, seller, ip_address=None, user_agent=''):
    """
    Penjual menerima tawaran harga:
    - Saklar SALE_OFFERS_ENABLED wajib aktif.
    - Hanya pemilik barang yang dapat menerima tawaran.
    - Tawaran harus berstatus MENUNGGU dan belum kedaluwarsa.
    - Status tawaran berubah menjadi DITERIMA.
    - Membuat pesanan SaleOrder dengan harga disepakati (price_snapshot = offered_price).
    - Menautkan offer.order = order.
    - Menolak tawaran aktif lain yang masih menunggu untuk barang tersebut.
    - Mengirim notifikasi ke pembeli dengan batas waktu pembayaran 6 jam.
    """
    if not getattr(settings, 'SALE_OFFERS_ENABLED', False):
        raise SaleOrderPermissionError("Fitur penawaran harga dinonaktifkan.")

    from apps.sales.models import SaleOffer, SaleItem
    from apps.core.models import Notification

    locked_offer = SaleOffer.objects.select_for_update().get(id=offer.id)
    if locked_offer.item.owner != seller:
        raise SaleOrderPermissionError("Hanya penjual barang yang dapat menerima tawaran.")

    if locked_offer.status != SaleOffer.Status.MENUNGGU or locked_offer.is_expired:
        raise SaleOrderStateError("Tawaran ini sudah tidak aktif atau telah kedaluwarsa.")

    # Buat pesanan dengan harga yang disepakati
    order = create_sale_order(
        item=locked_offer.item,
        buyer=locked_offer.buyer,
        terms_accepted=True,
        ip_address=ip_address,
        user_agent=user_agent,
        agreed_price=locked_offer.offered_price
    )

    locked_offer.status = SaleOffer.Status.DITERIMA
    locked_offer.order = order
    locked_offer.save(update_fields=['status', 'order'])

    # Tolak tawaran lain yang masih menunggu
    SaleOffer.objects.filter(
        item=locked_offer.item,
        status=SaleOffer.Status.MENUNGGU
    ).exclude(id=locked_offer.id).update(status=SaleOffer.Status.DITOLAK)

    Notification.notify(
        user=locked_offer.buyer,
        title="Tawaran harga Anda diterima",
        message=f"Tawaran Anda sebesar Rp{locked_offer.offered_price:,} untuk '{locked_offer.item.title}' telah diterima. Silakan selesaikan pembayaran dalam 6 jam.",
        url=f"/pesanan/{order.code}/"
    )

    return order


@transaction.atomic
def reject_sale_offer(offer, seller):
    """
    Penjual menolak tawaran harga:
    - Saklar SALE_OFFERS_ENABLED wajib aktif.
    - Hanya pemilik barang yang dapat menolak tawaran.
    - Status tawaran berubah menjadi DITOLAK.
    """
    if not getattr(settings, 'SALE_OFFERS_ENABLED', False):
        raise SaleOrderPermissionError("Fitur penawaran harga dinonaktifkan.")

    from apps.sales.models import SaleOffer
    from apps.core.models import Notification

    locked_offer = SaleOffer.objects.select_for_update().get(id=offer.id)
    if locked_offer.item.owner != seller:
        raise SaleOrderPermissionError("Hanya penjual barang yang dapat menolak tawaran.")

    if locked_offer.status != SaleOffer.Status.MENUNGGU:
        raise SaleOrderStateError("Tawaran ini sudah tidak berstatus menunggu.")

    locked_offer.status = SaleOffer.Status.DITOLAK
    locked_offer.save(update_fields=['status'])

    Notification.notify(
        user=locked_offer.buyer,
        title="Tawaran harga Anda ditolak",
        message=f"Tawaran Anda untuk '{locked_offer.item.title}' belum disetujui penjual.",
        url=f"/jual-beli/{locked_offer.item.slug}/"
    )

    return locked_offer


@transaction.atomic
def cancel_sale_offer(offer, buyer):
    """
    Pembeli membatalkan tawaran harga yang sebelumnya diajukan:
    - Saklar SALE_OFFERS_ENABLED wajib aktif.
    - Hanya calon pembeli penawar yang dapat membatalkan.
    - Status tawaran berubah menjadi DIBATALKAN.
    """
    if not getattr(settings, 'SALE_OFFERS_ENABLED', False):
        raise SaleOrderPermissionError("Fitur penawaran harga dinonaktifkan.")

    from apps.sales.models import SaleOffer

    locked_offer = SaleOffer.objects.select_for_update().get(id=offer.id)
    if locked_offer.buyer != buyer:
        raise SaleOrderPermissionError("Hanya penawar yang dapat membatalkan tawaran ini.")

    if locked_offer.status != SaleOffer.Status.MENUNGGU:
        raise SaleOrderStateError("Tawaran ini sudah tidak berstatus menunggu.")

    locked_offer.status = SaleOffer.Status.DIBATALKAN
    locked_offer.save(update_fields=['status'])

    return locked_offer



