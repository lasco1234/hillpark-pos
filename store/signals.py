from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product, Stock


@receiver(post_save, sender=Product)
def create_or_update_stock(sender, instance, created, **kwargs):
    """
    Automatically create Stock record when a new Product is created.
    Also update stock quantity if initial_stock is changed.
    """
    if created:
        # New product → create stock with initial_stock
        Stock.objects.create(
            product=instance,
            store=instance.store,
            quantity=instance.initial_stock
        )
    else:
        # Existing product updated → update stock quantity if initial_stock changed
        try:
            stock = Stock.objects.get(product=instance, store=instance.store)
            if stock.quantity != instance.initial_stock:
                stock.quantity = instance.initial_stock
                stock.save()
        except Stock.DoesNotExist:
            # Fallback: create if somehow missing
            Stock.objects.create(
                product=instance,
                store=instance.store,
                quantity=instance.initial_stock
            )