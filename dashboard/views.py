from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages

from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth, TruncDate
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json
from django.contrib.auth.decorators import login_required
from notifications.models import Notification   # ← import this

from customer.models import Customer
from store.models import Product, Stock, Sale, SaleItem, Store
from invoices.models import Invoice
from orders.models import SupplierOrder
from reports.models import CashOut 

@login_required(login_url='login')
def home(request):
    return render(request, 'home.html')

# UI Elements
def buttons(request):
    return render(request, 'pages/ui-features/buttons.html')

def dropdowns(request):
    return render(request, 'pages/ui-features/dropdowns.html')

def typography(request):
    return render(request, 'pages/ui-features/typography.html')

# Forms
def forms(request):
    return render(request, 'pages/forms/basic_elements.html')

# Tables
def tables(request):
    return render(request, 'pages/tables/basic-table.html')

# Charts
def charts(request):
    return render(request, 'pages/charts/chartjs.html')

# Icons
def icons(request):
    return render(request, 'pages/icons/mdi.html')

# Auth pages
def blank_page(request):
    return render(request, 'pages/samples/blank-page.html')

def error_404(request):
    return render(request, 'pages/samples/error-404.html')

def login(request):
    return render(request, 'pages/samples/login.html')

def register(request):
    return render(request, 'pages/samples/register.html')

def error_404(request):
    return render(request, "pages/samples/error-404.html")

def error_500(request):
    return render(request, "pages/samples/error-500.html")


@login_required(login_url='login')
def dashboard_main(request):
    user = request.user
    is_admin = getattr(user, 'can_see_all', False) or user.is_superuser

    # ---------- Period filter ----------
    period = request.GET.get('period', 'all')
    today = timezone.localdate()

    if period == '7d':
        start_date = today - timedelta(days=6)
        end_date = today
        period_label = "Last 7 Days"
    elif period == '30d':
        start_date = today - timedelta(days=29)
        end_date = today
        period_label = "Last 30 Days"
    elif period == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
        period_label = "This Month"
    elif period == 'this_year':
        start_date = today.replace(month=1, day=1)
        end_date = today
        period_label = "This Year"
    else:
        start_date = None
        end_date = None
        period_label = "All Time"

    # ---------- Base querysets ----------
    if is_admin:
        customers_qs = Customer.objects.all()
        products_qs = Product.objects.filter(is_deleted=False)
        stocks_qs = Stock.objects.select_related('product')
        sales_qs = Sale.objects.all()
        invoices_qs = Invoice.objects.all()
        orders_qs = SupplierOrder.objects.all()
        current_store = None
    else:
        if not getattr(user, 'store', None):
            return render(request, 'dashboard_main.html', {
                'error': 'You are not assigned to any store.'
            })
        store = user.store
        current_store = store
        customers_qs = Customer.objects.filter(store=store)
        products_qs = Product.objects.filter(store=store, is_deleted=False)
        stocks_qs = Stock.objects.filter(store=store).select_related('product')
        sales_qs = Sale.objects.filter(store=store)
        invoices_qs = Invoice.objects.filter(store=store)
        orders_qs = SupplierOrder.objects.filter(store=store)

    # Apply date filter
    if start_date:
        sales_qs = sales_qs.filter(sale_date__date__gte=start_date, sale_date__date__lte=end_date)
        invoices_qs = invoices_qs.filter(issue_date__gte=start_date, issue_date__lte=end_date)

    # ===================== KPIs =====================
    total_customers = customers_qs.count()
    company_customers = customers_qs.filter(customer_type='Company').count()
    individual_customers = customers_qs.filter(customer_type='Individual').count()
    group_customers = customers_qs.filter(customer_type='Group').count()
    school_customers = customers_qs.filter(customer_type='School').count()

    total_products = products_qs.count()
    cash_out_qs = CashOut.objects.all()

    stock_value = stocks_qs.aggregate(
        total=Sum(F('quantity') * F('product__buy_price'))
    )['total'] or Decimal('0')

    total_expenses = cash_out_qs.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

    # Stock status
    low_stock_count = 0
    out_of_stock_count = 0
    in_stock_count = 0
    low_stock_list = []

    for product in products_qs.select_related('store'):
        stock = stocks_qs.filter(product=product).first()
        qty = stock.quantity if stock else (getattr(product, 'initial_stock', 0) or 0)
        reorder = getattr(product, 'reorder_level', 0) or 0

        if qty == 0:
            out_of_stock_count += 1
        elif qty <= reorder:
            low_stock_count += 1
            low_stock_list.append({
                'name': product.product_name,
                'qty': qty,
                'reorder': reorder,
                'store': product.store.name if is_admin else None
            })
        else:
            in_stock_count += 1

    # Sales
    sales_agg = SaleItem.objects.filter(sale__in=sales_qs).aggregate(
        total_sales=Sum(
            ExpressionWrapper(
                F('quantity') * F('sold_price'),
                output_field=DecimalField()
            )
        ),
        total_profit=Sum(
            ExpressionWrapper(
                (F('sold_price') - F('product__buy_price')) * F('quantity'),
                output_field=DecimalField()
            )
        ),
        total_items=Sum('quantity')
    )

    total_sales = sales_agg['total_sales'] or Decimal('0')
    gross_profit = sales_agg['total_profit'] or Decimal('0')
    total_expenses = cash_out_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # Net profit = Gross profit − Expenses
    total_profit = gross_profit - total_expenses

    total_items_sold = sales_agg['total_items'] or 0
    total_sales_count = sales_qs.count()
    # Invoices
    total_invoices = invoices_qs.count()
    proforma_count = invoices_qs.filter(doc_type='proforma').count()
    invoice_count = invoices_qs.filter(doc_type='invoice').count()
    delivery_count = invoices_qs.filter(doc_type='delivery').count()

    # Orders
    total_orders = orders_qs.count()
    draft_orders = orders_qs.filter(status='draft').count()
    sent_orders = orders_qs.filter(status='sent').count()

    # ===================== CHART DATA =====================
    if period in ['7d', '30d']:
        sales_trend = (
            sales_qs.annotate(day=TruncDate('sale_date'))
            .values('day')
            .annotate(total=Sum('total_amount'))
            .order_by('day')
        )
        sales_labels = [item['day'].strftime('%d %b') for item in sales_trend]
        sales_data = [float(item['total'] or 0) for item in sales_trend]
    else:
        sales_trend = (
            sales_qs.annotate(month=TruncMonth('sale_date'))
            .values('month')
            .annotate(total=Sum('total_amount'))
            .order_by('month')
        )
        sales_labels = [item['month'].strftime('%b %Y') for item in sales_trend]
        sales_data = [float(item['total'] or 0) for item in sales_trend]

    customer_type_labels = ['Company', 'Individual', 'Group', 'School']
    customer_type_data = [company_customers, individual_customers, group_customers, school_customers]

    stock_status_labels = ['In Stock', 'Low Stock', 'Out of Stock']
    stock_status_data = [in_stock_count, low_stock_count, out_of_stock_count]

    invoice_type_labels = ['Invoice', 'Proforma', 'Delivery']
    invoice_type_data = [invoice_count, proforma_count, delivery_count]

    top_products = (
        SaleItem.objects.filter(sale__in=sales_qs)
        .values('product_name')
        .annotate(qty=Sum('quantity'))
        .order_by('-qty')[:8]
    )
    top_product_labels = [item['product_name'][:22] for item in top_products]
    top_product_data = [item['qty'] for item in top_products]

    # Recent
    recent_sales = sales_qs.select_related('store').order_by('-sale_date')[:6]
    recent_invoices = invoices_qs.order_by('-issue_date')[:5]
    recent_orders = orders_qs.order_by('-id')[:5]

    # Add these two lines
    recent_notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:6]   # show latest 6

    unread_count = Notification.objects.filter(
        user=request.user, 
        is_read=False
    ).count()

    

    context = {
        'is_admin': is_admin,
        'current_store': current_store,
        'period': period,
        'period_label': period_label,
        'total_expenses': total_expenses,
        'total_customers': total_customers,
        'company_customers': company_customers,
        'individual_customers': individual_customers,
        'group_customers': group_customers,
        'school_customers': school_customers,
        'total_products': total_products,
        'stock_value': stock_value,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'in_stock_count': in_stock_count,
        'total_sales': total_sales,
        'total_profit': total_profit,
        'total_items_sold': total_items_sold,
        'total_sales_count': total_sales_count,
        'total_invoices': total_invoices,
        'proforma_count': proforma_count,
        'invoice_count': invoice_count,
        'delivery_count': delivery_count,
        'total_orders': total_orders,
        'draft_orders': draft_orders,
        'sent_orders': sent_orders,

        'low_stock_list': low_stock_list[:8],
        'recent_sales': recent_sales,
        'recent_invoices': recent_invoices,
        'recent_orders': recent_orders,

        # Chart data
        'sales_labels': json.dumps(sales_labels),
        'sales_data': json.dumps(sales_data),
        'customer_type_labels': json.dumps(customer_type_labels),
        'customer_type_data': json.dumps(customer_type_data),
        'stock_status_labels': json.dumps(stock_status_labels),
        'stock_status_data': json.dumps(stock_status_data),
        'invoice_type_labels': json.dumps(invoice_type_labels),
        'invoice_type_data': json.dumps(invoice_type_data),
        'top_product_labels': json.dumps(top_product_labels),
        'top_product_data': json.dumps(top_product_data),

        'recent_notifications': recent_notifications,
        'unread_count': unread_count,
    }
    return render(request, 'dashboard_main.html', context)
