from django.urls import path
from . import views

urlpatterns = [
    path('sales-history/', views.sales_history, name='sales_history'),
    path('sales-history/<int:sale_id>/', views.sale_detail, name='sale_detail'),
    path('sales-return/', views.sales_return_list, name='sales_return_list'),
    path('sales-return/add/', views.sales_return_create, name='sales_return_create'),
    path('sales-return/<int:pk>/', views.sales_return_detail, name='sales_return_detail'),

]