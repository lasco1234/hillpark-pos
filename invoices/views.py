from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from django.utils import timezone

from store.models import Store, Product
from .models import Invoice, InvoiceItem
from .services import generate_invoice_pdf
from django.core.paginator import Paginator


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


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None


@login_required
def invoice_list(request):
    stores = _user_stores(request)
    store = _resolve_store(request, request.GET.get('store_id'))
    if store is None and stores.exists():
        store = stores.first()

    doc_type = request.GET.get('type', '')
    search = (request.GET.get('q') or '').strip()

    qs = Invoice.objects.none()
    if store:
        qs = Invoice.objects.filter(store=store).prefetch_related('items').order_by('-issue_date', '-id')

        if doc_type in ('proforma', 'invoice', 'delivery'):
            qs = qs.filter(doc_type=doc_type)

        if search:
            qs = qs.filter(customer_name__icontains=search)

    # Pagination
    paginator = Paginator(qs, 20)  # 20 per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'invoices/invoice_list.html', {
        'stores': stores,
        'store': store,
        'invoices': page_obj,          # page_obj acts like the list
        'page_obj': page_obj,
        'doc_type': doc_type,
        'search': search,
    })

@login_required
def invoice_create(request):
    stores = _user_stores(request)
    store = _resolve_store(request, request.GET.get('store_id') or request.POST.get('store_id'))
    if store is None and stores.exists():
        store = stores.first()

    products = []
    if store:
        products = Product.objects.filter(store=store, is_deleted=False).order_by('product_name')

    default_type = request.GET.get('type', 'invoice')
    if default_type not in ('proforma', 'invoice', 'delivery'):
        default_type = 'invoice'

    if request.method == 'POST':
        if not store:
            messages.error(request, "Select a store.")
            return redirect('invoices:invoice_create')

        customer_name = (request.POST.get('customer_name') or '').strip()
        if not customer_name:
            messages.error(request, "Customer name is required.")
            return redirect(f"/invoices/create/?store_id={store.pk}&type={default_type}")

        doc_type = request.POST.get('doc_type', 'invoice')
        if doc_type not in ('proforma', 'invoice', 'delivery'):
            doc_type = 'invoice'

        with transaction.atomic():
            inv = Invoice.objects.create(
                store=store,
                doc_type=doc_type,
                customer_name=customer_name,
                customer_phone=(request.POST.get('customer_phone') or '').strip(),
                customer_email=(request.POST.get('customer_email') or '').strip(),
                customer_address=(request.POST.get('customer_address') or '').strip(),
                customer_tin=(request.POST.get('customer_tin') or '').strip(),
                issue_date=_parse_date(request.POST.get('issue_date')) or timezone.localdate(),
                due_date=_parse_date(request.POST.get('due_date')),
                delivery_date=_parse_date(request.POST.get('delivery_date')),
                tax_percent=_dec(request.POST.get('tax_percent')),
                discount=_dec(request.POST.get('discount')),
                amount_paid=_dec(request.POST.get('amount_paid')),
                bank_account=(request.POST.get('bank_account') or '').strip(),  # ← ADD THIS
                notes=(request.POST.get('notes') or '').strip(),
                terms=(request.POST.get('terms') or '').strip() or Invoice._meta.get_field('terms').default,
                reference=(request.POST.get('reference') or '').strip(),
                created_by=request.user,
                status='issued',
            )

            # Existing products
            pids = request.POST.getlist('product_id')
            pqtys = request.POST.getlist('product_qty')
            pprices = request.POST.getlist('product_price')
            for pid, qty_s, price_s in zip(pids, pqtys, pprices):
                if not pid:
                    continue
                qty = int(_dec(qty_s, 0))
                if qty < 1:
                    continue
                try:
                    prod = Product.objects.get(pk=pid, store=store)
                except Product.DoesNotExist:
                    continue
                price = _dec(price_s, prod.sell_price or 0)
                InvoiceItem.objects.create(
                    invoice=inv,
                    product=prod,
                    description=prod.product_name,
                    quantity=qty,
                    unit_price=price,
                )

            # Custom lines
            descs = request.POST.getlist('custom_desc')
            cqtys = request.POST.getlist('custom_qty')
            cprices = request.POST.getlist('custom_price')
            for desc, qty_s, price_s in zip(descs, cqtys, cprices):
                desc = (desc or '').strip()
                if not desc:
                    continue
                qty = int(_dec(qty_s, 0))
                if qty < 1:
                    continue
                InvoiceItem.objects.create(
                    invoice=inv,
                    product=None,
                    description=desc,
                    quantity=qty,
                    unit_price=_dec(price_s),
                )

            if inv.items.count() == 0:
                inv.delete()
                messages.error(request, "Add at least one line item.")
                return redirect(f"/invoices/create/?store_id={store.pk}&type={doc_type}")

            inv.recalculate()

        messages.success(request, f"{inv.doc_title} {inv.number} created.")
        return redirect('invoices:invoice_detail', pk=inv.pk)

    return render(request, 'invoices/invoice_create.html', {
        'stores': stores,
        'store': store,
        'products': products,
        'default_type': default_type,
        'today': timezone.localdate().isoformat(),
    })


@login_required
def invoice_detail(request, pk):
    inv = get_object_or_404(Invoice.objects.prefetch_related('items'), pk=pk)
    if not _resolve_store(request, inv.store_id):
        messages.error(request, "Permission denied.")
        return redirect('invoices:invoice_list')
    return render(request, 'invoices/invoice_detail.html', {'invoice': inv})


@login_required
def invoice_pdf(request, pk):
    inv = get_object_or_404(Invoice.objects.prefetch_related('items'), pk=pk)
    if not _resolve_store(request, inv.store_id):
        return HttpResponse("Permission denied", status=403)
    buf = generate_invoice_pdf(inv)
    resp = HttpResponse(buf.getvalue(), content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{inv.number}.pdf"'
    return resp