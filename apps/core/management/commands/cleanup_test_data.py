import re
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Campus, User
from apps.chat.models import Conversation, Message
from apps.payments.models import WalletTransaction, WithdrawalRequest
from apps.sales.models import SaleItem


class Command(BaseCommand):
    help = (
        "Memeriksa atau membersihkan data uji coba (SaleItem bertimestamp, pesan uji, "
        "WalletTransaction user_wallet, referensi transfer TRF-DANA-12345, kampus Universitas Test) "
        "serta mengusulkan normalisasi nama singkat kampus yang terpotong. "
        "Bawaan: DRY-RUN (tidak mengubah data apa pun)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Eksekusi pembersihan data secara permanen. Membutuhkan flag --backup-verified.',
        )
        parser.add_argument(
            '--backup-verified',
            action='store_true',
            default=False,
            help='Konfirmasi eksplisit bahwa berkas pg_dump cadangan database telah dibuat sebelum eksekusi.',
        )

    def handle(self, *args, **options):
        is_apply = options['apply']
        is_backup_verified = options['backup_verified']

        if is_apply and not is_backup_verified:
            raise CommandError(
                "Keamanan data: flag --apply wajib disertai flag --backup-verified untuk memastikan "
                "cadangan database (pg_dump) telah tersedia di direktori backups/ sebelum eksekusi."
            )

        mode_label = "EKSEKUSI (--apply)" if is_apply else "DRY-RUN (Simulasi Pemeriksaan — Tanpa Perubahan Data)"
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== PERINTAH CLEANUP_TEST_DATA: {mode_label} ===\n"))

        # 1. SaleItem bertimestamp (pola angka unix epoch di judul, misalnya 179285...)
        timestamp_sale_items = []
        for item in SaleItem.objects.all():
            if re.search(r'\b17\d{8}\b', item.title) or 'test' in item.title.lower():
                timestamp_sale_items.append(item)

        self.stdout.write(self.style.SUCCESS(f"[1] SaleItem Bertimestamp / Uji Coba: {len(timestamp_sale_items)} record ditemukan"))
        for it in timestamp_sale_items:
            self.stdout.write(f"    - ID #{it.id}: '{it.title}' (Pemilik: {it.owner.username}, Dibuat: {it.created_at.strftime('%Y-%m-%d %H:%M')})")

        # 2. Pesan Chat Uji Coba & Percakapan Uji
        test_message_keywords = ['woy', 'nyo', 'cihuy', 'ahuy', 'anak mana kao', 'tes@kampus.ac.id']
        test_messages = []
        for msg in Message.objects.all():
            body_lower = msg.body.lower().strip()
            if any(k in body_lower for k in test_message_keywords):
                test_messages.append(msg)

        self.stdout.write(self.style.SUCCESS(f"\n[2] Pesan Chat Uji Coba: {len(test_messages)} pesan ditemukan"))
        for m in test_messages:
            self.stdout.write(f"    - Pesan ID #{m.id} (Conv #{m.conversation_id}, Pengirim: {m.sender.username}): '{m.body}'")

        # 3. WalletTransaction akun dummy 'user_wallet'
        user_wallet_txs = list(WalletTransaction.objects.filter(user__username='user_wallet'))
        self.stdout.write(self.style.SUCCESS(f"\n[3] WalletTransaction Akun Uji 'user_wallet': {len(user_wallet_txs)} transaksi ditemukan"))
        for wt in user_wallet_txs:
            self.stdout.write(f"    - Transaksi ID #{wt.id}: {wt.get_kind_display()} Rp{wt.amount:,} (User: {wt.user.username})")

        # 4. WithdrawalRequest referensi transfer dummy 'TRF-DANA-12345'
        dummy_withdrawals = list(WithdrawalRequest.objects.filter(transfer_reference__icontains='TRF-DANA-12345'))
        self.stdout.write(self.style.SUCCESS(f"\n[4] Penarikan Referensi Dummy 'TRF-DANA-12345': {len(dummy_withdrawals)} record ditemukan"))
        for wr in dummy_withdrawals:
            self.stdout.write(f"    - Penarikan ID #{wr.id}: Rp{wr.amount:,} ke {wr.method} - Ref: '{wr.transfer_reference}' (User: {wr.user.username})")

        # 5. Kampus 'Universitas Test'
        test_campuses = list(Campus.objects.filter(name__icontains='Universitas Test'))
        self.stdout.write(self.style.SUCCESS(f"\n[5] Kampus Uji 'Universitas Test': {len(test_campuses)} record ditemukan"))
        for tc in test_campuses:
            self.stdout.write(f"    - Kampus ID #{tc.id}: '{tc.name}' (Nama singkat: '{tc.short_name}')")

        # 6. Usulan Normalisasi Nama Singkat Kampus yang Terpotong
        campus_proposals = {
            'Institut Teknologi Kampus': {'current': 'Institut T', 'proposed': 'ITK'},
            'Kampus Seni & Desain': {'current': 'Kampus Sen', 'proposed': 'KSD'},
            'Politeknik Kampus': {'current': 'Politeknik', 'proposed': 'POLKAM'},
            'Universitas Sinsar': {'current': 'Universita', 'proposed': 'UNISIN'},
        }
        self.stdout.write(self.style.SUCCESS("\n[6] Usulan Normalisasi Nama Singkat Kampus Terpotong (Inisial Kata Bermakna):"))
        for name, prop in campus_proposals.items():
            camp = Campus.objects.filter(name=name).first()
            current_val = camp.short_name if camp else prop['current']
            self.stdout.write(f"    - '{name}': '{current_val}' -> Usulan Baru: '{prop['proposed']}'")

        self.stdout.write("\n" + "=" * 65)

        # Jika mode DRY-RUN, berhenti di sini
        if not is_apply:
            self.stdout.write(self.style.WARNING(
                "\n[PERINGATAN] Mode saat ini adalah DRY-RUN bawaan.\n"
                "Tidak ada record yang dihapus atau diubah di database.\n"
                "Untuk mengeksekusi pembersihan permanen, jalankan:\n"
                "  python manage.py cleanup_test_data --apply --backup-verified\n"
            ))
            return

        # Eksekusi pembersihan HANYA jika --apply dan --backup-verified aktif
        self.stdout.write(self.style.NOTICE("\nMengeksekusi pembersihan data permanen..."))
        with transaction.atomic():
            # 1. Hapus SaleItem bertimestamp beserta fotonya
            count_sale = len(timestamp_sale_items)
            for it in timestamp_sale_items:
                it.delete()

            # 2. Hapus pesan chat uji coba
            count_msg = len(test_messages)
            for m in test_messages:
                m.delete()

            # 3. Hapus transaksi dompet user_wallet
            count_wt = len(user_wallet_txs)
            for wt in user_wallet_txs:
                wt.delete()

            # 4. Hapus referensi dummy penarikan
            count_wr = len(dummy_withdrawals)
            for wr in dummy_withdrawals:
                wr.delete()

            # 5. Hapus kampus uji Universitas Test (jika tidak ada profil terkait)
            count_tc = 0
            for tc in test_campuses:
                if not tc.student_profiles.exists():
                    tc.delete()
                    count_tc += 1

            # 6. Perbarui nama singkat kampus terpotong
            count_short = 0
            for name, prop in campus_proposals.items():
                camp = Campus.objects.filter(name=name).first()
                if camp:
                    camp.short_name = prop['proposed']
                    camp.save(update_fields=['short_name'])
                    count_short += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n[SUKSES] Pembersihan berhasil dieksekusi:\n"
            f"  - SaleItem dihapus: {count_sale}\n"
            f"  - Pesan uji dihapus: {count_msg}\n"
            f"  - Transaksi dompet uji dihapus: {count_wt}\n"
            f"  - Penarikan dummy dihapus: {count_wr}\n"
            f"  - Kampus uji dihapus: {count_tc}\n"
            f"  - Nama singkat kampus diperbarui: {count_short}\n"
        ))
