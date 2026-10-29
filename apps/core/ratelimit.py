import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('apps.security')


def get_client_ip(request):
    """Ambil IP klien nyata, memperhitungkan reverse proxy (X-Forwarded-For)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def is_rate_limited(action_key, max_attempts, window_seconds, request=None, user_id=None):
    """
    Memeriksa apakah aksi telah melebihi batas laju (Rate Limit).
    - action_key: string unik (misal: 'login:127.0.0.1:budi')
    - max_attempts: jumlah maksimal percobaan
    - window_seconds: jendela waktu dalam detik
    Mengembalikan tuple: (is_limited: bool, remaining_seconds: int)
    """
    now = timezone.now().timestamp()
    cache_key = f"ratelimit:{action_key}"
    timestamps = cache.get(cache_key, [])
    
    # Filter hanya percobaan dalam rentang window
    valid_timestamps = [t for t in timestamps if now - t < window_seconds]

    if len(valid_timestamps) >= max_attempts:
        oldest_valid = min(valid_timestamps)
        remaining = int(window_seconds - (now - oldest_valid)) + 1
        client_ip = get_client_ip(request) if request else 'unknown'
        logger.warning(
            f"Rate limit terlampaui untuk '{action_key}' dari IP {client_ip} "
            f"(user_id={user_id}). Percobaan: {len(valid_timestamps)}/{max_attempts}. Sisa waktu: {remaining}s"
        )
        return True, max(remaining, 1)

    valid_timestamps.append(now)
    cache.set(cache_key, valid_timestamps, timeout=window_seconds)
    return False, 0


def clear_rate_limit(action_key):
    """Menghapus catatan laju (misal setelah login berhasil)."""
    cache.delete(f"ratelimit:{action_key}")
