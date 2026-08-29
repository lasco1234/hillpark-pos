from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth import get_user_model
from store.models import Store, Product, Stock

User = get_user_model()


class Installment(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('defaulted', 'Defaulted'),
    ]

    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='installments')
    
    # Customer Info
    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField(blank=True, null=True)          # NEW
    customer_address = models.TextField(blank=True, null=True)

    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    # Late fee
    late_fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # NEW
    late_fee_applied = models.BooleanField(default=False)                      # NEW

    # Due date
    due_date = models.DateField(null=True, blank=True)                         # NEW
    grace_days = models.PositiveIntegerField(default=7)                        # NEW

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"INST-{self.id} | {self.customer_name} | {self.get_status_display()}"

    @property
    def is_fully_paid(self):
        return self.balance <= 0

    @property
    def days_overdue(self):
        if not self.due_date or self.status != 'active':
            return 0
        delta = (timezone.now().date() - self.due_date).days
        return max(0, delta)

    @property
    def is_in_grace_period(self):
        return 0 < self.days_overdue <= self.grace_days

    @property
    def should_apply_late_fee(self):
        return self.days_overdue > self.grace_days and not self.late_fee_applied

    def apply_late_fee_if_needed(self):
        """Apply 3% late fee after grace period"""
        if self.should_apply_late_fee:
            fee = (self.total_amount * Decimal('0.03')).quantize(Decimal('1'))
            self.late_fee = fee
            self.late_fee_applied = True
            self.balance += fee
            self.save(update_fields=['late_fee', 'late_fee_applied', 'balance'])
            return fee
        return Decimal('0')

    def recalculate(self):
        self.total_amount = sum(item.subtotal for item in self.items.all()) or Decimal('0')
        self.amount_paid = sum(p.amount for p in self.payments.all()) or Decimal('0')
        
        # Include late fee in balance
        self.balance = (self.total_amount + self.late_fee) - self.amount_paid

        if self.balance <= 0 and self.status == 'active':
            self.status = 'completed'
            self.completed_at = timezone.now()
        elif self.balance > 0 and self.status == 'completed':
            self.status = 'active'
            self.completed_at = None

        self.save(update_fields=[
            'total_amount', 'amount_paid', 'balance', 
            'status', 'completed_at'
        ])


class InstallmentItem(models.Model):
    installment = models.ForeignKey(Installment, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product} x {self.quantity}"


class InstallmentPayment(models.Model):
    installment = models.ForeignKey(Installment, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['payment_date']

    def __str__(self):
        return f"{self.amount} on {self.payment_date.date()}"