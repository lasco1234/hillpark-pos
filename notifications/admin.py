from django.contrib import admin
from .models import Notification, NotificationPreference

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'level', 'is_read', 'store', 'created_at')
    list_filter = ('level', 'is_read', 'store')
    search_fields = ('title', 'message', 'user__username')

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__username',)