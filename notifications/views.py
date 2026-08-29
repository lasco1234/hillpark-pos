from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import Notification
from django.contrib.auth import get_user_model
from .models import Notification, NotificationPreference, NOTIFICATION_LABELS, NOTIFICATION_CATEGORIES
from django.contrib import messages

User = get_user_model()


@login_required
def all_notifications(request):
    """
    Admin / superuser sees ALL notifications across all stores.
    Non-admin users see only notifications in their own store.
    """
    qs = Notification.objects.select_related("user", "store").all()

    if not request.user.can_see_all:
        # Non-admin: only notifications for their store
        qs = qs.filter(store=request.user.store)

    paginator = Paginator(qs.order_by("-created_at"), 20)
    page = request.GET.get("page")
    notifications = paginator.get_page(page)

    return render(
        request,
        "notifications/all_notifications.html",
        {"notifications": notifications, "is_paginated": paginator.num_pages > 1},
    )


@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk)

    # Security: only the notification's owner or an admin can mark it read
    if not request.user.can_see_all and notification.user != request.user:
        return redirect("all_notifications")

    notification.is_read = True
    notification.save()

    next_url = request.GET.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("all_notifications")


@login_required
def mark_all_notifications_read(request):
    if request.user.can_see_all:
        qs = Notification.objects.all()
    else:
        qs = Notification.objects.filter(store=request.user.store)
    qs.filter(is_read=False).update(is_read=True)
    return redirect("all_notifications")

@login_required
def notification_settings(request):
    """
    Page with toggle switches for all notification types.
    Admin can configure settings for any user.
    """
    # Only admin can view other users' preferences
    target_user = request.user
    if request.user.can_see_all and request.GET.get('user_id'):
        try:
            target_user = User.objects.get(pk=request.GET.get('user_id'))
        except User.DoesNotExist:
            target_user = request.user

    pref = NotificationPreference.get_for_user(target_user)

    if request.method == 'POST':
        # Update all toggles from the submitted form
        for field_name in NOTIFICATION_LABELS.keys():
            value = request.POST.get(field_name) == 'on'
            setattr(pref, field_name, value)
        pref.save()
        messages.success(request, "Notification preferences updated successfully.")
        return redirect('notification_settings')

    context = {
        'pref': pref,
        'target_user': target_user,
        'is_admin': request.user.can_see_all,
        'labels': NOTIFICATION_LABELS,
        'categories': NOTIFICATION_CATEGORIES,
        # For admin: list of users to switch between
        'all_users': User.objects.filter(is_active=True).order_by('username') if request.user.can_see_all else [],
    }
    return render(request, 'notifications/notification_settings.html', context)