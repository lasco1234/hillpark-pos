import subprocess
import sys
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@login_required
def backup_page(request):
    """Backup dashboard page with manual backup button."""
    if not request.user.can_see_all:
        messages.error(request, "Only administrators can access backups.")
        return redirect("settings:home")

    backup_dir = Path(getattr(settings, "BACKUPS_DIR", settings.BASE_DIR / "backups"))
    backups = []
    if backup_dir.exists():
        for f in sorted(backup_dir.glob("db_backup_*.sql.gz"), reverse=True):
            backups.append({
                "name": f.name,
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(f.stat().st_mtime),   # ← FIXED
            })

    return render(request, "backup/backup_page.html", {"backups": backups})


@login_required
def create_backup(request):
    """Trigger a manual database backup. Admin only, POST only."""
    if not request.user.can_see_all:
        messages.error(request, "Only administrators can create backups.")
        return redirect("backup_page")

    if request.method == "POST":
        try:
            manage_py = Path(settings.BASE_DIR) / "manage.py"
            result = subprocess.run(
                [sys.executable, str(manage_py), "backup_db"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(settings.BASE_DIR),
            )

            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "Backup saved:" in line:
                        filepath = line.split("Backup saved:")[-1].strip()
                        messages.success(request, f"Backup created: {filepath}")
                        break
                else:
                    messages.success(request, "Backup created successfully.")
            else:
                messages.error(request, f"Backup failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            messages.error(request, "Backup timed out (took > 2 minutes).")
        except Exception as e:
            messages.error(request, f"Backup error: {str(e)}")

    return redirect("backup_page")