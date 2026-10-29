import logging
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Kunci fallback aman untuk lingkungan pengujian/pengembangan jika FIELD_ENCRYPTION_KEY kosong
_DEV_FALLBACK_KEY = b'VZwbZuQ8xrTxdGxdpVVw3sF03Kt8RivxSYNefr2gHM8='


def get_fernet_cipher() -> Fernet:
    """Mengembalikan instance Fernet dari FIELD_ENCRYPTION_KEY di settings."""
    raw_key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
    if raw_key and isinstance(raw_key, str) and raw_key.strip():
        try:
            return Fernet(raw_key.strip().encode('utf-8'))
        except Exception as e:
            logger.warning(f"FIELD_ENCRYPTION_KEY tidak valid ({e}), beralih ke kunci dev.")
    return Fernet(_DEV_FALLBACK_KEY)


def encrypt_account_number(plain_text: str) -> str:
    """
    Enkripsi nomor rekening atau dompet digital menggunakan Fernet.
    PENTING: Jangan pernah mencetak hasil plain_text ke logging.
    """
    if not plain_text:
        return ""
    clean = plain_text.strip()
    cipher = get_fernet_cipher()
    token = cipher.encrypt(clean.encode('utf-8'))
    return token.decode('utf-8')


def decrypt_account_number(cipher_text: str) -> str:
    """
    Dekripsi nomor rekening atau dompet digital dari ciphertext Fernet.
    PENTING: Jangan mencetak hasil dekripsi ke logging sistem.
    """
    if not cipher_text:
        return ""
    cipher = get_fernet_cipher()
    try:
        raw = cipher.decrypt(cipher_text.strip().encode('utf-8'))
        return raw.decode('utf-8')
    except (InvalidToken, Exception) as e:
        logger.error("Gagal mendekripsi nomor rekening penarikan (InvalidToken).")
        return ""


def mask_account_number(plain_number: str) -> str:
    """
    Menyamarkan nomor rekening/dompet, hanya menampilkan 4 digit terakhir:
    Contoh: '081234567890' -> '•••• 7890'
            '12345678'     -> '•••• 5678'
    """
    if not plain_number:
        return ""
    clean = plain_number.strip()
    if len(clean) <= 4:
        return f"•••• {clean}"
    last_four = clean[-4:]
    return f"•••• {last_four}"
