from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from store.models import Store, Product

User = get_user_model()


class SupplierOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('confirmed', 'Confirmed'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='supplier_orders')
    order_number = models.CharField(max_length=30, unique=True, blank=True)
    supplier_name = models.CharField(max_length=150)
    supplier_email = models.EmailField(blank=True, null=True)
    supplier_phone = models.CharField(max_length=30, blank=True, null=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number or f"Order #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            # e.g. PO-20260805-0001
            from django.utils import timezone
            prefix = timezone.now().strftime('PO-%Y%m%d')
            last = SupplierOrder.objects.filter(order_number__startswith=prefix).count() + 1
            self.order_number = f"{prefix}-{last:04d}"
        super().save(*args, **kwargs)

    @property
    def total_amount(self):
        return sum((item.line_total for item in self.items.all()), 0)

    @property
    def items_count(self):
        return self.items.count()


class SupplierOrderItem(models.Model):
    order = models.ForeignKey(SupplierOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Existing product (optional)"
    )
    product_name = models.CharField(max_length=200)
    description = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Expected / quoted unit price"
    )
    is_new_product = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    @property
    def line_total(self):
        from decimal import Decimal
        return Decimal(self.quantity or 0) * Decimal(self.unit_price or 0)