# authentication/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def user_created_notify(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from notifications.services import notify_user_registered
        notify_user_registered(instance)
    except Exception:
        pass