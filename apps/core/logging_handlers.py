import os
from logging.handlers import RotatingFileHandler


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    RotatingFileHandler yang toleran terhadap file-locking di Windows.

    Pada Windows saat menjalankan `python manage.py runserver` (StatReloader),
    terdapat 2 proses (watcher dan worker) yang sama-sama membuka file log.
    Jika ukuran file mencapai maxBytes, os.rename() pada doRollover() dapat
    menghasilkan PermissionError [WinError 32].

    Handler ini menangkap exception tersebut, memastikan stream tetap terbuka
    untuk penulisan log berikutnya, dan mencegah crash/error stack trace di konsol.
    """

    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError):
            if self.stream:
                try:
                    self.stream.close()
                except Exception:
                    pass
            self.stream = self._open()
