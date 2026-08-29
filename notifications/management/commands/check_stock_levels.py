"""
Scan all products and send out-of-stock / low-stock notifications.

Usage:
    python manage.py check_stock_levels
    python manage.py check_stock_levels --dry-run
    python manage.py check_stock_levels --include-low   # also check low stock (< 2)

Schedule daily (cron / Task Scheduler) to catch products
that have dropped below thresholds.

Place this file at:
    notifications/management/commands/check_stock_levels.py
"""
from django.core.management.base import BaseCommand
from notifications.utils import check_stock_and_notify


class Command(BaseCommand):
    help = "Scan products and send out-of-stock / low-stock alerts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list products that would be notified (no notifications sent)",
        )
        parser.add_argument(
            "--include-low",
            action="store_true",
            help="Also check low-stock products (quantity < 2), not just out-of-stock",
        )

    def handle(self, *args, **options):
        from store.models import Product, Stock

        dry_run = options["dry_run"]
        include_low = options["include_low"]

        products = Product.objects.filter(is_deleted=False).select_related("store")

        alerted = 0
        for product in products:
            if not product.store:
                continue

            stock = Stock.objects.filter(product=product, store=product.store).first()
            quantity = stock.quantity if stock else product.initial_stock

            # Only out-of-stock (0) by default; optionally include low stock (< 2)
            if quantity == 0:
                state = "OUT OF STOCK"
            elif include_low and quantity < 2:
                state = "LOW STOCK"
            else:
                continue

            self.stdout.write(
                f"  {state:12} | {product.product_name} | qty={quantity} | store={product.store.name}"
            )

            if not dry_run:
                try:
                    check_stock_and_notify(product, product.store)
                    alerted += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Failed {product.product_name}: {e}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no notifications were sent."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Stock alerts processed for {alerted} product(s)."))