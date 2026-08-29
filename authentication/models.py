from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        MANAGER = 'manager', 'Manager'
        CASHIER = 'cashier', 'Cashier'
        WAREHOUSE_STAFF = 'warehouse_staff', 'Warehouse Staff'

    store = models.ForeignKey(
        'store.Store',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Leave empty for Admin who can see all stores"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ADMIN)
    phone = models.CharField(max_length=20, blank=True, null=True, help_text="For SMS e.g. 0712345678")

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} - {self.store.name if self.store else 'Admin'}"

    @property
    def can_see_all(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_admin(self):
        return self.can_see_all