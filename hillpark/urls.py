"""
URL configuration for hillpark project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = "🛒 HillPark POS"
admin.site.site_title = "POS Control Panel"
admin.site.index_title = "Inventory & Sales Dashboard"

urlpatterns = [
    path('', include('authentication.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('admin/', admin.site.urls),
    path('store/', include('store.urls')),
    path('pos/', include('pos.urls')),
    path('sales', include('sales.urls')),
    path('select2/', include('django_select2.urls')),
    path('customer', include('customer.urls')),
    path('reports/', include('reports.urls')),
    path('orders/', include('orders.urls')),
    path('invoices/', include('invoices.urls')),
    path('notifications/', include('notifications.urls')),
    path('settings/', include('settings.urls')),
    path('expenses/', include('expenses.urls')),
    path('installments/', include('installment.urls')),
    path('backup/', include('backup.urls')),
]


urlpatterns += static(settings.MEDIA_URL,
                      document_root=settings.MEDIA_ROOT)