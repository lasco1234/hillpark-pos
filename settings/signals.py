from django.db.models.signals import post_save
from django.dispatch import receiver
from store.models import Store
from .models import StoreSettings

@receiver(post_save, sender=Store)
def create_store_settings(sender, instance, created, **kwargs):
    if created:
        StoreSettings.objects.get_or_create(store=instance)