from django.urls import path
from . import views

app_name = 'settings'

urlpatterns = [
    path('', views.settings_home, name='home'),
    path('system/', views.system_settings, name='system'),
    path('store/', views.store_settings_view, name='store'),                    # current user's store
    path('store/<int:store_id>/', views.store_settings_view, name='store'),    # admin can choose store
]