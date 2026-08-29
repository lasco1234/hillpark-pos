"""
INTEGRATION SNIPPETS
====================
Copy the relevant blocks into your existing views.
Import at the top of each file:

    from notifications.services import (
        notify_daily_report,
        notify_order_created,
        notify_stock_adjustment,
        notify_product_added,
        notify_product_updated,
        notify_product_deleted,
        notify_store_created,
        notify_installment_created,
        notify_installment_reminder,
        notify_installment_completed,
    )

--------------------------------------------------------------------
1. DAILY REPORT  (reports/views.py – download_daily_report or after
   get_day_data is available)
--------------------------------------------------------------------
Inside download_daily_report (or a dedicated "send report" button),
after you have the numbers:

    # After building data / before returning the file response
    from reports.services import get_day_data   # you already have this
    from decimal import Decimal

    data = get_day_data(store, report_date)
    # Adapt field names to whatever get_day_data returns
    total_sales = data.get('total_sales') or data.get('sales_total') or 0
    total_buy = data.get('total_buy') or data.get('cogs') or 0
    total_expenses = data.get('total_expenses') or sum(
        (c.amount for c in data.get('cash_outs', [])), 0
    )
    net_profit = (Decimal(str(total_sales)) - Decimal(str(total_buy))
                  - Decimal(str(total_expenses)))

    try:
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
        pass   # never break the download

Alternatively call it from sales_history when period == 'today'
if you prefer the sales history page to trigger it.

--------------------------------------------------------------------
2. ORDER CREATED  (orders/views.py – order_create)
--------------------------------------------------------------------
After:
    with transaction.atomic():
        order = SupplierOrder.objects.create(...)
        for it in items_to_create:
            SupplierOrderItem.objects.create(...)

    try:
        notify_order_created(order, created_by=request.user)
    except Exception:
        pass

    messages.success(...)
    return redirect(...)

--------------------------------------------------------------------
3. STOCK ADJUSTMENT  (store/views.py – save_stock_adjustments)
--------------------------------------------------------------------
Inside the loop, after StockAdjustment.objects.create(...):

    try:
        notify_stock_adjustment(
            product=product,
            store=store,
            adj_type=adj_type,
            quantity=quantity,
            adjusted_by=request.user,
            unit_price=new_unit_price if new_unit_price else None,
        )
    except Exception:
        pass

--------------------------------------------------------------------
4. PRODUCT ADDED  (store/views.py – Add_product)
--------------------------------------------------------------------
After product.save() and before the JsonResponse success:

    try:
        notify_product_added(product, created_by=request.user)
    except Exception:
        pass

--------------------------------------------------------------------
5. PRODUCT UPDATED  (store/views.py – update_product)
--------------------------------------------------------------------
After updated_product.save():

    try:
        notify_product_updated(updated_product, updated_by=request.user)
    except Exception:
        pass

--------------------------------------------------------------------
6. PRODUCT DELETED / TRASH  (store/views.py – delete_product)
--------------------------------------------------------------------
After product.save(skip_validation=True):

    try:
        notify_product_deleted(
            product_name=product.product_name,
            store=product.store,
            deleted_by=request.user,
            permanent=False,
        )
    except Exception:
        pass

And in permanent_delete / bulk delete, use permanent=True.
Capture product_name and store BEFORE deleting:

    product_name = product.product_name
    store = product.store
    # ... delete ...
    try:
        notify_product_deleted(
            product_name=product_name,
            store=store,
            deleted_by=request.user,
            permanent=True,
        )
    except Exception:
        pass

--------------------------------------------------------------------
7. STORE CREATED  (store/views.py – add_store)
--------------------------------------------------------------------
After form.save():

    store = form.save()
    try:
        notify_store_created(store, created_by=request.user)
    except Exception:
        pass

--------------------------------------------------------------------
8. INSTALLMENT CREATED  (installment/views.py – installment_create)
--------------------------------------------------------------------
After installment.recalculate() and before redirect:

    try:
        notify_installment_created(installment, created_by=request.user)
    except Exception:
        pass

--------------------------------------------------------------------
9. INSTALLMENT COMPLETED  (installment/views.py – inside final payment)
--------------------------------------------------------------------
After installment.status = 'completed' and save:

    try:
        notify_installment_completed(installment)
    except Exception:
        pass

--------------------------------------------------------------------
10. INSTALLMENT REMINDERS
--------------------------------------------------------------------
Option A – call from installment_list / installment_detail when
status == 'active' and due_date is near or past:

    if installment.status == 'active' and installment.due_date:
        # Optional: only send once per day – use a flag or cache
        try:
            notify_installment_reminder(installment)
        except Exception:
            pass

Option B – management command (recommended for production):

    python manage.py send_installment_reminders

See notifications/management/commands/send_installment_reminders.py
"""