from django import template

register = template.Library()


@register.filter(name='rupiah')
def rupiah(value):
    """
    Format angka rupiah dengan pemisah ribuan berupa titik.
    Contoh:
        25000 -> 'Rp25.000'
        500000 -> 'Rp500.000'
        728000 -> 'Rp728.000'
    """
    if value is None or value == '':
        return ''
    try:
        val = int(value)
        # Format dengan koma sebagai pemisah ribuan, lalu tukar koma menjadi titik
        return f"Rp{val:,}".replace(',', '.')
    except (ValueError, TypeError):
        return f"Rp{value}"


@register.filter(name='initial')
def initial(value):
    """
    Mengambil huruf pertama untuk avatar inisial (kapital).
    Contoh: 'Rina Pratiwi' -> 'R'
    """
    if not value:
        return '?'
    s = str(value).strip()
    return s[0].upper() if s else '?'


@register.filter(name='first_name_only')
def first_name_only(value):
    """
    Mengambil nama depan saja untuk tampilan navbar ringkas.
    Contoh: 'Rina Pratiwi' -> 'Rina'
    """
    if not value:
        return ''
    parts = str(value).strip().split()
    return parts[0] if parts else ''


@register.filter(name='ribuan')
def ribuan(value):
    """
    Format angka integer dengan pemisah ribuan berupa titik tanpa prefix Rp.
    Contoh:
        40000 -> '40.000'
        2000000 -> '2.000.000'
    """
    if value is None or value == '':
        return ''
    try:
        val = int(str(value).replace('.', '').replace(' ', ''))
        return f"{val:,}".replace(',', '.')
    except (ValueError, TypeError):
        return str(value)


@register.filter(name='short_display_name')
def short_display_name(value):
    """
    Format nama pemilik menjadi nama depan + inisial nama belakang agar tidak terpotong.
    Contoh:
        'Dani Kurniawan' -> 'Dani K.'
        'Rina Pratiwi' -> 'Rina P.'
        'Arfi' -> 'Arfi'
    """
    if not value:
        return ''
    parts = str(value).strip().split()
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[1][0].upper()}."


@register.filter(name='mask_nim')
def mask_nim(value):
    """
    Menampilkan hanya 4 digit terakhir NIM demi privasi kemahasiswaan.
    Contoh:
        '2359201022' -> '•••• 1022'
    """
    if not value:
        return '-'
    val = str(value).strip()
    if len(val) <= 4:
        return val
    return f"•••• {val[-4:]}"


