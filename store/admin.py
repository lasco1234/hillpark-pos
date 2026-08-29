from django.contrib import admin
from .models import Product
from .models import Sale
from .models import SaleItem
from django.utils.html import format_html


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    # Columns shown in admin list
    list_display = (
        'image_preview',
        'product_name',
        'category',
        'sell_price',
        'buy_price',
        'initial_stock',
        'unit_type',
        'created_at',
        'is_deleted',
    )

    # Search box
    search_fields = (
        'product_name',
        'category',
        'manufacturer',
    )

    # Right-side filters
    list_filter = (
        'category',
        'unit_type',
        'tax_type',
        'discount_type',
        'is_deleted',
        'created_at',
    )

    # Default ordering
    ordering = ('-created_at',)

    # Clickable link
    list_display_links = ('product_name',)

    # Records per page
    list_per_page = 20

    # Read-only fields
    readonly_fields = (
        'created_at',
        'updated_at',
        'deleted_at',
    )

    # Organize form into sections
    fieldsets = (

        ('Basic Information', {
            'fields': (
                'product_name',
                'category',
                'description',
                'product_image',
            )
        }),

        ('Pricing', {
            'fields': (
                'buy_price',
                'sell_price',
                'wholesale_price',
            )
        }),

        ('Stock Management', {
            'fields': (
                'initial_stock',
                'reorder_level',
                'low_stock_alert_quantity',
                'unit_type',
            )
        }),

        ('Tax & Discount', {
            'fields': (
                'tax_type',
                'tax_amount',
                'discount_type',
                'discount_value',
            )
        }),

        ('Manufacturer & Warranty', {
            'fields': (
                'has_manufacturer',
                'manufacturer',
                'has_warranty',
                'warranty_details',
            )
        }),

        ('Expiry', {
            'fields': (
                'has_expiry_date',
                'expiry_date',
            )
        }),

        ('System Information', {
            'classes': ('collapse',),
            'fields': (
                'created_at',
                'updated_at',
                'is_deleted',
                'deleted_at',
            )
        }),
    )

    def image_preview(self, obj):
        if obj.product_image:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius:5px;" />',
                obj.product_image.url
            )
        return "No Image"

    image_preview.short_description = "Image"



class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = (
        'product_name',
        'category',
        'unit_type',
        'sold_price',
        'quantity',
        'subtotal',
        'original_sell_price',
    )
    can_delete = False

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'sale_date',
        'total_amount',
        'items_count',
    )

    list_filter = (
        'sale_date',
    )

    search_fields = (
        'id',
    )

    readonly_fields = (
        'sale_date',
        'total_amount',
        'items_count',
        'created_at',
    )

    inlines = [SaleItemInline]

    ordering = ('-sale_date',)

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):

    list_display = (
        'sale',
        'product_name',
        'quantity',
        'sold_price',
        'subtotal',
    )

    list_filter = (
        'sale',
        'category',
    )

    search_fields = (
        'product_name',
    )

    readonly_fields = (
        'sale',
        'product',
        'product_name',
        'category',
        'unit_type',
        'sold_price',
        'quantity',
        'subtotal',
        'original_sell_price',
    )
