from django.core.management.base import BaseCommand
from apps.payments.reconciliation import run_financial_reconciliation


class Command(BaseCommand):
    help = "Melakukan audit dan rekonsiliasi keuangan platform KampusRent."

    def handle(self, *args, **options):
        self.stdout.write("=== Memulai Rekonsiliasi Keuangan KampusRent ===\n")
        data = run_financial_reconciliation()

        self.stdout.write(f"1. Total Dana Pembayaran Masuk (Settlement) : Rp{data['total_payment_settled']:,}")
        self.stdout.write(f"   (Buku Besar Masuk Tercatat                : Rp{data['ledger_masuk_aggr']:,})")
        self.stdout.write(f"2. Total Dana Ditahan di Escrow Platform     : Rp{data['total_escrow_held']:,}")
        self.stdout.write(f"   - Deposit Jaminan Ditahan                 : Rp{data['escrow_deposit_held']:,}")
        self.stdout.write(f"   - Sewa Pokok Berjalan                     : Rp{data['escrow_rent_held']:,}")
        self.stdout.write(f"3. Total Saldo Dompet Seluruh Pengguna       : Rp{data['total_user_wallets']:,}")
        self.stdout.write(f"4. Permintaan Penarikan Dana Aktif (Pending) : Rp{data['pending_withdrawals']:,}")
        self.stdout.write(f"   (Penarikan Berhasil Selesai Ditransfer    : Rp{data['completed_withdrawals']:,})")
        self.stdout.write(f"5. Akumulasi Pendapatan Komisi Platform      : Rp{data['total_commission']:,}")
        self.stdout.write(f"6. Saldo Cadangan Dana Gotong Royong        : Rp{data['total_protection_fund']:,}\n")

        self.stdout.write("-" * 65)
        if data['is_global_balanced']:
            self.stdout.write(self.style.SUCCESS("[SEIMBANG] Seluruh pembukuan, saldo dompet, escrow, dan penarikan konsisten."))
        else:
            self.stdout.write(self.style.ERROR(f"[SELISIH] Ditemukan ketidakseimbangan! Selisih global: Rp{data['global_diff']:,}"))
            self.stdout.write(self.style.WARNING(f"Jumlah sewa bermasalah: {data['per_rental_mismatches']}"))

        self.stdout.write("-" * 65)
        self.stdout.write(f"Jumlah transaksi sewa yang diperiksa: {len(data['rentals_data'])}\n")
