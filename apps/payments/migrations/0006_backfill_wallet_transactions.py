from django.db import migrations
from collections import defaultdict

def backfill_wallet_transactions(apps, schema_editor):
    Rental = apps.get_model('rentals', 'Rental')
    LedgerEntry = apps.get_model('payments', 'LedgerEntry')
    WalletTransaction = apps.get_model('payments', 'WalletTransaction')

    completed_rentals = Rental.objects.filter(status='selesai').select_related('owner', 'renter')
    
    transactions_to_create = []
    user_totals = defaultdict(int)

    for rental in completed_rentals:
        # 1. Payout pokok pemilik
        payout_entries = LedgerEntry.objects.filter(rental=rental, kind='keluar_payout_pemilik')
        for entry in payout_entries:
            if not WalletTransaction.objects.filter(rental=rental, user=rental.owner, kind='kredit_payout').exists():
                transactions_to_create.append(WalletTransaction(
                    user=rental.owner,
                    rental=rental,
                    kind='kredit_payout',
                    amount=entry.amount,
                    source='backfill',
                    note=f"Pencairan pokok sewa ke dompet pemilik ({rental.code})"
                ))
                user_totals[rental.owner.username] += entry.amount

        # 2. Denda keterlambatan atau ganti rugi kerusakan ke pemilik
        penalty_entries = LedgerEntry.objects.filter(
            rental=rental,
            kind__in=['keluar_denda_ke_pemilik', 'keluar_deposit_ke_pemilik']
        )
        total_penalty = sum(e.amount for e in penalty_entries)
        if total_penalty > 0:
            if not WalletTransaction.objects.filter(rental=rental, user=rental.owner, kind='kredit_denda_atau_potongan').exists():
                transactions_to_create.append(WalletTransaction(
                    user=rental.owner,
                    rental=rental,
                    kind='kredit_denda_atau_potongan',
                    amount=total_penalty,
                    source='backfill',
                    note=f"Denda atau potongan deposit diteruskan ke pemilik ({rental.code})"
                ))
                user_totals[rental.owner.username] += total_penalty

        # 3. Pengembalian sisa deposit jaminan ke penyewa
        refund_entries = LedgerEntry.objects.filter(rental=rental, kind='keluar_deposit_dikembalikan')
        for entry in refund_entries:
            if entry.amount > 0:
                if not WalletTransaction.objects.filter(rental=rental, user=rental.renter, kind='kredit_refund_deposit').exists():
                    transactions_to_create.append(WalletTransaction(
                        user=rental.renter,
                        rental=rental,
                        kind='kredit_refund_deposit',
                        amount=entry.amount,
                        source='backfill',
                        note=f"Pengembalian deposit jaminan sewa ({rental.code})"
                    ))
                    user_totals[rental.renter.username] += entry.amount

        # 4. Klaim dana proteksi (bila ada)
        claim_entries = LedgerEntry.objects.filter(rental=rental, kind='keluar_kompensasi_pemilik')
        for entry in claim_entries:
            if entry.amount > 0:
                if not WalletTransaction.objects.filter(rental=rental, user=rental.owner, kind='kredit_klaim_proteksi').exists():
                    transactions_to_create.append(WalletTransaction(
                        user=rental.owner,
                        rental=rental,
                        kind='kredit_klaim_proteksi',
                        amount=entry.amount,
                        source='backfill',
                        note=f"Kompensasi cadangan Dana Gotong Royong ({rental.code})"
                    ))
                    user_totals[rental.owner.username] += entry.amount

    # LAPORKAN total saldo hasil backfill per pengguna sebelum menyimpan
    print("\n" + "="*70)
    print("=== [MIGRASI DATA] LAPORAN TOTAL SALDO HASIL BACKFILL PER PENGGUNA ===")
    print("="*70)
    if user_totals:
        for username in sorted(user_totals.keys()):
            print(f"  * Pengguna '{username}': Rp{user_totals[username]:,}")
        print("-" * 70)
        print(f"  TOTAL KESELURUHAN HASIL BACKFILL: Rp{sum(user_totals.values()):,} ({len(transactions_to_create)} transaksi)")
    else:
        print("  Tidak ada transaksi sewa selesai yang memerlukan backfill.")
    print("="*70 + "\n")

    if transactions_to_create:
        WalletTransaction.objects.bulk_create(transactions_to_create)


def reverse_backfill(apps, schema_editor):
    WalletTransaction = apps.get_model('payments', 'WalletTransaction')
    WalletTransaction.objects.filter(source='backfill').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0005_add_wallet_and_withdrawals'),
    ]

    operations = [
        migrations.RunPython(backfill_wallet_transactions, reverse_backfill),
    ]
