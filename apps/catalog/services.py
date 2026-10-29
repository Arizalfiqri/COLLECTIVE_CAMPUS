from datetime import date, timedelta
from django.conf import settings
from apps.rentals.models import Rental


from apps.trust.services import calculate_minimum_deposit, calculate_protection_fee


def calculate_min_deposit(estimated_value, user=None):
    """
    Hitung deposit minimum untuk suatu barang sesuai SPEC v2 & Fase 7G:
    - Jika DEPOSIT_MODE='off' atau 'optional': mengembalikan 0.
    - Nilai barang <= NO_DEPOSIT_BELOW_VALUE (Rp150.000): boleh 0 (tanpa deposit).
    - Nilai barang > Rp150.000: minimum Rp25.000 dan persentase sesuai aturan.
    - Jika user memiliki TrustScore < 40 dan bukan pengguna baru, deposit minimum dikalikan 1.5x.
    """
    deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
    if deposit_mode in ['off', 'optional']:
        return 0

    if not estimated_value or estimated_value <= 0:
        return 0
    base_dep = calculate_minimum_deposit(estimated_value, renter_tier='baru', is_cross_campus=False)
    if user and getattr(user, 'is_authenticated', False):
        trust_score = getattr(user, 'trust_score', None)
        if trust_score and not getattr(trust_score, 'is_new_user', False) and trust_score.score < 40:
            base_dep = round(base_dep * 1.5)
    return base_dep


def get_suggested_deposit_range(estimated_value, user=None):
    """
    Rekomendasi rentang deposit platform (SPEC v2: minimum deposit platform s.d. 30% nilai barang).
    """
    deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
    if deposit_mode == 'off':
        return {'min': 0, 'suggested_min': 0, 'suggested_max': 0}

    min_dep = calculate_min_deposit(estimated_value, user)
    max_dep = max(min_dep, round(estimated_value * 0.30)) if estimated_value else 0
    return {
        'min': min_dep,
        'suggested_min': min_dep,
        'suggested_max': max_dep,
    }


def is_item_available(item, start_date, end_date):
    """
    Periksa apakah barang tersedia pada rentang [start_date, end_date].
    Anti double-booking: bertabrakan jika ada sewa berstatus BLOCKING_STATUSES
    dengan rentang tanggal yang saling tumpang tindih (start_date <= end_d and end_date >= start_d).
    """
    if not start_date or not end_date or start_date > end_date:
        return False

    overlapping = Rental.objects.filter(
        item=item,
        status__in=Rental.BLOCKING_STATUSES,
        start_date__lte=end_date,
        end_date__gte=start_date
    )
    return not overlapping.exists()


def get_unavailable_dates(item):
    """
    Dapatkan daftar rentang tanggal yang sudah dipesan untuk kalender ketersediaan (design.md 5.12).
    Mengembalikan list dict: [{'from': 'YYYY-MM-DD', 'to': 'YYYY-MM-DD'}, ...]
    serta himpunan string tanggal individual untuk kemudahan parsing di JavaScript/Alpine.
    """
    active_rentals = (
        Rental.objects
        .filter(item=item, status__in=Rental.BLOCKING_STATUSES)
        .order_by('start_date')
    )

    ranges = []
    disabled_dates = []

    for r in active_rentals:
        if r.start_date and r.end_date:
            ranges.append({
                'from': r.start_date.isoformat(),
                'to': r.end_date.isoformat(),
            })
            # Buat list tanggal harian
            curr = r.start_date
            while curr <= r.end_date:
                disabled_dates.append(curr.isoformat())
                curr += timedelta(days=1)

    return {
        'ranges': ranges,
        'disabled_dates': disabled_dates,
    }


def calculate_rental_summary(item, start_date, end_date, use_protection=False):
    """
    Hitung ringkasan harga sewa persis sesuai method Rental dan PROJECT_SPEC.md 7.2:
    - days = (end_date - start_date).days + 1
    - rent_total = price_per_day * days
    - deposit_total = item.deposit_amount
    - protection_fee = settings.PROTECTION_FEE jika use_protection else 0
    - grand_total = rent_total + deposit_total + protection_fee
    
    Juga memvalidasi min_days dan max_days barang.
    """
    errors = []

    deposit_mode = getattr(settings, 'DEPOSIT_MODE', 'off').lower().strip()
    default_deposit = 0 if deposit_mode == 'off' else (item.deposit_amount or 0)

    if not start_date or not end_date:
        return {
            'is_valid': False,
            'errors': ['Pilih tanggal mulai dan tanggal selesai sewa.'],
            'days': 0,
            'rent_total': 0,
            'deposit_total': default_deposit,
            'protection_fee': 0,
            'grand_total': default_deposit,
        }

    if start_date > end_date:
        return {
            'is_valid': False,
            'errors': ['Tanggal selesai tidak boleh sebelum tanggal mulai.'],
            'days': 0,
            'rent_total': 0,
            'deposit_total': default_deposit,
            'protection_fee': 0,
            'grand_total': default_deposit,
        }

    # Hitung jumlah hari sewa (inklusif)
    days = (end_date - start_date).days + 1

    # Validasi batas hari
    if days < item.min_days:
        errors.append(f"Minimum durasi sewa untuk barang ini adalah {item.min_days} hari.")
    if days > item.max_days:
        errors.append(f"Maksimum durasi sewa untuk barang ini adalah {item.max_days} hari.")

    # Cek tabrakan tanggal
    if not is_item_available(item, start_date, end_date):
        errors.append("Barang tidak tersedia pada rentang tanggal yang dipilih karena sudah disewa pengguna lain.")

    # Hitung komponen harga
    price_per_day = item.price_per_day
    rent_total = price_per_day * days
    deposit_total = 0 if deposit_mode == 'off' else (item.deposit_amount or 0)

    # Hitung proteksi kerusakan ringan SPEC v2 (5%, min Rp3.000, wajib jika > Rp500.000)
    prot_calc = calculate_protection_fee(rent_total, item.estimated_value)
    is_mandatory = prot_calc['is_mandatory']
    actual_use_protection = True if is_mandatory else bool(use_protection)
    prot_fee = prot_calc['fee'] if actual_use_protection else 0
    grand_total = rent_total + deposit_total + prot_fee

    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'days': days,
        'price_per_day': price_per_day,
        'rent_total': rent_total,
        'deposit_total': deposit_total,
        'protection_fee': prot_fee,
        'grand_total': grand_total,
        'use_protection': actual_use_protection,
        'is_protection_mandatory': is_mandatory,
        'protection_fee_rate': prot_calc['fee'],
    }
