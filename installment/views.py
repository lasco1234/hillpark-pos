from notifications.services import (
    notify_installment_created,
    notify_installment_completed,
    notify_installment_reminder,
)
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from store.models import Store, Product, Stock, Sale, SaleItem
from .models import Installment, InstallmentItem, InstallmentPayment
from .forms import InstallmentForm, InstallmentPaymentForm


def _user_stores(request):
    if getattr(request.user, 'can_see_all', False) or request.user.is_superuser:
        return Store.objects.filter(is_active=True)
    if getattr(request.user, 'store', None):
        return Store.objects.filter(pk=request.user.store.pk)
    return Store.objects.none()


@login_required
def installment_list(request):
    stores = _user_stores(request)
    store_id = request.GET.get('store_id')
    status = request.GET.get('status', '')

    if getattr(request.user, 'can_see_all', False) or request.user.is_superuser:
        qs = Installment.objects.select_related('store', 'created_by')
        if store_id:
            qs = qs.filter(store_id=store_id)
    else:
        qs = Installment.objects.filter(store=request.user.store).select_related('store', 'created_by')

    if status:
        qs = qs.filter(status=status)

    # Apply late fees for display (optional but useful)
    for inst in qs:
        if inst.status == 'active':
            inst.apply_late_fee_if_needed()

    return render(request, 'installment/installment_list.html', {
        'installments': qs,
        'stores': stores,
        'selected_store': store_id,
        'selected_status': status,
    })


@login_required
def installment_create(request):
    stores = _user_stores(request)
    if not stores.exists():
        messages.error(request, "No store available.")
        return redirect('installment:installment_list')

    if request.method == 'POST':
        form = InstallmentForm(request.POST, user=request.user)
        product_ids = request.POST.getlist('product_id')
        quantities = request.POST.getlist('quantity')
        prices = request.POST.getlist('unit_price')
        store_id = request.POST.get('store_id')

        store = get_object_or_404(Store, pk=store_id)

        # Permission check
        if not (getattr(request.user, 'can_see_all', False) or request.user.store == store):
            messages.error(request, "Permission denied.")
            return redirect('installment:installment_list')

        if form.is_valid() and product_ids:
            try:
                with transaction.atomic():
                    installment = form.save(commit=False)
                    installment.store = store
                    installment.created_by = request.user
                    installment.due_date = form.cleaned_data['due_date']
                    installment.save()

                    for pid, qty, price in zip(product_ids, quantities, prices):
                        product = Product.objects.get(pk=pid, store=store)
                        qty = int(qty)
                        price = Decimal(str(price))

                        # NOTE: We allow creation even if out of stock
                        InstallmentItem.objects.create(
                            installment=installment,
                            product=product,
                            quantity=qty,
                            unit_price=price,
                        )

                    installment.recalculate()

                    try:
                        notify_installment_created(installment, created_by=request.user)
                    except Exception:
                        pass

                    messages.success(request, f"Installment #INST-{installment.id} created successfully.")
                    return redirect('installment:installment_detail', pk=installment.pk)

            except Product.DoesNotExist:
                messages.error(request, "One of the selected products was not found.")
            except Exception as e:
                messages.error(request, f"Error creating installment: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields and add at least one product.")
    else:
        form = InstallmentForm(user=request.user)

    # Products for searchable dropdown
    products_qs = Product.objects.filter(
        store__in=stores,
        is_deleted=False
    ).select_related('store')

    products = []
    for p in products_qs:
        display_name = (
            f"{p.product_group} ({p.variant})"
            if p.product_group and p.variant
            else p.product_name
        )
        products.append({
            'id': p.id,
            'product_name': p.product_name,
            'display_name': display_name,
            'product_group': p.product_group or '',
            'variant': p.variant or '',
            'unit_type': p.unit_type or '',
            'sell_price': float(p.sell_price or 0),
            'store_id': p.store_id,
        })

    return render(request, 'installment/installment_form.html', {
        'form': form,
        'stores': stores,
        'products': products,
    })


@login_required
def installment_detail(request, pk):
    if getattr(request.user, 'can_see_all', False) or request.user.is_superuser:
        installment = get_object_or_404(
            Installment.objects.select_related('store')
            .prefetch_related('items__product', 'payments__received_by'),
            pk=pk
        )
    else:
        installment = get_object_or_404(
            Installment.objects.select_related('store')
            .prefetch_related('items__product', 'payments__received_by'),
            pk=pk,
            store=request.user.store
        )

    # Apply late fee if needed
    if installment.status == 'active':
        fee = installment.apply_late_fee_if_needed()
        if fee > 0:
            messages.warning(
                request,
                f"Late fee of {fee:,.0f} TZS (3%) has been applied because the grace period has passed."
            )

    payment_form = InstallmentPaymentForm(installment=installment)

    if request.method == 'POST' and 'add_payment' in request.POST:
        if installment.status != 'active':
            messages.error(request, "This installment is not active.")
            return redirect('installment:installment_detail', pk=pk)

        payment_form = InstallmentPaymentForm(request.POST, installment=installment)

        if payment_form.is_valid():
            try:
                with transaction.atomic():
                    payment = payment_form.save(commit=False)
                    payment.installment = installment
                    payment.received_by = request.user
                    payment.save()

                    installment.recalculate()

                    # ========== FINAL PAYMENT → TRY TO COMPLETE ==========
                    if installment.is_fully_paid:
                        # 1. Check stock availability
                        for item in installment.items.all():
                            stock = Stock.objects.filter(
                                product=item.product,
                                store=installment.store
                            ).first()
                            available = stock.quantity if stock else 0

                            if available < item.quantity:
                                # Rollback the payment status conceptually by raising
                                raise ValueError(
                                    f"Cannot complete installment. "
                                    f"Product '{item.product}' has only {available} in stock "
                                    f"(needed {item.quantity}). "
                                    f"Please add stock first before completing."
                                )

                        # 2. Reduce stock + Create Sale
                        sale = Sale.objects.create(
                            store=installment.store,
                            sale_date=timezone.now(),
                            total_amount=installment.total_amount + installment.late_fee,
                            items_count=installment.items.count(),
                        )

                        for item in installment.items.all():
                            # Reduce stock
                            stock = Stock.objects.get(
                                product=item.product,
                                store=installment.store
                            )
                            stock.quantity -= item.quantity
                            stock.save()

                            # Create SaleItem
                            SaleItem.objects.create(
                                sale=sale,
                                product=item.product,
                                product_name=item.product.product_name,
                                category=getattr(item.product, 'category', '') or '',
                                unit_type=getattr(item.product, 'unit_type', '') or '',
                                sold_price=item.unit_price,
                                quantity=item.quantity,
                                subtotal=item.subtotal,
                                original_sell_price=item.product.sell_price,
                            )

                        installment.status = 'completed'
                        installment.completed_at = timezone.now()
                        installment.save(update_fields=['status', 'completed_at'])

                        # === NOTIFICATION ===
                        try:
                            notify_installment_completed(installment)
                        except Exception:
                            pass

                        messages.success(
                            request,
                            f"Final payment recorded. Installment completed and Sale #{sale.id} created successfully."
                        )
                    else:
                        messages.success(request, f"Payment of {payment.amount:,.0f} TZS recorded successfully.")

                    return redirect('installment:installment_detail', pk=pk)

            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Error processing payment: {str(e)}")
        else:
            messages.error(request, "Invalid payment. Please check the amount.")

    return render(request, 'installment/installment_detail.html', {
        'installment': installment,
        'payment_form': payment_form,
    })


@login_required
def installment_cancel(request, pk):
    if request.method != 'POST':
        return redirect('installment:installment_list')

    if getattr(request.user, 'can_see_all', False) or request.user.is_superuser:
        installment = get_object_or_404(Installment, pk=pk)
    else:
        installment = get_object_or_404(Installment, pk=pk, store=request.user.store)

    # Rule: Cannot cancel completed installment
    if installment.status == 'completed':
        messages.error(request, "Completed installments cannot be cancelled.")
        return redirect('installment:installment_detail', pk=pk)

    if installment.status != 'active':
        messages.error(request, "Only active installments can be cancelled.")
        return redirect('installment:installment_detail', pk=pk)

    try:
        with transaction.atomic():
            installment.status = 'cancelled'
            installment.save(update_fields=['status'])
            messages.success(request, "Installment has been cancelled.")
    except Exception as e:
        messages.error(request, f"Error cancelling installment: {str(e)}")

    return redirect('installment:installment_detail', pk=pk)