from django.urls import path
from . import views

urlpatterns = [
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customer/customer_list/', views.customer_list, name='customer_list'),

]