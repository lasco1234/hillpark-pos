from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from store.models import Sale, SaleItem, SalesReturn
from reports.models import CashOut          # ← add this
from .forms import SalesReturnForm         # adjust if needed
from django.core.paginator import Paginator

from notifications.utils import (
    check_stock_and_notify,
    notify_new_sale,
    notify_sales_return,
    notify_invoice_paid,
    notify_supplier_order_received,
    notify_large_cash_out,
)


@login_required
def sales_history(request):
    """Display sales for the current user's store with optional time filtering"""

    sales = Sale.objects.for_user(request.user).order_by('-sale_date')

    # ---------- Time filtering ----------
    period = request.GET.get('period', 'all')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # We also need pure date objects for CashOut (it uses DateField)
    filter_start_date = None
    filter_end_date = None

    if period == 'today':
        sales = sales.filter(sale_date__gte=today_start)
        filter_start_date = today_start.date()
        filter_end_date = today_start.date()
        period_label = "Today"

    elif period == 'week':
        week_start = today_start - timedelta(days=today_start.weekday())
        sales = sales.filter(sale_date__gte=week_start)
        filter_start_date = week_start.date()
        filter_end_date = now.date()
        period_label = "This Week"

    elif period == 'month':
        month_start = today_start.replace(day=1)
        sales = sales.filter(sale_date__gte=month_start)
        filter_start_date = month_start.date()
        filter_end_date = now.date()
        period_label = "This Month"

    elif period == 'year':
        year_start = today_start.replace(month=1, day=1)
        sales = sales.filter(sale_date__gte=year_start)
        filter_start_date = year_start.date()
        filter_end_date = now.date()
        period_label = "This Year"

    elif period == 'custom' and start_date and end_date:
        try:
            start = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
            end = timezone.make_aware(
                datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            )
            sales = sales.filter(sale_date__gte=start, sale_date__lt=end)
            filter_start_date = start.date()
            filter_end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            period_label = f"{start_date} → {end_date}"
        except ValueError:
            period_label = "All Time"
            period = 'all'
    else:
        period = 'all'
        period_label = "All Time"

    # ---------- Aggregations ----------
    sales_agg = SaleItem.objects.filter(sale__in=sales).aggregate(
        total_sales=Sum(
            ExpressionWrapper(
                F('quantity') * F('sold_price'),
                output_field=DecimalField()
            )
        ),
        total_buy=Sum(
            ExpressionWrapper(
                F('product__buy_price') * F('quantity'),
                output_field=DecimalField()
            )
        ),
        gross_profit=Sum(
            ExpressionWrapper(
                (F('sold_price') - F('product__buy_price')) * F('quantity'),
                output_field=DecimalField()
            )
        ),
        total_items=Sum('quantity'),
    )

    total_sales = sales_agg['total_sales'] or Decimal('0')
    total_buy = sales_agg['total_buy'] or Decimal('0')          # ← Total Buy Price (COGS)
    gross_profit = sales_agg['gross_profit'] or Decimal('0')
    total_items = sales_agg['total_items'] or 0
    total_sales_count = sales.count()

    # ---------- Expenses (CashOut) ----------
    user = request.user
    is_admin = getattr(user, 'can_see_all', False) or user.is_superuser

    cash_out_qs = CashOut.objects.all()
    if not is_admin and user.store:
        cash_out_qs = cash_out_qs.filter(store=user.store)
    elif not is_admin:
        cash_out_qs = CashOut.objects.none()

    if filter_start_date and filter_end_date:
        cash_out_qs = cash_out_qs.filter(
            date__gte=filter_start_date,
            date__lte=filter_end_date
        )

    total_expenses = cash_out_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # Net profit = Gross profit − Expenses
    total_profit = gross_profit - total_expenses
    paginator = Paginator(sales, 25)          # 25 sales per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'sales': sales,
        'sales': page_obj,                   # use page_obj in the template
        'page_obj': page_obj,
        'sold_price': total_sales,
        'total_profit': total_profit,
        'sold_price': total_sales,           # Total Sales
        'total_buy': total_buy,              # ← Total Buy Price
        'gross_profit': gross_profit,        # optional, if you want to show it
        'total_profit': total_profit,        # Net Profit (after expenses)
        'total_items': total_items,
        'total_sales_count': total_sales_count,
        'total_expenses': total_expenses,          # ← new
        'period': period,
        'period_label': period_label,
        'start_date': start_date or '',
        'end_date': end_date or '',
    }

    return render(request, 'sales_history.html', context)


# ===================== SALE DETAIL =====================
@login_required
def sale_detail(request, sale_id):
    """View details of a specific sale"""
    sale = get_object_or_404(
        Sale.objects.for_user(request.user), 
        id=sale_id
    )
    
    items = sale.items.all()   # SaleItem related_name='items'

    context = {
        'sale': sale,
        'items': items,
    }
    return render(request, 'sale_detail.html', context)


# ===================== SALES RETURN VIEWS =====================

import json
from django.core.serializers.json import DjangoJSONEncoder

from notifications.utils import notify_sales_return


@login_required
def sales_return_create(request):
    if request.method == 'POST':
        form = SalesReturnForm(request.POST, user=request.user)
        if form.is_valid():
            return_obj = form.save()                           # ← FIXED: capture the object

            try:
                notify_sales_return(return_obj)
            except Exception:
                pass

            messages.success(request, "Sales return recorded successfully.")
            return redirect('sales_return_list')
    else:
        form = SalesReturnForm(user=request.user)

    # Only sale items that belong to the current user's store
    sale_items = (
        SaleItem.objects
        .filter(sale__in=Sale.objects.for_user(request.user))
        .select_related('product', 'sale', 'sale__store')
        .order_by('-sale__sale_date', 'product_name')
    )

    sold_products = []
    for item in sale_items:
        # How many already returned for this SaleItem
        already_returned = sum(r.quantity for r in item.returns.all())
        remaining = item.quantity - already_returned
        if remaining <= 0:
            continue  # fully returned → skip

        display = item.product_name
        if item.product and item.product.product_group and item.product.variant:
            display = f"{item.product.product_group} ({item.product.variant})"

        sold_products.append({
            'id': item.id,
            'display_name': display,
            'product_name': item.product_name,
            'sale_id': item.sale_id,
            'sale_date': item.sale.sale_date.strftime('%d %b %Y %H:%M') if item.sale else '',
            'qty_sold': item.quantity,
            'qty_remaining': remaining,
            'sold_price': float(item.sold_price or 0),
            'store': item.sale.store.name if item.sale and item.sale.store else '',
        })

    context = {
        'form': form,
        'sold_products_json': json.dumps(sold_products, cls=DjangoJSONEncoder),
    }
    return render(request, 'sales_return/sales_return_form.html', context)


from django.core.paginator import Paginator

@login_required
def sales_return_list(request):
    """List returns for current user's store (paginated)"""
    returns_qs = (
        SalesReturn.objects
        .select_related(
            'sale_item',
            'sale_item__product',
            'sale_item__sale'
        )
        .filter(
            sale_item__sale__in=Sale.objects.for_user(request.user)
        )
        .order_by('-return_date')
    )

    paginator = Paginator(returns_qs, 25)          # 25 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'returns': page_obj,      # current page
        'page_obj': page_obj,     # for pagination controls
    }
    return render(request, 'sales_return/sales_return_list.html', context)


@login_required
def sales_return_detail(request, pk):
    sales_return = get_object_or_404(
        SalesReturn.objects.select_related(
            'sale_item',
            'sale_item__product',
            'sale_item__sale'
        ).filter(
            sale_item__sale__in=Sale.objects.for_user(request.user)
        ),
        pk=pk
    )
    
    context = {'sales_return': sales_return}
    return render(request, 'sales_return/sales_return_detail.html', context)