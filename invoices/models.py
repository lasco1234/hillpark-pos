from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from store.models import Store, Product

User = get_user_model()


class Invoice(models.Model):
    DOC_TYPES = [
        ('proforma', 'Proforma Invoice'),
        ('invoice', 'Tax Invoice'),
        ('delivery', 'Delivery Note'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='invoices')
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES, default='invoice')
    number = models.CharField(max_length=40, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Customer
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=40, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_address = models.TextField(blank=True)
    customer_tin = models.CharField(max_length=50, blank=True, help_text="Customer TIN / VAT number")

    # Dates
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)

    # Money
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    bank_account = models.CharField(max_length=100, blank=True, help_text="Bank account number (shown on Tax Invoice)")

    # Extra
    notes = models.TextField(blank=True)
    terms = models.TextField(
        blank=True,
        default="Payment is due within the stated period. Goods remain the property of Hillpark Computers until paid in full."
    )
    reference = models.CharField(max_length=100, blank=True, help_text="PO number / reference")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.number} — {self.customer_name}"

    def save(self, *args, **kwargs):
        if not self.number:
            prefix_map = {'proforma': 'PI', 'invoice': 'INV', 'delivery': 'DN'}
            prefix = prefix_map.get(self.doc_type, 'DOC')
            stamp = timezone.now().strftime('%Y%m%d')
            count = Invoice.objects.filter(number__startswith=f"{prefix}-{stamp}").count() + 1
            self.number = f"{prefix}-{stamp}-{count:04d}"
        super().save(*args, **kwargs)

    def recalculate(self):
        sub = sum((i.line_total for i in self.items.all()), Decimal('0'))
        self.subtotal = sub
        self.tax_amount = (sub * Decimal(self.tax_percent or 0) / Decimal('100')).quantize(Decimal('1'))
        self.total = self.subtotal + self.tax_amount - Decimal(self.discount or 0)
        self.save(update_fields=['subtotal', 'tax_amount', 'total'])

    @property
    def balance_due(self):
        return self.total - (self.amount_paid or 0)

    @property
    def doc_title(self):
        return dict(self.DOC_TYPES).get(self.doc_type, 'Document')


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']

    @property
    def line_total(self):
        return Decimal(self.quantity or 0) * Decimal(self.unit_price or 0)

    def __str__(self):
        return f"{self.description} x {self.quantity}"