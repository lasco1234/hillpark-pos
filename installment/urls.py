from django.urls import path
from . import views

app_name = 'installment'

urlpatterns = [
    path('', views.installment_list, name='installment_list'),
    path('create/', views.installment_create, name='installment_create'),
    path('<int:pk>/', views.installment_detail, name='installment_detail'),
    path('<int:pk>/cancel/', views.installment_cancel, name='installment_cancel'),
]