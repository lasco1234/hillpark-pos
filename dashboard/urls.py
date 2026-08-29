from django.urls import path
from . import views
from authentication.views import user_logout

urlpatterns = [
    path('', views.home, name='home'),

    # UI
    path('buttons/', views.buttons, name='buttons'),
    path('dropdowns/', views.dropdowns, name='dropdowns'),
    path('typography/', views.typography, name='typography'),

    # Forms
    path('forms/', views.forms, name='forms'),

    # Tables
    path('tables/', views.tables, name='tables'),

    # Charts
    path('charts/', views.charts, name='charts'),

    # Icons
    path('icons/', views.icons, name='icons'),

    # Pages
    path('blank/', views.blank_page, name='blank_page'),
    path('404/', views.error_404, name='error_404'),
    #path('login/', views.login, name='login'),
    #path('register/', views.register, name='register'),

    path('404/', views.error_404, name='error_404'),
    path('500/', views.error_500, name='error_500'),
    path('home/', views.home, name='home'),
    path('logout/', user_logout, name='logout'),
    path('dashboard/', views.dashboard_main, name='dashboard_main'),
]