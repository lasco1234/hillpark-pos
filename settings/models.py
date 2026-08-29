from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from store.models import Store
from decimal import Decimal

class SystemSettings(models.Model):
    """
    Global settings (only one row should exist).
    Controlled by superuser / can_see_all users.
    """
    # Business
    company_name = models.CharField(max_length=200, default="My Company")
    company_phone = models.CharField(max_length=30, blank=True)
    company_email = models.EmailField(blank=True)
    company_address = models.TextField(blank=True)
    company_tin = models.CharField(max_length=50, blank=True, verbose_name="Company TIN")
    company_logo = models.ImageField(upload_to='settings/logo/', blank=True, null=True)

    # Currency & Tax
    currency = models.CharField(max_length=10, default="TZS")
    currency_symbol = models.CharField(max_length=5, default="TSh")
    default_tax_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('18.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # POS Behaviour
    allow_negative_stock = models.BooleanField(default=False)
    require_customer_on_sale = models.BooleanField(default=False)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    auto_print_receipt = models.BooleanField(default=True)

    # Invoice Defaults
    invoice_prefix = models.CharField(max_length=20, default="INV")
    proforma_prefix = models.CharField(max_length=20, default="PRO")
    delivery_prefix = models.CharField(max_length=20, default="DN")
    default_invoice_terms = models.TextField(
        default="Payment is due within 30 days. Thank you for your business.",
        blank=True
    )
    default_bank_account = models.TextField(blank=True, help_text="Bank name, Account number, etc.")

    # Security / System
    session_timeout_minutes = models.PositiveIntegerField(default=60)
    enable_audit_log = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return "System Settings"

    def save(self, *args, **kwargs):
        # Ensure only one instance
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class StoreSettings(models.Model):
    """
    Per-store settings. Created automatically when a store is created.
    """
    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name='settings')

    # Receipt
    receipt_header = models.TextField(blank=True, help_text="Appears at the top of receipts")
    receipt_footer = models.TextField(blank=True, help_text="Thank you message / return policy")
    show_cashier_name = models.BooleanField(default=True)
    show_tax_breakdown = models.BooleanField(default=True)

    # POS
    enable_tips = models.BooleanField(default=False)
    default_payment_method = models.CharField(
        max_length=30,
        choices=[
            ('cash', 'Cash'),
            ('card', 'Card'),
            ('mobile', 'Mobile Money'),
            ('bank', 'Bank Transfer'),
        ],
        default='cash'
    )

    # Inventory
    track_expiry = models.BooleanField(default=False)
    allow_stock_transfer = models.BooleanField(default=True)

    # Notifications
    low_stock_alert = models.BooleanField(default=True)
    daily_sales_email = models.BooleanField(default=False)
    notification_email = models.EmailField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Store Settings"
        verbose_name_plural = "Store Settings"

    def __str__(self):
        return f"Settings - {self.store.name}"