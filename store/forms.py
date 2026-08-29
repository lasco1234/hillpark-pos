from django import forms
from django.core.exceptions import ValidationError
import re
from .models import Product, Store
from .models import StockAdjustment
from decimal import Decimal


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'

        widgets = {
            'store': forms.Select(attrs={
                'class': 'form-select',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),

            'product_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. HP Laptop, Coca Cola 500ml',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
            }),

            'category': forms.Select(attrs={'class': 'form-select'}),
            # In ProductForm Meta.fields or widgets

            'product_group': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. HDMI Cable, Dell XPS 15',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),
            'variant': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 1.5m, 2m, 16GB/512GB, Gen 12',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),

            'buy_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
                'value': 0,
            }),

            # These are now calculated automatically → hide them
            'sell_price': forms.HiddenInput(),
            'wholesale_price': forms.HiddenInput(),

            'initial_stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
                'value': 0,
            }),
            'reorder_level': forms.NumberInput(attrs={
                'class': 'form-control',
                'style': 'color: black; background-color: rgb(239, 243, 243); border-color: rgb(208, 209, 212);',
                'value': 5,
            }),
            'unit_type': forms.Select(attrs={'class': 'form-select'}),

            'tax_type': forms.Select(attrs={'class': 'form-select', 'id': 'tax_type'}),
            'tax_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'style': 'color: white;',
                'id': 'tax_amount',
            }),

            'discount_type': forms.Select(attrs={'class': 'form-select', 'id': 'discount_type'}),
            'discount_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'style': 'color: white;',
                'id': 'discount_value',
            }),

            'product_image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'style': 'color: white;',
            }),

            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'style': 'color: white;',
                'placeholder': 'e.g. RAM 8GB STORAGE 256SSD, cable M5',
            }),

            'has_manufacturer': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'has_manufacturer',
            }),
            'manufacturer': forms.TextInput(attrs={
                'class': 'form-control',
                'style': 'color: white;',
                'id': 'manufacturer',
            }),

            'has_warranty': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'has_warranty',
            }),
            'warranty_details': forms.TextInput(attrs={
                'class': 'form-control',
                'style': 'color: white;',
                'id': 'warranty_details',
            }),

            'has_expiry_date': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'has_expiry_date',
            }),
            'expiry_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'style': 'color: white;',
                'id': 'expiry_date',
            }),

            'low_stock_alert_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'style': 'color: white;',
                'value': 2,
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        is_admin = self.user and (getattr(self.user, 'can_see_all', False) or self.user.is_superuser)
        is_update = bool(self.instance and self.instance.pk)

        if is_update:
            # ========== UPDATE ==========
            if 'store' in self.fields:
                del self.fields['store']
        else:
            # ========== CREATE ==========
            if not is_admin and self.user and self.user.store:
                self.fields['store'].widget = forms.HiddenInput()
                self.fields['store'].required = False
                self.fields['store'].queryset = Store.objects.filter(pk=self.user.store.pk)
                self.fields['store'].initial = self.user.store
                self.instance.store = self.user.store
            else:
                self.fields['store'].empty_label = "Select Store"
                self.fields['store'].required = True
                self.fields['store'].queryset = Store.objects.filter(is_active=True).order_by('name')

        # sell_price & wholesale_price are calculated → not required from user
        self.fields['sell_price'].required = False
        self.fields['wholesale_price'].required = False

        important_fields = ['product_name', 'buy_price', 'initial_stock', 'reorder_level']
        for field_name in important_fields:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})

    # ------------------------------------------------------------------
    # PRICE CALCULATION LOGIC
    # ------------------------------------------------------------------
    def calculate_prices(self, buy_price, category):
        """
        Returns (sell_price, wholesale_price) based on the business rules.
        category is a string: 'Laptop', 'Desktop', or 'Accessories'
        """
        if buy_price is None or buy_price <= 0:
            return Decimal('0'), Decimal('0')

        buy = Decimal(str(buy_price))
        category_name = (category or "").lower().strip()

        # ---------- ACCESSORY ----------
        if "accessor" in category_name:
            sell = buy + (buy * Decimal('0.35'))          # +35%
            wholesale = buy + (buy * Decimal('0.20'))     # +20%

        # ---------- LAPTOP / DESKTOP ----------
        elif "laptop" in category_name or "desktop" in category_name:
            if buy <= 399999:
                sell = buy + Decimal('50000')
            elif buy <= 499999:
                sell = buy + Decimal('70000')
            elif buy <= 699999:
                sell = buy + Decimal('90000')
            elif buy <= 999999:
                sell = buy + Decimal('100000')
            elif buy <= 1499999:
                sell = buy + Decimal('150000')
            elif buy <= 1999999:
                sell = buy + Decimal('200000')
            elif buy <= 2499999:
                sell = buy + Decimal('250000')
            elif buy <= 2999999:
                sell = buy + Decimal('300000')
            else:
                # above 2,999,999 → +25%
                sell = buy + (buy * Decimal('0.25'))

            margin = sell - buy
            wholesale = buy + (margin * Decimal('0.65'))

        # ---------- OTHER / fallback ----------
        else:
            sell = buy + (buy * Decimal('0.25'))
            wholesale = buy + (buy * Decimal('0.15'))

        # Round to nearest whole number (TZS)
        sell = sell.quantize(Decimal('1'))
        wholesale = wholesale.quantize(Decimal('1'))

        return sell, wholesale

    # ------------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------------
    def clean_store(self):
        if self.user and not getattr(self.user, 'can_see_all', False) and self.user.store:
            return self.user.store
        return self.cleaned_data.get('store')

    def clean_product_name(self):
        name = self.cleaned_data.get("product_name")
        if name and not re.match(r"^[A-Za-z]", name):
            raise ValidationError("Product name must start with a letter.")
        return name.strip() if name else name

    def clean_buy_price(self):
        value = self.cleaned_data.get("buy_price")
        if value is not None and value <= 0:
            raise ValidationError("Buy price must be greater than 0.")
        return value

    def clean_initial_stock(self):
        value = self.cleaned_data.get("initial_stock")
        if value is not None and value < 1:
            raise ValidationError("Initial stock must be at least 1.")
        return value

    def clean(self):
        cleaned_data = super().clean()

        buy = cleaned_data.get("buy_price")
        category = cleaned_data.get("category")   # this is a string, e.g. "Laptop"

        if buy is not None and category:
            sell, wholesale = self.calculate_prices(buy, category)
            cleaned_data['sell_price'] = sell
            cleaned_data['wholesale_price'] = wholesale

            if sell <= buy:
                self.add_error(
                    'buy_price',
                    "Calculated sell price is not greater than buy price. Check category or buy price."
                )

        return cleaned_data


# ===================== STORE FORM =====================
class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'location', 'address', 'phone', 'email', 'is_active']
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Main Branch, Downtown Store',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Dar es Salaam, Arusha',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Full address...',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 0712345678',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'store@example.com',
                'style': 'color: black; background-color: rgb(239, 243, 243);',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make ALL fields mandatory
        for field_name in ['name', 'location', 'address', 'phone', 'email']:
            if field_name in self.fields:
                self.fields[field_name].required = True

        # is_active can remain optional (default True)
        self.fields['is_active'].required = False

    # ===================== VALIDATIONS =====================
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            if len(name) < 3:
                raise ValidationError("Store name must be at least 3 characters long.")
            if len(name) > 100:
                raise ValidationError("Store name is too long.")
        else:
            raise ValidationError("Store name is required.")
        return name

    def clean_location(self):
        location = self.cleaned_data.get('location')
        if not location or len(location.strip()) < 2:
            raise ValidationError("Location is required and must be meaningful.")
        return location.strip()

    def clean_address(self):
        address = self.cleaned_data.get('address')
        if not address or len(address.strip()) < 5:
            raise ValidationError("Full address is required.")
        return address.strip()

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not phone:
            raise ValidationError("Phone number is required.")
        
        # Clean phone number
        phone = ''.join(filter(str.isdigit, phone))
        if len(phone) < 9:
            raise ValidationError("Phone number seems too short.")
        if len(phone) > 15:
            raise ValidationError("Phone number is too long.")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("Email address is required.")
        return email.strip()
    

class StockAdjustmentForm(forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = [
            'product', 'from_store', 'to_store',
            'adjustment_type', 'quantity', 'unit_price', 'reason'
        ]
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional reason'}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if not getattr(user, 'can_see_all', False) and getattr(user, 'store', None):
            self.fields['product'].queryset = Product.objects.filter(store=user.store)
            self.fields['from_store'].queryset = Store.objects.filter(id=user.store.id)
            self.fields['to_store'].queryset = Store.objects.filter(is_active=True)
        else:
            self.fields['product'].queryset = Product.objects.all()
            self.fields['from_store'].queryset = Store.objects.filter(is_active=True)
            self.fields['to_store'].queryset = Store.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        adj_type = cleaned.get('adjustment_type')
        from_store = cleaned.get('from_store')
        to_store = cleaned.get('to_store')

        if adj_type == 'transfer':
            if not from_store or not to_store:
                raise ValidationError("Both From Store and To Store are required for transfer.")
            if from_store == to_store:
                raise ValidationError("From and To stores cannot be the same.")
        elif adj_type == 'increase':
            if not to_store:
                raise ValidationError("Store is required for increase.")
            cleaned['from_store'] = None
        elif adj_type == 'decrease':
            if not from_store:
                raise ValidationError("Store is required for decrease.")
            cleaned['to_store'] = None

        return cleaned