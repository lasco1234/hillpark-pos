from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    relativedelta = None

from .models import Installment, InstallmentPayment


class InstallmentForm(forms.ModelForm):
    DURATION_TYPE_CHOICES = [
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
    ]

    duration_type = forms.ChoiceField(
        choices=DURATION_TYPE_CHOICES,
        initial='months',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_duration_type'
        })
    )

    duration_value = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_duration_value',
            'min': '1',
            'placeholder': 'e.g. 3',
            'style': 'background-color: #414344; color: #f8f9fa;',
        })
    )

    class Meta:
        model = Installment
        fields = [
            'customer_name',
            'customer_phone',
            'customer_email',
            'customer_address',
            'notes',
        ]
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Customer full name',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),
            'customer_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '07xxxxxxxx',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),
            'customer_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'customer@email.com',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),
            'customer_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional address',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional notes',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_customer_phone(self):
        phone = self.cleaned_data.get('customer_phone', '').strip()
        if not phone:
            raise ValidationError("Phone number is required.")
        digits = ''.join(filter(str.isdigit, phone))
        if len(digits) < 9:
            raise ValidationError("Phone number seems too short.")
        return phone

    def clean(self):
        cleaned = super().clean()
        duration_type = cleaned.get('duration_type')
        duration_value = cleaned.get('duration_value')

        if not duration_value or duration_value < 1:
            self.add_error('duration_value', "Please enter a valid duration (minimum 1).")
            return cleaned

        today = timezone.now().date()

        if duration_type == 'days':
            due_date = today + timedelta(days=duration_value)
        elif duration_type == 'weeks':
            due_date = today + timedelta(weeks=duration_value)
        else:  # months
            if relativedelta is None:
                # Fallback if python-dateutil is not installed
                due_date = today + timedelta(days=duration_value * 30)
            else:
                due_date = today + relativedelta(months=duration_value)

        cleaned['due_date'] = due_date
        return cleaned


class InstallmentPaymentForm(forms.ModelForm):
    class Meta:
        model = InstallmentPayment
        fields = ['amount', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Enter amount',
                'style': 'background-color: #414344; color: #f8f9fa;',
            }),
            'notes': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional note',
                'style': 'background-color: #414344; color: #f8f9fa;',
            }),
        }

    def __init__(self, *args, installment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.installment = installment

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= 0:
            raise ValidationError("Amount must be greater than zero.")

        if self.installment:
            # Apply late fee first (if needed)
            self.installment.apply_late_fee_if_needed()
            max_allowed = self.installment.balance
            if amount > max_allowed:
                raise ValidationError(
                    f"Amount cannot be more than remaining balance ({max_allowed:,.0f} TZS)."
                )
        return amount