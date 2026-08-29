"""
Send installment due / overdue reminders to customer, cashier, owner, manager.

Usage:
    python manage.py send_installment_reminders
    python manage.py send_installment_reminders --days-before 3
    python manage.py send_installment_reminders --dry-run

Schedule with cron or Celery beat, e.g. daily at 08:00.

Place this file at:
    notifications/management/commands/send_installment_reminders.py

Also create empty __init__.py files:
    notifications/management/__init__.py
    notifications/management/commands/__init__.py
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.services import notify_installment_reminder


class Command(BaseCommand):
    help = "Send installment due / overdue reminder notifications (in-app, email)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-before",
            type=int,
            default=1,
            help="Also remind installments due within N days (default: 1)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list installments that would be notified",
        )

    def handle(self, *args, **options):
        from installment.models import Installment

        today = timezone.localdate()
        days_before = options["days_before"]
        dry_run = options["dry_run"]

        qs = Installment.objects.filter(
            status="active",
            due_date__isnull=False,
        ).select_related("store")

        due_soon_or_overdue = qs.filter(
            due_date__lte=today + timedelta(days=days_before)
        )

        count = 0
        for inst in due_soon_or_overdue:
            self.stdout.write(
                f"  INST-{inst.id} | {inst.customer_name} | "
                f"due {inst.due_date} | balance {inst.balance} | "
                f"store {inst.store.name}"
            )
            if not dry_run:
                # Apply late fee BEFORE sending reminder
                if hasattr(inst, "apply_late_fee_if_needed"):
                    inst.apply_late_fee_if_needed()
                try:
                    notify_installment_reminder(inst)
                    count += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Failed INST-{inst.id}: {e}"))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: {due_soon_or_overdue.count()} would be notified"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Reminders sent for {count} installment(s)")
            )