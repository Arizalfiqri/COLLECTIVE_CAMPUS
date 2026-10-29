"""
Modul OCR Kartu Tanda Mahasiswa (KTM) — KampusRent
Implementasi pipeline pra-proses gambar, OCR pytesseract, ekstraksi data,
skor kecocokan, dan rekomendasi persis sesuai PROJECT_SPEC.md 9.1.
"""
import logging
import os
import re
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter
from django.conf import settings
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


def preprocess_ktm_image(image_path_or_file):
    """
    Pra-proses gambar KTM:
    1. Konversi ke Grayscale ('L')
    2. Resize jika resolusi terlalu kecil (agar detail teks terbaca)
    3. Tingkatkan kontras dan ketajaman
    """
    img = Image.open(image_path_or_file)
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Konversi ke Grayscale
    gray = img.convert('L')

    # Resize proporsional jika lebar kurang dari 1200 px
    w, h = gray.size
    if w < 1200:
        ratio = 1200 / float(w)
        new_size = (1200, int(h * ratio))
        gray = gray.resize(new_size, Image.Resampling.LANCZOS)

    # Tingkatkan kontras
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(1.8)

    # Tingkatkan ketajaman (sharpen)
    sharpened = enhanced.filter(ImageFilter.SHARPEN)

    return sharpened, (w, h)


def calculate_quality_score(original_size, ocr_text_len):
    """
    Skor kualitas gambar (0-100) berdasarkan resolusi dan keterbacaan teks.
    """
    w, h = original_size
    # Resolusi minimum yang disukai: 800 x 500 px
    res_score = min(100, int((w * h) / (800 * 500) * 100))
    # Keterbacaan teks (ada karakter yang terdeteksi)
    text_score = min(100, int(ocr_text_len * 2)) if ocr_text_len > 0 else 0

    return int(0.7 * res_score + 0.3 * text_score)


def calculate_match_score(nim_match, name_similarity, campus_match, quality_score):
    """
    Formula Skor Kecocokan persis sesuai PROJECT_SPEC.md 9.1:
    match_score = (50 jika nim_match) + (0.3 * name_similarity) + (10 jika campus_match) + (0.1 * quality_score)
    Skor berkisar antara 0 - 100.
    """
    score = (
        (50 if nim_match else 0) +
        (0.3 * float(name_similarity)) +
        (10 if campus_match else 0) +
        (0.1 * float(quality_score))
    )
    return max(0, min(100, round(score)))


def get_recommendation(match_score):
    """
    Rekomendasi persis sesuai PROJECT_SPEC.md 9.1:
    >= 85 -> 'setuju'
    60 - 84 -> 'tinjau'
    < 60 -> 'tolak'
    """
    if match_score >= 85:
        return 'setuju'
    elif match_score >= 60:
        return 'tinjau'
    else:
        return 'tolak'


def extract_ktm_data(image_path_or_file, target_nim, target_name, target_campus='', target_campus_keywords=None, nim_pattern=''):
    """
    Pipeline lengkap OCR KTM (SPEC v2 Bagian F):
    1. Pra-proses
    2. OCR pytesseract (ind+eng)
    3. Ekstraksi NIM (dengan dukungan nim_pattern kampus), nama, kampus (dengan target_campus_keywords)
    4. Perhitungan skor dan rekomendasi
    Toleransi jika Tesseract belum terpasang: kembalikan status 'perlu_tinjauan' dan catatan admin yang jelas.
    """
    import pytesseract

    # Konfigurasi TESSERACT_CMD jika didefinisikan di settings
    tesseract_cmd = getattr(settings, 'TESSERACT_CMD', '')
    if tesseract_cmd and os.path.exists(tesseract_cmd):
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    # 1. Pra-proses gambar
    try:
        processed_img, orig_size = preprocess_ktm_image(image_path_or_file)
    except Exception as e:
        logger.error(f"Gagal memproses gambar KTM: {e}")
        return {
            'ocr_available': False,
            'ocr_raw_text': '',
            'extracted_nim': '',
            'extracted_name': '',
            'extracted_campus': '',
            'nim_match': False,
            'name_similarity': 0,
            'campus_match': False,
            'quality_score': 0,
            'match_score': 0,
            'recommendation': 'tinjau',
            'status': 'perlu_tinjauan',
            'admin_note': f'Gambar tidak dapat diproses: {str(e)}',
        }

    # 2. Eksekusi OCR
    ocr_text = ""
    ocr_available = True
    try:
        # Coba bahasa 'ind+eng' terlebih dahulu, jika gagal coba 'eng'
        try:
            ocr_text = pytesseract.image_to_string(processed_img, lang='ind+eng')
        except pytesseract.TesseractError:
            ocr_text = pytesseract.image_to_string(processed_img, lang='eng')
    except (pytesseract.TesseractNotFoundError, FileNotFoundError, OSError) as e:
        logger.warning(f"Tesseract OCR tidak tersedia: {e}")
        ocr_available = False
        quality_score = calculate_quality_score(orig_size, 0)
        return {
            'ocr_available': False,
            'ocr_raw_text': '',
            'extracted_nim': '',
            'extracted_name': '',
            'extracted_campus': '',
            'nim_match': False,
            'name_similarity': 0,
            'campus_match': False,
            'quality_score': quality_score,
            'match_score': 0,
            'recommendation': 'tinjau',
            'status': 'perlu_tinjauan',
            'admin_note': 'OCR tidak tersedia di sistem (Tesseract belum terpasang). Menunggu peninjauan manual admin.',
        }
    except Exception as e:
        logger.error(f"Kesalahan tak terduga saat OCR: {e}")
        ocr_available = False
        quality_score = calculate_quality_score(orig_size, 0)
        return {
            'ocr_available': False,
            'ocr_raw_text': '',
            'extracted_nim': '',
            'extracted_name': '',
            'extracted_campus': '',
            'nim_match': False,
            'name_similarity': 0,
            'campus_match': False,
            'quality_score': quality_score,
            'match_score': 0,
            'recommendation': 'tinjau',
            'status': 'perlu_tinjauan',
            'admin_note': f'Gagal menjalankan OCR: {str(e)}',
        }

    # 3. Ekstraksi dan Pencocokan
    ocr_clean = ocr_text.strip()
    ocr_lower = ocr_clean.lower()

    # Ekstraksi NIM: cari angka dengan pola spesifik kampus jika ada, atau fallback 8-15 digit
    pattern_to_use = nim_pattern if nim_pattern else r'\b\d{8,15}\b'
    try:
        found_nims = re.findall(pattern_to_use, ocr_clean)
    except Exception:
        found_nims = re.findall(r'\b\d{8,15}\b', ocr_clean)

    clean_target_nim = re.sub(r'\D', '', str(target_nim))

    nim_match = False
    extracted_nim = found_nims[0] if found_nims else ''

    if clean_target_nim:
        if clean_target_nim in found_nims:
            nim_match = True
            extracted_nim = clean_target_nim
        elif clean_target_nim in ocr_clean.replace(' ', ''):
            nim_match = True
            extracted_nim = clean_target_nim

    # Ekstraksi dan Kemiripan Nama
    name_similarity = 0
    extracted_name = ''
    if target_name:
        target_name_clean = target_name.strip().lower()
        # Cari kemiripan token set dan partial ratio
        ratio_partial = fuzz.partial_ratio(target_name_clean, ocr_lower)
        ratio_token = fuzz.token_set_ratio(target_name_clean, ocr_lower)
        name_similarity = max(int(ratio_partial), int(ratio_token))

        # Cari baris yang paling mirip dengan nama pengguna
        lines = [l.strip() for l in ocr_clean.splitlines() if len(l.strip()) >= 3]
        best_line = ''
        best_line_score = 0
        for line in lines:
            score = fuzz.ratio(target_name_clean, line.lower())
            if score > best_line_score:
                best_line_score = score
                best_line = line
        if best_line_score >= 50:
            extracted_name = best_line

    # Ekstraksi dan Pencocokan Kampus (Fase 7B: cocok kabur token nama kampus, bukan daftar kata kunci tetap)
    campus_match = False
    extracted_campus = ''

    if target_campus:
        target_campus_clean = target_campus.strip().lower()
        # Periksa kecocokan token nama kampus dengan teks OCR
        token_sim = fuzz.token_set_ratio(target_campus_clean, ocr_lower)
        partial_sim = fuzz.partial_ratio(target_campus_clean, ocr_lower)
        if max(token_sim, partial_sim) >= 65:
            campus_match = True

        # Cari baris yang paling cocok untuk ekstraksi nama kampus
        lines = [l.strip() for l in ocr_clean.splitlines() if len(l.strip()) >= 3]
        best_c_line = ''
        best_c_score = 0
        for line in lines:
            score = fuzz.token_set_ratio(target_campus_clean, line.lower())
            if score > best_c_score:
                best_c_score = score
                best_c_line = line
        if best_c_score >= 60:
            extracted_campus = best_c_line
    elif target_campus_keywords:
        for kw in target_campus_keywords:
            if kw and kw.lower().strip() and kw.lower().strip() in ocr_lower:
                campus_match = True
                break

    # Kualitas Gambar
    quality_score = calculate_quality_score(orig_size, len(ocr_clean))

    # 4. Hitung Skor Kecocokan & Rekomendasi
    match_score = calculate_match_score(nim_match, name_similarity, campus_match, quality_score)
    recommendation = get_recommendation(match_score)

    status = 'menunggu'
    if recommendation == 'tinjau':
        status = 'perlu_tinjauan'

    return {
        'ocr_available': ocr_available,
        'ocr_raw_text': ocr_clean,
        'extracted_nim': extracted_nim,
        'extracted_name': extracted_name,
        'extracted_campus': extracted_campus or target_campus,
        'nim_match': nim_match,
        'name_similarity': name_similarity,
        'campus_match': campus_match,
        'quality_score': quality_score,
        'match_score': match_score,
        'recommendation': recommendation,
        'status': status,
        'admin_note': '',
    }
