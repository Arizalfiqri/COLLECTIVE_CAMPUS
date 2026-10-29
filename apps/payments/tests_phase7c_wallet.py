import datetime
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.catalog.models import Item, Category
from apps.rentals.models import Rental, Dispute
from apps.payments.models import (
    Payment, DepositHold, Payout, LedgerEntry,
    WalletTransaction, WithdrawalRequest, WithdrawalAccountAccessLog
)
from apps.payments.services import (
    get_user_wallet_balance,
    create_wallet_transaction,
    request_withdrawal,
    process_withdrawal,
    settle_rental_funds,
    process_cancellation_after_payment,
)
from apps.payments.reconciliation import run_financial_reconciliation
from apps.payments.encryption import encrypt_account_number, decrypt_account_number, mask_account_number

User = get_user_model()


class Phase7CWalletTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='pemilik_test',
            email='owner@kampus.ac.id',
            password='password123',
            full_name='Budi Pemilik'
        )
        self.renter = User.objects.create_user(
            username='penyewa_test',
            email='renter@kampus.ac.id',
            password='password123',
            full_name='Citra Penyewa'
        )
        self.staff_admin = User.objects.create_user(
            username='admin_test',
            email='admin@kampusrent.id',
            password='password123',
            full_name='Admin Staf',
            is_staff=True
        )

        self.category = Category.objects.create(name='Elektronik', slug='elektronik')
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title='Proyektor Epson',
            description='Proyektor presentasi',
            estimated_value=1500000,
            price_per_day=50000,
            deposit_amount=100000,
            is_active=True
        )

    def _create_paid_rental(self, code='RNT-TEST-01', rental_fee=100000, deposit=100000, days=2):
        now = timezone.now()
        rental = Rental.objects.create(
            code=code,
            item=self.item,
            renter=self.renter,
            owner=self.owner,
            status=Rental.Status.DIBAYAR,
            start_date=now.date(),
            end_date=(now + datetime.timedelta(days=days)).date(),
            days=days,
            price_per_day_snapshot=50000,
            rent_total=rental_fee,
            deposit_total=deposit,
            grand_total=rental_fee + deposit,
            use_protection=False,
            status_changed_at=now,
        )
        Payment.objects.create(
            rental=rental,
            order_id=f"ORDER-{code}",
            gross_amount=rental.grand_total,
            status=Payment.Status.SETTLEMENT,
            paid_at=now
        )
        DepositHold.objects.create(
            rental=rental,
            amount=deposit,
            status=DepositHold.Status.DITAHAN
        )
        Payout.objects.create(
            rental=rental,
            owner=self.owner,
            gross_rent=rental_fee,
            commission=int(rental_fee * 0.05),
            net_amount=rental_fee - int(rental_fee * 0.05),
            status=Payout.Status.MENUNGGU
        )
        LedgerEntry.objects.create(
            rental=rental,
            kind=LedgerEntry.Kind.MASUK_SEWA,
            amount=rental_fee,
            note="Dana sewa pokok masuk escrow"
        )
        LedgerEntry.objects.create(
            rental=rental,
            kind=LedgerEntry.Kind.MASUK_DEPOSIT,
            amount=deposit,
            note="Dana jaminan deposit masuk escrow"
        )
        return rental

    def test_idempotent_credits_scenarios(self):
        """1. Uji kredit saldo idempoten pada berbagai skenario (selesai, terlambat, pembatalan)."""
        # Skenario 1: Selesai tepat waktu
        rental1 = self._create_paid_rental(code='RNT-SEL-01', rental_fee=100000, deposit=100000)
        settle_rental_funds(rental1)
        
        # Cek saldo awal
        owner_bal = get_user_wallet_balance(self.owner)
        renter_bal = get_user_wallet_balance(self.renter)
        self.assertEqual(owner_bal, 92000)  # Rp100k - 8% komisi platform (Rp8k)
        self.assertEqual(renter_bal, 100000) # Full deposit

        # Panggil lagi (idempoten)
        settle_rental_funds(rental1)
        self.assertEqual(get_user_wallet_balance(self.owner), owner_bal)
        self.assertEqual(get_user_wallet_balance(self.renter), renter_bal)
        self.assertEqual(
            WalletTransaction.objects.filter(rental=rental1, user=self.owner).count(), 1
        )
        self.assertEqual(
            WalletTransaction.objects.filter(rental=rental1, user=self.renter).count(), 1
        )

        # Skenario 2: Terlambat & Denda Kerusakan
        rental2 = self._create_paid_rental(code='RNT-TEL-02', rental_fee=100000, deposit=100000)
        rental2.late_fee = 20000
        rental2.save(update_fields=['late_fee'])
        settle_rental_funds(rental2, late_fee=20000, damage_fee=30000)

        # Owner dapat payout (92k) + denda (20k) + kerusakan (30k) = 142k
        # Renter dapat sisa deposit (100k - 20k - 30k = 50k)
        owner_bal_after = get_user_wallet_balance(self.owner)
        renter_bal_after = get_user_wallet_balance(self.renter)
        self.assertEqual(owner_bal_after - owner_bal, 142000)
        self.assertEqual(renter_bal_after - renter_bal, 50000)

        # Panggil lagi untuk rental2 (idempoten)
        settle_rental_funds(rental2, late_fee=20000, damage_fee=30000)
        self.assertEqual(get_user_wallet_balance(self.owner), owner_bal_after)
        self.assertEqual(get_user_wallet_balance(self.renter), renter_bal_after)

        # Skenario 3: Pembatalan setelah bayar (refund sewa & deposit sesuai kebijakan <=24 jam: 20% kompensasi pemilik)
        rental3 = self._create_paid_rental(code='RNT-BATAL-03', rental_fee=80000, deposit=50000)
        renter_pre = get_user_wallet_balance(self.renter)
        owner_pre = get_user_wallet_balance(self.owner)
        process_cancellation_after_payment(rental3, cancelled_by=self.renter, reason="Batal mendadak")

        # Renter refund: 130k - 16k (20% sewa) = 114k
        self.assertEqual(get_user_wallet_balance(self.renter), renter_pre + 114000)
        self.assertEqual(get_user_wallet_balance(self.owner), owner_pre + 16000)
        # Panggil ulang pembatalan (idempoten)
        process_cancellation_after_payment(rental3, cancelled_by=self.renter, reason="Batal mendadak")
        self.assertEqual(get_user_wallet_balance(self.renter), renter_pre + 114000)
        self.assertEqual(get_user_wallet_balance(self.owner), owner_pre + 16000)

    def test_withdrawal_rules(self):
        """2. Uji aturan penarikan dana: saldo cukup, minimal WITHDRAWAL_MIN, satu aktif, tolak mengembalikan saldo."""
        # Beri pemilik saldo sebesar Rp50.000 via kredit
        create_wallet_transaction(
            user=self.owner,
            kind=WalletTransaction.Kind.KREDIT_PAYOUT,
            amount=50000,
            note="Injeksi saldo awal"
        )
        self.assertEqual(get_user_wallet_balance(self.owner), 50000)

        # Gagal: penarikan di bawah minimal Rp20.000
        with self.assertRaises(ValueError):
            request_withdrawal(
                user=self.owner,
                amount=10000,
                method=WithdrawalRequest.Method.BCA,
                account_name="Budi",
                account_number="12345678"
            )

        # Gagal: penarikan melebihi saldo (Rp60.000 > Rp50.000)
        with self.assertRaises(ValueError):
            request_withdrawal(
                user=self.owner,
                amount=60000,
                method=WithdrawalRequest.Method.BCA,
                account_name="Budi",
                account_number="12345678"
            )

        # Sukses: tarik Rp30.000
        w = request_withdrawal(
            user=self.owner,
            amount=30000,
            method=WithdrawalRequest.Method.BCA,
            account_name="Budi",
            account_number="12345678"
        )
        self.assertEqual(w.status, WithdrawalRequest.Status.DIMINTA)
        # Saldo langsung berkurang jadi Rp20.000
        self.assertEqual(get_user_wallet_balance(self.owner), 20000)

        # Gagal: satu permintaan aktif per pengguna
        with self.assertRaises(ValueError):
            request_withdrawal(
                user=self.owner,
                amount=20000,
                method=WithdrawalRequest.Method.MANDIRI,
                account_name="Budi",
                account_number="98765432"
            )

        # Admin menolak permintaan penarikan -> Saldo harus kembali utuh ke Rp50.000
        process_withdrawal(
            withdrawal=w,
            new_status=WithdrawalRequest.Status.DITOLAK,
            admin_user=self.staff_admin,
            admin_note="Nama rekening tidak cocok"
        )
        w.refresh_from_db()
        self.assertEqual(w.status, WithdrawalRequest.Status.DITOLAK)
        self.assertEqual(get_user_wallet_balance(self.owner), 50000)

    def test_fernet_encryption_and_security(self):
        """3. Uji enkripsi Fernet: plaintext tidak tersimpan di database dan tidak muncul di str."""
        raw_acc = "081234567890"
        w = WithdrawalRequest(
            user=self.owner,
            amount=25000,
            method=WithdrawalRequest.Method.DANA,
            account_name="Budi",
        )
        w.set_account_number(raw_acc)
        w.save()

        # Nilai di DB bukan teks asli
        self.assertNotEqual(w.account_number, raw_acc)
        self.assertNotIn(raw_acc, w.account_number)

        # Dapat didekripsi dengan benar
        self.assertEqual(w.get_decrypted_account_number(), raw_acc)

        # Masked version hanya tampilkan 4 digit terakhir
        self.assertEqual(w.masked_account_number, "•••• 7890")

        # Representasi string tidak memuat nomor rekening mentah
        self.assertNotIn(raw_acc, str(w))

    def test_staff_only_account_access_and_logging(self):
        """4. Uji pengungkapan nomor rekening hanya untuk staf via POST + alasan dan dicatat ke log audit."""
        w = WithdrawalRequest(
            user=self.owner,
            amount=30000,
            method=WithdrawalRequest.Method.MANDIRI,
            account_name="Budi",
        )
        w.set_account_number("1400012345678")
        w.save()

        client = Client()
        # 1. Non-login / user biasa ditolak
        client.force_login(self.renter)
        resp = client.post(f"/admin/penarikan/{w.id}/lihat-rekening/", {'reason': 'Cek rekening transfer'})
        self.assertIn(resp.status_code, [302, 403])
        self.assertEqual(WithdrawalAccountAccessLog.objects.count(), 0)

        # GET request ditolak (Method Not Allowed)
        client.force_login(self.staff_admin)
        resp_get = client.get(f"/admin/penarikan/{w.id}/lihat-rekening/")
        self.assertEqual(resp_get.status_code, 405)

        # Alasan kosong ditolak
        resp_blank = client.post(f"/admin/penarikan/{w.id}/lihat-rekening/", {'reason': ''})
        self.assertEqual(resp_blank.status_code, 400)

        # 2. Staf admin berhasil via POST dengan alasan valid
        resp = client.post(f"/admin/penarikan/{w.id}/lihat-rekening/", {'reason': 'Verifikasi nomor rekening transfer'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['account_number'], "1400012345678")

        # Cek log audit
        log = WithdrawalAccountAccessLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.withdrawal, w)
        self.assertEqual(log.accessed_by, self.staff_admin)
        self.assertEqual(log.reason, 'Verifikasi nomor rekening transfer')

    def test_reconciliation_balanced(self):
        """5. Uji rekonsiliasi keuangan sistem tetap seimbang."""
        rental = self._create_paid_rental(code='RNT-RECON-01', rental_fee=100000, deposit=50000)
        rental.status = Rental.Status.SELESAI
        rental.save(update_fields=['status'])
        settle_rental_funds(rental)

        recon = run_financial_reconciliation()
        self.assertTrue(recon['summary']['global_balanced'])
        self.assertEqual(recon['summary']['discrepancy'], 0)
        self.assertEqual(recon['summary']['mismatched_rentals_count'], 0)

    def test_reconciliation_detects_corrupted_source(self):
        """Uji rekonsiliasi independen mendeteksi jika salah satu sumber sengaja dirusak."""
        rental = self._create_paid_rental(code='RNT-CORRUPT-01', rental_fee=100000, deposit=50000)
        rental.status = Rental.Status.SELESAI
        rental.save(update_fields=['status'])
        settle_rental_funds(rental)

        # Kondisi awal seimbang
        recon_pre = run_financial_reconciliation()
        self.assertTrue(recon_pre['summary']['global_balanced'])

        # Sengaja merusak sumber: ubah nominal kredit pada salah satu WalletTransaction
        tx = WalletTransaction.objects.filter(rental=rental, user=self.renter).first()
        self.assertIsNotNone(tx)
        tx.amount = tx.amount + 15000  # Tambahkan nominal liar
        tx.save(update_fields=['amount'])

        # Jalankan rekonsiliasi ulang
        recon_post = run_financial_reconciliation()
        # Selisih wajib terdeteksi
        self.assertFalse(recon_post['summary']['global_balanced'])
        self.assertNotEqual(recon_post['summary']['discrepancy'], 0)
        self.assertGreater(recon_post['summary']['mismatched_rentals_count'], 0)

    def test_staff_cannot_process_own_withdrawal(self):
        """Uji staf dilarang menyetujui atau memproses permintaan penarikan dananya sendiri."""
        # Berikan saldo dompet ke staf_admin
        create_wallet_transaction(
            user=self.staff_admin,
            kind=WalletTransaction.Kind.KREDIT_PAYOUT,
            amount=50000,
            note="Saldo staf"
        )
        w = request_withdrawal(
            user=self.staff_admin,
            amount=30000,
            method=WithdrawalRequest.Method.BCA,
            account_name="Staf Admin",
            account_number="555000111"
        )
        
        # Percobaan proses oleh diri sendiri harus ditolak
        with self.assertRaises(ValueError) as cm:
            process_withdrawal(
                withdrawal=w,
                new_status=WithdrawalRequest.Status.DIPROSES,
                admin_user=self.staff_admin,
                admin_note="Proses sendiri"
            )
        self.assertIn("Staf dilarang memproses penarikan dananya sendiri", str(cm.exception))

    def test_withdrawal_request_password_confirmation(self):
        """Uji form penarikan dana wajib konfirmasi kata sandi akun."""
        create_wallet_transaction(
            user=self.owner,
            kind=WalletTransaction.Kind.KREDIT_PAYOUT,
            amount=60000,
            note="Saldo test"
        )
        client = Client()
        client.force_login(self.owner)

        # 1. Kata sandi salah -> ditolak form error
        resp_wrong = client.post("/dompet/tarik/", {
            'amount': '30000',
            'method': 'BCA',
            'account_name': 'Budi Pemilik',
            'account_number': '12345678',
            'password': 'salah_password'
        })
        self.assertEqual(resp_wrong.status_code, 200)
        self.assertContains(resp_wrong, "Konfirmasi kata sandi akun salah")
        self.assertEqual(WithdrawalRequest.objects.filter(user=self.owner).count(), 0)

        # 2. Kata sandi benar -> berhasil redirect
        resp_correct = client.post("/dompet/tarik/", {
            'amount': '30000',
            'method': 'BCA',
            'account_name': 'Budi Pemilik',
            'account_number': '12345678',
            'password': 'password123'
        })
        self.assertEqual(resp_correct.status_code, 302)
        self.assertEqual(WithdrawalRequest.objects.filter(user=self.owner).count(), 1)


    def test_account_number_never_logged(self):
        """Uji nomor rekening tidak pernah bocor ke log aplikasi saat diakses staf."""
        raw_account = "998877665544"
        w = WithdrawalRequest(
            user=self.owner,
            amount=35000,
            method=WithdrawalRequest.Method.BRI,
            account_name="Budi",
        )
        w.set_account_number(raw_account)
        w.save()

        client = Client()
        client.force_login(self.staff_admin)

        with self.assertLogs(logger='apps.payments', level='INFO') as cm:
            resp = client.post(f"/admin/penarikan/{w.id}/lihat-rekening/", {'reason': 'Audit perbankan'})
            self.assertEqual(resp.status_code, 200)

        # Pastikan string raw_account tidak ada di log manapun
        for log_msg in cm.output:
            self.assertNotIn(raw_account, log_msg)

    def test_idempotent_backfill(self):
        """6. Uji migrasi data backfill idempoten jika dijalankan ulang."""
        rental = self._create_paid_rental(code='RNT-BF-01', rental_fee=60000, deposit=40000)
        settle_rental_funds(rental)

        tx_count_before = WalletTransaction.objects.count()
        
        import importlib
        migration_mod = importlib.import_module('apps.payments.migrations.0006_backfill_wallet_transactions')
        from django.apps import apps
        migration_mod.backfill_wallet_transactions(apps, None)

        tx_count_after = WalletTransaction.objects.count()
        # Karena settle_rental_funds sudah membuat WalletTransaction, backfill tidak boleh menduplikasi
        self.assertEqual(tx_count_before, tx_count_after)

