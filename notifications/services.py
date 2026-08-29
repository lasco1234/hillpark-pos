from __future__ import annotations

import logging
from decimal import Decimal
from typing import List, Optional, Sequence

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db.models import Q
from django.utils import timezone
from django.utils.html import strip_tags

from .models import Notification
from notifications.models import NotificationPreference

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers to resolve recipients
# ---------------------------------------------------------------------------

def get_owners(store=None) -> List:
    """Users who can see all stores (Admin / superuser / role=admin)."""
    admin_role = _role_value("ADMIN", "admin")
    qs = User.objects.filter(is_active=True).filter(
        Q(is_superuser=True) | Q(role=admin_role)
    )
    return list(qs.distinct())


def _role_value(name: str, default: str) -> str:
    if hasattr(User, "Role") and hasattr(User.Role, name):
        return getattr(User.Role, name)
    return default


def get_managers(store=None) -> List:
    qs = User.objects.filter(is_active=True, role=_role_value("MANAGER", "manager"))
    if store is not None:
        qs = qs.filter(store=store)
    return list(qs)


def get_cashiers(store=None) -> List:
    qs = User.objects.filter(is_active=True, role=_role_value("CASHIER", "cashier"))
    if store is not None:
        qs = qs.filter(store=store)
    return list(qs)


def get_store_staff(store) -> List:
    """Owner + managers + cashiers for a store (owners always included)."""
    users = set(get_owners())
    if store:
        users.update(get_managers(store))
        users.update(get_cashiers(store))
        users.update(User.objects.filter(is_active=True, store=store))
    return list(users)


def get_owner_emails() -> List[str]:
    return [u.email for u in get_owners() if u.email]


# ---------------------------------------------------------------------------
# Core: create in-app notification
# ---------------------------------------------------------------------------

def create_notification(
    *,
    user,
    title: str,
    message: str,
    level: str = "info",
    icon: str = "mdi-bell",
    link: str = "",
    store=None,
    related_object_type: str = "",
    related_object_id: Optional[int] = None,
) -> Optional[Notification]:
    if not user:
        return None
    try:
        return Notification.objects.create(
            user=user,
            title=title[:255],
            message=message,
            level=level if level in dict(Notification.LEVEL_CHOICES) else "info",
            icon=icon or "mdi-bell",
            link=link or "",
            store=store,
            related_object_type=related_object_type or "",
            related_object_id=related_object_id,
            is_read=False,
            created_at=timezone.now(),
        )
    except Exception as e:
        logger.exception("Failed to create notification for %s: %s", user, e)
        return None


def notify_users(
    users: Sequence,
    *,
    title: str,
    message: str,
    level: str = "info",
    icon: str = "mdi-bell",
    link: str = "",
    store=None,
    related_object_type: str = "",
    related_object_id: Optional[int] = None,
    notification_type: str = "",
) -> int:
    count = 0
    seen = set()
    for user in users:
        if not user or user.pk in seen:
            continue
        seen.add(user.pk)

        # === CHECK PREFERENCE ===
        if notification_type and not NotificationPreference.is_enabled(user, notification_type):
            continue

        if create_notification(
            user=user,
            title=title,
            message=message,
            level=level,
            icon=icon,
            link=link,
            store=store,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
        ):
            count += 1
    return count


def notify_owners(
    *,
    title: str,
    message: str,
    level: str = "info",
    icon: str = "mdi-bell",
    link: str = "",
    store=None,
    related_object_type: str = "",
    related_object_id: Optional[int] = None,
) -> int:
    return notify_users(
        get_owners(store),
        title=title,
        message=message,
        level=level,
        icon=icon,
        link=link,
        store=store,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def send_email_notification(
    subject: str,
    message: str,
    recipient_list: Sequence[str],
    html_message: Optional[str] = None,
    from_email: Optional[str] = None,
) -> int:
    """Send plain/HTML email. Returns number of successfully sent messages."""
    recipients = [e for e in recipient_list if e and "@" in e]
    if not recipients:
        logger.warning("No valid email recipients for: %s", subject)
        return 0

    from_email = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
    try:
        if html_message:
            email = EmailMultiAlternatives(
                subject=subject,
                body=strip_tags(message),
                from_email=from_email,
                to=recipients,
            )
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)
            return len(recipients)
        return send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as e:
        logger.exception("Email send failed (%s): %s", subject, e)
        return 0


# ---------------------------------------------------------------------------
# High-level convenience: notify + email
# ---------------------------------------------------------------------------

def full_notify(
    *,
    users: Optional[Sequence] = None,
    title: str,
    message: str,
    level: str = "info",
    icon: str = "mdi-bell",
    link: str = "",
    store=None,
    related_object_type: str = "",
    related_object_id: Optional[int] = None,
    email_subject: Optional[str] = None,
    email_body: Optional[str] = None,
    email_html: Optional[str] = None,
    extra_emails: Optional[Sequence[str]] = None,
    notify_owners_only: bool = False,
    notification_type: str = "",
) -> dict:
    """
    Create in-app notifications and send emails.
    Returns summary dict: {"in_app": N, "emails": N}
    """
    result = {"in_app": 0, "emails": 0}

    if notify_owners_only or users is None:
        users = get_owners(store)
    users = list(users or [])

    result["in_app"] = notify_users(
        users,
        title=title,
        message=message,
        level=level,
        icon=icon,
        link=link,
        store=store,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        notification_type=notification_type,
    )

    emails = set()
    for u in users:
        if getattr(u, "email", None):
            emails.add(u.email)
    if extra_emails:
        emails.update(e for e in extra_emails if e)
    if emails:
        result["emails"] = send_email_notification(
            subject=email_subject or title,
            message=email_body or message,
            recipient_list=list(emails),
            html_message=email_html,
        )

    return result


# ---------------------------------------------------------------------------
# Domain-specific notification builders
# ---------------------------------------------------------------------------

def format_money(value) -> str:
    try:
        v = Decimal(str(value or 0))
        return f"{v:,.0f} TZS"
    except Exception:
        return "0 TZS"


def notify_daily_report(
    *,
    store,
    report_date,
    total_sales,
    total_buy,
    total_expenses,
    net_profit,
    generated_by=None,
):
    """
    Called when a daily sales report is generated / downloaded.
    Sends in-app + email to owners with summary.
    """
    title = f"Daily Report – {store.name} ({report_date})"
    message = (
        f"Daily sales report for {store.name} on {report_date}:\n"
        f"• Total Sales: {format_money(total_sales)}\n"
        f"• Total Buy (COGS): {format_money(total_buy)}\n"
        f"• Expenses: {format_money(total_expenses)}\n"
        f"• Net Profit: {format_money(net_profit)}"
    )
    if generated_by:
        message += f"\nGenerated by: {generated_by.get_username()}"

    html = f"""
    <h2>Daily Report – {store.name}</h2>
    <p><strong>Date:</strong> {report_date}</p>
    <table style="border-collapse:collapse;width:100%;max-width:480px">
      <tr><td>Total Sales</td><td style="text-align:right"><strong>{format_money(total_sales)}</strong></td></tr>
      <tr><td>Total Buy (COGS)</td><td style="text-align:right">{format_money(total_buy)}</td></tr>
      <tr><td>Expenses</td><td style="text-align:right">{format_money(total_expenses)}</td></tr>
      <tr style="border-top:2px solid #333"><td><strong>Net Profit</strong></td>
          <td style="text-align:right"><strong>{format_money(net_profit)}</strong></td></tr>
    </table>
    """

    return full_notify(
        title=title,
        message=message,
        level="info",
        icon="mdi-file-chart",
        link="/reports/daily/",
        store=store,
        related_object_type="daily_report",
        email_subject=title,
        email_body=message,
        email_html=html,
        notify_owners_only=True,
    )


def notify_order_created(order, created_by=None):
    """
    Supplier receives email.
    Owner receives in-app + email.
    """
    store = order.store
    title = f"New Supplier Order {order.order_number}"
    items_summary = ", ".join(
        f"{it.product_name} x{it.quantity}" for it in order.items.all()[:5]
    )
    if order.items.count() > 5:
        items_summary += f" … (+{order.items.count() - 5} more)"

    owner_msg = (
        f"Order {order.order_number} created for {store.name}.\n"
        f"Supplier: {order.supplier_name}\n"
        f"Items: {items_summary}\n"
        f"Total: {format_money(order.total_amount)}"
    )
    if created_by:
        owner_msg += f"\nCreated by: {created_by.get_username()}"

    full_notify(
        title=title,
        message=owner_msg,
        level="success",
        icon="mdi-truck-delivery",
        link=f"/orders/{order.pk}/",
        store=store,
        related_object_type="supplier_order",
        related_object_id=order.pk,
        email_subject=title,
        email_body=owner_msg,
        notify_owners_only=True,
    )

    # Supplier email only
    supplier_body = (
        f"Dear {order.supplier_name},\n\n"
        f"You have a new purchase order from {store.name}.\n"
        f"Order number: {order.order_number}\n"
        f"Items:\n"
    )
    for it in order.items.all():
        supplier_body += (
            f"  - {it.product_name} x {it.quantity} @ {format_money(it.unit_price)}\n"
        )
    supplier_body += f"\nTotal: {format_money(order.total_amount)}\n"
    if order.notes:
        supplier_body += f"\nNotes: {order.notes}\n"
    supplier_body += "\nPlease confirm availability and delivery.\nThank you."

    extra_emails = [order.supplier_email] if order.supplier_email else []
    if extra_emails:
        send_email_notification(
            subject=f"Purchase Order {order.order_number} from {store.name}",
            message=supplier_body,
            recipient_list=extra_emails,
        )

    return True


def notify_stock_adjustment(
    product, store, adj_type, quantity, adjusted_by=None, unit_price=None
):
    title = f"Stock {adj_type.title()} – {product.product_name}"
    display = (
        product.display_name
        if hasattr(product, "display_name")
        else product.product_name
    )
    msg = f"Stock {adj_type} of {quantity} unit(s) for {display} at {store.name}."
    if unit_price:
        msg += f" Unit price: {format_money(unit_price)}"
    if adjusted_by:
        msg += f" By: {adjusted_by.get_username()}"

    return full_notify(
        title=title,
        message=msg,
        level="warning" if adj_type == "decrease" else "info",
        icon="mdi-package-variant",
        link="/stock/levels/",
        store=store,
        related_object_type="stock_adjustment",
        related_object_id=product.pk,
        email_subject=title,
        email_body=msg,
        notify_owners_only=True,
    )


def notify_product_added(product, created_by=None):
    title = f"New Product: {product.product_name}"
    display = (
        product.display_name
        if hasattr(product, "display_name")
        else product.product_name
    )
    msg = (
        f'Product "{display}" added to {product.store.name}.\n'
        f"Category: {product.category}\n"
        f"Buy: {format_money(product.buy_price)} | Sell: {format_money(product.sell_price)}\n"
        f"Initial stock: {product.initial_stock}"
    )
    if created_by:
        msg += f"\nAdded by: {created_by.get_username()}"

    return full_notify(
        title=title,
        message=msg,
        level="success",
        icon="mdi-plus-box",
        link=f"/products/{product.pk}/",
        store=product.store,
        related_object_type="product",
        related_object_id=product.pk,
        email_subject=title,
        email_body=msg,
        notify_owners_only=True,
        notification_type="product_added",
    )


def notify_product_updated(product, updated_by=None):
    title = f"Product Updated: {product.product_name}"
    display = (
        product.display_name
        if hasattr(product, "display_name")
        else product.product_name
    )
    msg = f'Product "{display}" was updated in {product.store.name}.'
    if updated_by:
        msg += f" By: {updated_by.get_username()}"

    return full_notify(
        title=title,
        message=msg,
        level="info",
        icon="mdi-pencil",
        link=f"/products/{product.pk}/",
        store=product.store,
        related_object_type="product",
        related_object_id=product.pk,
        email_subject=title,
        email_body=msg,
        notify_owners_only=True,
    )


def notify_product_deleted(product_name, store, deleted_by=None, permanent=False):
    action = "permanently deleted" if permanent else "moved to trash"
    title = f"Product {action.title()}: {product_name}"
    msg = f'Product "{product_name}" was {action} from {store.name}.'
    if deleted_by:
        msg += f" By: {deleted_by.get_username()}"

    return full_notify(
        title=title,
        message=msg,
        level="danger" if permanent else "warning",
        icon="mdi-delete",
        link="/products/trash/" if not permanent else "/products/",
        store=store,
        related_object_type="product",
        email_subject=title,
        email_body=msg,
        notify_owners_only=True,
    )


def notify_store_created(store, created_by=None):
    title = f"New Store Created: {store.name}"
    msg = f'Store "{store.name}" has been created.'
    if store.location:
        msg += f" Location: {store.location}."
    if created_by:
        msg += f" By: {created_by.get_username()}"

    return full_notify(
        title=title,
        message=msg,
        level="success",
        icon="mdi-store",
        link="/store/list/",
        store=store,
        related_object_type="store",
        related_object_id=store.pk,
        email_subject=title,
        email_body=msg,
        notify_owners_only=True,
    )


def notify_installment_created(installment, created_by=None):
    """
    Notify owner, manager, cashier (store staff) + optional customer email.
    """
    store = installment.store
    title = f"New Installment INST-{installment.id}"
    msg = (
        f"Installment INST-{installment.id} created for {installment.customer_name} "
        f"({installment.customer_phone}) at {store.name}.\n"
        f"Total: {format_money(installment.total_amount)}\n"
        f"Due date: {installment.due_date or 'N/A'}"
    )
    if created_by:
        msg += f"\nCreated by: {created_by.get_username()}"

    staff = get_store_staff(store)
    return full_notify(
        users=staff,
        title=title,
        message=msg,
        level="success",
        icon="mdi-calendar-clock",
        link=f"/installment/{installment.pk}/",
        store=store,
        related_object_type="installment",
        related_object_id=installment.pk,
        email_subject=title,
        email_body=msg,
        extra_emails=[installment.customer_email] if installment.customer_email else None,
    )


def notify_installment_reminder(installment):
    """
    Reminder when installment is approaching / past due.
    Sent to customer (email), cashier, owner, manager.
    """
    store = installment.store
    days = installment.days_overdue
    if days <= 0:
        status_txt = f"due on {installment.due_date}"
        level = "info"
    elif installment.is_in_grace_period:
        status_txt = f"{days} day(s) overdue (grace period)"
        level = "warning"
    else:
        status_txt = f"{days} day(s) overdue – late fee may apply"
        level = "danger"

    title = f"Installment Reminder INST-{installment.id}"
    msg = (
        f"Reminder: Installment INST-{installment.id} for {installment.customer_name} "
        f"is {status_txt}.\n"
        f"Balance: {format_money(installment.balance)}\n"
        f"Store: {store.name}"
    )

    staff = get_store_staff(store)
    return full_notify(
        users=staff,
        title=title,
        message=msg,
        level=level,
        icon="mdi-bell-alert",
        link=f"/installment/{installment.pk}/",
        store=store,
        related_object_type="installment",
        related_object_id=installment.pk,
        email_subject=title,
        email_body=msg,
        extra_emails=[installment.customer_email] if installment.customer_email else None,
    )


def notify_installment_completed(installment):
    store = installment.store
    title = f"Installment Completed INST-{installment.id}"
    msg = (
        f"Installment INST-{installment.id} for {installment.customer_name} "
        f"has been fully paid and completed at {store.name}. "
        f"Total paid: {format_money(installment.amount_paid)}"
    )
    staff = get_store_staff(store)
    return full_notify(
        users=staff,
        title=title,
        message=msg,
        level="success",
        icon="mdi-check-circle",
        link=f"/installment/{installment.pk}/",
        store=store,
        related_object_type="installment",
        related_object_id=installment.pk,
        email_subject=title,
        email_body=msg,
    )


def notify_user_registered(new_user, registered_by=None):
    """Notify owners when a new user account is created."""
    title = f"New User Registered: {new_user.username}"
    role_display = (
        new_user.get_role_display()
        if hasattr(new_user, "get_role_display")
        else getattr(new_user, "role", "—")
    )
    store_name = (
        new_user.store.name
        if getattr(new_user, "store", None)
        else "None (Admin)"
    )
    msg = (
        f"New account created:\n"
        f"• Username: {new_user.username}\n"
        f"• Name: {new_user.get_full_name() or '—'}\n"
        f"• Email: {new_user.email or '—'}\n"
        f"• Phone: {getattr(new_user, 'phone', None) or '—'}\n"
        f"• Role: {role_display}\n"
        f"• Store: {store_name}"
    )
    if registered_by:
        msg += f"\nRegistered by: {registered_by.get_username()}"

    return full_notify(
        title=title,
        message=msg,
        level="success",
        icon="mdi-account-plus",
        link="/admin/authentication/customuser/",
        store=getattr(new_user, "store", None),
        related_object_type="user",
        related_object_id=new_user.pk,
        email_subject=title,
        email_body=msg,
        notify_owners_only=True,
    )

