from .models import Notification, NotificationPreference
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

User = get_user_model()

ICON_MAP = {
    "low_stock": "mdi-package-variant",
    "out_of_stock": "mdi-package-variant-remove",
    "sale": "mdi-cash-register",
    "return": "mdi-backup-restore",
    "invoice": "mdi-file-document",
    "paid": "mdi-cash-check",
    "supplier": "mdi-truck-check",
    "transfer": "mdi-swap-horizontal",
    "cash_out": "mdi-cash-minus",
    "closing": "mdi-calendar-check",
    "customer": "mdi-account-plus",
}


def _get_admin_emails():
    """Get email addresses of all admin users (with a preference record or default)."""
    return list(
        User.objects.filter(
            is_active=True,
            role__in=["admin", "ADMIN"],
            email__isnull=False,
        )
        .exclude(email="")
        .values_list("email", flat=True)
    )


from django.db.models.query import QuerySet


def notify_users(users, title, message, level="info", icon="mdi-bell", link=None, store=None, notification_type=""):
    """
    Create in-app notification for one or multiple users,
    AND send email to all admins.

    Skips users who have disabled the given `notification_type`
    in their NotificationPreference.
    """
    # Handle QuerySet, list, tuple, or single user
    if isinstance(users, QuerySet):
        users = list(users)
    elif not isinstance(users, (list, tuple)):
        users = [users]

    notifications = []
    for user in users:
        if not user:
            continue

        # === CHECK PREFERENCE ===
        if notification_type and not NotificationPreference.is_enabled(user, notification_type):
            continue

        notifications.append(
            Notification(
                user=user,
                title=title,
                message=message,
                level=level,
                icon=icon,
                link=link,
                store=store,
            )
        )

    if notifications:
        Notification.objects.bulk_create(notifications)

    # Send email to all admins
    admin_emails = _get_admin_emails()
    if admin_emails:
        try:
            send_mail(
                subject=title,
                message=message,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                recipient_list=admin_emails,
                fail_silently=True,
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Real-time stock alerts
# ---------------------------------------------------------------------------

def check_stock_and_notify(product, store):
    from store.models import Stock

    stock = Stock.objects.filter(product=product, store=store).first()
    if not stock:
        return

    quantity = stock.quantity

    managers = User.objects.filter(
        is_active=True,
        role__in=["admin", "manager", "ADMIN", "MANAGER"],
    )

    if quantity == 0:
        notify_users(
            users=managers,
            title="Out of Stock",
            message=f"{product.product_name} is now out of stock at {store.name}.",
            level="danger",
            icon="mdi-package-variant-remove",
            link=f"/products/{product.id}/",
            store=store,
            notification_type="out_of_stock",
        )
    elif quantity < 2:
        notify_users(
            users=managers,
            title="Low Stock Alert",
            message=f"{product.product_name} has only {quantity} left at {store.name}.",
            level="warning",
            icon="mdi-package-variant",
            link=f"/products/{product.id}/",
            store=store,
            notification_type="low_stock",
        )


# ---------------------------------------------------------------------------
# Sale notifications
# ---------------------------------------------------------------------------

def notify_new_sale(sale):
    managers = User.objects.filter(
        is_active=True,
        role__in=["admin", "manager", "ADMIN", "MANAGER"],
    )

    if sale.total_amount >= 500000:
        notify_users(
            users=managers,
            title="Large Sale Completed",
            message=f"Sale of TZS {sale.total_amount:,.0f} completed at {sale.store.name}.",
            level="success",
            icon="mdi-cash-register",
            link=f"/sales/{sale.id}/",
            store=sale.store,
            notification_type="new_sale",
        )


def notify_sales_return(return_obj):
    managers = User.objects.filter(
        is_active=True,
        role__in=["admin", "manager", "ADMIN", "MANAGER"],
    )

    notify_users(
        users=managers,
        title="Sales Return Processed",
        message=f"Return of {return_obj.quantity} x {return_obj.sale_item.product_name} by {return_obj.customer_name}.",
        level="warning",
        icon="mdi-backup-restore",
        store=return_obj.sale_item.sale.store,
        notification_type="sales_return",
    )


def notify_invoice_paid(invoice):
    managers = User.objects.filter(
        is_active=True,
        role__in=["admin", "manager", "ADMIN", "MANAGER"],
    )

    notify_users(
        users=managers,
        title="Invoice Paid",
        message=f"Invoice {invoice.number} ({invoice.customer_name}) has been fully paid.",
        level="success",
        icon="mdi-cash-check",
        link=f"/invoices/{invoice.id}/",
        store=invoice.store,
        notification_type="invoice_paid",
    )


def notify_supplier_order_received(order):
    managers = User.objects.filter(
        is_active=True,
        role__in=["admin", "manager", "ADMIN", "MANAGER"],
    )

    notify_users(
        users=managers,
        title="Supplier Order Received",
        message=f"Order {order.order_number} from {order.supplier_name} has been received.",
        level="success",
        icon="mdi-truck-check",
        link=f"/supplier-orders/{order.id}/",
        store=order.store,
        notification_type="supplier_order_received",
    )


def notify_large_cash_out(cash_out):
    if cash_out.amount >= 100000:
        managers = User.objects.filter(
            is_active=True,
            role__in=["admin", "manager", "ADMIN", "MANAGER"],
        )
        notify_users(
            users=managers,
            title="Large Cash Out",
            message=f"Cash out of TZS {cash_out.amount:,.0f} for '{cash_out.purpose}'.",
            level="warning",
            icon="mdi-cash-minus",
            store=cash_out.store,
            notification_type="large_cash_out",
        )