import os
import logging
from django.conf import settings
from django.core.management.base import BaseCommand
from apps.trust.models import TrustModelVersion
from apps.trust.services import clear_model_cache

logger = logging.getLogger(__name__)


def execute_rollback(version_string, user=None):
    """
    Eksekutor rollback model skor kepercayaan ke versi tertentu.
    Mengembalikan (success: bool, message: str).
    """
    version_obj = TrustModelVersion.objects.filter(version=version_string).first()

    # Verifikasi apakah artefak fisiknya ada
    version_dir = os.path.join(settings.BASE_DIR, 'ml', 'artifacts', 'versions', version_string)
    artifact_path = os.path.join(version_dir, 'trust_model.joblib')
    default_artifact = os.path.join(settings.BASE_DIR, 'ml', 'artifacts', 'trust_model.joblib')

    has_physical_artifact = os.path.exists(artifact_path) or (
        version_string == 'v1.0-logreg-calibrated' and os.path.exists(default_artifact)
    )

    if not version_obj and not has_physical_artifact:
        return False, f"Versi model '{version_string}' tidak ditemukan di database maupun folder artefak."

    # Nonaktifkan semua model aktif
    TrustModelVersion.objects.filter(is_active=True).update(is_active=False)

    actor_info = f" oleh {user.username}" if user else ""
    note_msg = f"Rollback ke versi ini{actor_info}."

    if version_obj:
        version_obj.is_active = True
        version_obj.notes = (version_obj.notes or '') + f" [{note_msg}]"
        version_obj.save(update_fields=['is_active', 'notes'])
    else:
        # Jika belum ada di DB tapi ada artefak fisiknya (misal versi awal)
        version_obj = TrustModelVersion.objects.create(
            version=version_string,
            is_active=True,
            notes=f"Dibuat via rollback{actor_info}."
        )

    # Bersihkan cache in-memory agar pemanggilan berikutnya langsung membaca artefak baru
    clear_model_cache()
    logger.info(f"Model ML skor kepercayaan berhasil di-rollback ke versi: {version_string}")

    return True, f"Model aktif berhasil dikembalikan (rollback) ke versi '{version_string}'."


class Command(BaseCommand):
    help = "Mengembalikan model skor kepercayaan ke versi tertentu jika ditemukan anomali performa"

    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        for action in list(parser._actions):
            if '--version' in action.option_strings:
                parser._actions.remove(action)
                for opt in action.option_strings:
                    parser._option_string_actions.pop(opt, None)
        parser.add_argument(
            '--version', type=str, required=True,
            help='Nama versi model yang ingin diaktifkan kembali (contoh: v1.0-logreg-calibrated)'
        )
        return parser

    def handle(self, *args, **options):
        target_version = options['version']
        self.stdout.write(self.style.NOTICE(f"Mencoba melakukan rollback model ke versi '{target_version}'..."))

        success, msg = execute_rollback(target_version)
        if success:
            self.stdout.write(self.style.SUCCESS(f"[SUKSES] {msg}"))
        else:
            self.stdout.write(self.style.ERROR(f"[GAGAL] {msg}"))
