from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Daily full report
    path('daily/', views.daily_report_page, name='daily_report'),
    path('daily/save/', views.save_daily_data, name='save_daily_data'),
    path('daily/download/', views.download_daily_report, name='download_daily_report'),
    path('daily/expense/<int:pk>/delete/', views.delete_cash_out, name='delete_cash_out'),
    path('daily/note/<int:pk>/delete/', views.delete_note, name='delete_note'),

    # Period reports
    path('expenses/', views.expenses_report_page, name='expenses_report'),
    path('stock/', views.stock_report_page, name='stock_report'),
    path('sales/', views.sales_report_page, name='sales_report'),
    path('export/', views.export_period_report, name='export_period'),
]