from .models import Notification


def notification_badge(request):
    """
    Add unread notification count and recent unread notifications
    to every template context.
    """
    if not request.user.is_authenticated:
        return {
            "unread_count": 0,
            "unread_notifications": [],
        }

    qs = Notification.objects.filter(is_read=False)

    if not request.user.can_see_all:
        qs = qs.filter(store=request.user.store)

    unread = qs.order_by("-created_at")

    return {
        "unread_count": unread.count(),
        "unread_notifications": unread[:5],
    }