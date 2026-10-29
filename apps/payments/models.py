from django.db import models
from django.conf import settings


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SETTLEMENT = 'settlement', 'Settlement'
        EXPIRE = 'expire', 'Expire'
        CANCEL = 'cancel', 'Cancel'
        DENY = 'deny', 'Deny'

    rental = models.ForeignKey(
        'rentals.Rental', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='payments', verbose_name="Sewa"
    )
    sale_order = models.ForeignKey(
        'sales.SaleOrder', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='payments', verbose_name="Pesanan Jual Beli"
    )
    order_id = models.CharField(max_length=100, unique=True, verbose_name="Order ID", db_index=True)
    gross_amount = models.PositiveIntegerField(verbose_name="Jumlah Bruto (Rp)")
    snap_token = models.CharField(max_length=255, blank=True, default='', verbose_name="Snap Token")
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, verbose_name="Status Pembayaran"
    )
    payment_type = models.CharField(max_length=50, blank=True, default='', verbose_name="Metode Pembayaran")
    transaction_id = models.CharField(max_length=100, blank=True, default='', verbose_name="Transaction ID")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Bayar")
    raw_response = models.JSONField(default=dict, blank=True, verbose_name="Response Mentah")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Pembayaran"
        verbose_name_plural = "Pembayaran"
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=(
                    (models.Q(rental__isnull=False) & models.Q(sale_order__isnull=True)) |
                    (models.Q(rental__isnull=True) & models.Q(sale_order__isnull=False))
                ),
                name='payment_rental_xor_sale_order'
            )
        ]

    def __str__(self):
        return f"Payment {self.order_id} – {self.get_status_display()}"


class DepositHold(models.Model):
    class Status(models.TextChoices):
        DITAHAN = 'ditahan', 'Ditahan'
        DIRILIS = 'dirilis', 'Dirilis'
        DIPOTONG_SEBAGIAN = 'dipotong_sebagian', 'Dipotong Sebagian'
        DIPOTONG_PENUH = 'dipotong_penuh', 'Dipotong Penuh'

    rental = models.OneToOneField(
        'rentals.Rental', on_delete=models.CASCADE,
        related_name='deposit_hold', verbose_name="Sewa"
    )
    amount = models.PositiveIntegerField(verbose_name="Jumlah Deposit (Rp)")
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.DITAHAN, verbose_name="Status Deposit"
    )
    released_amount = models.PositiveIntegerField(default=0, verbose_name="Jumlah Dirilis (Rp)")
    deducted_amount = models.PositiveIntegerField(default=0, verbose_name="Jumlah Dipotong (Rp)")
    reason = models.TextField(blank=True, default='', verbose_name="Alasan")
    released_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Rilis")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Deposit ditahan"
        verbose_name_plural = "Deposit ditahan"

    def __str__(self):
        return f"Deposit {self.rental.code} – {self.get_status_display()}"


class Payout(models.Model):
    class Status(models.TextChoices):
        MENUNGGU = 'menunggu', 'Menunggu'
        DICAIRKAN_SIMULASI = 'dicairkan_simulasi', 'Dicairkan (Simulasi)'

    rental = models.OneToOneField(
        'rentals.Rental', on_delete=models.CASCADE,
        related_name='payout', verbose_name="Sewa"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='payouts', verbose_name="Pemilik"
    )
    gross_rent = models.PositiveIntegerField(verbose_name="Sewa Kotor (Rp)")
    commission = models.PositiveIntegerField(verbose_name="Komisi Platform (Rp)")
    net_amount = models.PositiveIntegerField(verbose_name="Jumlah Bersih (Rp)")
    status = models.CharField(
        max_length=30, choices=Status.choices,
        default=Status.MENUNGGU, verbose_name="Status Payout"
    )
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Cairkan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")

    class Meta:
        verbose_name = "Payout"
        verbose_name_plural = "Payout"

    def __str__(self):
        return f"Payout {self.rental.code} – Rp{self.net_amount:,}"


class LedgerEntry(models.Model):
    class Kind(models.TextChoices):
        MASUK_SEWA = 'masuk_sewa', 'Masuk Sewa'
        MASUK_DEPOSIT = 'masuk_deposit', 'Masuk Deposit'
        MASUK_PROTEKSI = 'masuk_proteksi', 'Masuk Proteksi'
        MASUK_DANA_PROTEKSI = 'masuk_dana_proteksi', 'Masuk Dana Proteksi'
        MASUK_KLAIM_PROTEKSI = 'masuk_klaim_proteksi', 'Masuk Klaim Proteksi'
        MASUK_PENJUALAN = 'masuk_penjualan', 'Masuk Penjualan'
        KELUAR_KOMISI_PLATFORM = 'keluar_komisi_platform', 'Keluar Komisi Platform'
        KELUAR_KOMISI_PENJUALAN = 'keluar_komisi_penjualan', 'Keluar Komisi Penjualan'
        KELUAR_PAYOUT_PEMILIK = 'keluar_payout_pemilik', 'Keluar Payout Pemilik'
        KELUAR_PAYOUT_PENJUAL = 'keluar_payout_penjual', 'Keluar Payout Penjual'
        KELUAR_DEPOSIT_DIKEMBALIKAN = 'keluar_deposit_dikembalikan', 'Keluar Deposit Dikembalikan'
        KELUAR_DEPOSIT_KE_PEMILIK = 'keluar_deposit_ke_pemilik', 'Keluar Deposit ke Pemilik'
        KELUAR_PROTEKSI_PLATFORM = 'keluar_proteksi_platform', 'Keluar Proteksi Platform'
        KELUAR_KE_DANA_PROTEKSI = 'keluar_ke_dana_proteksi', 'Keluar ke Dana Proteksi'
        KELUAR_DENDA_KE_PEMILIK = 'keluar_denda_ke_pemilik', 'Keluar Denda ke Pemilik'
        KELUAR_REFUND_PENYEWA = 'keluar_refund_penyewa', 'Keluar Refund Penyewa'
        KELUAR_REFUND_SEWA = 'keluar_refund_sewa', 'Keluar Refund Sewa'
        KELUAR_REFUND_DEPOSIT = 'keluar_refund_deposit', 'Keluar Refund Deposit'
        KELUAR_REFUND_PROTEKSI = 'keluar_refund_proteksi', 'Keluar Refund Proteksi'
        KELUAR_KOMPENSASI_PEMILIK = 'keluar_kompensasi_pemilik', 'Keluar Kompensasi Pemilik'

    rental = models.ForeignKey(
        'rentals.Rental', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='ledger_entries', verbose_name="Sewa"
    )
    sale_order = models.ForeignKey(
        'sales.SaleOrder', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='ledger_entries', verbose_name="Pesanan Jual Beli"
    )
    kind = models.CharField(max_length=40, choices=Kind.choices, verbose_name="Jenis")
    amount = models.PositiveIntegerField(verbose_name="Jumlah (Rp)")
    note = models.TextField(blank=True, default='', verbose_name="Catatan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")

    class Meta:
        verbose_name = "Entri buku besar"
        verbose_name_plural = "Buku besar"
        ordering = ['created_at']
        constraints = [
            models.CheckConstraint(
                check=(
                    (models.Q(rental__isnull=False) & models.Q(sale_order__isnull=True)) |
                    (models.Q(rental__isnull=True) & models.Q(sale_order__isnull=False))
                ),
                name='ledger_rental_xor_sale_order'
            )
        ]

    def __str__(self):
        code = self.rental.code if self.rental else (self.sale_order.code if self.sale_order else '-')
        return f"{self.get_kind_display()} Rp{self.amount:,} – {code}"


class WalletTransaction(models.Model):
    class Kind(models.TextChoices):
        KREDIT_PAYOUT = 'kredit_payout', 'Kredit Payout'
        KREDIT_PENJUALAN = 'kredit_penjualan', 'Kredit Penjualan'
        KREDIT_REFUND_PENJUALAN = 'kredit_refund_penjualan', 'Kredit Refund Penjualan'
        KREDIT_REFUND_DEPOSIT = 'kredit_refund_deposit', 'Kredit Refund Deposit'
        KREDIT_DENDA_ATAU_POTONGAN = 'kredit_denda_atau_potongan', 'Kredit Denda atau Potongan'
        KREDIT_KLAIM_PROTEKSI = 'kredit_klaim_proteksi', 'Kredit Klaim Proteksi'
        KREDIT_TAGIHAN_TAMBAHAN = 'kredit_tagihan_tambahan', 'Kredit Pelunasan Tagihan Tambahan'
        DEBIT_PENARIKAN = 'debit_penarikan', 'Debit Penarikan'
        DEBIT_PENARIKAN_BATAL = 'debit_penarikan_batal', 'Debit Penarikan Batal'

    class Source(models.TextChoices):
        LIVE = 'live', 'Live'
        BACKFILL = 'backfill', 'Backfill'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='wallet_transactions', verbose_name="Pengguna"
    )
    rental = models.ForeignKey(
        'rentals.Rental', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='wallet_transactions', verbose_name="Sewa"
    )
    sale_order = models.ForeignKey(
        'sales.SaleOrder', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='wallet_transactions', verbose_name="Pesanan Jual Beli"
    )
    extra_charge = models.ForeignKey(
        'payments.ExtraCharge', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='wallet_transactions', verbose_name="Tagihan Tambahan"
    )
    kind = models.CharField(max_length=40, choices=Kind.choices, verbose_name="Jenis Transaksi")
    amount = models.PositiveIntegerField(verbose_name="Jumlah (Rp)")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.LIVE, verbose_name="Sumber")
    note = models.TextField(blank=True, default='', verbose_name="Catatan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")

    class Meta:
        verbose_name = "Transaksi Dompet"
        verbose_name_plural = "Transaksi Dompet"
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(rental__isnull=True) | models.Q(sale_order__isnull=True)
                ),
                name='wallet_tx_not_both_rental_and_sale_order'
            )
        ]

    @property
    def is_credit(self):
        return self.kind.startswith('kredit_')

    @property
    def label_display(self):
        mapping = {
            self.Kind.KREDIT_PAYOUT: 'Pendapatan sewa',
            self.Kind.KREDIT_PENJUALAN: 'Hasil penjualan',
            self.Kind.KREDIT_REFUND_PENJUALAN: 'Pengembalian dana',
            self.Kind.KREDIT_REFUND_DEPOSIT: 'Pengembalian deposit',
            self.Kind.KREDIT_DENDA_ATAU_POTONGAN: 'Denda atau ganti rugi',
            self.Kind.KREDIT_KLAIM_PROTEKSI: 'Santunan Dana Gotong Royong',
            self.Kind.KREDIT_TAGIHAN_TAMBAHAN: 'Pelunasan tagihan tambahan',
            self.Kind.DEBIT_PENARIKAN: 'Penarikan dana',
            self.Kind.DEBIT_PENARIKAN_BATAL: 'Pembatalan penarikan dana',
        }
        return mapping.get(self.kind, self.get_kind_display())

    def __str__(self):
        return f"{self.label_display} Rp{self.amount:,} – {self.user.username}"


class WithdrawalRequest(models.Model):
    class Method(models.TextChoices):
        DANA = 'DANA', 'DANA'
        SEABANK = 'SeaBank', 'SeaBank'
        MANDIRI = 'Mandiri', 'Mandiri'
        BCA = 'BCA', 'BCA'
        BRI = 'BRI', 'BRI'
        BNI = 'BNI', 'BNI'

    class Status(models.TextChoices):
        DIMINTA = 'diminta', 'Diminta'
        DIPROSES = 'diproses', 'Diproses'
        SELESAI = 'selesai', 'Selesai'
        DITOLAK = 'ditolak', 'Ditolak'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='withdrawals', verbose_name="Pengguna"
    )
    amount = models.PositiveIntegerField(verbose_name="Jumlah Penarikan (Rp)")
    method = models.CharField(max_length=30, choices=Method.choices, verbose_name="Metode Penarikan")
    account_name = models.CharField(max_length=150, verbose_name="Nama Pemilik Rekening")
    account_number = models.TextField(verbose_name="Nomor Rekening/Dompet (Terenkripsi)")
    masked_account_number = models.CharField(max_length=30, blank=True, default='', verbose_name="Nomor Terselubung")
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.DIMINTA, verbose_name="Status Penarikan"
    )
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name="Diminta pada")
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='processed_withdrawals', verbose_name="Diproses Oleh"
    )
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Diproses")
    admin_note = models.TextField(blank=True, default='', verbose_name="Catatan Admin")
    transfer_reference = models.CharField(max_length=100, blank=True, default='', verbose_name="Referensi Transfer")

    class Meta:
        verbose_name = "Permintaan Penarikan Dana"
        verbose_name_plural = "Permintaan Penarikan Dana"
        ordering = ['-requested_at']

    def __str__(self):
        return f"Penarikan Rp{self.amount:,} ({self.method}) – {self.user.username} [{self.get_status_display()}]"

    def set_account_number(self, plain_number: str):
        from .encryption import encrypt_account_number, mask_account_number
        self.account_number = encrypt_account_number(plain_number)
        self.masked_account_number = mask_account_number(plain_number)

    def get_decrypted_account_number(self) -> str:
        from .encryption import decrypt_account_number
        return decrypt_account_number(self.account_number)


class WithdrawalAccountAccessLog(models.Model):
    withdrawal = models.ForeignKey(
        WithdrawalRequest, on_delete=models.CASCADE,
        related_name='access_logs', verbose_name="Penarikan"
    )
    accessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        verbose_name="Diakses Oleh"
    )
    accessed_at = models.DateTimeField(auto_now_add=True, verbose_name="Waktu Akses")
    ip_address = models.CharField(max_length=50, blank=True, default='', verbose_name="Alamat IP")
    reason = models.TextField(blank=True, default='', verbose_name="Alasan Operasional Akses")

    class Meta:
        verbose_name = "Log Akses Rekening Penarikan"
        verbose_name_plural = "Log Akses Rekening Penarikan"
        ordering = ['-accessed_at']

    def __str__(self):
        return f"Akses rekening #{self.withdrawal_id} oleh {self.accessed_by.username} pada {self.accessed_at}"


class ExtraCharge(models.Model):
    class Type(models.TextChoices):
        KETERLAMBATAN = 'keterlambatan', 'Keterlambatan'
        KERUSAKAN = 'kerusakan', 'Kerusakan'
        KEHILANGAN = 'kehilangan', 'Kehilangan'

    ChargeType = Type

    class Status(models.TextChoices):
        TERUTANG = 'terutang', 'Terutang'
        LUNAS = 'lunas', 'Lunas'

    rental = models.ForeignKey(
        'rentals.Rental', on_delete=models.CASCADE,
        related_name='extra_charges', verbose_name="Sewa"
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='extra_charges_as_renter', verbose_name="Penyewa"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='extra_charges_as_owner', verbose_name="Pemilik"
    )
    charge_type = models.CharField(
        max_length=20, choices=Type.choices,
        verbose_name="Jenis Tagihan"
    )
    amount = models.PositiveIntegerField(
        verbose_name="Jumlah Tagihan (Rp)"
    )
    reason = models.TextField(
        verbose_name="Alasan Tagihan"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.TERUTANG, verbose_name="Status"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Dibuat pada"
    )
    paid_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Dilunasi pada"
    )
    settled_by = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name="Direferensikan Oleh / No. Referensi"
    )
    payment = models.ForeignKey(
        'payments.Payment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='extra_charges', verbose_name="Pembayaran Midtrans Terkait"
    )

    class Meta:
        verbose_name = "Tagihan Tambahan"
        verbose_name_plural = "Tagihan Tambahan"
        ordering = ['-created_at']

    def __str__(self):
        return f"Tagihan {self.get_charge_type_display()} Rp{self.amount:,} ({self.rental.code}) – {self.get_status_display()}"


