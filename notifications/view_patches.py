"""
Ready-to-paste patches for the main views.
Only the changed / added lines are shown.
"""

# =============================================================================
# store/views.py
# =============================================================================

# --- Add near the top imports ---
# from notifications.services import (
#     notify_product_added,
#     notify_product_updated,
#     notify_product_deleted,
#     notify_store_created,
#     notify_stock_adjustment,
# )

# ---------- Add_product (after product.save()) ----------
"""
            product.save()

            try:
                from notifications.services import notify_product_added
                notify_product_added(product, created_by=request.user)
            except Exception:
                pass

            return JsonResponse({
                "success": True,
                "message": "Product added successfully!",
                ...
"""

# ---------- update_product (after updated_product.save()) ----------
"""
            updated_product.save()

            try:
                from notifications.services import notify_product_updated
                notify_product_updated(updated_product, updated_by=request.user)
            except Exception:
                pass

            return JsonResponse({
                "success": True,
                "message": "Product updated successfully!"
            })
"""

# ---------- delete_product ----------
"""
    product.is_deleted = True
    product.deleted_at = timezone.now()
    product.save(skip_validation=True)

    try:
        from notifications.services import notify_product_deleted
        notify_product_deleted(
            product_name=product.product_name,
            store=product.store,
            deleted_by=request.user,
            permanent=False,
        )
    except Exception:
        pass

    messages.success(request, "Product moved to trash.")
    return redirect("product_list")
"""

# ---------- permanent_delete (inside the atomic block, after product.delete()) ----------
"""
            product.delete()

        try:
            from notifications.services import notify_product_deleted
            notify_product_deleted(
                product_name=product_name,
                store=product.store,   # capture store before delete if needed
                deleted_by=request.user,
                permanent=True,
            )
        except Exception:
            pass
"""
# Note: capture store = product.store and product_name before deleting.

# ---------- add_store (after form.save()) ----------
"""
        if form.is_valid():
            store = form.save()
            try:
                from notifications.services import notify_store_created
                notify_store_created(store, created_by=request.user)
            except Exception:
                pass
            messages.success(request, "Store created successfully!")
            return redirect('store_list')
"""

# ---------- save_stock_adjustments (after StockAdjustment.objects.create) ----------
"""
                StockAdjustment.objects.create(
                    product=product,
                    to_store=store if adj_type == 'increase' else None,
                    from_store=store if adj_type == 'decrease' else None,
                    adjustment_type=adj_type,
                    quantity=quantity,
                    unit_price=new_unit_price,
                    adjusted_by=request.user,
                )

                try:
                    from notifications.services import notify_stock_adjustment
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
"""

# =============================================================================
# orders/views.py – order_create
# =============================================================================
"""
        with transaction.atomic():
            order = SupplierOrder.objects.create(...)
            for it in items_to_create:
                SupplierOrderItem.objects.create(order=order, **it)

        try:
            from notifications.services import notify_order_created
            notify_order_created(order, created_by=request.user)
        except Exception:
            pass

        messages.success(request, f"Order {order.order_number} created.")
        return redirect('orders:order_detail', pk=order.pk)
"""

# =============================================================================
# installment/views.py
# =============================================================================

# ---------- installment_create (after recalculate) ----------
"""
                    installment.recalculate()

                    try:
                        from notifications.services import notify_installment_created
                        notify_installment_created(installment, created_by=request.user)
                    except Exception:
                        pass

                    messages.success(request, f"Installment #INST-{installment.id} created successfully.")
                    return redirect('installment:installment_detail', pk=installment.pk)
"""

# ---------- installment_detail – final payment success block ----------
"""
                        installment.status = 'completed'
                        installment.completed_at = timezone.now()
                        installment.save(update_fields=['status', 'completed_at'])

                        try:
                            from notifications.services import notify_installment_completed
                            notify_installment_completed(installment)
                        except Exception:
                            pass

                        messages.success(
                            request,
                            f"Final payment recorded. Installment completed and Sale #{sale.id} created successfully."
                        )
"""

# =============================================================================
# reports/views.py – download_daily_report (or a dedicated send button)
# =============================================================================
"""
    # After you have store + report_date and can compute the numbers:

    from decimal import Decimal
    from reports.services import get_day_data
    from notifications.services import notify_daily_report

    data = get_day_data(store, report_date)
    # Adjust keys to match your get_day_data implementation
    total_sales = Decimal(str(data.get('total_sales') or data.get('sales_total') or 0))
    total_buy = Decimal(str(data.get('total_buy') or data.get('cogs') or 0))
    cash_outs = data.get('cash_outs') or []
    total_expenses = sum((getattr(c, 'amount', 0) or 0) for c in cash_outs)
    total_expenses = Decimal(str(total_expenses))
    net_profit = total_sales - total_buy - total_expenses

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
        pass

    # then continue with generating excel/pdf/word as before
"""