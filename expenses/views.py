from datetime import datetime, date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from store.models import Store
from reports.models import CashOut          # ← shared model

from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from calendar import monthrange

from django.core.paginator import Paginator
from django.db.models import Sum



def _user_stores(request):
    stores = Store.objects.filter(is_active=True)
    if not (getattr(request.user, 'can_see_all', False) or request.user.is_superuser):
        if getattr(request.user, 'store', None):
            stores = stores.filter(pk=request.user.store.pk)
    return stores


def _resolve_store(request, store_id=None):
    if store_id:
        store = get_object_or_404(Store, pk=store_id)
    elif getattr(request.user, 'store', None):
        store = request.user.store
    else:
        return None
    is_admin = getattr(request.user, 'can_see_all', False) or request.user.is_superuser
    if not is_admin and store != getattr(request.user, 'store', None):
        return None
    return store


def _dec(value, default=Decimal('0')):
    try:
        default = Decimal(str(default))
    except Exception:
        default = Decimal('0')
    try:
        if value is None or str(value).strip() == '':
            return default.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        d = Decimal(str(value).replace(',', '').strip())
        if not d.is_finite():
            return default.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return default.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _resolve_period(period, start_str=None, end_str=None):
    """Return (start_date, end_date, period_label)"""
    today = date.today()

    if period == 'today':
        return today, today, 'Today'
    if period == 'week':
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end, 'This Week'
    if period == 'month':
        start = today.replace(day=1)
        last = monthrange(today.year, today.month)[1]
        end = today.replace(day=last)
        return start, end, 'This Month'
    if period == 'year':
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
        return start, end, 'This Year'
    if period == 'all':
        return None, None, 'All Time'

    # custom
    try:
        start = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else today
        end = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else today
        if start > end:
            start, end = end, start
        return start, end, f"{start.strftime('%d %b %Y')} → {end.strftime('%d %b %Y')}"
    except (ValueError, TypeError):
        return today, today, 'Today'

@login_required
def expenses_page(request):
    stores = _user_stores(request)
    report_date_str = request.GET.get('date') or date.today().isoformat()
    store_id = request.GET.get('store_id')

    try:
        report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()
    except ValueError:
        report_date = date.today()

    store = _resolve_store(request, store_id)
    if store is None and stores.exists():
        store = stores.first()

    cash_outs = []
    if store:
        cash_outs = list(
            CashOut.objects.filter(store=store, date=report_date).order_by('id')
        )

    return render(request, 'expenses/expenses.html', {
        'stores': stores,
        'store': store,
        'report_date': report_date.isoformat(),
        'cash_outs': cash_outs,
        'today': date.today().isoformat(),
    })

@login_required
@require_POST
def save_expenses(request):
    store_id = request.POST.get('store_id')
    date_str = request.POST.get('date')

    store = _resolve_store(request, store_id)
    if not store:
        messages.error(request, "Store not found or permission denied.")
        return redirect('expenses:expenses')

    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        messages.error(request, "Invalid date.")
        return redirect('expenses:expenses')

    amounts = request.POST.getlist('expense_amount')
    purposes = request.POST.getlist('expense_purpose')
    saved = 0
    MAX_AMOUNT = Decimal('9999999999999.99')

    for amt_s, purpose in zip(amounts, purposes):
        purpose = (purpose or '').strip()
        amt = _dec(amt_s)
        if amt <= 0 or not purpose:
            continue
        if amt > MAX_AMOUNT:
            messages.error(request, f"Amount {amt:,.0f} is too large.")
            continue
        try:
            CashOut.objects.create(
                store=store,
                date=report_date,
                amount=amt,
                purpose=purpose,
            )
            saved += 1
        except Exception as e:
            messages.error(request, f"Could not save '{purpose}': {e}")

    if saved:
        messages.success(request, f"{saved} expense(s) saved.")
    else:
        messages.info(request, "No new expenses were saved.")

    return redirect(f"/expenses/?date={report_date}&store_id={store.pk}")


@login_required
def expenses_list(request):
    """Main expenses list with period filter + pagination + total."""
    stores = _user_stores(request)
    store_id = request.GET.get('store_id')
    period = request.GET.get('period', 'today')
    start_str = request.GET.get('start_date', '')
    end_str = request.GET.get('end_date', '')

    store = _resolve_store(request, store_id)
    if store is None and stores.exists():
        store = stores.first()

    start_date, end_date, period_label = _resolve_period(period, start_str, end_str)

    qs = CashOut.objects.none()
    total_expenses = Decimal('0')
    total_count = 0

    if store:
        qs = CashOut.objects.filter(store=store).order_by('-date', '-id')
        if start_date and end_date:
            qs = qs.filter(date__gte=start_date, date__lte=end_date)
        # else period=all → no date filter

        total_expenses = qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        total_count = qs.count()

    # Pagination (25 per page)
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'expenses/expenses_list.html', {
        'stores': stores,
        'store': store,
        'period': period,
        'start_date': start_date.isoformat() if start_date else '',
        'end_date': end_date.isoformat() if end_date else '',
        'period_label': period_label,
        'page_obj': page_obj,
        'total_expenses': total_expenses,
        'total_count': total_count,
    })


@login_required
@require_POST
def delete_expense(request, pk):
    co = get_object_or_404(CashOut, pk=pk)
    store = _resolve_store(request, co.store_id)
    if not store:
        messages.error(request, "Permission denied.")
        return redirect('expenses:expenses')

    # Only allow deleting expenses from today
    if co.date != date.today():
        messages.error(request, "You can only delete expenses from today.")
        return redirect(f"/expenses/?date={co.date}&store_id={co.store_id}")

    d, sid = co.date, co.store_id
    co.delete()
    messages.success(request, "Expense deleted.")
    return redirect(f"/expenses/?date={d}&store_id={sid}")