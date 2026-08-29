from django import forms
from .models import SystemSettings, StoreSettings

class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = [
            'company_name', 'company_phone', 'company_email', 'company_address',
            'company_tin', 'company_logo',
            'currency', 'currency_symbol', 'default_tax_percent',
            'allow_negative_stock', 'require_customer_on_sale',
            'low_stock_threshold', 'auto_print_receipt',
            'invoice_prefix', 'proforma_prefix', 'delivery_prefix',
            'default_invoice_terms', 'default_bank_account',
            'session_timeout_minutes', 'enable_audit_log',
        ]
        widgets = {
            'company_address': forms.Textarea(attrs={'rows': 3}),
            'default_invoice_terms': forms.Textarea(attrs={'rows': 4}),
            'default_bank_account': forms.Textarea(attrs={'rows': 3}),
            'company_logo': forms.ClearableFileInput(),
        }


class StoreSettingsForm(forms.ModelForm):
    class Meta:
        model = StoreSettings
        fields = [
            'receipt_header', 'receipt_footer',
            'show_cashier_name', 'show_tax_breakdown',
            'enable_tips', 'default_payment_method',
            'track_expiry', 'allow_stock_transfer',
            'low_stock_alert', 'daily_sales_email', 'notification_email',
        ]
        widgets = {
            'receipt_header': forms.Textarea(attrs={'rows': 3}),
            'receipt_footer': forms.Textarea(attrs={'rows': 3}),
        }