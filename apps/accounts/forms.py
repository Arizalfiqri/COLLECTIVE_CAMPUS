import re
from datetime import date
from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User, StudentProfile
from apps.trust.models import TrustScore


class StudentRegistrationForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        label="Nama Lengkap",
        widget=forms.TextInput(attrs={
            'placeholder': 'Contoh: Rina Pratiwi',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={'required': 'Nama lengkap wajib diisi.'}
    )
    username = forms.CharField(
        max_length=150,
        label="Username",
        widget=forms.TextInput(attrs={
            'placeholder': 'Contoh: rina_pratiwi',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={'required': 'Username wajib diisi.'}
    )
    email = forms.EmailField(
        label="Alamat Email",
        widget=forms.EmailInput(attrs={
            'placeholder': 'Contoh: rina@mahasiswa.ac.id',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={
            'required': 'Alamat email wajib diisi.',
            'invalid': 'Format alamat email tidak valid.',
        }
    )
    phone_whatsapp = forms.CharField(
        max_length=20,
        label="Nomor WhatsApp",
        widget=forms.TextInput(attrs={
            'placeholder': 'Contoh: 081234567890',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={'required': 'Nomor WhatsApp wajib diisi.'}
    )
    campus = forms.CharField(
        max_length=150,
        label="Nama Kampus / Universitas",
        widget=forms.TextInput(attrs={
            'placeholder': 'Ketik nama kampus (misal: Institut Teknologi Sumatera)',
            'autocomplete': 'off',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={'required': 'Nama kampus wajib diisi.'}
    )
    is_new_campus = forms.CharField(required=False, widget=forms.HiddenInput())
    campus_city = forms.CharField(max_length=100, required=False, widget=forms.HiddenInput())
    campus_short_name = forms.CharField(max_length=50, required=False, widget=forms.HiddenInput())
    nim = forms.CharField(
        max_length=30,
        label="Nomor Induk Mahasiswa (NIM)",
        widget=forms.TextInput(attrs={
            'placeholder': 'Contoh: 2021110001',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={'required': 'NIM wajib diisi.'}
    )
    major = forms.CharField(
        max_length=100,
        label="Jurusan / Program Studi",
        widget=forms.TextInput(attrs={
            'placeholder': 'Contoh: Teknik Informatika',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={'required': 'Program studi wajib diisi.'}
    )
    entry_year = forms.IntegerField(
        label="Tahun Angkatan",
        widget=forms.NumberInput(attrs={
            'placeholder': 'Contoh: 2021',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={'required': 'Tahun angkatan wajib diisi.'}
    )
    campus_email = forms.EmailField(
        required=False,
        label="Email Kampus Resmi (.ac.id) — Opsional",
        widget=forms.EmailInput(attrs={
            'placeholder': 'Contoh: rina@mahasiswa.itera.ac.id',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        help_text="Opsional. Domain .ac.id yang terverifikasi menjadi sinyal kepercayaan tambahan saat admin meninjau KTM."
    )
    password = forms.CharField(
        label="Kata Sandi",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Minimal 8 karakter',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={'required': 'Kata sandi wajib diisi.'}
    )
    password_confirm = forms.CharField(
        label="Konfirmasi Kata Sandi",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Ulangi kata sandi',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={'required': 'Konfirmasi kata sandi wajib diisi.'}
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.data:
            data = self.data.copy()
            if 'campus_name' in data and not data.get('campus'):
                data['campus'] = data.get('campus_name', '')
            self.data = data

    def clean_campus(self):
        val = self.cleaned_data.get('campus')
        if not val:
            raise ValidationError("Nama kampus wajib diisi.")

        from apps.accounts.models import Campus
        if isinstance(val, Campus):
            return val

        from apps.accounts.services import resolve_or_create_campus
        is_new = str(self.data.get('is_new_campus', '')).strip().lower() in ['1', 'true', 'yes', 'on']
        campus_city = str(self.data.get('campus_city', '')).strip()
        campus_short_name = str(self.data.get('campus_short_name', '')).strip()

        campus_obj, created, conflict = resolve_or_create_campus(
            raw_campus_input=str(val),
            city=campus_city,
            is_explicit_new=is_new,
            custom_short_name=campus_short_name
        )
        if conflict:
            raise ValidationError(
                f'Nama kampus mirip dengan kampus terdaftar "{conflict.name}". '
                f'Silakan pilih dari saran kampus yang sudah ada atau gunakan ejaan resmi.'
            )
        if not campus_obj:
            raise ValidationError("Nama kampus tidak valid.")
        return campus_obj

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not re.match(r'^[a-zA-Z0-9_.]+$', username):
            raise ValidationError("Username hanya boleh berisi huruf, angka, titik, dan garis bawah.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Username ini sudah terdaftar. Silakan pilih username lain.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Alamat email ini sudah terdaftar. Silakan masuk atau gunakan email lain.")
        return email

    def clean_phone_whatsapp(self):
        phone = self.cleaned_data.get('phone_whatsapp', '').strip()
        # Bersihkan spasi dan strip
        cleaned_phone = re.sub(r'[\s\-]', '', phone)
        if not re.match(r'^(\+62|62|0)8[1-9][0-9]{6,11}$', cleaned_phone):
            raise ValidationError("Format nomor WhatsApp tidak valid. Gunakan format seperti 081234567890.")
        return cleaned_phone

    def clean_nim(self):
        nim = self.cleaned_data.get('nim', '').strip()
        cleaned_nim = re.sub(r'[\s\-]', '', nim)
        if len(cleaned_nim) < 6 or len(cleaned_nim) > 30:
            raise ValidationError("NIM harus berisi antara 6 sampai 30 karakter.")
        
        # Cek daftar hitam NIM (SPEC v2 Bagian G & I)
        from apps.accounts.models import BlacklistedNim
        if BlacklistedNim.objects.filter(nim=cleaned_nim).exists():
            raise ValidationError("NIM ini telah masuk daftar hitam platform dan tidak dapat digunakan untuk mendaftar.")
        return cleaned_nim

    def clean_entry_year(self):
        year = self.cleaned_data.get('entry_year')
        current_year = date.today().year
        if year < 2010 or year > (current_year + 1):
            raise ValidationError(f"Tahun angkatan harus antara 2010 dan {current_year + 1}.")
        return year

    def clean_campus_email(self):
        c_email = self.cleaned_data.get('campus_email', '').strip().lower()
        if c_email and not c_email.endswith('.ac.id'):
            raise ValidationError("Email kampus harus berakhiran domain '.ac.id'.")
        return c_email

    def clean_password(self):
        pwd = self.cleaned_data.get('password')
        if len(pwd) < 8:
            raise ValidationError("Kata sandi harus terdiri dari minimal 8 karakter.")
        return pwd

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get('password')
        pwd_confirm = cleaned_data.get('password_confirm')
        if pwd and pwd_confirm and pwd != pwd_confirm:
            self.add_error('password_confirm', "Konfirmasi kata sandi tidak cocok dengan kata sandi.")

        # Cek pola NIM sesuai kampus jika kampus memiliki nim_pattern (SPEC v2 Bagian F)
        campus = cleaned_data.get('campus')
        nim = cleaned_data.get('nim')
        if campus and campus.nim_pattern and nim:
            if not re.search(campus.nim_pattern, nim):
                self.add_error('nim', f"Pola NIM tidak sesuai dengan format {campus.name}.")

        return cleaned_data

    @transaction.atomic
    def save(self, request=None):
        cd = self.cleaned_data
        user = User.objects.create_user(
            username=cd['username'],
            email=cd['email'],
            password=cd['password'],
            full_name=cd['full_name'],
            phone_whatsapp=cd['phone_whatsapp'],
            is_verified_student=False,
            is_email_verified=False,
        )
        profile = StudentProfile.objects.create(
            user=user,
            nim=cd['nim'],
            campus=cd['campus'],
            major=cd['major'],
            entry_year=cd['entry_year'],
            student_status='aktif',
            campus_email=cd.get('campus_email', ''),
            is_campus_email_verified=False,
        )
        # Buat TrustScore inisial untuk pengguna baru (skor awal 60)
        TrustScore.objects.get_or_create(
            user=user,
            defaults={
                'score': 60,
                'is_new_user': True,
                'risk_probability': 0.4,
                'computed_at': timezone.now(),
            }
        )

        # Kirim email verifikasi aktivasi akun
        from apps.accounts.emails import send_account_verification_email, send_campus_email_verification
        send_account_verification_email(user, request=request)

        # Kirim verifikasi email kampus jika diisi
        if profile.campus_email:
            send_campus_email_verification(user, profile.campus_email, request=request)

        return user


class StudentLoginForm(forms.Form):
    username_or_email = forms.CharField(
        label="Username atau Email",
        widget=forms.TextInput(attrs={
            'placeholder': 'Username atau email terdaftar',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={'required': 'Username atau email wajib diisi.'}
    )
    password = forms.CharField(
        label="Kata Sandi",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Masukkan kata sandi Anda',
            'class': 'w-full bg-card border border-line rounded-lg px-4 py-2.5 text-ink placeholder-ink-muted/60 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent',
        }),
        error_messages={'required': 'Kata sandi wajib diisi.'}
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

    def clean(self):
        cleaned_data = super().clean()
        login_id = cleaned_data.get('username_or_email', '').strip()
        pwd = cleaned_data.get('password', '')

        # 1. Rate limiting pada percobaan login: maks 5 percobaan per 5 menit
        rate_key = None
        if login_id:
            from apps.core.ratelimit import is_rate_limited, clear_rate_limit, get_client_ip
            ip = get_client_ip(self.request) if self.request else '127.0.0.1'
            rate_key = f"login:{ip}:{login_id.lower()}"
            limited, wait_sec = is_rate_limited(rate_key, max_attempts=5, window_seconds=300, request=self.request)
            if limited:
                raise ValidationError(
                    f"Terlalu banyak percobaan masuk yang gagal. "
                    f"Demi keamanan akun, silakan tunggu {wait_sec} detik sebelum mencoba lagi."
                )

        if login_id and pwd:
            # Dukung login via username atau email
            username_target = login_id
            if '@' in login_id:
                user_match = User.objects.filter(email__iexact=login_id).first()
                if user_match:
                    username_target = user_match.username

            user = authenticate(username=username_target, password=pwd)
            if user is None:
                raise ValidationError("Username/email atau kata sandi tidak valid. Silakan coba lagi.")
            if not user.is_active:
                raise ValidationError("Akun ini sedang dinonaktifkan. Silakan hubungi admin.")
            if getattr(user, 'is_suspended', False):
                raise ValidationError("Akun Anda telah dibekukan karena pelanggaran sewa. Silakan hubungi admin.")

            # Cek verifikasi email untuk akun baru (akun yang sudah ada tidak dikunci karena is_email_verified=True)
            if not getattr(user, 'is_email_verified', True):
                raise ValidationError(
                    "Alamat email belum diverifikasi. Silakan periksa tautan verifikasi yang telah kami kirimkan ke email Anda, "
                    "atau gunakan menu 'Kirim Ulang Verifikasi Email'."
                )

            # Jika berhasil, bersihkan riwayat percobaan rate limit
            if rate_key:
                clear_rate_limit(rate_key)

            cleaned_data['user'] = user

        return cleaned_data
