from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.expenses_page, name='expenses'),
    path('save/', views.save_expenses, name='save_expenses'),
    path('delete/<int:pk>/', views.delete_expense, name='delete_expense'),
    path('list', views.expenses_list, name='list'),
]