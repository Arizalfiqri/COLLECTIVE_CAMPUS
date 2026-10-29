import os
from pathlib import Path
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize django-environ
env = environ.Env(
    DEBUG=(bool, False),
    USE_HTTPS=(bool, False),
    SECURE_SSL_REDIRECT=(bool, False),
    SESSION_COOKIE_SECURE=(bool, False),
    CSRF_COOKIE_SECURE=(bool, False),
    SERVE_MEDIA_LOCAL=(bool, True),
    MIDTRANS_IS_PRODUCTION=(bool, False),
    KTM_AUTO_APPROVE=(bool, False),
    KTM_DELETE_AFTER_DECISION=(bool, True),
    PLATFORM_COMMISSION_PERCENT=(int, 8),
    PROTECTION_FEE=(int, 3000),
    LATE_FEE_PERCENT_PER_DAY=(int, 50),
    APPROVAL_DEADLINE_HOURS=(int, 24),
    PAYMENT_DEADLINE_HOURS=(int, 6),
    AUTO_CONFIRM_RETURN_HOURS=(int, 48),
    TRUST_TIERS=(str, 'baru:750000:15,tepercaya:1500000:10,sangat_tepercaya:3000000:10'),
    MAX_ITEM_VALUE=(int, 3000000),
    NO_DEPOSIT_BELOW_VALUE=(int, 150000),
    MIN_DEPOSIT_AMOUNT=(int, 25000),
    CROSS_CAMPUS_EXTRA_DEPOSIT_PERCENT=(int, 5),
    PROTECTION_FEE_PERCENT=(int, 5),
    PROTECTION_FEE_MIN=(int, 3000),
    PROTECTION_MANDATORY_ABOVE=(int, 500000),
    HANDOVER_PHOTO_RETENTION_DAYS=(int, 30),
    NON_RETURN_GRACE_HOURS=(int, 48),
    DEPOSIT_MODE=(str, 'off'),
    SALE_MAX_PRICE_NEW=(int, 1000000),
    SALE_MAX_PRICE_TRUSTED=(int, 3000000),
    SALE_MAX_PRICE_TOP=(int, 8000000),
    SITE_NAME=(str, 'Collective Campus'),
    SITE_SHORT_NAME=(str, 'Collective'),
    SITE_LOGOTYPE_DARK=(str, 'Collective'),
    SITE_LOGOTYPE_ACCENT=(str, 'Campus'),
    SITE_TAGLINE=(str, 'Saling sewa, saling jual, saling bantu.'),
    SITE_DOMAIN=(str, ''),
    KONFIRMASI_BUDAYA=(str, 'tidak'),
)

# Read .env file from root
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))

# Security and hosts
DEBUG = env('DEBUG')
import sys
SECRET_KEY = env('SECRET_KEY', default='')
if not SECRET_KEY:
    if DEBUG or 'test' in sys.argv:
        SECRET_KEY = 'django-insecure-kampusrent-secret-key-fallback'
    else:
        raise ValueError("SECRET_KEY wajib disetel pada lingkungan produksi (DEBUG=False).")

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost', 'testserver'])
CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=['http://127.0.0.1:8000', 'http://localhost:8000', 'https://127.0.0.1:8000', 'https://localhost:8000']
)

# Admin URL customization
ADMIN_URL = env('ADMIN_URL', default='admin/').strip('/') + '/'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    # KampusRent local apps
    'apps.core',
    'apps.accounts',
    'apps.verification',
    'apps.catalog',
    'apps.rentals',
    'apps.payments',
    'apps.trust',
    'apps.chat',
    'apps.sales',
    'dev_tools',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.chat.context_processors.unread_messages_count',
                'apps.core.context_processors.unread_notifications_count',
                'apps.core.context_processors.staff_operational_counts',
                'apps.core.context_processors.platform_settings',
                'apps.core.context_processors.site_branding',
            ],
        },
    },
]


WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
}

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Fast password hasher for test execution (Fase 7B: percepat test suite)
import sys
if 'test' in sys.argv or any('test' in arg for arg in sys.argv):
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]


# Internationalization
LANGUAGE_CODE = 'id'
TIME_ZONE = 'Asia/Jakarta'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Public Media (Item photos, condition photos)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
SERVE_MEDIA_LOCAL = env('SERVE_MEDIA_LOCAL')

# Private Media (KTM images - NEVER served publicly)
PRIVATE_MEDIA_ROOT = BASE_DIR / 'private_media'

# Security & HTTPS Configuration (Fase 7B Bagian C)
USE_HTTPS = env('USE_HTTPS')
SECURE_SSL_REDIRECT = env('SECURE_SSL_REDIRECT') if not DEBUG else False
SESSION_COOKIE_SECURE = env('SESSION_COOKIE_SECURE') if not DEBUG else False
CSRF_COOKIE_SECURE = env('CSRF_COOKIE_SECURE') if not DEBUG else False

if USE_HTTPS and not DEBUG:
    SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True)
    SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=True)
else:
    # Bila dijalankan di lingkungan lokal / tanpa sertifikat HTTPS, redam peringatan SSL
    SILENCED_SYSTEM_CHECKS = [
        'security.W004',  # SECURE_HSTS_SECONDS
        'security.W008',  # SECURE_SSL_REDIRECT
        'security.W012',  # SESSION_COOKIE_SECURE
        'security.W016',  # CSRF_COOKIE_SECURE
    ]


SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'

CSRF_FAILURE_VIEW = 'apps.core.views.csrf_failure_view'

# Email Configuration (Fase 7B Bagian C)
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='Collective Campus <no-reply@collectivecampus.id>')
SUPPORT_EMAIL = env('SUPPORT_EMAIL', default='bantuan@collectivecampus.id')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication URLs
LOGIN_URL = '/masuk/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Midtrans Sandbox Configuration (Fase 5A & 5A.1)
MIDTRANS_SERVER_KEY = env('MIDTRANS_SERVER_KEY', default='')
MIDTRANS_CLIENT_KEY = env('MIDTRANS_CLIENT_KEY', default='')
MIDTRANS_IS_PRODUCTION = env('MIDTRANS_IS_PRODUCTION', default=False)
MIDTRANS_ENABLED_PAYMENTS_RAW = env('MIDTRANS_ENABLED_PAYMENTS', default='')
MIDTRANS_ENABLED_PAYMENTS = [
    p.strip() for p in MIDTRANS_ENABLED_PAYMENTS_RAW.split(',') if p.strip()
]
MIDTRANS_SNAP_MODE = env('MIDTRANS_SNAP_MODE', default='popup').strip().lower()

# Handover WhatsApp Setting (Fase 5A.1)
WHATSAPP_HANDOVER_ENABLED = env.bool('WHATSAPP_HANDOVER_ENABLED', default=True)

# OCR Configuration
TESSERACT_CMD = env('TESSERACT_CMD', default='')
KTM_AUTO_APPROVE = env('KTM_AUTO_APPROVE')
KTM_DELETE_AFTER_DECISION = env('KTM_DELETE_AFTER_DECISION')

# Business Rules Settings
PLATFORM_COMMISSION_PERCENT = env('PLATFORM_COMMISSION_PERCENT')
PROTECTION_FEE = env('PROTECTION_FEE')
LATE_FEE_PERCENT_PER_DAY = env('LATE_FEE_PERCENT_PER_DAY')
APPROVAL_DEADLINE_HOURS = env('APPROVAL_DEADLINE_HOURS')
PAYMENT_DEADLINE_HOURS = env('PAYMENT_DEADLINE_HOURS')
AUTO_CONFIRM_RETURN_HOURS = env('AUTO_CONFIRM_RETURN_HOURS')

# SPEC v2 Settings
TRUST_TIERS_RAW = env('TRUST_TIERS')
MAX_ITEM_VALUE = env('MAX_ITEM_VALUE')
NO_DEPOSIT_BELOW_VALUE = env('NO_DEPOSIT_BELOW_VALUE')
MIN_DEPOSIT_AMOUNT = env('MIN_DEPOSIT_AMOUNT')
CROSS_CAMPUS_EXTRA_DEPOSIT_PERCENT = env('CROSS_CAMPUS_EXTRA_DEPOSIT_PERCENT')
PROTECTION_FEE_PERCENT = env('PROTECTION_FEE_PERCENT')
PROTECTION_FEE_MIN = env('PROTECTION_FEE_MIN')
PROTECTION_MANDATORY_ABOVE = env('PROTECTION_MANDATORY_ABOVE')
HANDOVER_PHOTO_RETENTION_DAYS = env('HANDOVER_PHOTO_RETENTION_DAYS')
NON_RETURN_GRACE_HOURS = env('NON_RETURN_GRACE_HOURS')
DEPOSIT_MODE = env('DEPOSIT_MODE', default='off').lower().strip()

# Fase 7C Settings (Dompet, Penarikan Dana & Retraining ML)
# Kunci enkripsi Fernet 32-byte url-safe base64 untuk data sensitif (nomor rekening bank/e-wallet)
FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY', default='bWk5ZmljRDBkY3h6M1Z2Uld5b3BLblV3M3kyRUR4MGh1YThwOG5VWTJtOD0=')
WITHDRAWAL_MIN = env.int('WITHDRAWAL_MIN', default=20000)
TRUST_MIN_REAL_EXAMPLES = env.int('TRUST_MIN_REAL_EXAMPLES', default=200)
TRUST_MIN_POSITIVES = env.int('TRUST_MIN_POSITIVES', default=20)

# Logging with RotatingFileHandler (Fase 7B Bagian C)
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file_app': {
            'class': 'apps.core.logging_handlers.SafeRotatingFileHandler',
            'filename': LOGS_DIR / 'kampusrent.log',
            'maxBytes': 5 * 1024 * 1024,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'file_security': {
            'class': 'apps.core.logging_handlers.SafeRotatingFileHandler',
            'filename': LOGS_DIR / 'security.log',
            'maxBytes': 5 * 1024 * 1024,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_app'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['file_security', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'apps.security': {
            'handlers': ['file_security', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['file_app', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# ==============================================================================
# KONFIGURASI FASE 7C: DOMPET, PENARIKAN DANA, & AMBANG PEMBELAJARAN ML
# ==============================================================================
FIELD_ENCRYPTION_KEY = os.environ.get('FIELD_ENCRYPTION_KEY', '')
WITHDRAWAL_MIN = int(os.environ.get('WITHDRAWAL_MIN', 20000))
TRUST_MIN_REAL_EXAMPLES = int(os.environ.get('TRUST_MIN_REAL_EXAMPLES', 200))
TRUST_MIN_POSITIVES = int(os.environ.get('TRUST_MIN_POSITIVES', 20))

# ==============================================================================
# KONFIGURASI FASE 8A: JUAL BELI (THRIFT)
# ==============================================================================
SALE_MAX_PRICE_NEW = env('SALE_MAX_PRICE_NEW')
SALE_MAX_PRICE_TRUSTED = env('SALE_MAX_PRICE_TRUSTED')
SALE_MAX_PRICE_TOP = env('SALE_MAX_PRICE_TOP')
SALE_PROHIBITED_KEYWORDS = [
    'obat resep', 'obat keras', 'miras', 'minuman keras', 'alkohol',
    'rokok', 'vape', 'pod', 'liquid vape', 'senjata', 'senjata tajam',
    'senapan', 'hewan', 'binatang', 'kucing', 'anjing',
    'makanan olahan', 'makanan basah', 'barang palsu', 'barang curian',
    'kw super', 'clone', 'akun digital', 'akun game', 'topup game',
]

# ==============================================================================
# KONFIGURASI FASE 8B: JUAL BELI - TRANSAKSI & DEADLINES
# ==============================================================================
SALE_PAYMENT_DEADLINE_HOURS = int(os.environ.get('SALE_PAYMENT_DEADLINE_HOURS', 6))
SALE_MEETUP_DEADLINE_DAYS = int(os.environ.get('SALE_MEETUP_DEADLINE_DAYS', 7))
SALE_INSPECTION_HOURS = int(os.environ.get('SALE_INSPECTION_HOURS', 48))
SALE_COMMISSION_PERCENT = int(os.environ.get('SALE_COMMISSION_PERCENT', 5))
SALE_COMMISSION_MIN = int(os.environ.get('SALE_COMMISSION_MIN', 2000))

# ==============================================================================
# KONFIGURASI FASE 8C: JUAL BELI - FITUR TAWAR HARGA TERSTRUKTUR (OPSIONAL)
# ==============================================================================
SALE_OFFERS_ENABLED = os.environ.get('SALE_OFFERS_ENABLED', 'False').lower() in ('true', '1', 'yes')

# ==============================================================================
# KONFIGURASI FASE 10: NAMA MEREK, LOGOTYPE, TAGLINE, & BUDAYA
# ==============================================================================
SITE_NAME = env('SITE_NAME', default='Collective Campus')
SITE_SHORT_NAME = env('SITE_SHORT_NAME', default='Collective')
SITE_LOGOTYPE_DARK = env('SITE_LOGOTYPE_DARK', default='Collective')
SITE_LOGOTYPE_ACCENT = env('SITE_LOGOTYPE_ACCENT', default='Campus')
SITE_LOGOTYPE = {
    'dark': SITE_LOGOTYPE_DARK,
    'accent': SITE_LOGOTYPE_ACCENT,
    'blue': SITE_LOGOTYPE_ACCENT,
}
SITE_TAGLINE = env('SITE_TAGLINE', default='Saling sewa, saling jual, saling bantu.')
SITE_DOMAIN = env('SITE_DOMAIN', default='')
SUPPORT_EMAIL = env('SUPPORT_EMAIL', default='bantuan@collectivecampus.id')
KONFIRMASI_BUDAYA = env('KONFIRMASI_BUDAYA', default='tidak')

