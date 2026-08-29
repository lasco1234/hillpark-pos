from django.urls import path
from . import views

urlpatterns = [
    path('', views.pos_home, name='pos_home'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('get-cart/', views.get_cart, name='get_cart'),
    path('remove-from-cart/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('clear-cart/', views.clear_cart, name='clear_cart'),
    path('complete-sale/', views.complete_sale, name='complete_sale'),
   
]