import random
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction, models

from apps.rentals.models import Rental
from apps.payments.models import Payment, LedgerEntry
from apps.core.models import Notification
from apps.chat.models import Message

# Karakter aman: tanpa karakter yang mudah tertukar (hindari 0, O, 1, I, L)
SAFE_CHARS = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'


def generate_safe_rental_code(existing_codes):
    """Menghasilkan kode unik KR-XXXXXX (6 karakter aman) tanpa karakter yang mudah tertukar."""
    while True:
        code = 'KR-' + ''.join(random.choices(SAFE_CHARS, k=6))
        if code not in existing_codes and not Rental.objects.filter(code=code).exists():
            existing_codes.add(code)
            return code


class Command(BaseCommand):
    help = (
        "Mengubah kode sewa berawalan 'KR-DEMO' menjadi kode acak berformat KR-XXXXXX "
        "(6 karakter aman tanpa karakter tertukar) secara atomik, menjaga konsistensi "
        "seluruh relasi, URL, order_id pembayaran, dan buku besar. "
        "Bawaan: DRY-RUN. Gunakan --apply untuk mengeksekusi setelah cadangan dibuat."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help="Eksekusi perubahan kode sewa demo dalam satu transaksi atomik setelah pg_dump."
        )

    def handle(self, *args, **options):
        apply_mode = options.get('apply', False)

        # Cari semua sewa yang memiliki awalan KR-DEMO atau memuat kata DEMO
        demo_rentals = list(
            Rental.objects.filter(
                models.Q(code__startswith='KR-DEMO') | models.Q(code__icontains='DEMO')
            ).select_related('item', 'renter', 'owner').order_by('id')
        )

        count = len(demo_rentals)

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Tidak ada kode sewa berawalan KR-DEMO atau memuat kata DEMO."))
            return

        existing_codes = set(Rental.objects.values_list('code', flat=True))
        code_plan = []
        for r in demo_rentals:
            new_code = generate_safe_rental_code(existing_codes)
            code_plan.append((r, r.code, new_code))

        if not apply_mode:
            self.stdout.write(self.style.NOTICE(
                f"=== DRY-RUN: Rencana Pengubahan Kode Sewa Demo ({count} sewa ditemukan) ==="
            ))
            self.stdout.write(
                f"{'ID':<6} | {'Kode Lama':<14} | {'Kode Baru':<12} | {'Barang':<28} | {'Status':<18} | {'Pembayaran'}"
            )
            self.stdout.write("-" * 95)
            for r, old_code, new_code in code_plan:
                p_count = r.payments.count()
                self.stdout.write(
                    f"{r.id:<6} | {old_code:<14} | {new_code:<12} | {r.item.title[:26]:<28} | {r.status[:16]:<18} | {p_count} pembayaran"
                )
            self.stdout.write("-" * 95)
            self.stdout.write(self.style.WARNING(
                f"[DRY-RUN] Ditemukan {count} sewa dengan kode DEMO.\n"
                "Semua order_id pembayaran, entri buku besar, dan notifikasi terkait akan diselaraskan.\n"
                "PERINGATAN: Tidak ada data yang diubah dalam mode DRY-RUN.\n"
                "Jalankan dengan flag --apply untuk mengeksekusi setelah cadangan dibuat."
            ))
            return

        # MODE --APPLY
        self.stdout.write(self.style.WARNING("=== MENJALANKAN MODE --APPLY ==="))
        # 1. Buat cadangan database pg_dump
        self.stdout.write("[1/3] Menjalankan pencadangan basis data PostgreSQL (pg_dump)...")
        call_command('backup_data', skip_media=True)

        # 2. Eksekusi perubahan atomik
        self.stdout.write(f"[2/3] Memperbarui {count} kode sewa dalam satu transaksi basis data...")
        with transaction.atomic():
            updated_rentals = 0
            updated_payments = 0
            updated_ledgers = 0
            updated_notifs = 0
            updated_messages = 0

            for r, old_code, new_code in code_plan:
                # Update kode sewa
                r.code = new_code
                r.save(update_fields=['code'])
                updated_rentals += 1

                # Update Payment order_id
                for p in r.payments.all():
                    if old_code in p.order_id:
                        p.order_id = p.order_id.replace(old_code, new_code)
                        p.save(update_fields=['order_id'])
                        updated_payments += 1

                # Update LedgerEntry notes
                for l in r.ledger_entries.all():
                    if l.note and old_code in l.note:
                        l.note = l.note.replace(old_code, new_code)
                        l.save(update_fields=['note'])
                        updated_ledgers += 1

                # Update Notification (url dan message)
                related_notifs = Notification.objects.filter(
                    models.Q(url__icontains=old_code) |
                    models.Q(message__icontains=old_code) |
                    models.Q(title__icontains=old_code)
                )
                for n in related_notifs:
                    changed = False
                    if n.url and old_code in n.url:
                        n.url = n.url.replace(old_code, new_code)
                        changed = True
                    if n.message and old_code in n.message:
                        n.message = n.message.replace(old_code, new_code)
                        changed = True
                    if n.title and old_code in n.title:
                        n.title = n.title.replace(old_code, new_code)
                        changed = True
                    if changed:
                        n.save(update_fields=['url', 'message', 'title'])
                        updated_notifs += 1

                # Update Chat Message jika ada referensi kode
                related_msgs = Message.objects.filter(body__icontains=old_code)
                for m in related_msgs:
                    m.body = m.body.replace(old_code, new_code)
                    m.save(update_fields=['body'])
                    updated_messages += 1

                self.stdout.write(f"  [OK] {old_code} -> {new_code}")

        self.stdout.write(self.style.SUCCESS(
            f"[3/3] Selesai! Berhasil mengubah {updated_rentals} kode sewa, "
            f"{updated_payments} order_id pembayaran, {updated_ledgers} catatan buku besar, "
            f"{updated_notifs} notifikasi, dan {updated_messages} pesan obrolan secara konsisten."
        ))
