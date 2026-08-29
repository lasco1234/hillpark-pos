from decimal import Decimal, InvalidOperation
from notifications.services import notify_order_created
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.db import transaction

from store.models import Store, Product
from .models import SupplierOrder, SupplierOrderItem
from .services import generate_order_pdf, send_order_email, whatsapp_url, build_order_text
from datetime import datetime, timedelta
from django.core.paginator import Paginator
from django.utils import timezone
# ... keep all your existing imports ...


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


def _dec(val, default=Decimal('0')):
    try:
        if val is None or str(val).strip() == '':
            return default
        return Decimal(str(val).replace(',', ''))
    except (InvalidOperation, ValueError):
        return default




@login_required
def order_list(request):
    stores = _user_stores(request)
    store_id = request.GET.get('store_id')
    store = _resolve_store(request, store_id)
    if store is None and stores.exists():
        store = stores.first()

    orders = SupplierOrder.objects.none()
    period = request.GET.get('period', 'all')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    period_label = 'All Time'

    if store:
        orders = (
            SupplierOrder.objects
            .filter(store=store)
            .prefetch_related('items')
            .order_by('-created_at')
        )

        today = timezone.localdate()

        if period == 'today':
            orders = orders.filter(created_at__date=today)
            period_label = 'Today'
        elif period == 'week':
            start = today - timedelta(days=today.weekday())  # Monday
            orders = orders.filter(created_at__date__gte=start, created_at__date__lte=today)
            period_label = 'This Week'
        elif period == 'month':
            start = today.replace(day=1)
            orders = orders.filter(created_at__date__gte=start, created_at__date__lte=today)
            period_label = 'This Month'
        elif period == 'year':
            start = today.replace(month=1, day=1)
            orders = orders.filter(created_at__date__gte=start, created_at__date__lte=today)
            period_label = 'This Year'
        elif period == 'custom' and start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                orders = orders.filter(created_at__date__gte=start, created_at__date__lte=end)
                period_label = f'{start.strftime("%d %b %Y")} – {end.strftime("%d %b %Y")}'
            except ValueError:
                period = 'all'
                period_label = 'All Time'
        else:
            period = 'all'
            period_label = 'All Time'

    # Pagination
    paginator = Paginator(orders, 25)  # 25 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'orders/order_list.html', {
        'stores': stores,
        'store': store,
        'orders': page_obj,          # current page of orders
        'page_obj': page_obj,        # for pagination controls
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'period_label': period_label,
    })


@login_required
def order_create(request):
    stores = _user_stores(request)
    store_id = request.GET.get('store_id') or request.POST.get('store_id')
    store = _resolve_store(request, store_id)
    if store is None and stores.exists():
        store = stores.first()

    products_qs = (
        Product.objects.filter(store=store, is_deleted=False).order_by('product_name')
        if store else Product.objects.none()
    )

    # Prepare products for searchable dropdown (json_script)
    products_data = [
        {
            'id': p.pk,
            'pk': p.pk,
            'product_name': p.product_name or '',
            'display_name': getattr(p, 'display_name', None) or p.product_name or '',
            'buy_price': float(p.buy_price or 0),
            'product_group': getattr(p, 'product_group', '') or '',
            'variant': getattr(p, 'variant', '') or '',
            'unit_type': getattr(p, 'unit_type', '') or '',
        }
        for p in products_qs
    ]

    if request.method == 'POST':
        if not store:
            messages.error(request, "Please select a store.")
            return redirect('orders:order_create')

        supplier_name = (request.POST.get('supplier_name') or '').strip()
        supplier_email = (request.POST.get('supplier_email') or '').strip()
        supplier_phone = (request.POST.get('supplier_phone') or '').strip()
        notes = (request.POST.get('notes') or '').strip()

        if not supplier_name:
            messages.error(request, "Supplier name is required.")
            return redirect(f"/orders/create/?store_id={store.pk}")

        # Existing products
        product_ids = request.POST.getlist('product_id')
        product_qtys = request.POST.getlist('product_qty')
        product_prices = request.POST.getlist('product_price')

        # New products
        new_names = request.POST.getlist('new_name')
        new_descs = request.POST.getlist('new_desc')
        new_qtys = request.POST.getlist('new_qty')
        new_prices = request.POST.getlist('new_price')

        items_to_create = []

        for pid, qty_s, price_s in zip(product_ids, product_qtys, product_prices):
            if not pid:
                continue
            qty = int(_dec(qty_s, 0))
            if qty < 1:
                continue
            try:
                prod = Product.objects.get(pk=pid, store=store)
            except Product.DoesNotExist:
                continue
            price = _dec(price_s, prod.buy_price or 0)
            items_to_create.append({
                'product': prod,
                'product_name': prod.product_name,
                'description': '',
                'quantity': qty,
                'unit_price': price,
                'is_new_product': False,
            })

        for name, desc, qty_s, price_s in zip(new_names, new_descs, new_qtys, new_prices):
            name = (name or '').strip()
            if not name:
                continue
            qty = int(_dec(qty_s, 0))
            if qty < 1:
                continue
            items_to_create.append({
                'product': None,
                'product_name': name,
                'description': (desc or '').strip(),
                'quantity': qty,
                'unit_price': _dec(price_s),
                'is_new_product': True,
            })

        if not items_to_create:
            messages.error(request, "Add at least one product (existing or new).")
            return redirect(f"/orders/create/?store_id={store.pk}")

        with transaction.atomic():
            order = SupplierOrder.objects.create(
                store=store,
                supplier_name=supplier_name,
                supplier_email=supplier_email or None,
                supplier_phone=supplier_phone or None,
                notes=notes,
                created_by=request.user,
                status='draft',
            )
            for it in items_to_create:
                SupplierOrderItem.objects.create(order=order, **it)

                # === NOTIFICATION ===
        try:
            notify_order_created(order, created_by=request.user)
        except Exception:
            pass

        messages.success(request, f"Order {order.order_number} created.")
        return redirect('orders:order_detail', pk=order.pk)

    return render(request, 'orders/order_create.html', {
        'stores': stores,
        'store': store,
        'products': products_data,   # list of dicts for {{ products|json_script:"products-data" }}
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(SupplierOrder.objects.prefetch_related('items'), pk=pk)
    store = _resolve_store(request, order.store_id)
    if not store:
        messages.error(request, "Permission denied.")
        return redirect('orders:order_list')

    wa_link = whatsapp_url(order) if order.supplier_phone else None
    preview_text = build_order_text(order)

    return render(request, 'orders/order_detail.html', {
        'order': order,
        'wa_link': wa_link,
        'preview_text': preview_text,
    })


@login_required
def order_pdf(request, pk):
    order = get_object_or_404(SupplierOrder.objects.prefetch_related('items'), pk=pk)
    store = _resolve_store(request, order.store_id)
    if not store:
        return HttpResponse("Permission denied", status=403)

    buf = generate_order_pdf(order)
    resp = HttpResponse(buf.getvalue(), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{order.order_number}.pdf"'
    return resp


@login_required
@require_POST
def order_send_email(request, pk):
    order = get_object_or_404(SupplierOrder.objects.prefetch_related('items'), pk=pk)
    store = _resolve_store(request, order.store_id)
    if not store:
        messages.error(request, "Permission denied.")
        return redirect('orders:order_list')

    ok, msg = send_order_email(order)
    if ok:
        messages.success(request, msg)
    else:
        messages.error(request, msg)
    return redirect('orders:order_detail', pk=order.pk)


@login_required
@require_POST
def order_mark_sent(request, pk):
    """Mark as sent after user opened WhatsApp."""
    order = get_object_or_404(SupplierOrder, pk=pk)
    store = _resolve_store(request, order.store_id)
    if not store:
        return JsonResponse({'ok': False}, status=403)
    from django.utils import timezone
    order.status = 'sent'
    order.sent_at = timezone.now()
    order.save(update_fields=['status', 'sent_at'])
    return JsonResponse({'ok': True})