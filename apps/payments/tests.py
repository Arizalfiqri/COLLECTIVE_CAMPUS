import hashlib
import json
from datetime import date, timedelta, datetime
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.utils import timezone

from apps.accounts.models import Campus, StudentProfile
from apps.catalog.models import Category, Item
from apps.payments.models import Payment, DepositHold, Payout, LedgerEntry
from apps.payments.services import (
    create_or_get_payment_token,
    sync_payment_status,
    verify_midtrans_signature,
    settle_rental_funds,
    process_cancellation_after_payment,
    record_payment_settlement,
    validate_ledger_invariant,
    is_midtrans_configured,
)
from apps.rentals.models import Rental

User = get_user_model()


@override_settings(
    MIDTRANS_SERVER_KEY="SB-Mid-server-test-key-12345",
    MIDTRANS_CLIENT_KEY="SB-Mid-client-test-key-12345",
    MIDTRANS_IS_PRODUCTION=False,
    PLATFORM_COMMISSION_PERCENT=8,
    PAYMENT_DEADLINE_HOURS=6,
    PROTECTION_FEE_MIN=3000,
    PROTECTION_FEE_PERCENT=5,
)
class BasePaymentTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.campus = Campus.objects.create(
            name="Universitas Uji Sandbox",
            short_name="UUS",
            city="Bandar Lampung",
            is_active=True
        )

        # Pemilik
        self.owner = User.objects.create_user(
            username="pemilik_barang",
            email="owner@kampus.id",
            password="TestPassword123!",
            first_name="Pemilik",
            phone_whatsapp="081234567801",
            is_verified_student=True
        )
        StudentProfile.objects.create(
            user=self.owner,
            nim="2020110001",
            campus=self.campus,
            major="Informatika",
            entry_year=2020,
        )

        # Penyewa
        self.renter = User.objects.create_user(
            username="penyewa_sah",
            email="renter@kampus.id",
            password="TestPassword123!",
            first_name="Penyewa",
            phone_whatsapp="081234567802",
            is_verified_student=True
        )
        StudentProfile.objects.create(
            user=self.renter,
            nim="2020110002",
            campus=self.campus,
            major="Sistem Informasi",
            entry_year=2020,
        )

        # Pihak ketiga untuk uji IDOR
        self.other_user = User.objects.create_user(
            username="orang_lain",
            email="other@kampus.id",
            password="TestPassword123!",
            first_name="OrangLain",
            phone_whatsapp="081234567803",
            is_verified_student=True
        )
        StudentProfile.objects.create(
            user=self.other_user,
            nim="2020110003",
            campus=self.campus,
            major="Teknik Komputer",
            entry_year=2020,
        )

        self.category = Category.objects.create(
            name="Elektronik",
            slug="elektronik"
        )

        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="Kamera DSLR Uji",
            slug="kamera-dslr-uji",
            price_per_day=50000,
            deposit_amount=100000,
            estimated_value=1000000,
            is_active=True
        )

        self.today = date.today() + timedelta(days=2)
        self.end_date = self.today + timedelta(days=2) # 3 hari

        self.rental = Rental.objects.create(
            code="KR-TESTPAY",
            item=self.item,
            owner=self.owner,
            renter=self.renter,
            start_date=self.today,
            end_date=self.end_date,
            days=3,
            price_per_day_snapshot=50000,
            rent_total=150000,
            deposit_total=100000,
            protection_fee=7500, # 5% dari 150.000 = 7.500
            grand_total=257500, # 150.000 + 100.000 + 7.500
            use_protection=True,
            status=Rental.Status.MENUNGGU_PEMBAYARAN,
            approved_at=timezone.now(),
            requested_at=timezone.now() - timedelta(hours=1),
        )


class PaymentTokenCreationTests(BasePaymentTestCase):
    @patch('midtransclient.Snap')
    def test_create_payment_token_success(self, mock_snap_cls):
        mock_snap = MagicMock()
        mock_snap.create_transaction.return_value = {'token': 'snap-test-token-xyz'}
        mock_snap_cls.return_value = mock_snap

        payment = create_or_get_payment_token(self.rental, self.renter)
        self.assertEqual(payment.snap_token, 'snap-test-token-xyz')
        self.assertEqual(payment.gross_amount, 257500)
        self.assertTrue(payment.order_id.startswith(f"KR-{self.rental.code}-"))
        self.assertEqual(payment.status, Payment.Status.PENDING)

    @patch('midtransclient.Snap')
    def test_reuse_existing_pending_token(self, mock_snap_cls):
        mock_snap = MagicMock()
        mock_snap.create_transaction.return_value = {'token': 'first-token'}
        mock_snap_cls.return_value = mock_snap

        payment1 = create_or_get_payment_token(self.rental, self.renter)
        self.assertEqual(payment1.snap_token, 'first-token')
        self.assertEqual(mock_snap.create_transaction.call_count, 1)

        # Pemanggilan kedua harus memakai ulang pending token tanpa panggil Midtrans lagi
        payment2 = create_or_get_payment_token(self.rental, self.renter)
        self.assertEqual(payment1.id, payment2.id)
        self.assertEqual(mock_snap.create_transaction.call_count, 1)

    @patch('apps.payments.services.is_midtrans_configured', return_value=False)
    def test_payment_rejected_when_keys_missing(self, mock_conf):
        self.client.login(username="penyewa_sah", password="TestPassword123!")
        res = self.client.post(f"/sewa/{self.rental.code}/bayar/")
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertIn("Kunci Midtrans belum diisi", data['message'])

    def test_idor_payment_only_renter_allowed(self):
        # Percobaan bayar oleh pengguna lain
        self.client.login(username="orang_lain", password="TestPassword123!")
        res = self.client.post(f"/sewa/{self.rental.code}/bayar/")
        self.assertEqual(res.status_code, 403)

        # Percobaan bayar oleh pemilik
        self.client.login(username="pemilik_barang", password="TestPassword123!")
        res = self.client.post(f"/sewa/{self.rental.code}/bayar/")
        self.assertEqual(res.status_code, 403)

    def test_payment_token_rejected_on_wrong_status(self):
        self.rental.status = Rental.Status.MENUNGGU_PERSETUJUAN
        self.rental.save()

        self.client.login(username="penyewa_sah", password="TestPassword123!")
        res = self.client.post(f"/sewa/{self.rental.code}/bayar/")
        self.assertEqual(res.status_code, 400)


class PaymentSyncAndWebhookTests(BasePaymentTestCase):
    def setUp(self):
        super().setUp()
        self.payment = Payment.objects.create(
            rental=self.rental,
            order_id=f"KR-{self.rental.code}-01",
            gross_amount=self.rental.grand_total,
            snap_token="snap-token-abc",
            status=Payment.Status.PENDING
        )

    @patch('midtransclient.CoreApi')
    def test_sync_settlement_success_and_idempotent(self, mock_core_cls):
        mock_core = MagicMock()
        mock_core.transactions.status.return_value = {
            'transaction_status': 'settlement',
            'payment_type': 'bank_transfer',
            'transaction_id': 'trx-12345678',
            'gross_amount': str(self.rental.grand_total),
        }
        mock_core_cls.return_value = mock_core

        # Panggilan pertama sync
        p, r = sync_payment_status(self.payment.order_id)
        self.assertEqual(p.status, Payment.Status.SETTLEMENT)
        self.assertEqual(r.status, Rental.Status.DIBAYAR)
        self.assertIsNotNone(p.paid_at)

        # Periksa DepositHold
        hold = DepositHold.objects.get(rental=self.rental)
        self.assertEqual(hold.status, DepositHold.Status.DITAHAN)
        self.assertEqual(hold.amount, self.rental.deposit_total)

        # Periksa LedgerEntry Masuk
        entries = self.rental.ledger_entries.all()
        kinds = [e.kind for e in entries]
        self.assertIn(LedgerEntry.Kind.MASUK_SEWA, kinds)
        self.assertIn(LedgerEntry.Kind.MASUK_DEPOSIT, kinds)
        self.assertIn(LedgerEntry.Kind.MASUK_DANA_PROTEKSI, kinds)

        total_masuk = sum(e.amount for e in entries if e.kind.startswith('masuk_'))
        self.assertEqual(total_masuk, self.rental.grand_total)

        count_before = entries.count()

        # Panggilan kedua (idempotency check)
        p2, r2 = sync_payment_status(self.payment.order_id)
        self.assertEqual(self.rental.ledger_entries.count(), count_before)
        self.assertEqual(DepositHold.objects.filter(rental=self.rental).count(), 1)

    @patch('midtransclient.CoreApi')
    def test_sync_capture_accept_is_treated_as_settlement(self, mock_core_cls):
        mock_core = MagicMock()
        mock_core.transactions.status.return_value = {
            'transaction_status': 'capture',
            'fraud_status': 'accept',
            'payment_type': 'credit_card',
            'transaction_id': 'trx-card-999',
            'gross_amount': str(self.rental.grand_total),
        }
        mock_core_cls.return_value = mock_core

        p, r = sync_payment_status(self.payment.order_id)
        self.assertEqual(p.status, Payment.Status.SETTLEMENT)
        self.assertEqual(r.status, Rental.Status.DIBAYAR)

    @patch('midtransclient.CoreApi')
    def test_sync_pending_and_expire_status(self, mock_core_cls):
        mock_core = MagicMock()
        mock_core_cls.return_value = mock_core

        # 1. Pending
        mock_core.transactions.status.return_value = {
            'transaction_status': 'pending',
            'payment_type': 'echannel',
        }
        p, r = sync_payment_status(self.payment.order_id)
        self.assertEqual(p.status, Payment.Status.PENDING)
        self.assertEqual(r.status, Rental.Status.MENUNGGU_PEMBAYARAN)

        # 2. Expire
        mock_core.transactions.status.return_value = {
            'transaction_status': 'expire',
            'payment_type': 'echannel',
        }
        p, r = sync_payment_status(self.payment.order_id)
        self.assertEqual(p.status, Payment.Status.EXPIRE)
        self.assertEqual(r.status, Rental.Status.MENUNGGU_PEMBAYARAN)

    def test_webhook_signature_verification(self):
        order_id = self.payment.order_id
        status_code = "200"
        gross_amount = str(self.rental.grand_total)
        server_key = settings.MIDTRANS_SERVER_KEY

        # Buat signature yang valid
        raw_str = f"{order_id}{status_code}{gross_amount}{server_key}"
        valid_sig = hashlib.sha512(raw_str.encode('utf-8')).hexdigest()

        self.assertTrue(verify_midtrans_signature(order_id, status_code, gross_amount, valid_sig))
        self.assertFalse(verify_midtrans_signature(order_id, status_code, gross_amount, "invalidsignature"))

    def test_webhook_post_flow(self):
        order_id = self.payment.order_id
        status_code = "200"
        gross_amount = str(self.rental.grand_total)
        server_key = settings.MIDTRANS_SERVER_KEY

        raw_str = f"{order_id}{status_code}{gross_amount}{server_key}"
        valid_sig = hashlib.sha512(raw_str.encode('utf-8')).hexdigest()

        payload = {
            'order_id': order_id,
            'status_code': status_code,
            'gross_amount': gross_amount,
            'signature_key': valid_sig,
            'transaction_status': 'settlement',
            'payment_type': 'qris',
            'transaction_id': 'trx-qris-123'
        }

        # 1. Invalid signature harus ditolak 403
        bad_payload = dict(payload, signature_key="bad-sig")
        res_bad = self.client.post(
            "/midtrans/notifikasi/",
            data=json.dumps(bad_payload),
            content_type="application/json"
        )
        self.assertEqual(res_bad.status_code, 403)

        # 2. Valid signature harus diterima 200 dan merubah sewa jadi dibayar
        res_ok = self.client.post(
            "/midtrans/notifikasi/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res_ok.status_code, 200)

        self.rental.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.rental.status, Rental.Status.DIBAYAR)
        self.assertEqual(self.payment.status, Payment.Status.SETTLEMENT)


class LedgerEscrowInvariantTests(BasePaymentTestCase):
    def setUp(self):
        super().setUp()
        # Catat pembayaran masuk ke escrow
        self.payment = Payment.objects.create(
            rental=self.rental,
            order_id=f"KR-{self.rental.code}-01",
            gross_amount=self.rental.grand_total,
            snap_token="snap-token-abc",
            status=Payment.Status.SETTLEMENT,
            paid_at=timezone.now()
        )
        self.rental.status = Rental.Status.DIBAYAR
        self.rental.save()
        record_payment_settlement(self.rental, self.payment)

    def test_normal_settlement_invariant(self):
        # Sewa selesai normal tanpa denda atau kerusakan
        payout = settle_rental_funds(self.rental, late_fee=0, damage_fee=0)
        self.assertEqual(payout.status, Payout.Status.DICAIRKAN_SIMULASI)

        # Verifikasi rumus:
        # rent_total = 150.000, komisi 8% = 12.000, owner_net = 138.000
        # deposit = 100.000 (dikembalikan)
        # proteksi = 7.500 (dipindahkan ke dana bersama)
        self.assertEqual(payout.commission, 12000)
        self.assertEqual(payout.net_amount, 138000)

        # Invarian wajib: total masuk == total keluar
        self.assertTrue(validate_ledger_invariant(self.rental))

    def test_late_fee_settlement_invariant(self):
        # Sewa terlambat: denda 25.000 diteruskan ke pemilik dari deposit
        payout = settle_rental_funds(self.rental, late_fee=25000, damage_fee=0)
        self.assertEqual(payout.net_amount, 138000 + 25000)

        # Deposit refund berkurang menjadi 75.000
        hold = self.rental.deposit_hold
        hold.refresh_from_db()
        self.assertEqual(hold.released_amount, 75000)
        self.assertEqual(hold.deducted_amount, 25000)

        # Invarian wajib
        self.assertTrue(validate_ledger_invariant(self.rental))

    def test_damage_fee_settlement_invariant(self):
        # Sewa rusak: potongan 40.000 ke pemilik dari deposit
        payout = settle_rental_funds(self.rental, late_fee=10000, damage_fee=40000)
        self.assertEqual(payout.net_amount, 138000 + 10000 + 40000)

        hold = self.rental.deposit_hold
        hold.refresh_from_db()
        self.assertEqual(hold.released_amount, 50000)
        self.assertEqual(hold.deducted_amount, 50000)

        # Invarian wajib
        self.assertTrue(validate_ledger_invariant(self.rental))

    def test_settlement_without_protection_fee(self):
        # Sewa tanpa proteksi
        self.rental.protection_fee = 0
        self.rental.grand_total = self.rental.rent_total + self.rental.deposit_total
        self.rental.save()
        self.rental.ledger_entries.all().delete()
        record_payment_settlement(self.rental, self.payment)

        settle_rental_funds(self.rental, late_fee=0, damage_fee=0)
        self.assertTrue(validate_ledger_invariant(self.rental))


class CancellationAfterPaymentTests(BasePaymentTestCase):
    def setUp(self):
        super().setUp()
        self.payment = Payment.objects.create(
            rental=self.rental,
            order_id=f"KR-{self.rental.code}-01",
            gross_amount=self.rental.grand_total,
            snap_token="snap-token-abc",
            status=Payment.Status.SETTLEMENT,
            paid_at=timezone.now()
        )
        self.rental.status = Rental.Status.DIBAYAR
        self.rental.save()
        record_payment_settlement(self.rental, self.payment)

    def test_owner_cancels_after_payment_full_refund(self):
        from apps.rentals.services import batalkan_sewa
        # Pemilik membatalkan sewa yang sudah dibayar
        batalkan_sewa(self.rental, self.owner, reason="Barang tiba-tiba rusak")
        self.rental.refresh_from_db()
        self.assertEqual(self.rental.status, Rental.Status.DIBATALKAN)

        # Invarian buku besar terpenuhi
        self.assertTrue(validate_ledger_invariant(self.rental))

        refund_entry = self.rental.ledger_entries.get(kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA)
        self.assertEqual(refund_entry.amount, self.rental.grand_total)

    def test_renter_cancels_more_than_24h_before_start_full_refund(self):
        from apps.rentals.services import batalkan_sewa
        # start_date adalah H+2 (> 24 jam)
        batalkan_sewa(self.rental, self.renter, reason="Rencana berubah")
        self.rental.refresh_from_db()
        self.assertEqual(self.rental.status, Rental.Status.DIBATALKAN)

        self.assertTrue(validate_ledger_invariant(self.rental))
        refund_entry = self.rental.ledger_entries.get(kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA)
        self.assertEqual(refund_entry.amount, self.rental.grand_total)

    def test_renter_cancels_within_24h_before_start_owner_compensation(self):
        from apps.rentals.services import batalkan_sewa
        # Ubah start_date menjadi hari ini pukul 00:00 (kurang dari 24 jam)
        self.rental.start_date = date.today()
        self.rental.save()

        batalkan_sewa(self.rental, self.renter, reason="Membatalkan mendadak di hari H")
        self.rental.refresh_from_db()
        self.assertEqual(self.rental.status, Rental.Status.DIBATALKAN)

        self.assertTrue(validate_ledger_invariant(self.rental))

        # 20% dari rent_total (150.000 * 20% = 30.000) ke pemilik
        compensation = round(self.rental.rent_total * 0.20)
        owner_entry = self.rental.ledger_entries.get(kind=LedgerEntry.Kind.KELUAR_PAYOUT_PEMILIK)
        self.assertEqual(owner_entry.amount, compensation)

        # Sisanya (257.500 - 30.000 = 227.500) di-refund ke penyewa
        refund_entry = self.rental.ledger_entries.get(kind=LedgerEntry.Kind.KELUAR_REFUND_PENYEWA)
        self.assertEqual(refund_entry.amount, self.rental.grand_total - compensation)


class MidtransEnabledPaymentsTestCase(BasePaymentTestCase):
    @patch('apps.payments.services.get_midtrans_snap_client')
    def test_enabled_payments_passed_to_snap_transaction(self, mock_get_client):
        mock_snap = MagicMock()
        mock_snap.create_transaction.return_value = {'token': 'test-snap-token-123'}
        mock_get_client.return_value = mock_snap

        with override_settings(MIDTRANS_ENABLED_PAYMENTS_RAW="dana,seabank_va,echannel,other_qris"):
            payment = create_or_get_payment_token(self.rental, self.renter)
            self.assertEqual(payment.snap_token, 'test-snap-token-123')
            call_args = mock_snap.create_transaction.call_args[0][0]
            self.assertIn('enabled_payments', call_args)
            self.assertEqual(
                call_args['enabled_payments'],
                ['dana', 'seabank_va', 'echannel', 'other_qris']
            )

    @patch('apps.payments.services.get_midtrans_snap_client')
    def test_empty_enabled_payments_omitted_from_snap_transaction(self, mock_get_client):
        mock_snap = MagicMock()
        mock_snap.create_transaction.return_value = {'token': 'test-snap-token-all'}
        mock_get_client.return_value = mock_snap

        with override_settings(MIDTRANS_ENABLED_PAYMENTS_RAW=""):
            payment = create_or_get_payment_token(self.rental, self.renter)
            call_args = mock_snap.create_transaction.call_args[0][0]
            self.assertNotIn('enabled_payments', call_args)


class PaymentFinishRedirectTestCase(BasePaymentTestCase):
    @patch('apps.payments.services.get_midtrans_snap_client')
    def test_finish_url_passed_in_callbacks(self, mock_get_client):
        mock_snap = MagicMock()
        mock_snap.create_transaction.return_value = {'token': 'test-snap-token-finish'}
        mock_get_client.return_value = mock_snap

        test_finish_url = "http://127.0.0.1:8000/sewa/KR-TEST/selesai-bayar/"
        payment = create_or_get_payment_token(
            self.rental,
            self.renter,
            force_new=True,
            finish_url=test_finish_url
        )
        call_args = mock_snap.create_transaction.call_args[0][0]
        self.assertIn('callbacks', call_args)
        self.assertEqual(call_args['callbacks']['finish'], test_finish_url)

    @patch('apps.payments.services.get_midtrans_snap_client')
    def test_rental_pay_view_passes_finish_url(self, mock_get_client):
        mock_snap = MagicMock()
        mock_snap.create_transaction.return_value = {'token': 'test-snap-token-pay'}
        mock_get_client.return_value = mock_snap

        self.client.login(username="penyewa_sah", password="TestPassword123!")
        res = self.client.post(f"/sewa/{self.rental.code}/bayar/", {'force_new': '1'})
        self.assertEqual(res.status_code, 200)

        call_args = mock_snap.create_transaction.call_args[0][0]
        self.assertIn('callbacks', call_args)
        self.assertTrue(call_args['callbacks']['finish'].endswith(f"/sewa/{self.rental.code}/selesai-bayar/"))

    @patch('apps.payments.views.sync_payment_status')
    def test_rental_payment_finish_view_renders_for_renter(self, mock_sync):
        payment = Payment.objects.create(
            rental=self.rental,
            order_id=f"KR-{self.rental.code}-01",
            gross_amount=self.rental.grand_total,
            snap_token="snap-token-test",
            status=Payment.Status.SETTLEMENT
        )
        self.rental.status = Rental.Status.DIBAYAR
        self.rental.save()
        mock_sync.return_value = (payment, self.rental)

        self.client.login(username="penyewa_sah", password="TestPassword123!")
        res = self.client.get(f"/sewa/{self.rental.code}/selesai-bayar/?order_id={payment.order_id}")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'rentals/rental_payment_finish.html')
        self.assertContains(res, "Pembayaran berhasil diverifikasi")
        self.assertContains(res, payment.order_id)
        self.assertContains(res, "Buka Ruang Sewa & Rincian Pesanan")

    def test_rental_payment_finish_view_idor_protection(self):
        self.client.login(username="orang_lain", password="TestPassword123!")
        res = self.client.get(f"/sewa/{self.rental.code}/selesai-bayar/")
        self.assertEqual(res.status_code, 403)

    def test_rental_payment_finish_view_login_required(self):
        self.client.logout()
        res = self.client.get(f"/sewa/{self.rental.code}/selesai-bayar/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/masuk/", res.url)


class SaleOrderPaymentTest(TestCase):
    """Pengujian integrasi Midtrans dan webhook untuk pesanan jual beli (Fase 8B Butir 4)."""

    def setUp(self):
        self.campus = Campus.objects.create(name="ITERA", short_name="ITERA", city="Lampung")
        self.seller = User.objects.create_user(
            username="seller_midtrans", email="seller@kampus.id", password="Password123!", is_verified_student=True,
            phone_whatsapp="081299990001"
        )
        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim="121140080")

        self.buyer = User.objects.create_user(
            username="buyer_midtrans", email="buyer@kampus.id", password="Password123!", is_verified_student=True,
            phone_whatsapp="081299990002"
        )
        StudentProfile.objects.create(user=self.buyer, campus=self.campus, nim="121140081")

        self.other_user = User.objects.create_user(
            username="other_midtrans", email="other@kampus.id", password="Password123!", is_verified_student=True
        )
        StudentProfile.objects.create(user=self.other_user, campus=self.campus, nim="121140082")

        self.cat, _ = Category.objects.get_or_create(slug="elektronik-jual", defaults={'name': 'Elektronik', 'scope': Category.Scope.JUAL})
        from apps.sales.models import SaleItem, SaleOrder
        from apps.sales.services import create_sale_order
        self.item = SaleItem.objects.create(
            owner=self.seller,
            category=self.cat,
            title="Earphone Wireless ANC",
            slug="earphone-wireless-anc",
            description="Mulus terawat, baterai tahan 8 jam.",
            condition="seperti_baru",
            price=200_000,
            pickup_area="Perpustakaan Lt 2",
            status=SaleItem.Status.AKTIF,
            expires_at=timezone.now() + timedelta(days=60),
        )
        self.order = create_sale_order(
            item=self.item,
            buyer=self.buyer,
            terms_accepted=True,
            ip_address="127.0.0.1",
            user_agent="TestAgent"
        )
        self.client = Client()

    @patch('apps.payments.services.get_midtrans_snap_client')
    @patch('apps.payments.services.is_midtrans_configured', return_value=True)
    def test_create_or_get_sale_payment_token_order_id_prefix(self, mock_cfg, mock_snap_client):
        """order_id Midtrans untuk SaleOrder wajib berawalan KJ-."""
        from apps.payments.services import create_or_get_sale_payment_token
        mock_snap = MagicMock()
        mock_snap.create_transaction.return_value = {'token': 'snap-test-kj-token'}
        mock_snap_client.return_value = mock_snap

        payment = create_or_get_sale_payment_token(self.order, self.buyer)
        self.assertTrue(payment.order_id.startswith('KJ-'))
        self.assertEqual(payment.gross_amount, 200_000)
        self.assertEqual(payment.snap_token, 'snap-test-kj-token')
        self.assertEqual(payment.sale_order, self.order)
        self.assertIsNone(payment.rental)

        call_params = mock_snap.create_transaction.call_args[0][0]
        self.assertTrue(call_params['transaction_details']['order_id'].startswith('KJ-'))
        self.assertEqual(call_params['transaction_details']['gross_amount'], 200_000)

    @patch('apps.payments.services.get_midtrans_snap_client')
    @patch('apps.payments.services.is_midtrans_configured', return_value=True)
    def test_sale_order_pay_view_anti_idor(self, mock_cfg, mock_snap_client):
        """Hanya pembeli yang berhak memanggil sale_order_pay_view, orang lain 403."""
        mock_snap = MagicMock()
        mock_snap.create_transaction.return_value = {'token': 'snap-test-token-123'}
        mock_snap_client.return_value = mock_snap

        # Orang lain ditolak
        self.client.login(username="other_midtrans", password="Password123!")
        res = self.client.post(f"/midtrans/pesanan/{self.order.code}/bayar/")
        self.assertEqual(res.status_code, 403)

        # Pembeli berhasil
        self.client.login(username="buyer_midtrans", password="Password123!")
        res = self.client.post(f"/midtrans/pesanan/{self.order.code}/bayar/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['snap_token'], 'snap-test-token-123')
        self.assertTrue(data['order_id'].startswith('KJ-'))

    def test_sync_payment_status_idempotent_settlement(self):
        """Sinkronisasi settlement pesanan jual beli idempoten: status dibayar, masuk_penjualan tercatat."""
        from apps.payments.models import Payment, LedgerEntry
        from apps.payments.services import sync_payment_status
        from apps.sales.models import SaleOrder
        from apps.chat.models import Conversation, Message

        payment = Payment.objects.create(
            sale_order=self.order,
            order_id=f"{self.order.code}-01",
            gross_amount=self.order.price_snapshot,
            snap_token="snap-kj-settle-token",
            status=Payment.Status.PENDING
        )

        conv = Conversation.objects.create(
            sale_item=self.item,
            renter=self.buyer,
            owner=self.seller,
        )
        self.assertFalse(conv.has_successful_payment())

        payload = {
            'order_id': payment.order_id,
            'transaction_status': 'settlement',
            'gross_amount': str(payment.gross_amount),
            'payment_type': 'qris',
            'transaction_id': 'trx-kj-12345',
        }

        # Sync pertama
        sync_payment_status(payment.order_id, external_status_data=payload)

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SETTLEMENT)
        self.assertEqual(self.order.status, SaleOrder.Status.DIBAYAR)
        self.assertIsNotNone(self.order.paid_at)

        # Masuk penjualan tercatat di buku besar
        entries = LedgerEntry.objects.filter(sale_order=self.order, kind=LedgerEntry.Kind.MASUK_PENJUALAN)
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.first().amount, 200_000)

        # Kontak otomatis terbuka di chat setelah pembayaran
        self.assertTrue(conv.has_successful_payment())

        # Sync kedua (idempoten)
        sync_payment_status(payment.order_id, external_status_data=payload)
        entries_after = LedgerEntry.objects.filter(sale_order=self.order, kind=LedgerEntry.Kind.MASUK_PENJUALAN)
        self.assertEqual(entries_after.count(), 1)

    @override_settings(MIDTRANS_SERVER_KEY="server-key-test")
    def test_webhook_processes_kj_order_with_valid_signature(self):
        """Webhook resmi Midtrans dapat memproses pembayaran pesanan KJ- dengan verifikasi signature."""
        from apps.payments.models import Payment, LedgerEntry
        from apps.sales.models import SaleOrder

        payment = Payment.objects.create(
            sale_order=self.order,
            order_id=f"{self.order.code}-01",
            gross_amount=self.order.price_snapshot,
            snap_token="snap-token-webhook-kj",
            status=Payment.Status.PENDING
        )

        status_code = "200"
        gross_amount = f"{payment.gross_amount}.00"
        raw_str = f"{payment.order_id}{status_code}{gross_amount}server-key-test"
        signature = hashlib.sha512(raw_str.encode('utf-8')).hexdigest()

        payload = {
            'order_id': payment.order_id,
            'status_code': status_code,
            'gross_amount': gross_amount,
            'signature_key': signature,
            'transaction_status': 'settlement',
            'payment_type': 'bank_transfer',
            'transaction_id': 'trx-webhook-kj-999',
        }

        res = self.client.post(
            '/midtrans/notifikasi/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SETTLEMENT)
        self.assertEqual(self.order.status, SaleOrder.Status.DIBAYAR)
        self.assertTrue(LedgerEntry.objects.filter(sale_order=self.order, kind=LedgerEntry.Kind.MASUK_PENJUALAN).exists())


class SaleOrderReconciliationAdminTest(TestCase):
    """Pengujian Butir 8: Rekonsiliasi keuangan pesanan jual beli dan antrean operasional admin."""

    def setUp(self):
        from apps.accounts.models import Campus, MeetingPoint, StudentProfile
        from apps.catalog.models import Category
        from apps.sales.models import SaleItem, SaleOrder
        from apps.sales.services import create_sale_order
        from apps.core.models import TermsVersion

        self.campus = Campus.objects.create(name="Universitas Test", short_name="UT", city="Bandung")
        self.mp = MeetingPoint.objects.create(campus=self.campus, name="Lobi Utama", is_public=True)

        self.seller = User.objects.create_user(
            username='seller_recon',
            email='seller_recon@univ.ac.id',
            password='Password123!',
            is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.seller, campus=self.campus, nim="121140091")

        self.buyer = User.objects.create_user(
            username='buyer_recon',
            email='buyer_recon@univ.ac.id',
            password='Password123!',
            is_verified_student=True,
        )
        StudentProfile.objects.create(user=self.buyer, campus=self.campus, nim="121140092")

        self.admin_user = User.objects.create_superuser(
            username='admin_recon',
            email='admin_recon@univ.ac.id',
            password='Password123!',
        )

        self.category = Category.objects.create(name='Buku Recon', slug='buku-recon', scope=Category.Scope.JUAL)
        self.item = SaleItem.objects.create(
            owner=self.seller,
            title='Buku Rekonsiliasi Akuntansi',
            slug='buku-rekonsiliasi-akuntansi',
            category=self.category,
            price=200_000,
            status=SaleItem.Status.AKTIF,
        )

        self.terms = TermsVersion.objects.create(
            version="1.0",
            term_type=TermsVersion.Type.JUAL_PEMBELI,
            content="Syarat dan ketentuan pembelian resmi kampus.",
            is_active=True
        )

        self.order = create_sale_order(
            item=self.item,
            buyer=self.buyer,
            terms_accepted=True,
            ip_address="127.0.0.1",
            user_agent="TestAgent"
        )

    def test_reconciliation_with_paid_sale_order_in_escrow(self):
        """Pesanan status dibayar terhitung di escrow_sales_held dan seimbang secara global."""
        from apps.payments.models import Payment, LedgerEntry
        from apps.payments.services import sync_payment_status
        from apps.payments.reconciliation import run_financial_reconciliation

        Payment.objects.create(
            sale_order=self.order,
            order_id=f"{self.order.code}-01",
            gross_amount=self.order.price_snapshot,
            snap_token="snap-recon-token",
            status=Payment.Status.PENDING
        )

        payload = {
            'order_id': f"{self.order.code}-01",
            'transaction_status': 'settlement',
            'gross_amount': str(self.order.price_snapshot),
            'payment_type': 'qris',
        }
        sync_payment_status(f"{self.order.code}-01", external_status_data=payload)

        recon = run_financial_reconciliation()
        summary = recon['summary']

        self.assertTrue(summary['global_balanced'])
        self.assertEqual(summary['discrepancy'], 0)
        self.assertEqual(summary['escrow_sales_held'], 200_000)
        self.assertEqual(summary['mismatched_sales_count'], 0)
        self.assertEqual(summary['total_sales_checked'], 1)
        self.assertEqual(recon['independent_checks']['sale_payment_ledger_mismatch'], 0)
        self.assertEqual(recon['independent_checks']['sale_payments_settled'], 200_000)
        self.assertEqual(recon['independent_checks']['ledger_masuk_penjualan'], 200_000)
        self.assertTrue(recon['independent_checks']['all_independent_balanced'])

    def test_reconciliation_with_settled_sale_order(self):
        """Pesanan yang diselesaikan melepas komisi dan kredit penjual secara seimbang."""
        from apps.payments.models import Payment
        from apps.payments.services import sync_payment_status
        from apps.sales.services import mark_sale_order_handed_over, settle_sale_order
        from apps.payments.reconciliation import run_financial_reconciliation

        Payment.objects.create(
            sale_order=self.order,
            order_id=f"{self.order.code}-01",
            gross_amount=self.order.price_snapshot,
            snap_token="snap-recon-token",
            status=Payment.Status.PENDING
        )
        sync_payment_status(f"{self.order.code}-01", external_status_data={
            'order_id': f"{self.order.code}-01",
            'transaction_status': 'settlement',
            'gross_amount': str(self.order.price_snapshot),
            'payment_type': 'qris',
        })

        self.order.refresh_from_db()
        mark_sale_order_handed_over(self.order, user=self.seller)
        self.order.refresh_from_db()
        settle_sale_order(self.order)

        recon = run_financial_reconciliation()
        summary = recon['summary']

        self.assertTrue(summary['global_balanced'])
        self.assertEqual(summary['escrow_sales_held'], 0)
        # Komisi 5% dari 200.000 = 10.000
        self.assertEqual(summary['total_platform_commission'], 10_000)
        # Saldo penjual = 190.000
        self.assertEqual(summary['total_user_wallets'], 190_000)
        self.assertEqual(summary['mismatched_sales_count'], 0)
        self.assertEqual(recon['independent_checks']['sale_payout_wallet_mismatch'], 0)
        self.assertTrue(recon['independent_checks']['all_independent_balanced'])

    def test_reconciliation_with_cancelled_sale_order_refund(self):
        """Pesanan yang dibatalkan setelah bayar mengembalikan dana ke dompet pembeli secara seimbang."""
        from apps.payments.models import Payment
        from apps.payments.services import sync_payment_status
        from apps.sales.services import cancel_sale_order
        from apps.payments.reconciliation import run_financial_reconciliation

        Payment.objects.create(
            sale_order=self.order,
            order_id=f"{self.order.code}-01",
            gross_amount=self.order.price_snapshot,
            snap_token="snap-recon-token",
            status=Payment.Status.PENDING
        )
        sync_payment_status(f"{self.order.code}-01", external_status_data={
            'order_id': f"{self.order.code}-01",
            'transaction_status': 'settlement',
            'gross_amount': str(self.order.price_snapshot),
            'payment_type': 'qris',
        })

        self.order.refresh_from_db()
        cancel_sale_order(self.order, user=self.seller, reason="Stok fisik rusak")

        recon = run_financial_reconciliation()
        summary = recon['summary']

        self.assertTrue(summary['global_balanced'])
        self.assertEqual(summary['escrow_sales_held'], 0)
        # Refund penuh ke dompet pembeli
        self.assertEqual(summary['total_user_wallets'], 200_000)
        self.assertEqual(summary['mismatched_sales_count'], 0)
        self.assertEqual(recon['independent_checks']['sale_refund_wallet_mismatch'], 0)
        self.assertTrue(recon['independent_checks']['all_independent_balanced'])

    def test_admin_operational_stats_and_pages(self):
        """Antrean operasional dan halaman rekonsiliasi admin memuat metrik jual beli."""
        from django.utils import timezone
        import datetime
        from apps.core.services import get_staff_operational_stats
        from apps.sales.models import SaleItem, SaleOrder

        # 1. Buat pesanan bermasalah (sengketa & terlambat serah terima)
        self.order.status = SaleOrder.Status.SENGKETA
        self.order.save(update_fields=['status'])

        # Buat pesanan kedua yang terlambat serah terima
        item2 = SaleItem.objects.create(
            owner=self.seller,
            title='Barang Janji Temu Terlewat',
            slug='barang-janji-temu-terlewat',
            category=self.category,
            price=150_000,
            status=SaleItem.Status.AKTIF,
        )
        from apps.sales.services import create_sale_order
        order2 = create_sale_order(
            item=item2,
            buyer=self.buyer,
            terms_accepted=True,
            ip_address="127.0.0.1",
            user_agent="TestAgent"
        )
        order2.status = SaleOrder.Status.DIBAYAR
        order2.meetup_at = timezone.now() - datetime.timedelta(hours=2)
        order2.save(update_fields=['status', 'meetup_at'])

        stats = get_staff_operational_stats()
        self.assertGreaterEqual(stats['sale_dispute_count'], 1)
        self.assertGreaterEqual(stats['sale_overdue_meetup_count'], 1)
        self.assertGreaterEqual(stats['sale_problematic_count'], 2)
        self.assertGreaterEqual(stats['total_queue'], 2)

        # 2. Login admin dan akses halaman admin rekonsiliasi
        self.client.force_login(self.admin_user)
        res_recon = self.client.get('/admin/rekonsiliasi/')
        self.assertEqual(res_recon.status_code, 200)
        self.assertContains(res_recon, "Audit invarian per pesanan jual beli")
        self.assertContains(res_recon, "Jual beli bermasalah")

        # 3. Akses dashboard admin index
        res_dash = self.client.get('/admin/')
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, "Pesanan jual beli bermasalah")
