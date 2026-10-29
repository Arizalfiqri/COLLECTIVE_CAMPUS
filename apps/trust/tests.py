from datetime import date
from django.test import TestCase, override_settings
from apps.accounts.models import User, Campus, StudentProfile
from apps.catalog.models import Category, Item
from apps.rentals.models import Rental
from apps.trust.models import TrustScore
from apps.trust.services import (
    get_renter_tier,
    get_tier_info,
    calculate_minimum_deposit,
    calculate_protection_fee,
    is_renter_eligible_for_item,
)


class TrustTierAndDepositServicesTest(TestCase):
    def setUp(self):
        self.campus_a, _ = Campus.objects.get_or_create(name='Univ A', defaults={'short_name': 'UA', 'city': 'Bandar Lampung'})
        self.campus_b, _ = Campus.objects.get_or_create(name='Univ B', defaults={'short_name': 'UB', 'city': 'Bandar Lampung'})

        self.user_new = User.objects.create_user(
            username='user_new', email='new@test.id', password='Password123!', full_name='User Baru'
        )
        StudentProfile.objects.create(user=self.user_new, nim='111111', campus=self.campus_a, major='TI')

        self.user_trusted = User.objects.create_user(
            username='user_trusted', email='trusted@test.id', password='Password123!', full_name='User Tepercaya'
        )
        StudentProfile.objects.create(user=self.user_trusted, nim='222222', campus=self.campus_a, major='TI')

        self.user_very_trusted = User.objects.create_user(
            username='user_very_trusted', email='vtrusted@test.id', password='Password123!', full_name='User Sangat Tepercaya'
        )
        StudentProfile.objects.create(user=self.user_very_trusted, nim='333333', campus=self.campus_b, major='TI')

        self.owner = User.objects.create_user(
            username='owner_user', email='owner@test.id', password='Password123!', full_name='Owner User'
        )
        StudentProfile.objects.create(user=self.owner, nim='999999', campus=self.campus_a, major='TI')

        self.category = Category.objects.create(name='Elektronik', slug='elektronik', order=1)

        self.item = Item.objects.create(
            owner=self.owner, category=self.category, title='Kamera Mirrorless',
            estimated_value=1200000, price_per_day=50000, deposit_amount=200000,
            min_days=1, max_days=5, pickup_area='Perpustakaan'
        )

        # Buat sewa selesai untuk user_trusted (4 sewa selesai tanpa sengketa)
        for i in range(4):
            Rental.objects.create(
                item=self.item, renter=self.user_trusted, owner=self.owner,
                start_date=date(2026, 1, 1), end_date=date(2026, 1, 2), days=2,
                price_per_day_snapshot=50000, rent_total=100000, deposit_total=200000, grand_total=300000,
                status=Rental.Status.SELESAI
            )

        # Buat sewa selesai untuk user_very_trusted (7 sewa selesai tanpa sengketa)
        for i in range(7):
            Rental.objects.create(
                item=self.item, renter=self.user_very_trusted, owner=self.owner,
                start_date=date(2026, 1, 1), end_date=date(2026, 1, 2), days=2,
                price_per_day_snapshot=50000, rent_total=100000, deposit_total=200000, grand_total=300000,
                status=Rental.Status.SELESAI
            )

    def test_renter_tier_determination(self):
        """Uji penentuan tingkat penyewa (baru, tepercaya, sangat tepercaya)."""
        # 1. User baru (< 3 sewa selesai) -> baru
        self.assertEqual(get_renter_tier(self.user_new), 'baru')

        # 2. User 4 sewa selesai -> tepercaya
        self.assertEqual(get_renter_tier(self.user_trusted), 'tepercaya')

        # 3. User 7 sewa selesai -> sangat_tepercaya
        self.assertEqual(get_renter_tier(self.user_very_trusted), 'sangat_tepercaya')

    def test_tier_info_max_value_and_deposit(self):
        """Uji info tingkat: batas nilai barang dan persentase deposit."""
        info_baru = get_tier_info('baru')
        self.assertEqual(info_baru['max_value'], 750000)
        self.assertEqual(info_baru['deposit_percent'], 15)

        info_tepercaya = get_tier_info('tepercaya')
        self.assertEqual(info_tepercaya['max_value'], 1500000)
        self.assertEqual(info_tepercaya['deposit_percent'], 10)

        info_sangat = get_tier_info('sangat_tepercaya')
        self.assertEqual(info_sangat['max_value'], 3000000)
        self.assertEqual(info_sangat['deposit_percent'], 10)

    @override_settings(DEPOSIT_MODE='legacy')
    def test_minimum_deposit_calculation(self):
        """
        Uji rumus perhitungan deposit minimum:
        - Barang bernilai <= 150.000 boleh 0 (tanpa deposit).
        - Barang bernilai > 150.000 deposit tidak kurang dari Rp25.000.
        - Lintas kampus menambah 5 poin persen.
        """
        # Nilai <= 150.000 -> 0
        self.assertEqual(calculate_minimum_deposit(100000, 'baru', is_cross_campus=False), 0)
        self.assertEqual(calculate_minimum_deposit(150000, 'baru', is_cross_campus=False), 0)

        # Nilai 200.000, tier baru (15% = 30.000, >= min deposit 25.000)
        self.assertEqual(calculate_minimum_deposit(200000, 'baru', is_cross_campus=False), 30000)

        # Nilai 160.000, tier tepercaya (10% = 16.000, di bawah batas minimum 25.000 -> harus jadi 25.000)
        self.assertEqual(calculate_minimum_deposit(160000, 'tepercaya', is_cross_campus=False), 25000)

        # Lintas kampus: tier baru (15% + 5% = 20%) dari 1.000.000 = 200.000
        self.assertEqual(calculate_minimum_deposit(1000000, 'baru', is_cross_campus=True), 200000)

        # Satu kampus: tier baru (15%) dari 1.000.000 = 150.000
        self.assertEqual(calculate_minimum_deposit(1000000, 'baru', is_cross_campus=False), 150000)

    @override_settings(DEPOSIT_MODE='off')
    def test_deposit_mode_off_returns_zero(self):
        """Memverifikasi bahwa saat DEPOSIT_MODE='off', deposit minimum selalu 0."""
        self.assertEqual(calculate_minimum_deposit(200000, 'baru'), 0)
        self.assertEqual(calculate_minimum_deposit(1000000, 'sangat_tepercaya', is_cross_campus=True), 0)

    def test_protection_fee_calculation(self):
        """
        Uji biaya proteksi: 5% dari biaya sewa, minimum Rp3.000, wajib > Rp500.000.
        """
        # Sewa 40.000: 5% = 2.000 < min 3.000 -> 3.000
        p1 = calculate_protection_fee(rent_total=40000, estimated_value=300000)
        self.assertEqual(p1['fee'], 3000)
        self.assertFalse(p1['is_mandatory'])

        # Sewa 200.000: 5% = 10.000
        p2 = calculate_protection_fee(rent_total=200000, estimated_value=400000)
        self.assertEqual(p2['fee'], 10000)
        self.assertFalse(p2['is_mandatory'])

        # Barang bernilai 800.000 (> 500.000) -> wajib
        p3 = calculate_protection_fee(rent_total=200000, estimated_value=800000)
        self.assertTrue(p3['is_mandatory'])

    def test_renter_eligibility_for_item(self):
        """Uji kelayakan penyewa terhadap nilai barang dan syarat min_renter_tier."""
        item_cheap = Item.objects.create(
            owner=self.owner, category=self.category, title='Kalkulator',
            estimated_value=200000, price_per_day=15000, deposit_amount=30000,
            min_renter_tier='baru'
        )
        item_expensive = Item.objects.create(
            owner=self.owner, category=self.category, title='Kamera Pro',
            estimated_value=2500000, price_per_day=100000, deposit_amount=250000,
            min_renter_tier='sangat_tepercaya'
        )

        # User baru boleh sewa kalkulator (nilai 200k <= 750k dan tier baru)
        elig, reason = is_renter_eligible_for_item(self.user_new, item_cheap)
        self.assertTrue(elig)

        # User baru TIDAK boleh sewa kamera pro (nilai 2.5jt > 750k dan butuh sangat_tepercaya)
        elig, reason = is_renter_eligible_for_item(self.user_new, item_expensive)
        self.assertFalse(elig)

        # User sangat tepercaya boleh sewa kamera pro
        elig, reason = is_renter_eligible_for_item(self.user_very_trusted, item_expensive)
        self.assertTrue(elig)

