import re
from rapidfuzz import fuzz
from django.db import models
from apps.accounts.models import Campus


def normalize_campus_name(name: str) -> str:
    """
    Normalisasi nama kampus:
    - Bersihkan spasi berlebih dan karakter tak perlu.
    - Format kapitalisasi rapi (menjaga akronim umum seperti ITERA, ITB, UI, UGM).
    """
    if not name:
        return ""
    cleaned = re.sub(r'\s+', ' ', name.strip())
    words = cleaned.split(' ')
    norm_words = []
    stopwords = {'dan', 'di', 'ke', 'dari', 'pada'}
    for idx, w in enumerate(words):
        # Jika kata merupakan akronim (semua huruf besar, 2-6 karakter)
        if w.isupper() and 2 <= len(w) <= 6:
            norm_words.append(w)
        elif idx > 0 and w.lower() in stopwords:
            norm_words.append(w.lower())
        else:
            norm_words.append(w.capitalize())
    return ' '.join(norm_words)


def generate_campus_short_name(name: str) -> str:
    """
    Buat nama pendek otomatis dari nama kampus:
    - Singkatan dari inisial kata bermakna (misal 'Universitas Sinsar' -> 'US')
    - Nama penuh bila pendek (misal 'ITERA' -> 'ITERA', 'UI' -> 'UI')
    - Tidak pernah memotong di tengah kata.
    """
    if not name:
        return ""
    clean_name = str(name).strip()
    words = [w for w in re.split(r'[\s\-]+', clean_name) if w]
    if not words:
        return ""

    # Jika hanya 1 kata: gunakan nama penuh tanpa memotong
    if len(words) == 1:
        return words[0].upper() if len(words[0]) <= 8 else words[0]

    # Lebih dari 1 kata: ambil inisial dari tiap kata bermakna
    stopwords = {'dan', '&', 'di', 'ke', 'pada', 'of', 'and', 'the', 'dalam'}
    sig_words = [w for w in words if w.lower() not in stopwords] or words
    initials = ''.join(w[0].upper() for w in sig_words if w[0].isalnum())
    return initials


INSTITUTIONAL_WORDS = {
    'universitas', 'univ', 'institut', 'institute', 'politeknik', 'poltek',
    'sekolah', 'tinggi', 'akademi', 'stie', 'stmik', 'stkipt',
    'negeri', 'swasta', 'indonesia', 'kampus', 'dan', '&', 'di', 'pada'
}


def extract_distinctive_words(name: str) -> list[str]:
    """Ekstrak kata-kata pembeda utama kampus, mengabaikan kata institusional umum."""
    tokens = [w.lower() for w in re.split(r'[\s\-.,/()]+', str(name)) if w.strip()]
    distinctive = [w for w in tokens if w not in INSTITUTIONAL_WORDS]
    return distinctive if distinctive else tokens


def resolve_or_create_campus(
    raw_campus_input: str,
    city: str = '',
    is_explicit_new: bool = False,
    custom_short_name: str = ''
) -> tuple[Campus | None, bool, Campus | None]:
    """
    Memeriksa dan membuat kampus secara dinamis:
    Returns: (campus_object, is_new, conflicting_campus)
    - Jika input cocok (exact match case-insensitive atau ID angka): kembalikan kampus tersebut.
    - Jika tidak cocok, cek kemiripan dengan rapidfuzz:
      * Bandingkan kemiripan nama keseluruhan dan kemiripan kata pembeda (distinctive words)
        agar tidak salah mendeteksi kampus berbeda yang hanya berbagi kata 'Institut Teknologi' / 'Universitas'.
      * Jika ada kampus yang sangat mirip (typo nyata >= 95% atau >= 85% dengan distinctive >= 80%):
        kembalikan (None, False, conflicting_campus) sehingga form meminta memilih kampus terdaftar.
      * Jika pengguna secara eksplisit mendaftarkan kampus baru (is_explicit_new=True),
        hanya tolak jika hampir 100% duplikat (>= 98%).
    - Jika tidak ada yang mirip: buat kampus baru dengan nama dinormalisasi, city, dan short_name.
    """
    if not raw_campus_input or not str(raw_campus_input).strip():
        return None, False, None

    raw_clean = str(raw_campus_input).strip()

    # Cek jika input adalah ID angka (misal dikirim oleh form testing atau select)
    if raw_clean.isdigit():
        campus = Campus.objects.filter(pk=int(raw_clean), is_active=True).first()
        if campus:
            return campus, False, None

    norm_name = normalize_campus_name(raw_clean)

    # 1. Cek kecocokan persis (case-insensitive) pada nama atau short_name terhadap kampus aktif
    existing_exact = Campus.objects.filter(
        models.Q(name__iexact=norm_name) | models.Q(short_name__iexact=norm_name),
        is_active=True
    ).first()
    if existing_exact:
        return existing_exact, False, None

    # 2. Cek kemiripan fuzzy menggunakan rapidfuzz terhadap seluruh kampus aktif
    norm_distinctive = extract_distinctive_words(norm_name)
    norm_dist_str = " ".join(norm_distinctive)

    campuses = Campus.objects.filter(is_active=True)
    conflict_campus = None
    highest_conflict_score = 0.0

    for c in campuses:
        score_token = fuzz.token_sort_ratio(norm_name.lower(), c.name.lower())
        score_ratio = fuzz.ratio(norm_name.lower(), c.name.lower())
        overall_score = max(score_token, score_ratio)

        if c.short_name:
            score_short = fuzz.ratio(norm_name.lower(), c.short_name.lower())
            overall_score = max(overall_score, score_short)

        c_distinctive = extract_distinctive_words(c.name)
        c_dist_str = " ".join(c_distinctive)
        dist_token = fuzz.token_sort_ratio(norm_dist_str, c_dist_str)
        dist_ratio = fuzz.ratio(norm_dist_str, c_dist_str)
        distinctive_score = max(dist_token, dist_ratio)

        # Evaluasi konflik typo
        is_conflict = (overall_score >= 95.0) or (overall_score >= 85.0 and distinctive_score >= 80.0)

        # Jika aksi eksplisit tambah kampus baru: hanya blok jika hampir 100% sama (>= 98%)
        if is_explicit_new:
            is_conflict = (overall_score >= 98.0)

        if is_conflict and overall_score > highest_conflict_score:
            highest_conflict_score = overall_score
            conflict_campus = c

    if conflict_campus:
        return None, False, conflict_campus

    # 3. Buat kampus baru secara otomatis jika belum ada yang mirip
    short_name = (custom_short_name.strip().upper() if custom_short_name else '') or generate_campus_short_name(norm_name)
    new_campus = Campus.objects.create(
        name=norm_name,
        short_name=short_name,
        city=city.strip(),
        is_active=True
    )
    return new_campus, True, None
