from django.urls import path
from . import views

urlpatterns = [
    path('', views.store_home, name='store_home'),
    path('Add_product/', views.Add_product, name='Add_product'),
    path('product_list/', views.product_list, name='product_list'),
    path('product/<int:id>/', views.product_detail, name='product_detail'),
    path('product/delete/<int:pk>/', views.delete_product, name='delete_product'),
    path("trash/", views.trash_products, name="trash_products"),
    path("restore/<int:pk>/", views.restore_product, name="restore_product"),
    path("permanent_delete/<int:pk>/", views.permanent_delete, name="permanent_delete"),
    path('trash/bulk-action/', views.bulk_trash_action, name='bulk_trash_action'),
    path('update-product/<int:pk>/', views.update_product, name='update_product'),
    path('stores/', views.store_list, name='store_list'),
    path('stores/add/', views.add_store, name='add_store'),
    path('stores/<int:pk>/edit/', views.edit_store, name='edit_store'),
    path('stores/<int:pk>/delete/', views.delete_store, name='delete_store'),
    path('stock-adjustment/', views.stock_adjustment, name='stock_adjustment'),
    path('save-stock-adjustments/', views.save_stock_adjustments, name='save_stock_adjustments'),
    path('stock-levels/', views.stock_levels, name='stock_levels'),
    path('stock/export/excel/', views.export_stock_excel, name='export_stock_excel'),
    path('stock/export/pdf/', views.export_stock_pdf, name='export_stock_pdf'),
    path('live_stock_records/', views.live_stock_records, name='live_stock_records'),

    
]