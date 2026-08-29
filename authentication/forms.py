from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser
from store.models import Store


class CustomUserCreationForm(UserCreationForm):
    store = forms.ModelChoiceField(
        queryset=Store.objects.filter(is_active=True).order_by('name'),
        required=True,
        label="Assign Shop",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        label="Phone (SMS)",
        help_text="e.g. 0712345678 – used for SMS notifications",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '0712345678',
        })
    )

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'phone', 'role', 'store', 'password1', 'password2',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'placeholder': field.replace('_', ' ').title()
            })

        self.fields['role'].widget.attrs.update({'class': 'form-select'})
        self.fields['store'].widget.attrs.update({'class': 'form-select'})

        # Remove Admin from registration
        self.fields['role'].choices = [
            ('manager', 'Manager'),
            ('cashier', 'Cashier'),
            ('warehouse_staff', 'Warehouse Staff'),
        ]

    def clean(self):
        cleaned_data = super().clean()
        store = cleaned_data.get('store')

        if not store:
            self.add_error('store', 'Store is required for all users.')

        return cleaned_data


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter username'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter password'
        })