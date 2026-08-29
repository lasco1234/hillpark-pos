from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.order_list, name='order_list'),
    path('create/', views.order_create, name='order_create'),
    path('<int:pk>/', views.order_detail, name='order_detail'),
    path('<int:pk>/pdf/', views.order_pdf, name='order_pdf'),
    path('<int:pk>/send-email/', views.order_send_email, name='order_send_email'),
    path('<int:pk>/mark-sent/', views.order_mark_sent, name='order_mark_sent'),
]