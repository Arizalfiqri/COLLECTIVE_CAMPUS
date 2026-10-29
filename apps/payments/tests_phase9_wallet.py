from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings

from apps.catalog.models import Item, Category
from apps.rentals.models import Rental
from apps.payments.models import WalletTransaction, WithdrawalRequest
from apps.payments.services import get_user_wallet_balance

User = get_user_model()


class Phase9WalletTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='user_wallet',
            email='wallet@kampus.ac.id',
            password='Password123!',
            full_name='User Dompet'
        )
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.client.force_login(self.user)

    def test_wallet_label_sentence_case_and_no_uppercase_class(self):
        """Label 'Saldo dompet aktif' sentence case dan tidak menggunakan kelas uppercase."""
        response = self.client.get(reverse('payments:wallet'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('Saldo dompet aktif', content)
        # Pastikan tidak ada class 'uppercase' pada span saldo aktif
        self.assertNotIn('uppercase tracking-wider block mb-1', content)

    def test_withdrawal_chip_only_when_balance_eligible(self):
        """Chip 'Dapat ditarik' hanya muncul jika saldo >= batas minimal penarikan."""
        min_w = getattr(settings, 'WITHDRAWAL_MIN', 20000)

        # 1. Saldo 0: Chip TIDAK boleh muncul
        response = self.client.get(reverse('payments:wallet'))
        content = response.content.decode('utf-8')
        self.assertNotIn('Dapat ditarik', content)

        # 2. Saldo kurang dari minimal (Rp10.000): Chip TIDAK boleh muncul
        WalletTransaction.objects.create(
            user=self.user,
            kind=WalletTransaction.Kind.KREDIT_PAYOUT,
            amount=10000
        )
        response = self.client.get(reverse('payments:wallet'))
        content = response.content.decode('utf-8')
        self.assertNotIn('Dapat ditarik', content)

        # 3. Saldo >= minimal penarikan (tambah Rp20.000 -> Rp30.000): Chip HARUS muncul
        WalletTransaction.objects.create(
            user=self.user,
            kind=WalletTransaction.Kind.KREDIT_PAYOUT,
            amount=20000
        )
        response = self.client.get(reverse('payments:wallet'))
        content = response.content.decode('utf-8')
        self.assertIn('Dapat ditarik', content)

    def test_fee_description_reads_from_settings(self):
        """Deskripsi potongan komisi sewa dan jual membaca nilai dinamis dari settings."""
        response = self.client.get(reverse('payments:wallet'))
        content = response.content.decode('utf-8')

        sewa_pct = getattr(settings, 'PLATFORM_COMMISSION_PERCENT', 8)
        sale_pct = getattr(settings, 'SALE_COMMISSION_PERCENT', 5)

        self.assertIn(f'komisi platform {sewa_pct}%', content)
        self.assertIn(f'komisi {sale_pct}%', content)

    def test_no_pada_versi_ini_wording(self):
        """Frasa 'pada versi ini' telah dihapus dari catatan pencairan dana."""
        response = self.client.get(reverse('payments:wallet'))
        content = response.content.decode('utf-8')

        self.assertNotIn('pada versi ini', content)
        self.assertIn('Pencairan dana diproses manual oleh admin', content)

    def test_mutation_labels_sentence_case(self):
        """Label mutasi transaksi menggunakan kalimat sentence case sesuai spesifikasi."""
        # Buat transaksi dari berbagai jenis
        t_payout = WalletTransaction.objects.create(
            user=self.user,
            kind=WalletTransaction.Kind.KREDIT_PAYOUT,
            amount=50000
        )
        t_penjualan = WalletTransaction.objects.create(
            user=self.user,
            kind=WalletTransaction.Kind.KREDIT_PENJUALAN,
            amount=75000
        )
        t_refund_jual = WalletTransaction.objects.create(
            user=self.user,
            kind=WalletTransaction.Kind.KREDIT_REFUND_PENJUALAN,
            amount=25000
        )
        t_denda = WalletTransaction.objects.create(
            user=self.user,
            kind=WalletTransaction.Kind.KREDIT_DENDA_ATAU_POTONGAN,
            amount=15000
        )
        t_penarikan = WalletTransaction.objects.create(
            user=self.user,
            kind=WalletTransaction.Kind.DEBIT_PENARIKAN,
            amount=30000
        )
        t_deposit = WalletTransaction.objects.create(
            user=self.user,
            kind=WalletTransaction.Kind.KREDIT_REFUND_DEPOSIT,
            amount=100000
        )

        # Verifikasi properti model
        self.assertEqual(t_payout.label_display, 'Pendapatan sewa')
        self.assertEqual(t_penjualan.label_display, 'Hasil penjualan')
        self.assertEqual(t_refund_jual.label_display, 'Pengembalian dana')
        self.assertEqual(t_denda.label_display, 'Denda atau ganti rugi')
        self.assertEqual(t_penarikan.label_display, 'Penarikan dana')
        self.assertEqual(t_deposit.label_display, 'Pengembalian deposit')

        # Verifikasi tampilan template
        response = self.client.get(reverse('payments:wallet'))
        content = response.content.decode('utf-8')

        self.assertIn('Pendapatan sewa', content)
        self.assertIn('Hasil penjualan', content)
        self.assertIn('Pengembalian dana', content)
        self.assertIn('Denda atau ganti rugi', content)
        self.assertIn('Penarikan dana', content)
        self.assertIn('Pengembalian deposit', content)

    def test_nominal_column_present_and_visible(self):
        """Kolom nominal ada pada header tabel dan terdapat tata letak kartu mobile agar selalu terlihat."""
        WalletTransaction.objects.create(
            user=self.user,
            kind=WalletTransaction.Kind.KREDIT_PAYOUT,
            amount=50000
        )
        response = self.client.get(reverse('payments:wallet'))
        content = response.content.decode('utf-8')

        # Header tabel nominal
        self.assertIn('Nominal', content)
        # Nilai nominal kredit
        self.assertIn('+Rp50.000', content)
        # Layout kartu responsif untuk mobile
        self.assertIn('sm:hidden divide-y divide-line/70', content)
