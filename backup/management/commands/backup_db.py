"""
Database backup command.

Usage:
    python manage.py backup_db
    python manage.py backup_db --output /path/to/backup.sql.gz
    python manage.py backup_db --keep 14

Creates a compressed SQL dump of the database.
"""
import os
import subprocess
import gzip
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Create a compressed database backup"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            help="Custom output path. Defaults to BACKUPS_DIR / db_backup_YYYY-MM-DD_HHMMSS.sql.gz",
        )
        parser.add_argument(
            "--keep",
            type=int,
            default=30,
            help="Number of recent backups to keep (default: 30)",
        )

    def handle(self, *args, **options):
        backup_dir = Path(getattr(settings, "BACKUPS_DIR", settings.BASE_DIR / "backups"))
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_path = options["output"] or str(backup_dir / f"db_backup_{timestamp}.sql.gz")

        db_settings = settings.DATABASES["default"]
        engine = db_settings["ENGINE"]

        try:
            if engine == "django.db.backends.sqlite3":
                self._backup_sqlite(db_settings, output_path)
            elif engine == "django.db.backends.postgresql":
                self._backup_postgres(db_settings, output_path)
            elif engine == "django.db.backends.mysql":
                self._backup_mysql(db_settings, output_path)
            else:
                self.stderr.write(self.style.ERROR(f"Unsupported engine: {engine}"))
                return

            self._cleanup_old(backup_dir, keep=options["keep"])
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Backup failed: {e}"))
            raise

    def _backup_sqlite(self, db_settings, output_path):
        db_path = db_settings["NAME"]
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")

        with open(db_path, "rb") as f_in:
            with gzip.open(output_path, "wb") as f_out:
                f_out.write(f_in.read())

        self._report_size(output_path)

    def _backup_postgres(self, db_settings, output_path):
        env = os.environ.copy()
        if db_settings.get("PASSWORD"):
            env["PGPASSWORD"] = db_settings["PASSWORD"]

        cmd = [
            "pg_dump",
            "-h", db_settings.get("HOST", "localhost"),
            "-p", str(db_settings.get("PORT", 5432)),
            "-U", db_settings.get("USER", "postgres"),
            "-d", db_settings["NAME"],
            "--no-owner",
            "--no-acl",
        ]

        with gzip.open(output_path, "wb") as f_out:
            result = subprocess.run(cmd, env=env, stdout=f_out, stderr=subprocess.PIPE, check=True)

        self._report_size(output_path)

    def _backup_mysql(self, db_settings, output_path):
        cmd = [
            "mysqldump",
            "-h", db_settings.get("HOST", "localhost"),
            "-P", str(db_settings.get("PORT", 3306)),
            "-u", db_settings.get("USER", "root"),
        ]
        if db_settings.get("PASSWORD"):
            cmd.append(f"-p{db_settings['PASSWORD']}")
        cmd.append(db_settings["NAME"])

        with gzip.open(output_path, "wb") as f_out:
            subprocess.run(cmd, stdout=f_out, stderr=subprocess.PIPE, check=True)

        self._report_size(output_path)

    def _report_size(self, output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f"Backup saved: {output_path} ({size_mb:.1f} MB)"))

    def _cleanup_old(self, backup_dir, keep=30):
        backups = sorted(
            backup_dir.glob("db_backup_*.sql.gz"),
            key=os.path.getmtime,
            reverse=True,
        )
        for old in backups[keep:]:
            old.unlink()
            self.stdout.write(f"  Removed old backup: {old.name}")