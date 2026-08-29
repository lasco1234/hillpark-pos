from datetime import datetime, date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from store.models import Store
from .models import CashOut, DailyNote, DailyClosing
from notifications.utils import notify_large_cash_out
from notifications.services import notify_daily_report
from notifications.utils import notify_large_cash_out, check_stock_and_notify

from .services import (
    generate_excel_report, generate_pdf_report, generate_word_report,
    get_day_data,
)


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
    """
    Safely convert any value to a Decimal quantized to 2 places.
    Never raises. Always returns a Decimal.
    """
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


@login_required
def daily_report_page(request):
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
    data = None
    closing = None
    if store:
        data = get_day_data(store, report_date)
        closing = DailyClosing.objects.filter(store=store, date=report_date).first()
    return render(request, 'reports/daily_report.html', {
        'stores': stores,
        'store': store,
        'today': date.today().isoformat(),
        'report_date': report_date.isoformat(),
        'data': data,
        'closing': closing,
        'cash_outs': data['cash_outs'] if data else [],
        'notes': data['notes'] if data else [],
    })


@login_required
@require_POST
def save_daily_data(request):
    store_id = request.POST.get('store_id')
    date_str = request.POST.get('date')
    store = _resolve_store(request, store_id)
    if not store:
        messages.error(request, "Store not found or permission denied.")
        return redirect('reports:daily_report')
    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        messages.error(request, "Invalid date.")
        return redirect('reports:daily_report')

    # ── Multiple expenses ──────────────────────────────────────
    amounts = request.POST.getlist('expense_amount')
    purposes = request.POST.getlist('expense_purpose')
    saved_exp = 0

    MAX_AMOUNT = Decimal('9999999999999.99')   # safe for max_digits=16

    for amt_s, purpose in zip(amounts, purposes):
        purpose = (purpose or '').strip()
        amt = _dec(amt_s)

        if amt <= 0 or not purpose:
            continue

        if amt > MAX_AMOUNT:
            messages.error(
                request,
                f"Expense amount {amt:,.0f} is too large. Maximum allowed is {MAX_AMOUNT:,.0f}."
            )
            continue

        try:
            cash_out = CashOut.objects.create(
                store=store,
                date=report_date,
                amount=amt,
                purpose=purpose
            )
            saved_exp += 1

            # === NOTIFICATION: large cash out ===
            if amt >= 100000:
                try:
                    notify_large_cash_out(cash_out)
                except Exception:
                    pass
        except Exception as e:
            messages.error(request, f"Could not save expense '{purpose}': {e}")

    if saved_exp:
        messages.success(request, f"{saved_exp} expense(s) saved.")

    # ── Multiple comments ──────────────────────────────────────
    notes_list = request.POST.getlist('note_text')
    saved_notes = 0
    for text in notes_list:
        text = (text or '').strip()
        if text:
            DailyNote.objects.create(store=store, date=report_date, note=text)
            saved_notes += 1
    if saved_notes:
        messages.success(request, f"{saved_notes} comment(s) saved.")

    # ── Daily closing ──────────────────────────────────────────
    closing, _ = DailyClosing.objects.get_or_create(store=store, date=report_date)

    closing.opening_balance    = _dec(request.POST.get('opening_balance'), closing.opening_balance or 0)
    closing.bank_total         = _dec(request.POST.get('bank_total'), closing.bank_total or 0)
    closing.lipa_namba_total   = _dec(request.POST.get('lipa_namba_total'), closing.lipa_namba_total or 0)
    closing.advance_payments   = _dec(request.POST.get('advance_payments'), closing.advance_payments or 0)
    closing.maintenance_income = _dec(request.POST.get('maintenance_income'), closing.maintenance_income or 0)

    # Recalculate everything
    data = get_day_data(store, report_date)

    closing.stock_in       = _dec(data.get('stock_in', 0))
    closing.stock_out      = _dec(data.get('stock_out', 0))
    closing.opening_stock  = _dec(data.get('opening_stock', 0))
    closing.closing_stock  = _dec(data.get('closing_stock', 0))
    closing.cash_in_hand   = _dec(data.get('cash_in_hand', 0))

    try:
        closing.save()
    except Exception as e:
        messages.error(request, f"Could not save numbers: {e}")
        return redirect(f"/reports/daily/?date={report_date}&store_id={store.pk}")

    messages.success(request, "Daily data saved. Cash in hand and stock updated automatically.")

    # === NOTIFICATION: daily report summary ===
    try:
        total_sales = _dec(data.get('total_sales', data.get('sales_total', 0)))
        total_buy = _dec(data.get('total_buy', data.get('cogs', 0)))
        cash_outs = data.get('cash_outs') or []
        total_expenses = sum((_dec(getattr(c, 'amount', 0))) for c in cash_outs)
        net_profit = total_sales - total_buy - total_expenses

        notify_daily_report(
            store=store,
            report_date=report_date,
            total_sales=total_sales,
            total_buy=total_buy,
            total_expenses=total_expenses,
            net_profit=net_profit,
            generated_by=request.user,
        )
    except Exception:
        pass

    # === STOCK ALERTS: out-of-stock / low-stock after saving daily sales ===
    try:
        from store.models import Product, Stock

        store_products = Product.objects.filter(
            store=store,
            is_deleted=False,
        ).select_related("store")

        for product in store_products:
            check_stock_and_notify(product, store)
    except Exception:
        pass

    # === AUTO BACKUP: create a backup after daily report is saved ===
    try:
        import subprocess, sys
        from pathlib import Path
        from django.conf import settings

        manage_py = Path(settings.BASE_DIR) / "manage.py"
        subprocess.run(
            [sys.executable, str(manage_py), "backup_db"],
            capture_output=True,
            timeout=120,
            cwd=str(settings.BASE_DIR),
        )
    except Exception:
        pass

    return redirect(f"/reports/daily/?date={report_date}&store_id={store.pk}")


@login_required
@require_POST
def delete_cash_out(request, pk):
    co = get_object_or_404(CashOut, pk=pk)
    store = _resolve_store(request, co.store_id)
    if not store:
        messages.error(request, "Permission denied.")
        return redirect('reports:daily_report')

    # Only allow deleting expenses from today
    if co.date != date.today():
        messages.error(request, "You can only delete expenses from today.")
        return redirect(f"/reports/daily/?date={co.date}&store_id={co.store_id}")

    d, sid = co.date, co.store_id
    co.delete()
    messages.success(request, "Expense deleted.")
    return redirect(f"/reports/daily/?date={d}&store_id={sid}")

@login_required
@require_POST
def delete_note(request, pk):
    note = get_object_or_404(DailyNote, pk=pk)
    store = _resolve_store(request, note.store_id)
    if not store:
        messages.error(request, "Permission denied.")
        return redirect('reports:daily_report')
    d, sid = note.date, note.store_id
    note.delete()
    messages.success(request, "Comment deleted.")
    return redirect(f"/reports/daily/?date={d}&store_id={sid}")


@login_required
def download_daily_report(request):
    fmt = request.GET.get('format', 'excel').lower()
    date_str = request.GET.get('date')
    store_id = request.GET.get('store_id')
    if not date_str:
        return JsonResponse({'error': 'Date is required'}, status=400)
    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date'}, status=400)
    store = _resolve_store(request, store_id)
    if not store:
        return JsonResponse({'error': 'Store required or permission denied'}, status=403)

    filename = f"Daily_Report_{store.name}_{report_date.strftime('%Y%m%d')}"

    # === NOTIFICATION: daily report summary (on download) ===
    try:
        data = get_day_data(store, report_date)
        total_sales = _dec(data.get('total_sales', data.get('sales_total', 0)))
        total_buy = _dec(data.get('total_buy', data.get('cogs', 0)))
        cash_outs = data.get('cash_outs') or []
        total_expenses = sum((_dec(getattr(c, 'amount', 0))) for c in cash_outs)
        net_profit = total_sales - total_buy - total_expenses

        notify_daily_report(
            store=store,
            report_date=report_date,
            total_sales=total_sales,
            total_buy=total_buy,
            total_expenses=total_expenses,
            net_profit=net_profit,
            generated_by=request.user,
        )
    except Exception:
        pass

    if fmt == 'excel':
        buf = generate_excel_report(store, report_date)
        resp = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return resp
    if fmt == 'pdf':
        buf = generate_pdf_report(store, report_date)
        resp = HttpResponse(buf.getvalue(), content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        return resp
    if fmt == 'word':
        buf = generate_word_report(store, report_date)
        resp = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        resp['Content-Disposition'] = f'attachment; filename="{filename}.docx"'
        return resp
    return JsonResponse({'error': 'Use format=excel, pdf or word'}, status=400)



# ── shared period helper for views ──
def _period_context(request):
    period = request.GET.get('period', 'daily')
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    store_id = request.GET.get('store_id')

    from .services import resolve_period
    start_date, end_date = resolve_period(period, start_str, end_str)

    stores = _user_stores(request)
    store = _resolve_store(request, store_id)
    if store is None and stores.exists():
        store = stores.first()

    return {
        'stores': stores,
        'store': store,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'start_str': start_date.isoformat(),
        'end_str': end_date.isoformat(),
        'today': date.today().isoformat(),
    }


from django.core.paginator import Paginator

@login_required
def expenses_report_page(request):
    ctx = _period_context(request)
    data = None
    page_obj = None

    if ctx['store']:
        from .services import get_expenses_report
        data = get_expenses_report(ctx['store'], ctx['start_date'], ctx['end_date'])

        # Paginate the items list
        paginator = Paginator(data['items'], 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        data['items'] = page_obj   # template still uses data.items

    ctx['data'] = data
    ctx['page_obj'] = page_obj
    return render(request, 'reports/expenses_report.html', ctx)


@login_required
def sales_report_page(request):
    ctx = _period_context(request)
    data = None
    page_obj = None

    if ctx['store']:
        from .services import get_sales_period_report
        data = get_sales_period_report(ctx['store'], ctx['start_date'], ctx['end_date'])

        paginator = Paginator(data['lines'], 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        data['lines'] = page_obj

    ctx['data'] = data
    ctx['page_obj'] = page_obj
    return render(request, 'reports/sales_report.html', ctx)


@login_required
def stock_report_page(request):
    ctx = _period_context(request)
    data = None
    page_obj = None

    if ctx['store']:
        from .services import get_stock_adjustments_report
        data = get_stock_adjustments_report(ctx['store'], ctx['start_date'], ctx['end_date'])

        paginator = Paginator(data['rows'], 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        data['rows'] = page_obj

    ctx['data'] = data
    ctx['page_obj'] = page_obj
    return render(request, 'reports/stock_report.html', ctx)


@login_required
def export_period_report(request):
    """
    ?type=expenses|stock|sales
    &format=excel|pdf
    &period=daily|weekly|monthly|yearly|custom
    &start=YYYY-MM-DD &end=YYYY-MM-DD
    &store_id=
    """
    report_type = request.GET.get('type', 'expenses')
    fmt = request.GET.get('format', 'excel').lower()
    period = request.GET.get('period', 'daily')
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    store_id = request.GET.get('store_id')

    from .services import (
        resolve_period,
        export_expenses_excel, export_stock_excel, export_sales_excel,
        export_expenses_pdf, export_stock_pdf, export_sales_pdf,
    )

    start_date, end_date = resolve_period(period, start_str, end_str)
    store = _resolve_store(request, store_id)
    if not store:
        return JsonResponse({'error': 'Store required'}, status=400)

    if report_type == 'expenses':
        if fmt == 'pdf':
            buf = export_expenses_pdf(store, start_date, end_date)
            name = f"Expenses_{store.name}_{start_date}_{end_date}.pdf"
            content_type = 'application/pdf'
        else:
            buf = export_expenses_excel(store, start_date, end_date)
            name = f"Expenses_{store.name}_{start_date}_{end_date}.xlsx"
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    elif report_type == 'stock':
        if fmt == 'pdf':
            buf = export_stock_pdf(store, start_date, end_date)
            name = f"Stock_Adjustments_{store.name}_{start_date}_{end_date}.pdf"
            content_type = 'application/pdf'
        else:
            buf = export_stock_excel(store, start_date, end_date)
            name = f"Stock_Adjustments_{store.name}_{start_date}_{end_date}.xlsx"
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    else:  # sales
        if fmt == 'pdf':
            buf = export_sales_pdf(store, start_date, end_date)
            name = f"Sales_{store.name}_{start_date}_{end_date}.pdf"
            content_type = 'application/pdf'
        else:
            buf = export_sales_excel(store, start_date, end_date)
            name = f"Sales_{store.name}_{start_date}_{end_date}.xlsx"
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    resp = HttpResponse(buf.getvalue(), content_type=content_type)
    resp['Content-Disposition'] = f'attachment; filename="{name}"'
    return resp