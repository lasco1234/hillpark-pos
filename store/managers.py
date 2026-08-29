from django.db import models

class StoreAwareManager(models.Manager):
    def for_user(self, user):
        if not user or not user.is_authenticated:
            return self.none()
        if user.can_see_all:
            return self.get_queryset()
        if user.store_id:                      # .store_id avoids a DB hit
            return self.get_queryset().filter(store_id=user.store_id)
        return self.none()