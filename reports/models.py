from django.db import models
from django.core.validators import MinValueValidator
from store.models import Store


class CashOut(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='report_cash_outs')
    date = models.DateField()
    amount = models.DecimalField(max_digits=16, decimal_places=2, validators=[MinValueValidator(0)])
    purpose = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'id']

    def __str__(self):
        return f"{self.date} - {self.purpose}: {self.amount}"


class DailyNote(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='report_notes')
    date = models.DateField()
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'id']

    def __str__(self):
        return f"{self.date}: {self.note[:50]}"


class DailyClosing(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='report_closings')
    date = models.DateField()

    opening_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    bank_total = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    cash_in_hand = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    # Extra income (counted with daily sales)
    advance_payments = models.DecimalField(
        max_digits=16, decimal_places=2, default=0,
        help_text="Money paid in advance by customers"
    )
    maintenance_income = models.DecimalField(
        max_digits=16, decimal_places=2, default=0,
        help_text="Money from customer device maintenance / repair"
    )

    opening_stock = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    closing_stock = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    stock_in = models.DecimalField(max_digits=16, decimal_places=2, default=0)   # auto from adjustments
    stock_out = models.DecimalField(max_digits=16, decimal_places=2, default=0)  # auto from adjustments
    lipa_namba_total = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('store', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"Closing {self.store.name} - {self.date}"