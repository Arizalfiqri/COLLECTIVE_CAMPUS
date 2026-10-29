import hashlib
from datetime import date, timedelta
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, StudentProfile, Campus, BlacklistedNim
from apps.catalog.models import Category, Item
from apps.catalog.forms import ItemForm
from apps.catalog.services import calculate_rental_summary, calculate_min_deposit
from apps.core.models import TermsVersion
from apps.payments.models import ExtraCharge, WalletTransaction, Payment, DepositHold
from apps.payments.services import settle_extra_charge, record_payment_settlement
from apps.payments.reconciliation import run_financial_reconciliation
from apps.rentals.models import Rental, RentalAgreement, ConditionPhoto
from apps.rentals.services import (
    ajukan_sewa,
    setujui_sewa,
    konfirmasi_pembayaran,
    ajukan_pengembalian,
    laporkan_masalah_sengketa,
    penyewa_setujui_potongan,
    selesaikan_sengketa_admin,
    proses_barang_tidak_dikembalikan,
    RentalValidationError,
)
from apps.trust.services import calculate_minimum_deposit, label_training_example_for_rental


class Phase7GDepositModeAndExtraChargeTest(TestCase):
    """Pengujian komprehensif FASE 7G: Saklar DEPOSIT_MODE, Tagihan Tambahan, dan S&K Digital."""

    def setUp(self):
        self.campus_a = Campus.objects.create(name='Univ A', short_name='UA', city='Bandar Lampung')
        self.campus_b = Campus.objects.create(name='Univ B', short_name='UB', city='Bandar Lampung')

        self.owner = User.objects.create_user(
            username='owner_7g', email='owner7g@test.id', password='Password123!',
            full_name='Budi Pemilik', is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.owner, campus=self.campus_a, nim='11112222')

        self.renter = User.objects.create_user(
            username='renter_7g', email='renter7g@test.id', password='Password123!',
            full_name='Siti Penyewa', is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.renter, campus=self.campus_a, nim='33334444')

        self.category = Category.objects.create(name='Kamera 7G', slug='kamera-7g', order=1)
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title='Sony A7 Mark III',
            slug='sony-a7-mark-iii',
            price_per_day=100000,
            deposit_amount=500000,
            estimated_value=500000,
            min_days=1,
            max_days=7,
            pickup_area='Perpustakaan Pusat',
        )

        self.terms = TermsVersion.objects.create(
            term_type=TermsVersion.TermType.PENYEWA,
            version='v1.0-test',
            content='Syarat dan ketentuan penyewaan digital resmi KampusRent...',
            is_active=True,
        )

        self.today = timezone.localdate()
        self.client = Client()

    # --- 1. SAKLAR DEPOSIT_MODE ---
    @override_settings(DEPOSIT_MODE='off')
    def test_deposit_mode_off_behavior(self):
        """Saat DEPOSIT_MODE='off': deposit_total=0, form abaikan deposit, calculate_minimum_deposit=0."""
        self.assertEqual(calculate_minimum_deposit(self.item.estimated_value, 'baru'), 0)
        self.assertEqual(calculate_min_deposit(self.item.estimated_value, self.renter), 0)

        # Rental summary menghasilkan deposit_total = 0
        summary = calculate_rental_summary(self.item, self.today + timedelta(days=1), self.today + timedelta(days=3))
        self.assertEqual(summary['deposit_total'], 0)

        # Form pasang barang mengabaikan deposit dan membersihkan ke 0
        form_data = {
            'title': 'Kamera Uji Form',
            'category': self.category.id,
            'description': 'Deskripsi barang',
            'condition': Item.Condition.BAIK,
            'estimated_value': 1000000,
            'price_per_day': 50000,
            'deposit_amount': 300000,  # Dikirim dari form tapi harus jadi 0
            'min_days': 1,
            'max_days': 5,
            'pickup_area': 'Gedung A',
            'min_renter_tier': 'baru',
            'owner_declaration': 'on',
        }
        form = ItemForm(data=form_data, user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['deposit_amount'], 0)

    @override_settings(DEPOSIT_MODE='optional')
    def test_deposit_mode_optional_behavior(self):
        """Saat DEPOSIT_MODE='optional': pemilik boleh mengisi deposit bawaan 0 atau lebih."""
        self.assertEqual(calculate_minimum_deposit(self.item.estimated_value, 'baru'), 0)

        # Form pasang barang menerima deposit opsional
        form_data = {
            'title': 'Lensa Uji Opsional',
            'category': self.category.id,
            'description': 'Deskripsi barang opsional',
            'condition': Item.Condition.BAIK,
            'estimated_value': 1000000,
            'price_per_day': 50000,
            'deposit_amount': 150000,
            'min_days': 1,
            'max_days': 5,
            'pickup_area': 'Gedung B',
            'min_renter_tier': 'baru',
            'owner_declaration': 'on',
        }
        form = ItemForm(data=form_data, user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['deposit_amount'], 150000)

    # --- 2. PERJANJIAN DIGITAL S&K ---
    @override_settings(DEPOSIT_MODE='off')
    def test_rental_agreement_creation_and_hash(self):
        """Sewa membuat RentalAgreement lengkap dengan hash SHA-256, identitas, dan IP."""
        rental = ajukan_sewa(
            item=self.item,
            renter=self.renter,
            start_date=self.today + timedelta(days=2),
            end_date=self.today + timedelta(days=4),
            terms_accepted=True,
            ip_address='192.168.1.100',
            user_agent='Mozilla/5.0 TestBrowser',
        )

        self.assertEqual(rental.deposit_total, 0)
        self.assertTrue(hasattr(rental, 'agreement'))
        ag = rental.agreement
        self.assertEqual(ag.terms_version, self.terms)
        self.assertEqual(ag.terms_version_string, 'v1.0-test')
        self.assertEqual(ag.terms_hash, self.terms.calculate_sha256())
        self.assertEqual(ag.renter_name, 'Siti Penyewa')
        self.assertEqual(ag.renter_nim, '33334444')
        self.assertEqual(ag.owner_name, 'Budi Pemilik')
        self.assertEqual(ag.owner_nim, '11112222')
        self.assertEqual(ag.ip_address, '192.168.1.100')
        self.assertEqual(ag.user_agent, 'Mozilla/5.0 TestBrowser')

    @override_settings(DEPOSIT_MODE='off')
    def test_terms_accepted_mandatory_validation(self):
        """Pengajuan sewa gagal jika terms_accepted=False."""
        with self.assertRaises(RentalValidationError) as ctx:
            ajukan_sewa(
                item=self.item,
                renter=self.renter,
                start_date=self.today + timedelta(days=2),
                end_date=self.today + timedelta(days=4),
                terms_accepted=False,
            )
        self.assertIn('syarat dan ketentuan', str(ctx.exception).lower())

    @override_settings(DEPOSIT_MODE='off')
    def test_rental_agreement_view_anti_idor(self):
        """Halaman perjanjian /sewa/<kode>/perjanjian/ hanya bisa diakses penyewa, pemilik, atau staf."""
        rental = ajukan_sewa(
            item=self.item,
            renter=self.renter,
            start_date=self.today + timedelta(days=2),
            end_date=self.today + timedelta(days=4),
            terms_accepted=True,
        )
        url = reverse('rentals:rental_agreement', kwargs={'code': rental.code})

        # Tamu anonim -> redirect login
        res_anon = self.client.get(url)
        self.assertEqual(res_anon.status_code, 302)

        # Pengguna asing (pihak ketiga) -> 403 Forbidden
        intruder = User.objects.create_user(username='intruder', email='intruder@test.id', password='Password123!')
        self.client.force_login(intruder)
        res_intruder = self.client.get(url)
        self.assertEqual(res_intruder.status_code, 403)

        # Penyewa sah -> 200 OK dengan konten perjanjian
        self.client.force_login(self.renter)
        res_renter = self.client.get(url)
        self.assertEqual(res_renter.status_code, 200)
        self.assertContains(res_renter, "SURAT PERJANJIAN SEWA MENYEWA DIGITAL")
        self.assertContains(res_renter, rental.code)
        self.assertContains(res_renter, "Tanpa Uang Jaminan")

        # Pemilik sah -> 200 OK
        self.client.force_login(self.owner)
        res_owner = self.client.get(url)
        self.assertEqual(res_owner.status_code, 200)

    # --- 3. TAGIHAN TAMBAHAN (EXTRA CHARGE) ---
    def _create_active_rental(self):
        rental = ajukan_sewa(
            item=self.item,
            renter=self.renter,
            start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=3),
            terms_accepted=True,
        )
        setujui_sewa(rental, self.owner)
        payment = Payment.objects.create(
            rental=rental,
            order_id=f"TEST-{rental.code}",
            payment_type="qris",
            gross_amount=rental.grand_total,
            transaction_id=f"mock-{rental.code}",
            status=Payment.Status.SETTLEMENT,
        )
        record_payment_settlement(rental, payment)
        konfirmasi_pembayaran(rental, payment)
        rental.status = Rental.Status.SEDANG_DISEWA
        rental.save()
        return rental

    @override_settings(DEPOSIT_MODE='off')
    def test_late_fee_creates_extra_charge(self):
        """Keterlambatan pengembalian pada DEPOSIT_MODE='off' menerbitkan ExtraCharge keterlambatan."""
        rental = self._create_active_rental()
        rental.end_date = self.today - timedelta(days=2)  # Terlambat 2 hari
        rental.save()

        # Buat dummy foto pengembalian
        ConditionPhoto.objects.create(rental=rental, uploaded_by=self.renter, phase=ConditionPhoto.Phase.SESUDAH, image='test1.jpg')
        ConditionPhoto.objects.create(rental=rental, uploaded_by=self.renter, phase=ConditionPhoto.Phase.SESUDAH, image='test2.jpg')

        ajukan_pengembalian(rental, self.renter)
        rental.refresh_from_db()

        self.assertEqual(rental.late_days, 2)
        self.assertEqual(rental.late_fee, 0)  # Dipindahkan ke ExtraCharge

        # Verifikasi ExtraCharge diterbitkan
        charge = ExtraCharge.objects.filter(rental=rental, charge_type=ExtraCharge.ChargeType.KETERLAMBATAN).first()
        self.assertIsNotNone(charge)
        # 50% dari 100.000 x 2 hari = 100.000
        self.assertEqual(charge.amount, 100000)
        self.assertEqual(charge.status, ExtraCharge.Status.TERUTANG)

    @override_settings(DEPOSIT_MODE='off')
    def test_damage_dispute_creates_extra_charge(self):
        """Persetujuan kerusakan pada DEPOSIT_MODE='off' menerbitkan ExtraCharge kerusakan."""
        rental = self._create_active_rental()
        rental.status = Rental.Status.MENUNGGU_KONFIRMASI_PENGEMBALIAN
        rental.save()

        # Pemilik laporkan masalah kerusakan Rp200.000
        laporkan_masalah_sengketa(rental, self.owner, reason="Lensa tergores", deduction_amount=200000)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.SENGKETA)

        # Penyewa setujui potongan -> terbit ExtraCharge
        penyewa_setujui_potongan(rental, self.renter)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.SELESAI)

        charge = ExtraCharge.objects.filter(rental=rental, charge_type=ExtraCharge.ChargeType.KERUSAKAN).first()
        self.assertIsNotNone(charge)
        self.assertEqual(charge.amount, 200000)
        self.assertEqual(charge.status, ExtraCharge.Status.TERUTANG)

    @override_settings(DEPOSIT_MODE='off')
    def test_non_return_creates_extra_charge_and_blacklists(self):
        """Barang tidak dikembalikan menerbitkan ExtraCharge kehilangan seharga estimated_value, suspend, dan blacklist."""
        rental = self._create_active_rental()

        proses_barang_tidak_dikembalikan(rental)
        rental.refresh_from_db()

        self.assertEqual(rental.status, Rental.Status.SELESAI)

        # ExtraCharge kehilangan
        charge = ExtraCharge.objects.filter(rental=rental, charge_type=ExtraCharge.ChargeType.KEHILANGAN).first()
        self.assertIsNotNone(charge)
        self.assertEqual(charge.amount, self.item.estimated_value)
        self.assertEqual(charge.status, ExtraCharge.Status.TERUTANG)

        # Akun penyewa dibekukan & NIM diblacklist
        self.renter.refresh_from_db()
        self.assertTrue(self.renter.is_suspended)
        self.assertTrue(BlacklistedNim.objects.filter(nim='33334444').exists())

    @override_settings(DEPOSIT_MODE='off')
    def test_renter_with_unpaid_extra_charge_cannot_rent(self):
        """Penyewa yang memiliki ExtraCharge berstatus terutang diblokir dari pengajuan sewa baru."""
        rental = self._create_active_rental()
        ExtraCharge.objects.create(
            rental=rental,
            renter=self.renter,
            owner=self.owner,
            charge_type=ExtraCharge.ChargeType.KETERLAMBATAN,
            amount=50000,
            status=ExtraCharge.Status.TERUTANG,
        )

        item2 = Item.objects.create(
            owner=self.owner, category=self.category, title='Item 2', slug='item-2',
            price_per_day=30000, estimated_value=500000,
        )

        with self.assertRaises(RentalValidationError) as ctx:
            ajukan_sewa(
                item=item2,
                renter=self.renter,
                start_date=self.today + timedelta(days=5),
                end_date=self.today + timedelta(days=6),
                terms_accepted=True,
            )
        self.assertIn("tagihan denda atau ganti rugi yang belum diselesaikan", str(ctx.exception))

    @override_settings(DEPOSIT_MODE='off')
    def test_settle_extra_charge_idempotent_and_credits_owner(self):
        """Pelunasan ExtraCharge mengkredit dompet pemilik dan idempoten."""
        rental = self._create_active_rental()
        charge = ExtraCharge.objects.create(
            rental=rental,
            renter=self.renter,
            owner=self.owner,
            charge_type=ExtraCharge.ChargeType.KERUSAKAN,
            amount=150000,
            status=ExtraCharge.Status.TERUTANG,
        )

        admin_user = User.objects.create_superuser(username='admin_7g', email='admin7g@test.id', password='Password123!')

        # Pelunasan pertama
        settle_extra_charge(charge, settled_by='admin', admin_user=admin_user)
        charge.refresh_from_db()
        self.assertEqual(charge.status, ExtraCharge.Status.LUNAS)
        self.assertIsNotNone(charge.paid_at)

        # Transaksi dompet pemilik bertambah
        tx = WalletTransaction.objects.filter(
            user=self.owner,
            kind=WalletTransaction.Kind.KREDIT_TAGIHAN_TAMBAHAN,
            extra_charge=charge,
        ).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 150000)

        # Pelunasan kedua (idempoten, tidak duplikasi kredit)
        settle_extra_charge(charge, settled_by='admin', admin_user=admin_user)
        self.assertEqual(
            WalletTransaction.objects.filter(extra_charge=charge).count(),
            1
        )

    # --- 4. REKONSILIASI KEUANGAN ---
    @override_settings(DEPOSIT_MODE='off')
    def test_reconciliation_invariant_with_extra_charges(self):
        """Invarian rekonsiliasi keuangan memperhitungkan tagihan tambahan terutang dan lunas."""
        metrics = run_financial_reconciliation()
        self.assertTrue(metrics['is_global_balanced'])
        self.assertIn('total_extra_charges_unpaid', metrics)
        self.assertIn('total_extra_charges_paid', metrics)

    # --- 5. MODEL ML LABELING ---
    @override_settings(DEPOSIT_MODE='off')
    def test_ml_labeling_recognizes_extra_charge_damage(self):
        """Pelabelan ML menandai sewa sebagai bermasalah (label=1) jika memiliki ExtraCharge kerusakan."""
        rental = self._create_active_rental()
        ExtraCharge.objects.create(
            rental=rental,
            renter=self.renter,
            owner=self.owner,
            charge_type=ExtraCharge.ChargeType.KERUSAKAN,
            amount=100000,
            status=ExtraCharge.Status.TERUTANG,
        )
        rental.status = Rental.Status.SELESAI
        rental.save()

        example = label_training_example_for_rental(rental)
        self.assertIsNotNone(example)
        self.assertEqual(example.label_problem, 1)

    # --- 6. PEMERIKSAAN HALAMAN PUBLIK (BEBAS KATA DEPOSIT) ---
    @override_settings(DEPOSIT_MODE='off')
    def test_public_pages_do_not_contain_unwanted_deposit_words(self):
        """Memastikan halaman publik (/tentang/, /kalkulator-sewa/) tidak memuat kata deposit di luar konteks penjelasan."""
        res_tentang = self.client.get(reverse('core:tentang'))
        self.assertEqual(res_tentang.status_code, 200)
        content_tentang = res_tentang.content.decode('utf-8').lower()
        self.assertNotIn("uang sewa dan deposit ditahan", content_tentang)

        res_calc = self.client.get('/kalkulator-sewa/?price_per_day=50000&days=3&tier=baru&estimated_value=500000')
        self.assertEqual(res_calc.status_code, 200)
        content_calc = res_calc.content.decode('utf-8').lower()
        self.assertNotIn("deposit jaminan", content_calc)
        self.assertNotIn("estimasi pengembalian deposit", content_calc)
