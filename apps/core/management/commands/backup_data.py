import os
import sys
import shutil
import tarfile
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Membuat cadangan data lengkap KampusRent: dump database PostgreSQL "
        "dan arsip media (tanpa mengekspos kredensial rahasia)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='',
            help="Direktori tujuan penyimpanan backup (bawaan: <BASE_DIR>/backups)."
        )
        parser.add_argument(
            '--skip-media',
            action='store_true',
            help="Hanya mencadangkan database tanpa mengarsipkan berkas media."
        )

    def handle(self, *args, **options):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_dir = Path(settings.BASE_DIR)
        
        output_dir = Path(options['output_dir']) if options['output_dir'] else base_dir / 'backups'
        output_dir.mkdir(parents=True, exist_ok=True)

        self.stdout.write(self.style.NOTICE(f"=== Memulai Proses Pencadangan Data KampusRent ({timestamp}) ==="))

        # 1. Pencadangan Database
        db_conf = settings.DATABASES['default']
        db_engine = db_conf.get('ENGINE', '')
        db_backup_path = output_dir / f"kampusrent_db_{timestamp}.sql"

        if 'postgresql' in db_engine:
            db_name = db_conf.get('NAME')
            db_user = db_conf.get('USER')
            db_password = db_conf.get('PASSWORD')
            db_host = db_conf.get('HOST', '127.0.0.1')
            db_port = str(db_conf.get('PORT', '5432'))

            # Gunakan lingkungan aman PGPASSWORD tanpa mencetak di commandline
            env = os.environ.copy()
            if db_password:
                env['PGPASSWORD'] = str(db_password)

            # Cari biner pg_dump di PATH atau lokasi PostgreSQL standar Windows
            pg_dump_bin = shutil.which('pg_dump')
            if not pg_dump_bin and sys.platform.startswith('win'):
                pg_root = Path("C:/Program Files/PostgreSQL")
                if pg_root.exists():
                    for version_dir in sorted(pg_root.glob("*/bin/pg_dump.exe"), reverse=True):
                        pg_dump_bin = str(version_dir)
                        break

            if not pg_dump_bin:
                pg_dump_bin = 'pg_dump'

            cmd = [
                pg_dump_bin,
                '-h', db_host,
                '-p', db_port,
                '-U', db_user,
                '-d', db_name,
                '-f', str(db_backup_path),
            ]

            self.stdout.write(f"Mencadangkan database PostgreSQL '{db_name}' dari host {db_host}:{db_port}...")
            try:
                subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
                size_bytes = db_backup_path.stat().st_size
                self.stdout.write(self.style.SUCCESS(
                    f"[OK] Database berhasil dicadangkan: {db_backup_path.name} ({size_bytes:,} bytes)"
                ))
            except Exception as err:
                self.stderr.write(self.style.ERROR(
                    f"Gagal mencadangkan database via pg_dump: {err}\n"
                    f"Pastikan pg_dump terinstal dan dapat diakses."
                ))
        else:
            # SQLite fallback
            db_name = db_conf.get('NAME')
            if db_name and Path(db_name).exists():
                sqlite_backup = output_dir / f"db_backup_{timestamp}.sqlite3"
                shutil.copy2(db_name, sqlite_backup)
                self.stdout.write(self.style.SUCCESS(
                    f"[OK] SQLite database dicadangkan: {sqlite_backup.name}"
                ))

        # 2. Pencadangan Berkas Media
        if not options['skip_media']:
            media_archive_path = output_dir / f"kampusrent_media_{timestamp}.tar.gz"
            self.stdout.write("Mengarsipkan berkas media publik dan privat...")

            media_dirs_to_backup = []
            if hasattr(settings, 'MEDIA_ROOT') and Path(settings.MEDIA_ROOT).exists():
                media_dirs_to_backup.append(('media', Path(settings.MEDIA_ROOT)))
            if hasattr(settings, 'PRIVATE_MEDIA_ROOT') and Path(settings.PRIVATE_MEDIA_ROOT).exists():
                media_dirs_to_backup.append(('private_media', Path(settings.PRIVATE_MEDIA_ROOT)))

            if media_dirs_to_backup:
                with tarfile.open(media_archive_path, "w:gz") as tar:
                    for arcname, folder in media_dirs_to_backup:
                        tar.add(folder, arcname=arcname)
                
                size_bytes = media_archive_path.stat().st_size
                self.stdout.write(self.style.SUCCESS(
                    f"[OK] Media berhasil diarsipkan: {media_archive_path.name} ({size_bytes:,} bytes)"
                ))

            else:
                self.stdout.write(self.style.WARNING("Direktori media kosong atau belum dibuat."))

        self.stdout.write(self.style.SUCCESS(
            f"\n=== Pencadangan Selesai! Seluruh berkas tersimpan di: {output_dir} ==="
        ))
        self.stdout.write(
            "Untuk memulihkan database:\n"
            f"  pg_restore -h 127.0.0.1 -U <user> -d <database> --clean {db_backup_path}\n"
            "  (atau jika plain SQL: psql -h 127.0.0.1 -U <user> -d <database> -f <file.sql>)\n"
        )
