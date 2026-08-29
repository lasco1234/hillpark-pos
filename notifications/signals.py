# Call this after every sale or stock adjustment

def check_stock_and_notify(product, store):
    from store.models import Stock
    from django.contrib.auth import get_user_model
    from notifications.utils import notify_users

    User = get_user_model()
    stock = Stock.objects.filter(product=product, store=store).first()
    if not stock:
        return

    quantity = stock.quantity
    reorder = product.reorder_level or 5
    low_alert = product.low_stock_alert_quantity or 2

    managers = User.objects.filter(groups__name__in=['Manager', 'Admin'], is_active=True)

    if quantity == 0:
        notify_users(
            users=managers,
            title="Out of Stock",
            message=f"{product.product_name} is now out of stock at {store.name}.",
            level="danger",
            icon="mdi-package-variant-remove",
            link=f"/products/{product.id}/",
            store=store
        )
    elif quantity <= low_alert:
        notify_users(
            users=managers,
            title="Critical Low Stock",
            message=f"{product.product_name} has only {quantity} left at {store.name}.",
            level="danger",
            icon="mdi-package-variant-closed",
            link=f"/products/{product.id}/",
            store=store
        )
    elif quantity <= reorder:
        notify_users(
            users=managers,
            title="Low Stock Alert",
            message=f"{product.product_name} has reached reorder level ({quantity} left).",
            level="warning",
            icon="mdi-package-variant",
            link=f"/products/{product.id}/",
            store=store
        )

def notify_new_sale(sale):
    from notifications.utils import notify_users
    from django.contrib.auth import get_user_model
    User = get_user_model()

    managers = User.objects.filter(groups__name__in=['Manager', 'Admin'])

    # Notify only if sale is big (example: > 500,000 TZS)
    if sale.total_amount >= 500000:
        notify_users(
            users=managers,
            title="Large Sale Completed",
            message=f"Sale of TZS {sale.total_amount:,.0f} completed at {sale.store.name}.",
            level="success",
            icon="mdi-cash-register",
            link=f"/sales/{sale.id}/",
            store=sale.store
        )

def notify_sales_return(return_obj):
    from notifications.utils import notify_users
    from django.contrib.auth import get_user_model
    User = get_user_model()

    managers = User.objects.filter(groups__name__in=['Manager', 'Admin'])

    notify_users(
        users=managers,
        title="Sales Return Processed",
        message=f"Return of {return_obj.quantity} x {return_obj.sale_item.product_name} by {return_obj.customer_name}.",
        level="warning",
        icon="mdi-backup-restore",
        store=return_obj.sale_item.sale.store
    )

def notify_invoice_paid(invoice):
    from notifications.utils import notify_users
    from django.contrib.auth import get_user_model
    User = get_user_model()

    managers = User.objects.filter(groups__name__in=['Manager', 'Admin'])

    notify_users(
        users=managers,
        title="Invoice Paid",
        message=f"Invoice {invoice.number} ({invoice.customer_name}) has been fully paid.",
        level="success",
        icon="mdi-cash-check",
        link=f"/invoices/{invoice.id}/",
        store=invoice.store
    )
def notify_supplier_order_received(order):
    from notifications.utils import notify_users
    from django.contrib.auth import get_user_model
    User = get_user_model()

    managers = User.objects.filter(groups__name__in=['Manager', 'Admin'])

    notify_users(
        users=managers,
        title="Supplier Order Received",
        message=f"Order {order.order_number} from {order.supplier_name} has been received.",
        level="success",
        icon="mdi-truck-check",
        link=f"/supplier-orders/{order.id}/",
        store=order.store
    )

def notify_large_cash_out(cash_out):
    from notifications.utils import notify_users
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if cash_out.amount >= 100000:  # example threshold
        managers = User.objects.filter(groups__name__in=['Manager', 'Admin'])
        notify_users(
            users=managers,
            title="Large Cash Out",
            message=f"Cash out of TZS {cash_out.amount:,.0f} for '{cash_out.purpose}'.",
            level="warning",
            icon="mdi-cash-minus",
            store=cash_out.store
        )