from django.urls import path
from . import views

urlpatterns = [
    path('', views.all_notifications, name='all_notifications'),
    path('mark-read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
    path('mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('', views.all_notifications, name='all_notifications'),

    path('settings/', views.notification_settings, name='notification_settings'),  
]