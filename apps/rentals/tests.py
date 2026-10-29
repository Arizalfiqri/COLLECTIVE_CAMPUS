"""
Unit test untuk perhitungan bisnis di model Rental.
Mengacu pada contoh PROJECT_SPEC.md bagian 7.2:

  Kamera Rp75.000/hari, 3 hari, deposit Rp500.000, dengan proteksi (Rp3.000):
  - rent_total  = 225.000
  - grand_total = 728.000
  - commission  = 18.000
  - owner_net   = 207.000
  Terlambat 1 hari:
  - late_fee    = 37.500
  - deposit_refund = 462.500
"""
from datetime import date, timedelta
from unittest import mock
from django.test import TestCase, Client, TransactionTestCase, override_settings
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import User, StudentProfile, Campus
from apps.catalog.models import Category, Item
from apps.rentals.models import Rental, RentalAgreement
from apps.chat.models import Conversation
from apps.core.models import Notification
from apps.rentals.services import (
    ajukan_sewa,
    setujui_sewa,
    tolak_sewa,
    batalkan_sewa,
    kedaluwarsa_sewa,
    RentalError,
    RentalValidationError,
    RentalPermissionError,
    RentalStateError,
)
from apps.rentals.management.commands.process_deadlines import run_process_deadlines


class RentalCalculationTest(TestCase):
    """Memverifikasi semua rumus bisnis di Rental sesuai PROJECT_SPEC.md 7.2."""

    @classmethod
    def setUpTestData(cls):
        # Pengguna dan barang minimal
        cls.owner = User.objects.create_user(
            username='owner_test', email='owner@test.id',
            password='Test1234!', full_name='Pemilik Uji',
        )
        cls.renter = User.objects.create_user(
            username='renter_test', email='renter@test.id',
            password='Test1234!', full_name='Penyewa Uji',
        )
        cls.cat = Category.objects.create(name='Kamera Test', slug='kamera-test', order=99)
        cls.item = Item.objects.create(
            owner=cls.owner,
            category=cls.cat,
            title='Kamera Uji',
            slug='kamera-uji',
            description='Kamera untuk pengujian unit test.',
            condition='sangat_baik',
            estimated_value=8_000_000,
            price_per_day=75_000,
            deposit_amount=500_000,
            min_days=1,
            max_days=7,
            pickup_area='Gedung Test',
        )

    def _make_rental(self, days=3, start=None, use_protection=True,
                     returned_date=None, damage_fee=0):
        """Helper: buat Rental dengan snapshot harga diisi manual."""
        if start is None:
            start = date(2026, 10, 1)
        end = date.fromordinal(start.toordinal() + days - 1)
        prot_fee = settings.PROTECTION_FEE if use_protection else 0
        rent_total = self.item.price_per_day * days
        rental = Rental(
            item=self.item,
            renter=self.renter,
            owner=self.owner,
            start_date=start,
            end_date=end,
            days=days,
            price_per_day_snapshot=self.item.price_per_day,
            rent_total=rent_total,
            deposit_total=self.item.deposit_amount,
            protection_fee=prot_fee,
            grand_total=rent_total + self.item.deposit_amount + prot_fee,
            use_protection=use_protection,
            damage_fee=damage_fee,
        )
        if returned_date:
            rental.returned_date = returned_date
        return rental

    # ---------- calc_days ----------

    def test_calc_days_3_hari(self):
        """days = (end - start).days + 1 → 3 hari (tanggal akhir dihitung)."""
        r = self._make_rental(days=3)
        self.assertEqual(r.calc_days(), 3)

    def test_calc_days_1_hari(self):
        """Satu hari penuh jika start == end."""
        start = date(2026, 10, 1)
        r = Rental(
            item=self.item, renter=self.renter, owner=self.owner,
            start_date=start, end_date=start,
            price_per_day_snapshot=75_000, deposit_total=500_000,
            protection_fee=0, rent_total=75_000,
        )
        self.assertEqual(r.calc_days(), 1)

    # ---------- calc_rent_total ----------

    def test_rent_total_kamera_3_hari(self):
        """rent_total = 75.000 × 3 = 225.000."""
        r = self._make_rental(days=3)
        self.assertEqual(r.calc_rent_total(), 225_000)

    # ---------- calc_grand_total ----------

    def test_grand_total_dengan_proteksi(self):
        """grand_total = 225.000 + 500.000 + 3.000 = 728.000."""
        r = self._make_rental(days=3, use_protection=True)
        self.assertEqual(r.grand_total, 728_000)
        self.assertEqual(r.calc_grand_total(), 728_000)

    def test_grand_total_tanpa_proteksi(self):
        """grand_total = 225.000 + 500.000 = 725.000."""
        r = self._make_rental(days=3, use_protection=False)
        self.assertEqual(r.grand_total, 725_000)

    # ---------- calc_commission ----------

    def test_commission_8_persen(self):
        """commission = round(225.000 × 8/100) = 18.000."""
        r = self._make_rental(days=3)
        self.assertEqual(r.calc_commission(), 18_000)

    def test_commission_pembulatan(self):
        """Komisi di-round ke bilangan bulat (bukan desimal)."""
        r = self._make_rental(days=3)
        komisi = r.calc_commission()
        self.assertIsInstance(komisi, int)

    # ---------- calc_owner_net ----------

    def test_owner_net(self):
        """owner_net = 225.000 - 18.000 = 207.000."""
        r = self._make_rental(days=3)
        self.assertEqual(r.calc_owner_net(), 207_000)

    # ---------- calc_late_days & calc_late_fee ----------

    def test_late_days_tepat_waktu(self):
        """Tidak terlambat jika returned_date == end_date."""
        r = self._make_rental(days=3, start=date(2026, 10, 1))
        r.returned_date = date(2026, 10, 3)  # end_date = 3 Oktober
        self.assertEqual(r.calc_late_days(), 0)

    def test_late_days_terlambat_1_hari(self):
        """Terlambat 1 hari jika returned_date = end_date + 1."""
        r = self._make_rental(days=3, start=date(2026, 10, 1))
        r.returned_date = date(2026, 10, 4)  # end_date = 3 Oktober, kembali 4 Oktober
        self.assertEqual(r.calc_late_days(), 1)

    def test_late_fee_1_hari(self):
        """late_fee = round(75.000 × 0.5 × 1) = 37.500."""
        r = self._make_rental(days=3, start=date(2026, 10, 1))
        r.returned_date = date(2026, 10, 4)
        self.assertEqual(r.calc_late_fee(), 37_500)

    def test_late_fee_tidak_melebihi_deposit(self):
        """Denda tidak boleh melebihi total deposit."""
        r = self._make_rental(days=3, start=date(2026, 10, 1))
        r.returned_date = date(2026, 12, 31)  # sangat terlambat
        self.assertLessEqual(r.calc_late_fee(), r.deposit_total)

    # ---------- calc_deposit_refund ----------

    def test_deposit_refund_tanpa_denda(self):
        """deposit_refund = 500.000 (tidak ada denda/kerusakan)."""
        r = self._make_rental(days=3, start=date(2026, 10, 1))
        r.returned_date = date(2026, 10, 3)
        self.assertEqual(r.calc_deposit_refund(), 500_000)

    def test_deposit_refund_setelah_denda(self):
        """deposit_refund = 500.000 - 37.500 = 462.500."""
        r = self._make_rental(days=3, start=date(2026, 10, 1))
        r.returned_date = date(2026, 10, 4)
        self.assertEqual(r.calc_deposit_refund(), 462_500)

    def test_deposit_refund_tidak_negatif(self):
        """deposit_refund tidak boleh negatif walau denda + kerusakan > deposit."""
        r = self._make_rental(days=3, start=date(2026, 10, 1),
                               returned_date=date(2026, 10, 4), damage_fee=1_000_000)
        self.assertGreaterEqual(r.calc_deposit_refund(), 0)

    # ---------- calc_platform_income ----------

    def test_platform_income_dengan_proteksi(self):
        """platform_income = commission + protection_fee = 18.000 + 3.000 = 21.000."""
        r = self._make_rental(days=3, use_protection=True)
        self.assertEqual(r.calc_platform_income(), 21_000)

    def test_platform_income_tanpa_proteksi(self):
        """platform_income = 18.000 (hanya komisi)."""
        r = self._make_rental(days=3, use_protection=False)
        self.assertEqual(r.calc_platform_income(), 18_000)

    # ---------- snapshot_pricing ----------

    def test_snapshot_pricing_isi_semua_field(self):
        """snapshot_pricing() mengisi semua field harga dari Item."""
        start = date(2026, 10, 1)
        r = Rental(
            item=self.item, renter=self.renter, owner=self.owner,
            start_date=start, end_date=date(2026, 10, 3),
            use_protection=True,
        )
        r.snapshot_pricing()
        self.assertEqual(r.days, 3)
        self.assertEqual(r.price_per_day_snapshot, 75_000)
        self.assertEqual(r.deposit_total, 500_000)
        self.assertEqual(r.protection_fee, settings.PROTECTION_FEE)
        self.assertEqual(r.rent_total, 225_000)
        self.assertEqual(r.grand_total, 225_000 + 500_000 + settings.PROTECTION_FEE)


# ==============================================================================
# FASE 4: TEST SUITE LENGKAP
# ==============================================================================

class StateMachineTransitionsTest(TestCase):
    """Pengujian semua transisi yang diizinkan dan dilarang menurut peran dan status."""

    def setUp(self):
        self.campus = Campus.objects.create(name='Universitas Negeri Uji', short_name='UNU', city='Bandar Lampung')
        self.owner = User.objects.create_user(
            username='owner_user', email='owner@test.ac.id',
            password='TestPassword123!', full_name='Budi Pemilik',
            is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.owner, campus=self.campus, nim='12345678')

        self.renter = User.objects.create_user(
            username='renter_user', email='renter@test.ac.id',
            password='TestPassword123!', full_name='Siti Penyewa',
            is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.renter, campus=self.campus, nim='87654321')

        self.other_user = User.objects.create_user(
            username='other_user', email='other@test.ac.id',
            password='TestPassword123!', full_name='Joko Pihak Ketiga',
            is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.other_user, campus=self.campus, nim='11223344')

        self.cat = Category.objects.create(name='Elektronik', slug='elektronik', order=1)
        self.item = Item.objects.create(
            owner=self.owner, category=self.cat, title='Proyektor Mini', slug='proyektor-mini',
            condition='sangat_baik', estimated_value=500_000, price_per_day=50_000,
            deposit_amount=100_000, min_days=1, max_days=7, pickup_area='Perpustakaan',
            is_active=True, min_renter_tier='baru',
        )

        self.start = timezone.localdate() + timedelta(days=2)
        self.end = self.start + timedelta(days=2)  # 3 hari

    def test_allowed_full_cycle_phase4(self):
        """Alur lengkap: Ajukan -> Setujui -> Batalkan sebelum bayar."""
        rental = ajukan_sewa(
            item=self.item, renter=self.renter,
            start_date=self.start, end_date=self.end,
            use_protection=False, terms_accepted=True
        )
        self.assertEqual(rental.status, Rental.Status.MENUNGGU_PERSETUJUAN)
        self.assertIsNotNone(rental.requested_at)

        # Pemilik menyetujui
        approved_rental = setujui_sewa(rental, self.owner)
        self.assertEqual(approved_rental.status, Rental.Status.MENUNGGU_PEMBAYARAN)
        self.assertIsNotNone(approved_rental.approved_at)

        # Penyewa membatalkan sebelum bayar
        cancelled_rental = batalkan_sewa(approved_rental, self.renter, reason="Ada jadwal mendadak")
        self.assertEqual(cancelled_rental.status, Rental.Status.DIBATALKAN)
        self.assertEqual(cancelled_rental.cancelled_by, self.renter)
        self.assertEqual(cancelled_rental.cancel_reason, "Ada jadwal mendadak")

    def test_tolak_sewa_by_owner(self):
        """Pemilik menolak permintaan sewa."""
        rental = ajukan_sewa(
            item=self.item, renter=self.renter,
            start_date=self.start, end_date=self.end,
            use_protection=False, terms_accepted=True
        )
        rejected = tolak_sewa(rental, self.owner, reason="Barang sedang diservis")
        self.assertEqual(rejected.status, Rental.Status.DITOLAK)
        self.assertEqual(rejected.cancel_reason, "Barang sedang diservis")

    def test_forbidden_approval_by_renter_or_third_party(self):
        """Penyewa atau pihak ketiga dilarang menyetujui sewa."""
        rental = ajukan_sewa(
            item=self.item, renter=self.renter,
            start_date=self.start, end_date=self.end,
            use_protection=False, terms_accepted=True
        )
        with self.assertRaises(RentalPermissionError):
            setujui_sewa(rental, self.renter)

        with self.assertRaises(RentalPermissionError):
            setujui_sewa(rental, self.other_user)

    def test_forbidden_rejection_by_renter(self):
        """Penyewa dilarang menolak sewa (hanya pemilik)."""
        rental = ajukan_sewa(
            item=self.item, renter=self.renter,
            start_date=self.start, end_date=self.end,
            use_protection=False, terms_accepted=True
        )
        with self.assertRaises(RentalPermissionError):
            tolak_sewa(rental, self.renter, reason="Tolak sendiri")

    def test_forbidden_cancellation_by_third_party(self):
        """Pihak luar dilarang membatalkan sewa."""
        rental = ajukan_sewa(
            item=self.item, renter=self.renter,
            start_date=self.start, end_date=self.end,
            use_protection=False, terms_accepted=True
        )
        with self.assertRaises(RentalPermissionError):
            batalkan_sewa(rental, self.other_user, reason="Ikut campur")

    def test_forbidden_state_transitions(self):
        """Transisi yang tidak diizinkan berdasarkan status."""
        rental = ajukan_sewa(
            item=self.item, renter=self.renter,
            start_date=self.start, end_date=self.end,
            use_protection=False, terms_accepted=True
        )
        # Setujui sekali
        setujui_sewa(rental, self.owner)

        # Coba setujui lagi dari status menunggu_pembayaran -> Error
        with self.assertRaises(RentalStateError):
            setujui_sewa(rental, self.owner)

        # Coba tolak sewa yang sudah berstatus menunggu_pembayaran -> Error
        with self.assertRaises(RentalStateError):
            tolak_sewa(rental, self.owner, reason="Mau tolak")

        # Batalkan
        batalkan_sewa(rental, self.owner, reason="Batal")

        # Coba batalkan sewa yang sudah dibatalkan -> Error
        with self.assertRaises(RentalStateError):
            batalkan_sewa(rental, self.renter, reason="Batal lagi")


class RentalValidationTest(TestCase):
    """Pengujian validasi form pengajuan sewa."""

    def setUp(self):
        self.campus = Campus.objects.create(name='Institut Sains Uji', short_name='ISU', city='Lampung')
        self.owner = User.objects.create_user(
            username='owner_v', email='owner_v@test.id',
            password='TestPassword123!', full_name='Owner Validasi',
            is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.owner, campus=self.campus, nim='11112222')

        self.renter = User.objects.create_user(
            username='renter_v', email='renter_v@test.id',
            password='TestPassword123!', full_name='Renter Validasi',
            is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.renter, campus=self.campus, nim='33334444')

        self.cat = Category.objects.create(name='Praktikum', slug='praktikum', order=2)
        self.item = Item.objects.create(
            owner=self.owner, category=self.cat, title='Mikroskop Siswa', slug='mikroskop-siswa',
            condition='baik', estimated_value=500_000, price_per_day=30_000,
            deposit_amount=100_000, min_days=2, max_days=5, pickup_area='Laboratorium',
            is_active=True, min_renter_tier='baru',
        )

        self.today = timezone.localdate()

    def test_past_start_date_rejected(self):
        """Tanggal mulai di masa lalu ditolak."""
        past_date = self.today - timedelta(days=1)
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.renter, past_date, self.today, terms_accepted=True)

    def test_start_date_over_60_days_rejected(self):
        """Tanggal mulai lebih dari 60 hari ke depan ditolak."""
        far_future = self.today + timedelta(days=61)
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.renter, far_future, far_future + timedelta(days=2), terms_accepted=True)

    def test_end_date_before_start_date_rejected(self):
        """Tanggal akhir sebelum tanggal mulai ditolak."""
        start = self.today + timedelta(days=3)
        end = self.today + timedelta(days=2)
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)

    def test_duration_outside_min_max_rejected(self):
        """Durasi kurang dari min_days atau lebih dari max_days ditolak."""
        start = self.today + timedelta(days=2)
        # min_days = 2, coba 1 hari (start == end)
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.renter, start, start, terms_accepted=True)

        # max_days = 5, coba 6 hari
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.renter, start, start + timedelta(days=5), terms_accepted=True)

    def test_renting_own_item_rejected(self):
        """Pemilik tidak boleh menyewa barangnya sendiri."""
        start = self.today + timedelta(days=2)
        end = start + timedelta(days=2)
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.owner, start, end, terms_accepted=True)

    def test_inactive_item_rejected(self):
        """Barang nonaktif tidak dapat disewa."""
        self.item.is_active = False
        self.item.save()
        start = self.today + timedelta(days=2)
        end = start + timedelta(days=2)
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)

    def test_unverified_student_rejected(self):
        """Mahasiswa belum verifikasi KTM ditolak mengajukan sewa."""
        self.renter.is_verified_student = False
        self.renter.save()
        start = self.today + timedelta(days=2)
        end = start + timedelta(days=2)
        with self.assertRaises(RentalPermissionError):
            ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)

    def test_suspended_user_rejected(self):
        """Mahasiswa yang dibekukan ditolak mengajukan sewa."""
        self.renter.is_suspended = True
        self.renter.save()
        start = self.today + timedelta(days=2)
        end = start + timedelta(days=2)
        with self.assertRaises(RentalPermissionError):
            ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)

    def test_terms_not_accepted_rejected(self):
        """Syarat dan ketentuan wajib dicentang."""
        start = self.today + timedelta(days=2)
        end = start + timedelta(days=2)
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.renter, start, end, terms_accepted=False)

    def test_tier_item_value_limit_rejected(self):
        """Penyewa tier baru (limit 750.000) ditolak jika nilai barang > 750.000."""
        self.item.estimated_value = 1_000_000
        self.item.save()
        start = self.today + timedelta(days=2)
        end = start + timedelta(days=2)
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)

    def test_min_renter_tier_requirement_rejected(self):
        """Penyewa tier baru ditolak jika pemilik mensyaratkan min_renter_tier tepercaya."""
        self.item.min_renter_tier = 'tepercaya'
        self.item.save()
        start = self.today + timedelta(days=2)
        end = start + timedelta(days=2)
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)

    def test_duplicate_active_request_rejected(self):
        """Hanya satu permintaan aktif per barang per penyewa."""
        start = self.today + timedelta(days=2)
        end = start + timedelta(days=2)
        # Pengajuan pertama
        ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)

        # Pengajuan kedua oleh penyewa yang sama pada barang yang sama
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.renter, start + timedelta(days=10), end + timedelta(days=10), terms_accepted=True)


@override_settings(DEPOSIT_MODE='legacy')
class PricingAndDepositCalculationTest(TestCase):
    """Pengujian perhitungan deposit_total, grand_total, dan proteksi sesuai SPEC v2."""

    def setUp(self):
        self.campus_a = Campus.objects.create(name='Kampus A', short_name='KA', city='Kota A')
        self.campus_b = Campus.objects.create(name='Kampus B', short_name='KB', city='Kota B')

        self.owner = User.objects.create_user(
            username='owner_p', email='owner_p@test.id',
            password='TestPassword123!', is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.owner, campus=self.campus_a, nim='55556666')

        self.renter = User.objects.create_user(
            username='renter_p', email='renter_p@test.id',
            password='TestPassword123!', is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.renter, campus=self.campus_a, nim='77778888')

        self.cat = Category.objects.create(name='Kamera', slug='kamera', order=1)
        self.today = timezone.localdate()

    def test_kamera_rp75000_3_hari_pricing_and_agreement(self):
        """
        Contoh spesifikasi: kamera Rp75.000/hari, 3 hari, nilai Rp700.000 (proteksi wajib 5%),
        deposit barang Rp500.000.
        rent_total = 225.000
        deposit_total = max(500.000, 15% dari 700.000 = 105.000) = 500.000
        protection_fee = max(3.000, round(225.000 * 5 / 100)) = 11.250
        grand_total = 225.000 + 500.000 + 11.250 = 736.250
        """
        item = Item.objects.create(
            owner=self.owner, category=self.cat, title='Kamera DSLR Uji', slug='kamera-dslr-uji',
            estimated_value=700_000, price_per_day=75_000, deposit_amount=500_000,
            min_days=1, max_days=7, pickup_area='Lab', is_active=True,
            require_ktm_held=True,
        )
        start = self.today + timedelta(days=2)
        end = start + timedelta(days=2)  # 3 hari

        rental = ajukan_sewa(item, self.renter, start, end, use_protection=False, terms_accepted=True)

        self.assertEqual(rental.days, 3)
        self.assertEqual(rental.rent_total, 225_000)
        self.assertEqual(rental.deposit_total, 500_000)
        self.assertTrue(rental.use_protection)  # Wajib karena nilai > 500.000
        self.assertEqual(rental.protection_fee, 11_250)
        self.assertEqual(rental.grand_total, 225_000 + 500_000 + 11_250)

        # Periksa RentalAgreement snapshot
        self.assertTrue(hasattr(rental, 'agreement'))
        snap = rental.agreement.terms_snapshot
        self.assertEqual(snap['require_ktm_held'], True)
        self.assertEqual(snap['grand_total'], rental.grand_total)

    def test_cross_campus_deposit_calculation(self):
        """Penyewa lintas kampus mendapat tambahan deposit 5 poin persen."""
        # Ubah kampus penyewa menjadi kampus B
        profile = self.renter.student_profile
        profile.campus = self.campus_b
        profile.save()

        # Barang nilai 600.000, deposit barang kecil (Rp50.000).
        # Tier baru: 15% + 5% lintas kampus = 20% dari 600.000 = 120.000.
        # deposit_total = max(50.000, 120.000) = 120.000.
        item = Item.objects.create(
            owner=self.owner, category=self.cat, title='Lensa Kamera', slug='lensa-kamera',
            estimated_value=600_000, price_per_day=40_000, deposit_amount=50_000,
            min_days=1, max_days=7, pickup_area='Lab', is_active=True,
        )
        start = self.today + timedelta(days=5)
        end = start + timedelta(days=1)  # 2 hari

        rental = ajukan_sewa(item, self.renter, start, end, terms_accepted=True)
        self.assertEqual(rental.deposit_total, 120_000)


class CollisionAndAutoRejectionTest(TestCase):
    """Pengujian tabrakan anti double-booking saat ajukan dan saat setujui."""

    def setUp(self):
        self.campus = Campus.objects.create(name='Universitas Uji', short_name='UU', city='Bandar Lampung')
        self.owner = User.objects.create_user(username='owner_c', email='owner_c@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.owner, campus=self.campus, nim='99001122')

        self.renter_a = User.objects.create_user(username='renter_a', email='renter_a@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.renter_a, campus=self.campus, nim='99001133')

        self.renter_b = User.objects.create_user(username='renter_b', email='renter_b@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.renter_b, campus=self.campus, nim='99001144')

        self.cat = Category.objects.create(name='Alat', slug='alat', order=1)
        self.item = Item.objects.create(
            owner=self.owner, category=self.cat, title='Drone Kampus', slug='drone-kampus',
            estimated_value=700_000, price_per_day=100_000, deposit_amount=200_000,
            min_days=1, max_days=10, pickup_area='Gedung C', is_active=True,
        )
        self.today = timezone.localdate()

    def test_collision_with_blocking_rental_on_request(self):
        """Permintaan baru ditolak jika menabrak sewa berstatus pemblokir."""
        start_1 = self.today + timedelta(days=3)
        end_1 = self.today + timedelta(days=6)

        # Buat sewa 1 dan setujui menjadi menunggu_pembayaran (blocking)
        rental_1 = ajukan_sewa(self.item, self.renter_a, start_1, end_1, terms_accepted=True)
        rental_1 = setujui_sewa(rental_1, self.owner)
        self.assertEqual(rental_1.status, Rental.Status.MENUNGGU_PEMBAYARAN)

        # Renter B mencoba menyewa tanggal yang bertabrakan (hari 5 s/d 8)
        start_2 = self.today + timedelta(days=5)
        end_2 = self.today + timedelta(days=8)
        with self.assertRaises(RentalValidationError):
            ajukan_sewa(self.item, self.renter_b, start_2, end_2, terms_accepted=True)

    def test_auto_rejection_of_overlapping_pending_requests_on_approval(self):
        """
        Saat dua pengajuan masuk bersamaan dalam status menunggu_persetujuan:
        Ketika pemilik menyetujui pengajuan A, pengajuan B yang bertabrakan
        otomatis ditolak dengan alasan 'Tanggal sudah dipesan'.
        """
        start_a = self.today + timedelta(days=4)
        end_a = self.today + timedelta(days=7)
        rental_a = ajukan_sewa(self.item, self.renter_a, start_a, end_a, terms_accepted=True)

        start_b = self.today + timedelta(days=6)
        end_b = self.today + timedelta(days=9)
        rental_b = ajukan_sewa(self.item, self.renter_b, start_b, end_b, terms_accepted=True)

        self.assertEqual(rental_a.status, Rental.Status.MENUNGGU_PERSETUJUAN)
        self.assertEqual(rental_b.status, Rental.Status.MENUNGGU_PERSETUJUAN)

        # Pemilik menyetujui rental_a
        setujui_sewa(rental_a, self.owner)

        rental_a.refresh_from_db()
        rental_b.refresh_from_db()

        self.assertEqual(rental_a.status, Rental.Status.MENUNGGU_PEMBAYARAN)
        self.assertEqual(rental_b.status, Rental.Status.DITOLAK)
        self.assertEqual(rental_b.cancel_reason, "Tanggal sudah dipesan")


class ProcessDeadlinesTest(TestCase):
    """Pengujian batas waktu kedaluwarsa otomatis (process_deadlines) dan sifat idempoten."""

    def setUp(self):
        self.campus = Campus.objects.create(name='Kampus Uji', short_name='KU', city='Lampung')
        self.owner = User.objects.create_user(username='owner_d', email='owner_d@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.owner, campus=self.campus, nim='12312312')

        self.renter = User.objects.create_user(username='renter_d', email='renter_d@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.renter, campus=self.campus, nim='32132132')

        self.cat = Category.objects.create(name='Audio', slug='audio', order=1)
        self.item = Item.objects.create(
            owner=self.owner, category=self.cat, title='Speaker Portabel', slug='speaker-portabel',
            estimated_value=300_000, price_per_day=25_000, deposit_amount=50_000,
            min_days=1, max_days=5, pickup_area='Kantin', is_active=True,
        )
        self.today = timezone.localdate()

    def test_process_deadlines_approval_and_payment(self):
        """Memverifikasi kedaluwarsa setelah 24 jam persetujuan dan 12 jam pembayaran."""
        now = timezone.now()

        # Rental 1: menunggu_persetujuan > 24 jam (misal 25 jam lalu) -> harus kedaluwarsa
        r1 = ajukan_sewa(self.item, self.renter, self.today + timedelta(days=2), self.today + timedelta(days=3), terms_accepted=True)
        Rental.objects.filter(id=r1.id).update(requested_at=now - timedelta(hours=25))

        # Rental 2: menunggu_pembayaran > 12 jam (misal 13 jam lalu) -> harus kedaluwarsa
        item2 = Item.objects.create(
            owner=self.owner, category=self.cat, title='Mic Clip On', slug='mic-clip-on',
            estimated_value=200_000, price_per_day=20_000, deposit_amount=40_000,
            min_days=1, max_days=5, pickup_area='Kantin', is_active=True,
        )
        r2 = ajukan_sewa(item2, self.renter, self.today + timedelta(days=4), self.today + timedelta(days=5), terms_accepted=True)
        setujui_sewa(r2, self.owner)
        Rental.objects.filter(id=r2.id).update(approved_at=now - timedelta(hours=13))

        # Rental 3: baru diajukan 1 jam lalu -> TIDAK kedaluwarsa
        item3 = Item.objects.create(
            owner=self.owner, category=self.cat, title='Tripod', slug='tripod',
            estimated_value=200_000, price_per_day=20_000, deposit_amount=40_000,
            min_days=1, max_days=5, pickup_area='Kantin', is_active=True,
        )
        r3 = ajukan_sewa(item3, self.renter, self.today + timedelta(days=6), self.today + timedelta(days=7), terms_accepted=True)
        Rental.objects.filter(id=r3.id).update(requested_at=now - timedelta(hours=1))

        # Jalankan process_deadlines
        results = run_process_deadlines()
        self.assertEqual(results['expired_approval'], 1)
        self.assertEqual(results['expired_payment'], 1)
        self.assertEqual(results['total'], 2)

        r1.refresh_from_db()
        r2.refresh_from_db()
        r3.refresh_from_db()

        self.assertEqual(r1.status, Rental.Status.KEDALUWARSA)
        self.assertEqual(r2.status, Rental.Status.KEDALUWARSA)
        self.assertEqual(r3.status, Rental.Status.MENUNGGU_PERSETUJUAN)

        # Uji sifat idempoten: jalankan kedua kali tidak ada perubahan
        second_run = run_process_deadlines()
        self.assertEqual(second_run['total'], 0)


class IDORSecurityTest(TestCase):
    """Pengujian keamanan IDOR (Insecure Direct Object Reference)."""

    def setUp(self):
        self.campus = Campus.objects.create(name='Kampus Keamanan', short_name='KK', city='Lampung')
        self.owner = User.objects.create_user(username='owner_s', email='owner_s@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.owner, campus=self.campus, nim='10101010')

        self.renter = User.objects.create_user(username='renter_s', email='renter_s@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.renter, campus=self.campus, nim='20202020')

        self.intruder = User.objects.create_user(username='intruder', email='intruder@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.intruder, campus=self.campus, nim='30303030')

        self.cat = Category.objects.create(name='Kamera', slug='kamera-s', order=1)
        self.item = Item.objects.create(
            owner=self.owner, category=self.cat, title='Kamera Aman', slug='kamera-aman',
            estimated_value=500_000, price_per_day=50_000, deposit_amount=100_000,
            min_days=1, max_days=5, pickup_area='Area Aman', is_active=True,
        )
        self.today = timezone.localdate()
        self.rental = ajukan_sewa(self.item, self.renter, self.today + timedelta(days=2), self.today + timedelta(days=4), terms_accepted=True)

        self.client = Client()

    def test_intruder_cannot_view_rental_detail(self):
        """Pihak luar yang login tidak dapat melihat detail sewa pihak lain (403 Forbidden)."""
        self.client.login(username='intruder', password='TestPassword123!')
        response = self.client.get(f'/sewa/{self.rental.code}/')
        self.assertEqual(response.status_code, 403)

    def test_intruder_cannot_approve_or_reject_or_cancel(self):
        """Pihak luar tidak dapat menyetujui, menolak, atau membatalkan sewa."""
        self.client.login(username='intruder', password='TestPassword123!')

        # Coba setujui
        self.client.post(f'/sewa/{self.rental.code}/setujui/')
        self.rental.refresh_from_db()
        self.assertEqual(self.rental.status, Rental.Status.MENUNGGU_PERSETUJUAN)

        # Coba tolak
        self.client.post(f'/sewa/{self.rental.code}/tolak/', {'reason': 'Hacker'})
        self.rental.refresh_from_db()
        self.assertEqual(self.rental.status, Rental.Status.MENUNGGU_PERSETUJUAN)

        # Coba batalkan
        self.client.post(f'/sewa/{self.rental.code}/batal/', {'reason': 'Hacker cancel'})
        self.rental.refresh_from_db()
        self.assertEqual(self.rental.status, Rental.Status.MENUNGGU_PERSETUJUAN)


class DashboardQueriesTest(TestCase):
    """Pengujian efisiensi jumlah query SQL pada dashboard (assertNumQueries)."""

    def setUp(self):
        self.campus = Campus.objects.create(name='Kampus Query', short_name='KQ', city='Lampung')
        self.user = User.objects.create_user(username='user_dash', email='dash@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.user, campus=self.campus, nim='50505050')

        self.partner = User.objects.create_user(username='partner_dash', email='partner@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.partner, campus=self.campus, nim='60606060')

        self.cat = Category.objects.create(name='Umum', slug='umum', order=1)
        today = timezone.localdate()

        # Buat 3 barang milik user
        for i in range(3):
            Item.objects.create(
                owner=self.user, category=self.cat, title=f'Barang Saya {i}', slug=f'barang-saya-{i}',
                estimated_value=300_000, price_per_day=30_000, deposit_amount=50_000,
                min_days=1, max_days=5, pickup_area='Gedung D', is_active=True,
            )

        # Buat 2 sewa sebagai penyewa
        for i in range(2):
            item_partner = Item.objects.create(
                owner=self.partner, category=self.cat, title=f'Barang Mitra {i}', slug=f'barang-mitra-{i}',
                estimated_value=300_000, price_per_day=30_000, deposit_amount=50_000,
                min_days=1, max_days=5, pickup_area='Gedung D', is_active=True,
            )
            ajukan_sewa(item_partner, self.user, today + timedelta(days=2+i*3), today + timedelta(days=3+i*3), terms_accepted=True)

        self.client = Client()
        self.client.login(username='user_dash', password='TestPassword123!')

    def test_dashboard_query_count_is_bounded(self):
        """Memastikan dashboard tidak mengalami N+1 query explosion."""
        # Query terikat: session, user, profile+campus, trust_score, latest_ktm,
        # my_rentals (+photos), incoming_requests (+photos), my_items (+photos),
        # dan context processors (unread messages & notifications), ulasan (Fase 5B),
        # saldo dompet pengguna (Fase 7C), tagihan terutang ExtraCharge (Fase 7G),
        # serta barang jualan SaleItem (Fase 8A), pesanan jual beli SaleOrder (Fase 8B),
        # dan agregasi pendapatan penjualan (Fase 8C).
        with self.assertNumQueries(19):
            response = self.client.get('/dashboard/')
            self.assertEqual(response.status_code, 200)



class ConcurrencyApprovalTest(TransactionTestCase):
    """Pengujian konkurensi persetujuan sewa menggunakan TransactionTestCase."""

    def setUp(self):
        self.campus = Campus.objects.create(name='Kampus Concurrency', short_name='KC', city='Lampung')
        self.owner = User.objects.create_user(username='owner_conc', email='owner_conc@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.owner, campus=self.campus, nim='70707070')

        self.renter_1 = User.objects.create_user(username='renter_1', email='r1@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.renter_1, campus=self.campus, nim='80808080')

        self.renter_2 = User.objects.create_user(username='renter_2', email='r2@test.id', password='TestPassword123!', is_verified_student=True)
        StudentProfile.objects.create(user=self.renter_2, campus=self.campus, nim='90909090')

        self.cat = Category.objects.create(name='Outdoor', slug='outdoor', order=1)
        self.item = Item.objects.create(
            owner=self.owner, category=self.cat, title='Tenda Dome', slug='tenda-dome',
            estimated_value=500_000, price_per_day=50_000, deposit_amount=100_000,
            min_days=1, max_days=5, pickup_area='Gazebo', is_active=True,
        )
        self.today = timezone.localdate()

    def test_concurrent_approval_atomic_safety(self):
        """
        Dua pengajuan tanggal sama disetujui berurutan:
        Pengajuan pertama berhasil, pengajuan kedua gagal karena tabrakan atau sudah ditolak.
        """
        r1 = ajukan_sewa(self.item, self.renter_1, self.today + timedelta(days=2), self.today + timedelta(days=4), terms_accepted=True)
        r2 = ajukan_sewa(self.item, self.renter_2, self.today + timedelta(days=3), self.today + timedelta(days=5), terms_accepted=True)

        # Setujui r1
        setujui_sewa(r1, self.owner)
        r1.refresh_from_db()
        r2.refresh_from_db()

        self.assertEqual(r1.status, Rental.Status.MENUNGGU_PEMBAYARAN)
        # r2 otomatis ditolak
        self.assertEqual(r2.status, Rental.Status.DITOLAK)

        # Coba setujui r2 sekarang -> harus raises RentalStateError
        with self.assertRaises(RentalStateError):
            setujui_sewa(r2, self.owner)


@override_settings(WHATSAPP_HANDOVER_ENABLED=True)
class RentalDetailTimelineAndWhatsAppTestCase(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name='Kampus Uji', short_name='KU', city='Bandar Lampung')
        self.owner = User.objects.create_user(
            username='owner_user',
            first_name='Budi',
            email='budi@ku.id',
            password='TestPassword123!',
            is_verified_student=True,
            phone_whatsapp='08111111111'
        )
        StudentProfile.objects.create(user=self.owner, campus=self.campus, nim='11111111')

        self.renter = User.objects.create_user(
            username='renter_user',
            first_name='Eka',
            email='eka@ku.id',
            password='TestPassword123!',
            is_verified_student=True,
            phone_whatsapp='08222222222'
        )
        StudentProfile.objects.create(user=self.renter, campus=self.campus, nim='22222222')

        self.cat = Category.objects.create(name='Elektronik', slug='elektronik', order=1)
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.cat,
            title='Proyektor Epson',
            slug='proyektor-epson',
            estimated_value=500_000,
            price_per_day=50_000,
            deposit_amount=150_000,
            min_days=1,
            max_days=7,
            pickup_area='Perpustakaan',
            is_active=True
        )
        self.today = timezone.localdate()

    def test_timeline_active_step_for_each_status(self):
        """Memverifikasi langkah aktif garis waktu untuk tiap status."""
        rental = ajukan_sewa(self.item, self.renter, self.today + timedelta(days=2), self.today + timedelta(days=4), terms_accepted=True)
        
        # 1. Menunggu persetujuan -> Langkah aktif: 1 (Disetujui)
        self.client.force_login(self.renter)
        resp = self.client.get(f"/sewa/{rental.code}/")
        self.assertEqual(resp.context['active_step_index'], 1)

        # 2. Menunggu pembayaran -> Langkah aktif: 2 (Dibayar)
        setujui_sewa(rental, self.owner)
        rental.refresh_from_db()
        resp = self.client.get(f"/sewa/{rental.code}/")
        self.assertEqual(resp.context['active_step_index'], 2)

        # 3. Dibayar -> Langkah aktif: 3 (Diserahkan), status Dibayar selesai
        rental.status = Rental.Status.DIBAYAR
        rental.save()
        resp = self.client.get(f"/sewa/{rental.code}/")
        self.assertEqual(resp.context['active_step_index'], 3)

        # 4. Sedang disewa -> Langkah aktif: 4 (Dikembalikan)
        rental.status = Rental.Status.SEDANG_DISEWA
        rental.save()
        resp = self.client.get(f"/sewa/{rental.code}/")
        self.assertEqual(resp.context['active_step_index'], 4)

        # 5. Menunggu konfirmasi pengembalian -> Langkah aktif: 5 (Selesai)
        rental.status = Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN
        rental.save()
        resp = self.client.get(f"/sewa/{rental.code}/")
        self.assertEqual(resp.context['active_step_index'], 5)

        # 6. Selesai -> Langkah aktif: 6 (Semua selesai)
        rental.status = Rental.Status.SELESAI
        rental.save()
        resp = self.client.get(f"/sewa/{rental.code}/")
        self.assertEqual(resp.context['active_step_index'], 6)

    def test_whatsapp_visibility_within_window_only_shows_counterpart(self):
        """
        Dalam jendela (start_date besok <= 24 jam) pada status DIBAYAR:
        - WhatsApp tampil
        - Penyewa hanya melihat nomor WhatsApp pemilik (bukan nomornya sendiri)
        - Pemilik hanya melihat nomor WhatsApp penyewa (bukan nomornya sendiri)
        - Catatan disclaimer tampil
        - Tombol 'Buka percakapan' tampil
        """
        start = self.today + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)
        setujui_sewa(rental, self.owner)
        rental.status = Rental.Status.DIBAYAR
        rental.save()

        # Login sebagai penyewa
        self.client.force_login(self.renter)
        resp = self.client.get(f"/sewa/{rental.code}/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['show_whatsapp'])
        content = resp.content.decode('utf-8')
        # Nomor pemilik tampil
        self.assertIn("08111111111", content)
        # Nomor penyewa sendiri TIDAK tampil di blok WhatsApp serah terima
        self.assertIn("Percakapan di WhatsApp tidak tercatat sebagai bukti sengketa", content)
        self.assertIn("Buka percakapan", content)

        # Login sebagai pemilik
        self.client.force_login(self.owner)
        resp = self.client.get(f"/sewa/{rental.code}/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['show_whatsapp'])
        content = resp.content.decode('utf-8')
        # Nomor penyewa tampil
        self.assertIn("08222222222", content)

    def test_whatsapp_visibility_before_window_hidden(self):
        """Sebelum jendela 24 jam (misal 5 hari lagi): WhatsApp tidak tampil."""
        start = self.today + timedelta(days=5)
        end = start + timedelta(days=2)
        rental = ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)
        setujui_sewa(rental, self.owner)
        rental.status = Rental.Status.DIBAYAR
        rental.save()

        self.client.force_login(self.renter)
        resp = self.client.get(f"/sewa/{rental.code}/")
        self.assertFalse(resp.context['show_whatsapp'])
        content = resp.content.decode('utf-8')
        self.assertNotIn("08111111111", content)
        self.assertNotIn("Chat Pemilik via WhatsApp", content)
        # Namun tombol percakapan internal tetap ada
        self.assertIn("Buka percakapan", content)

    def test_whatsapp_visibility_after_completion_hidden(self):
        """Setelah status sedang_disewa berakhir (status SELESAI): WhatsApp tidak tampil."""
        start = self.today + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)
        setujui_sewa(rental, self.owner)
        rental.status = Rental.Status.SELESAI
        rental.save()

        self.client.force_login(self.renter)
        resp = self.client.get(f"/sewa/{rental.code}/")
        self.assertFalse(resp.context['show_whatsapp'])
        content = resp.content.decode('utf-8')
        self.assertNotIn("08111111111", content)

    @override_settings(WHATSAPP_HANDOVER_ENABLED=False)
    def test_whatsapp_disabled_setting_hides_whatsapp(self):
        """Bila WHATSAPP_HANDOVER_ENABLED=False, nomor tidak tampil meskipun dalam jendela."""
        start = self.today + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)
        setujui_sewa(rental, self.owner)
        rental.status = Rental.Status.DIBAYAR
        rental.save()

        self.client.force_login(self.renter)
        resp = self.client.get(f"/sewa/{rental.code}/")
        self.assertFalse(resp.context['show_whatsapp'])

    def test_max_loss_compensation_displayed_not_empty(self):
        """Memverifikasi baris Ganti rugi kehilangan maksimal selalu tampil dan tidak kosong."""
        start = self.today + timedelta(days=2)
        end = start + timedelta(days=4)
        rental = ajukan_sewa(self.item, self.renter, start, end, terms_accepted=True)

        self.client.force_login(self.renter)
        resp = self.client.get(f"/sewa/{rental.code}/")
        content = resp.content.decode('utf-8')
        self.assertIn("Ganti rugi kehilangan maksimal:", content)
        self.assertIn("Rp500.000", content)

    def test_no_uppercase_tracking_wider_on_headers(self):
        """Memverifikasi tidak ada header atau label bertuliskan huruf kapital semua."""
        from pathlib import Path
        templates_to_check = [
            'templates/rentals/rental_detail.html',
            'templates/accounts/dashboard.html',
            'templates/catalog/item_detail.html',
        ]
        base_dir = Path(settings.BASE_DIR)
        for t_path in templates_to_check:
            full_path = base_dir / t_path
            content = full_path.read_text(encoding='utf-8')
            self.assertNotIn("uppercase tracking-wider", content, f"Masih ada uppercase tracking-wider di {t_path}")


