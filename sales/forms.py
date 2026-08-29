from django import forms
from store.models import SalesReturn, SaleItem, Sale
from django.core.exceptions import ValidationError


class SalesReturnForm(forms.ModelForm):
    class Meta:
        model = SalesReturn
        fields = [
            'customer_name',
            'sale_item',
            'quantity',
            'price',
            'reason',
            'recommendations'
        ]
        
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter customer name',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),
            'recommendations': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),
        }

    def __init__(self, *args, **kwargs):
        # Pop user from kwargs (passed from view)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # ===================== FILTER SALE ITEM BY USER'S STORE =====================
        if self.user and not getattr(self.user, 'can_see_all', False) and self.user.store:
            # Normal user: Only show sales from their own store
            self.fields['sale_item'].queryset = SaleItem.objects.filter(
                sale__store=self.user.store
            ).select_related('sale', 'product').order_by('-sale__sale_date')
        else:
            # Admin: Can see all sale items
            self.fields['sale_item'].queryset = SaleItem.objects.all().select_related(
                'sale', 'product'
            ).order_by('-sale__sale_date')

        # Custom label for dropdown
        self.fields['sale_item'].label_from_instance = (
            lambda obj: f"{obj.product_name} (x{obj.quantity}) - {obj.sale.store.name if obj.sale else ''}"
        )

        # Make sale_item required
        self.fields['sale_item'].required = True

    # Optional: Extra validation
    def clean(self):
        cleaned_data = super().clean()
        sale_item = cleaned_data.get('sale_item')
        quantity = cleaned_data.get('quantity')

        if sale_item and quantity:
            if quantity > sale_item.quantity:
                self.add_error('quantity', f"Cannot return more than sold quantity ({sale_item.quantity}).")
        
        return cleaned_data