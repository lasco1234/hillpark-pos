# store/models.py
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from .managers import StoreAwareManager
from django.shortcuts import redirect, get_object_or_404

User = get_user_model()

# ===================== MANAGER =====================
class ProductManager(StoreAwareManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# ===================== STORE =====================
class Store(models.Model):
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ===================== STOCK =====================
class Stock(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='stocks')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='stocks')
    quantity = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'store')
        ordering = ['product', 'store']

    objects = StoreAwareManager()   # ← Added

    def __str__(self):
        return f"{self.product.product_name} @ {self.store.name} ({self.quantity})"
    

# ===================== PRODUCT =====================
class Product(models.Model):
    CATEGORY_CHOICES = [
        ('Laptop', 'Laptop'),
        ('Desktop', 'Desktop'),
        ('Accessories', 'Accessories'),
    ]
    UNIT_CHOICES = [
        ('Pieces', 'Pieces'),
        ('Box', 'Box'),
        ('Carton', 'Carton'),
    ]
    DISCOUNT_CHOICES = [
        ('None', 'None'),
        ('Percentage', 'Percentage'),
        ('Fixed', 'Fixed'),
    ]
    TAX_CHOICES = [
        ('None', 'None'),
        ('VAT', 'VAT'),
        ('GST', 'GST'),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')

    product_name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    buy_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    sell_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    initial_stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    reorder_level = models.IntegerField(default=5)
    unit_type = models.CharField(max_length=20, choices=UNIT_CHOICES)
    tax_type = models.CharField(max_length=20, choices=TAX_CHOICES, default='None')
    tax_amount = models.DecimalField(max_digits=5, decimal_places=2, default=0, blank=True, null=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_CHOICES, default='None')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    
    has_warranty = models.BooleanField(default=False)
    warranty_details = models.CharField(max_length=255, blank=True, null=True)
    has_manufacturer = models.BooleanField(default=False)
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    has_expiry_date = models.BooleanField(default=False)
    expiry_date = models.DateField(blank=True, null=True)
    low_stock_alert_quantity = models.IntegerField(default=2, validators=[MinValueValidator(0)])
    
    product_image = models.ImageField(upload_to='products/', null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    product_group = models.CharField(max_length=120, blank=True, null=True, help_text="e.g. HDMI Cable, Dell XPS 15, HP EliteBook")
    variant = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. 1.5m, 2m, 16GB/512GB, Gen 12 i7")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ProductManager()        # ← Main filtered manager
    all_objects = models.Manager()    # For admin to see everything (including deleted)

    class Meta:
        unique_together = ('store', 'product_name', 'variant')
        ordering = ['store', 'product_name']

    def __str__(self):
        return f"{self.product_name} ({self.store.name})"

    def clean(self):
        # Normalize empty strings to None
        if self.product_group == '':
            self.product_group = None
        if self.variant == '':
            self.variant = None

        # Only enforce minimum stock when creating
        if self._state.adding or self.pk is None:
            if self.initial_stock < 1:
                raise ValidationError({'initial_stock': 'Initial stock must be at least 1 when adding new product.'})

        if self.store_id is None:
            raise ValidationError("Product must belong to a store.")

        if self.buy_price is not None and self.buy_price <= 0:
            raise ValidationError({'buy_price': 'Buy price must be greater than 0.'})

        if self.sell_price is not None and self.sell_price <= 0:
            raise ValidationError({'sell_price': 'Sell price must be greater than 0.'})

        if self.buy_price is not None and self.sell_price is not None:
            if self.sell_price <= self.buy_price:
                raise ValidationError({'sell_price': 'Sell price must be greater than buy price.'})

        # ========== VALIDATION FOR UNIQUENESS ==========
        # Case 1: No group and no variant → product_name must be unique
        if not self.product_group and not self.variant:
            existing = Product.objects.filter(
                store=self.store,
                product_name__iexact=self.product_name.strip() if self.product_name else '',
                product_group__isnull=True,
                variant__isnull=True
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)

            if existing.exists():
                raise ValidationError({
                    'product_name': 'A product with this name already exists. If this is a variant, please fill Product Group and Variant.'
                })

        # Case 2: Both group and variant are filled → combination must be unique
        elif self.product_group and self.variant:
            existing = Product.objects.filter(
                store=self.store,
                product_group__iexact=self.product_group.strip(),
                variant__iexact=self.variant.strip()
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)

            if existing.exists():
                raise ValidationError({
                    'variant': f'This variant ({self.variant}) already exists for "{self.product_group}".'
                })

        # Case 3: Only one of them is filled → not allowed
        else:
            raise ValidationError(
                'Please fill both Product Group and Variant, or leave both empty.'
            )


    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if kwargs.pop('skip_validation', False):
            super().save(*args, **kwargs)
        else:
            self.full_clean()
            super().save(*args, **kwargs)

        # Create Stock record only when product is newly created
        if is_new:
            from .models import Stock   # avoid circular import if needed
            Stock.objects.get_or_create(
                product=self,
                store=self.store,
                defaults={'quantity': self.initial_stock}
            )

    @property
    def display_name(self):
        if self.product_group and self.variant:
            return f"{self.product_group} ({self.variant})"
        return self.product_name

# ===================== PRODUCT TRANSFER =====================
class ProductTransfer(models.Model):
    TRANSFER_STATUS = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='transfers')
    from_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='transfers_out')
    to_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='transfers_in')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    transfer_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=TRANSFER_STATUS, default='Pending')
    reason = models.TextField(blank=True, null=True)
    transferred_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    objects = StoreAwareManager()

    class Meta:
        ordering = ['-transfer_date']

    def __str__(self):
        return f"{self.product} → {self.to_store}"

# ===================== SALE MODELS =====================
class Sale(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sales')
    sale_date = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    items_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = StoreAwareManager()

    class Meta:
        ordering = ['-sale_date']

    def __str__(self):
        return f"Sale #{self.id} @ {self.store}"

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, blank=True)
    unit_type = models.CharField(max_length=20, blank=True)
    sold_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    original_sell_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    objects = StoreAwareManager()

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

class SalesReturn(models.Model):
    sale_item = models.ForeignKey(SaleItem, on_delete=models.PROTECT, related_name='returns')
    customer_name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    recommendations = models.TextField(blank=True, null=True)
    return_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-return_date']


# ... existing imports ...

class StockAdjustment(models.Model):
    ADJUSTMENT_TYPE_CHOICES = [
        ('increase', 'Increase Stock'),
        ('decrease', 'Decrease Stock'),
        ('transfer', 'Stock Transfer'),
    ]

    product = models.ForeignKey('Product', on_delete=models.PROTECT, related_name='adjustments')
    from_store = models.ForeignKey(
        'Store', on_delete=models.PROTECT, related_name='adjustments_out',
        null=True, blank=True
    )
    to_store = models.ForeignKey(
        'Store', on_delete=models.PROTECT, related_name='adjustments_in',
        null=True, blank=True
    )
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPE_CHOICES)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    adjusted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    adjustment_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-adjustment_date']

    def __str__(self):
        if self.adjustment_type == 'transfer':
            return f"Transfer {self.quantity} of {self.product} from {self.from_store} → {self.to_store}"
        return f"{self.get_adjustment_type_display()} {self.quantity} of {self.product}"

    def clean(self):
        super().clean()
        if self.adjustment_type == 'transfer':
            if not self.from_store or not self.to_store:
                raise ValidationError("Both from_store and to_store are required for transfer.")
            if self.from_store_id == self.to_store_id:
                raise ValidationError("From and To stores cannot be the same.")
        elif self.adjustment_type == 'increase':
            if not self.to_store:
                raise ValidationError("to_store is required for increase.")
        elif self.adjustment_type == 'decrease':
            if not self.from_store:
                raise ValidationError("from_store is required for decrease.")

    