from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Token generator untuk verifikasi email pendaftaran akun baru."""
    def _make_hash_value(self, user, timestamp):
        # Saat user.is_email_verified berubah menjadi True, token otomatis kedaluwarsa
        return f"{user.pk}{timestamp}{user.is_email_verified}{user.email}"


class CampusEmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Token generator untuk verifikasi email kampus (.ac.id) opsional."""
    def _make_hash_value(self, user, timestamp):
        profile = getattr(user, 'student_profile', None)
        c_email = profile.campus_email if profile else ''
        c_verified = profile.is_campus_email_verified if profile else False
        return f"{user.pk}{timestamp}{c_email}{c_verified}"


email_verification_token = EmailVerificationTokenGenerator()
campus_email_verification_token = CampusEmailVerificationTokenGenerator()
