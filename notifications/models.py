from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Notification(models.Model):
    LEVEL_CHOICES = (
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('danger', 'Danger'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='info')
    icon = models.CharField(max_length=60, default='mdi-bell')
    link = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    # Optional: useful for filtering later
    store = models.ForeignKey('store.Store', on_delete=models.CASCADE, null=True, blank=True)
    related_object_type = models.CharField(max_length=50, blank=True)  # e.g. 'sale', 'invoice'
    related_object_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} → {self.user.username}"


# ================================================================
# Notification Preference Model
# ================================================================

class NotificationPreference(models.Model):
    """
    Per-user toggles for each notification type.
    Defaults to True (enabled) for all notification types.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )

    # ── Product events ──
    product_added = models.BooleanField(default=True)
    product_updated = models.BooleanField(default=True)
    product_deleted = models.BooleanField(default=True)

    # ── Stock events ──
    stock_adjustment = models.BooleanField(default=True)
    low_stock = models.BooleanField(default=True)
    out_of_stock = models.BooleanField(default=True)

    # ── Order events ──
    order_created = models.BooleanField(default=True)
    supplier_order_received = models.BooleanField(default=True)

    # ── Store events ──
    store_created = models.BooleanField(default=True)

    # ── Sale events ──
    new_sale = models.BooleanField(default=True)
    sales_return = models.BooleanField(default=True)

    # ── Invoice events ──
    invoice_paid = models.BooleanField(default=True)

    # ── Installment events ──
    installment_created = models.BooleanField(default=True)
    installment_reminder = models.BooleanField(default=True)
    installment_completed = models.BooleanField(default=True)

    # ── Cash events ──
    large_cash_out = models.BooleanField(default=True)

    # ── Report events ──
    daily_report = models.BooleanField(default=True)

    # ── User events ──
    user_registered = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                name='unique_notification_preference_per_user'
            )
        ]

    def __str__(self):
        return f"Notification preferences for {self.user.username}"

    @classmethod
    def get_for_user(cls, user):
        """Get or create preferences for a user."""
        pref, _ = cls.objects.get_or_create(user=user)
        return pref

    @classmethod
    def is_enabled(cls, user, notification_type):
        """
        Check if a notification type is enabled for a given user.
        Returns True if the user has no preference record (default: enabled).
        """
        if not user or not user.is_active:
            return False
        try:
            pref = cls.objects.get(user=user)
            return getattr(pref, notification_type, True)
        except cls.DoesNotExist:
            return True  # not configured → default to enabled


# ── Notification type labels for display ──
NOTIFICATION_LABELS = {
    'product_added': 'Product Added',
    'product_updated': 'Product Updated',
    'product_deleted': 'Product Deleted',
    'stock_adjustment': 'Stock Adjustment',
    'low_stock': 'Low Stock Alert',
    'out_of_stock': 'Out of Stock Alert',
    'order_created': 'Supplier Order Created',
    'supplier_order_received': 'Supplier Order Received',
    'store_created': 'Store Created',
    'new_sale': 'New Sale (Large)',
    'sales_return': 'Sales Return',
    'invoice_paid': 'Invoice Paid',
    'installment_created': 'Installment Created',
    'installment_reminder': 'Installment Reminder',
    'installment_completed': 'Installment Completed',
    'large_cash_out': 'Large Cash Out',
    'daily_report': 'Daily Report',
    'user_registered': 'User Registered',
}

NOTIFICATION_CATEGORIES = {
    'Products': ['product_added', 'product_updated', 'product_deleted'],
    'Stock': ['stock_adjustment', 'low_stock', 'out_of_stock'],
    'Orders': ['order_created', 'supplier_order_received'],
    'Store': ['store_created'],
    'Sales': ['new_sale', 'sales_return'],
    'Invoices': ['invoice_paid'],
    'Installments': ['installment_created', 'installment_reminder', 'installment_completed'],
    'Cash': ['large_cash_out'],
    'Reports': ['daily_report'],
    'Users': ['user_registered'],
}