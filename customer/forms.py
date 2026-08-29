from django import forms
from .models import Customer
from store.models import Store


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'store',
            'first_name',
            'last_name',
            'phone',
            'email',
            'customer_type'
        ]
        widgets = {
            'store': forms.Select(attrs={
                'class': 'form-select',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter first name',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter last name',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),
            'customer_type': forms.Select(attrs={
                'class': 'form-select',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),
        }

    def __init__(self, *args, **kwargs):
        # Pop the user from kwargs
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # ===================== STORE FIELD LOGIC =====================
        if self.user and not getattr(self.user, 'can_see_all', False) and self.user.store:
            # Normal user (Cashier, Manager, etc.) → Hide store field
            self.fields['store'].widget = forms.HiddenInput()
            self.fields['store'].required = False
            self.fields['store'].initial = self.user.store
        else:
            # Admin → Show store dropdown
            try:
                self.fields['store'].queryset = Store.objects.filter(is_active=True).order_by('name')
            except:
                self.fields['store'].queryset = Store.objects.none()
            
            self.fields['store'].empty_label = "Select Store"
            self.fields['store'].required = True

        # Optional: Make other fields look consistent
        for field_name in ['first_name', 'last_name', 'phone', 'email']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'class': 'form-control'
                })

    # Optional: Extra validation
    def clean(self):
        cleaned_data = super().clean()
        store = cleaned_data.get('store')
        phone = cleaned_data.get('phone')

        if not store and self.user and not getattr(self.user, 'can_see_all', False):
            self.add_error('store', 'Store is required.')

        return cleaned_data