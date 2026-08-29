from django.db import models
from django.core.exceptions import ValidationError

class Customer(models.Model):
    CUSTOMER_TYPE_CHOICES = [
        ('Individual', 'Individual'),
        ('Company', 'Company'),
        ('Group', 'Group'),
        ('School', 'School'),
    ]
    
    store = models.ForeignKey(
        'store.Store',
        on_delete=models.CASCADE,
        related_name='customers',
        null=True,      # ← Add this temporarily
        blank=True
    )
    
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    customer_type = models.CharField(
        max_length=20,
        choices=CUSTOMER_TYPE_CHOICES
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('store', 'phone')
        ordering = ['first_name']

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name or ''}".strip()
        return f"{full_name} - {self.store.name if self.store else 'No Store'}"

    def clean(self):
        if not self.store:
            raise ValidationError({'store': 'Store is required for this customer.'})
        if not self.first_name:
            raise ValidationError({'first_name': 'First name is required.'})
        if not self.phone:
            raise ValidationError({'phone': 'Phone number is required.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)