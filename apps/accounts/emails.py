import logging
from django.conf import settings
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from apps.accounts.tokens import email_verification_token, campus_email_verification_token

logger = logging.getLogger('apps')


def send_account_verification_email(user, request=None):
    """Kirim email verifikasi aktivasi akun untuk pendaftaran baru."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)

    if request:
        base_url = request.build_absolute_uri('/')[:-1]
    else:
        base_url = 'http://localhost:8000'

    verify_url = f"{base_url}/verifikasi-email/{uid}/{token}/"

    site_name = getattr(settings, 'SITE_NAME', 'Collective Campus')
    subject = f"Verifikasi Alamat Email Anda | {site_name}"
    message = (
        f"Halo {user.full_name or user.username},\n\n"
        f"Terima kasih telah mendaftar di {site_name} - platform sewa dan jual beli barang antarmahasiswa terpercaya.\n\n"
        f"Silakan klik tautan di bawah ini untuk memverifikasi alamat email Anda:\n"
        f"{verify_url}\n\n"
        f"Tautan ini berlaku selama 24 jam.\n\n"
        f"Jika Anda tidak merasa mendaftar di {site_name}, silakan abaikan email ini.\n\n"
        f"Salam hangat,\n"
        f"Tim Pengelola {site_name}"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', f'{site_name} <no-reply@collectivecampus.id>'),
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Email verifikasi akun terkirim ke {user.email}")
        return True
    except Exception as e:
        logger.error(f"Gagal mengirim email verifikasi ke {user.email}: {e}")
        return False


def send_campus_email_verification(user, campus_email, request=None):
    """Kirim email verifikasi tautan email kampus (.ac.id)."""
    site_name = getattr(settings, 'SITE_NAME', 'Collective Campus')
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = campus_email_verification_token.make_token(user)

    if request:
        base_url = request.build_absolute_uri('/')[:-1]
    else:
        base_url = 'http://localhost:8000'

    verify_url = f"{base_url}/verifikasi-email-kampus/{uid}/{token}/"

    subject = f"Konfirmasi Email Kampus Anda | {site_name}"
    message = (
        f"Halo {user.full_name or user.username},\n\n"
        f"Anda telah menambahkan email kampus '{campus_email}' pada profil {site_name} Anda.\n\n"
        f"Konfirmasi email kampus ini dengan mengeklik tautan berikut:\n"
        f"{verify_url}\n\n"
        f"Setelah terverifikasi, status email .ac.id akan menjadi sinyal kepercayaan tambahan saat peninjauan KTM oleh administrator.\n\n"
        f"Salam hangat,\n"
        f"Tim Pengelola {site_name}"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', f'{site_name} <no-reply@collectivecampus.id>'),
            recipient_list=[campus_email],
            fail_silently=False,
        )
        logger.info(f"Email verifikasi kampus terkirim ke {campus_email}")
        return True
    except Exception as e:
        logger.error(f"Gagal mengirim email verifikasi kampus ke {campus_email}: {e}")
        return False
