from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode
from django.utils.encoding import force_str

from django.conf import settings
from apps.accounts.forms import StudentRegistrationForm, StudentLoginForm
from apps.accounts.models import User, StudentProfile
from apps.accounts.tokens import email_verification_token, campus_email_verification_token
from apps.verification.models import KtmVerification


def register_view(request):
    """Halaman pendaftaran mahasiswa baru (/daftar/)."""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        # Rate limit pendaftaran: maks 5 pendaftaran per jam per IP
        from apps.core.ratelimit import is_rate_limited, get_client_ip
        ip = get_client_ip(request)
        limited, wait_sec = is_rate_limited(f"register:{ip}", max_attempts=5, window_seconds=3600, request=request)
        if limited:
            messages.error(request, f"Terlalu banyak permintaan pendaftaran dari jaringan Anda. Silakan tunggu beberapa saat.")
            return redirect('accounts:register')

        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(request=request)
            messages.success(
                request,
                f"Pendaftaran berhasil! Tautan verifikasi telah dikirimkan ke email {user.email}. "
                f"Silakan periksa kotak masuk dan klik tautan untuk mengaktifkan akun Anda sebelum masuk."
            )
            return redirect('accounts:login')
    else:
        form = StudentRegistrationForm()

    from apps.accounts.models import Campus
    campuses = Campus.objects.filter(is_active=True).order_by('name')

    return render(request, 'accounts/register.html', {
        'form': form,
        'campuses': campuses,
    })


def login_view(request):
    """Halaman masuk akun (/masuk/)."""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    next_url = request.GET.get('next', '')

    if request.method == 'POST':
        form = StudentLoginForm(request.POST, request=request)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)
            messages.success(request, f"Selamat datang kembali, {user.full_name or user.username}!")

            # Cek redirect tujuan yang aman
            next_target = request.POST.get('next', '')
            if next_target and url_has_allowed_host_and_scheme(next_target, allowed_hosts={request.get_host()}):
                return redirect(next_target)
            return redirect('accounts:dashboard')
    else:
        form = StudentLoginForm(request=request)

    return render(request, 'accounts/login.html', {
        'form': form,
        'next': next_url,
    })


def verify_email_view(request, uidb64, token):
    """Verifikasi email aktivasi akun pendaftaran baru."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and email_verification_token.check_token(user, token):
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        messages.success(request, "Alamat email Anda berhasil diverifikasi! Akun kini aktif, silakan masuk.")
        return redirect('accounts:login')
    else:
        messages.error(request, "Tautan verifikasi email tidak valid atau telah kedaluwarsa. Silakan ajukan kirim ulang.")
        return redirect('accounts:resend_verification')


def resend_verification_email_view(request):
    """Halaman dan proses kirim ulang tautan verifikasi email akun."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        from apps.core.ratelimit import is_rate_limited, get_client_ip
        ip = get_client_ip(request)
        limited, wait_sec = is_rate_limited(f"resend_verif:{ip}", max_attempts=3, window_seconds=3600, request=request)
        if limited:
            messages.error(request, f"Terlalu banyak permintaan kirim ulang. Silakan tunggu {wait_sec} detik.")
            return redirect('accounts:resend_verification')

        user = User.objects.filter(email__iexact=email).first()
        if user:
            if user.is_email_verified:
                messages.info(request, "Akun dengan email tersebut sudah terverifikasi. Silakan langsung masuk.")
                return redirect('accounts:login')
            from apps.accounts.emails import send_account_verification_email
            send_account_verification_email(user, request=request)
            messages.success(request, f"Tautan verifikasi baru telah dikirimkan ke {user.email}. Silakan periksa kotak masuk.")
            return redirect('accounts:login')
        else:
            messages.error(request, "Alamat email tidak ditemukan dalam sistem.")

    return render(request, 'accounts/resend_verification.html')


def verify_campus_email_view(request, uidb64, token):
    """Verifikasi email kampus resmi (.ac.id) sebagai sinyal kepercayaan tambahan."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and campus_email_verification_token.check_token(user, token):
        profile = getattr(user, 'student_profile', None)
        if profile:
            profile.is_campus_email_verified = True
            profile.save(update_fields=['is_campus_email_verified'])
            messages.success(
                request,
                f"Email kampus ({profile.campus_email}) berhasil diverifikasi! "
                f"Sinyal .ac.id telah terpasang pada profil Anda sebagai sinyal kepercayaan tambahan."
            )
            return redirect('accounts:dashboard' if request.user.is_authenticated else 'accounts:login')
    messages.error(request, "Tautan verifikasi email kampus tidak valid atau telah kedaluwarsa.")
    return redirect('accounts:dashboard' if request.user.is_authenticated else 'accounts:login')


def logout_view(request):
    """Keluar dari akun (/keluar/). Mendukung GET dan POST."""
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, "Anda berhasil keluar dari akun KampusRent.")
    return redirect('/')


@login_required(login_url='/masuk/')
def dashboard_view(request):
    """Dashboard mahasiswa (/dashboard/) dengan tab Sewa Saya, Permintaan Masuk, dan Barang Saya."""
    user = request.user
    profile = (
        StudentProfile.objects
        .select_related('campus')
        .filter(user=user)
        .first()
    )
    trust_score = getattr(user, 'trust_score', None)
    latest_ktm = KtmVerification.objects.filter(user=user).order_by('-created_at').first()

    # Query teroptimasi untuk mencegah N+1
    my_rentals = list(
        user.rentals_as_renter
        .select_related('item', 'item__category', 'owner', 'item__owner', 'owner__trust_score')
        .prefetch_related('item__photos')
        .order_by('-created_at')
    )

    incoming_requests = list(
        user.rentals_as_owner
        .select_related('item', 'item__category', 'renter', 'renter__student_profile__campus', 'renter__trust_score')
        .prefetch_related('item__photos')
        .order_by('-created_at')
    )

    my_items = list(
        user.items
        .select_related('category')
        .prefetch_related('photos')
        .order_by('-created_at')
    )

    items_count = len(my_items)
    rentals_count = len(my_rentals)
    orders_count = len(incoming_requests)

    reviews_received = list(
        user.reviews_received
        .select_related('rental', 'rental__item', 'reviewer')
        .order_by('-created_at')
    )

    from apps.payments.services import get_user_wallet_balance
    wallet_balance = get_user_wallet_balance(user)

    from apps.payments.models import ExtraCharge
    unpaid_extra_charges = list(
        ExtraCharge.objects.filter(renter=user, status=ExtraCharge.Status.TERUTANG)
        .select_related('rental', 'owner')
        .order_by('-created_at')
    )
    total_unpaid_extra_charges = sum(c.amount for c in unpaid_extra_charges)

    from apps.sales.models import SaleItem, SaleOrder
    my_sale_items = list(
        SaleItem.objects.filter(owner=user)
        .select_related('category')
        .prefetch_related('photos')
        .order_by('-created_at')
    )
    sale_items_count = len(my_sale_items)

    my_sale_purchases = list(
        SaleOrder.objects.filter(buyer=user)
        .select_related('item', 'seller', 'seller__student_profile__campus')
        .prefetch_related('item__photos')
        .order_by('-created_at')
    )
    sale_purchases_count = len(my_sale_purchases)

    my_sale_orders = list(
        SaleOrder.objects.filter(seller=user)
        .select_related('item', 'buyer', 'buyer__student_profile__campus')
        .prefetch_related('item__photos')
        .order_by('-created_at')
    )
    sale_orders_count = len(my_sale_orders)

    from django.db.models import Sum
    from apps.payments.models import WalletTransaction
    sales_sold_count = sum(1 for itm in my_sale_items if itm.status == SaleItem.Status.TERJUAL)
    active_sale_orders_count = sum(
        1 for o in my_sale_orders
        if o.status in (
            SaleOrder.Status.MENUNGGU_PEMBAYARAN,
            SaleOrder.Status.DIBAYAR,
            SaleOrder.Status.DISERAHKAN,
            SaleOrder.Status.SENGKETA,
        )
    )
    sales_revenue_total = WalletTransaction.objects.filter(
        user=user, kind=WalletTransaction.Kind.KREDIT_PENJUALAN
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    return render(request, 'accounts/dashboard.html', {
        'user': user,
        'profile': profile,
        'trust_score': trust_score,
        'wallet_balance': wallet_balance,
        'latest_ktm': latest_ktm,
        'items_count': items_count,
        'rentals_count': rentals_count,
        'orders_count': orders_count,
        'my_rentals': my_rentals,
        'incoming_requests': incoming_requests,
        'my_items': my_items,
        'my_sale_items': my_sale_items,
        'sale_items_count': sale_items_count,
        'my_sale_purchases': my_sale_purchases,
        'sale_purchases_count': sale_purchases_count,
        'my_sale_orders': my_sale_orders,
        'sale_orders_count': sale_orders_count,
        'sales_sold_count': sales_sold_count,
        'sales_revenue_total': sales_revenue_total,
        'active_sale_orders_count': active_sale_orders_count,
        'reviews_received': reviews_received,
        'unpaid_extra_charges': unpaid_extra_charges,
        'total_unpaid_extra_charges': total_unpaid_extra_charges,
    })



def user_profile_view(request, username):
    """
    Halaman profil publik mahasiswa (/profil/<username>/).
    Menampilkan info kampus, segel verifikasi KTM, cincin skor kepercayaan,
    daftar barang yang disewakan & dijual, serta riwayat ulasan yang diterima (sewa & jual beli).
    """
    from django.shortcuts import get_object_or_404
    from django.utils import timezone
    from apps.accounts.models import User
    from apps.sales.models import SaleItem, SaleReview

    target_user = get_object_or_404(
        User.objects.select_related('student_profile', 'student_profile__campus', 'trust_score'),
        username=username
    )
    profile = getattr(target_user, 'student_profile', None)
    trust_score = getattr(target_user, 'trust_score', None)
    active_items = target_user.items.filter(is_active=True).prefetch_related('photos').order_by('-created_at')
    reviews_received = target_user.reviews_received.select_related('reviewer', 'rental', 'rental__item').order_by('-created_at')

    active_sale_items = target_user.sale_items.filter(
        status=SaleItem.Status.AKTIF, expires_at__gt=timezone.now()
    ).prefetch_related('photos').order_by('-created_at')
    sale_reviews_received = target_user.sale_reviews_received.select_related(
        'reviewer', 'order', 'order__item'
    ).order_by('-created_at')

    from apps.sales.services import get_seller_tier, SELLER_TIER_LABELS
    seller_tier = get_seller_tier(target_user)
    seller_tier_label = SELLER_TIER_LABELS.get(seller_tier, 'Penjual baru')

    return render(request, 'accounts/user_profile.html', {
        'target_user': target_user,
        'profile': profile,
        'trust_score': trust_score,
        'active_items': active_items,
        'active_sale_items': active_sale_items,
        'reviews_received': reviews_received,
        'sale_reviews_received': sale_reviews_received,
        'seller_tier': seller_tier,
        'seller_tier_label': seller_tier_label,
    })


from django.contrib.auth import views as auth_views

class RateLimitedPasswordResetView(auth_views.PasswordResetView):
    """View atur ulang kata sandi dengan pembatasan laju (maks 5 request per jam per IP)."""
    template_name = 'accounts/password_reset_form.html'
    email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    extra_email_context = {
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'Collective Campus'),
        'site_name': getattr(settings, 'SITE_NAME', 'Collective Campus'),
    }

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST':
            from apps.core.ratelimit import is_rate_limited, get_client_ip
            ip = get_client_ip(request)
            limited, wait_sec = is_rate_limited(f"pwdreset:{ip}", max_attempts=5, window_seconds=3600, request=request)
            if limited:
                messages.error(request, "Terlalu banyak permohonan atur ulang kata sandi dari jaringan Anda. Silakan coba kembali nanti.")
                return redirect('accounts:password_reset')
        return super().dispatch(request, *args, **kwargs)



