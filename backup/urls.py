from django.urls import path
from . import views

urlpatterns = [
    path('', views.backup_page, name='backup_page'),
    path('create/', views.create_backup, name='create_backup'),
]