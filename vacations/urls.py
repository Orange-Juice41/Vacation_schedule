from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('employee/', views.employee_panel, name='employee_panel'),
    path('hr/', views.hr_panel, name='hr_panel'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('admin-panel/user/add/', views.user_create, name='user_create'),
    path('admin-panel/user/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('admin-panel/user/<int:user_id>/delete/', views.user_delete, name='user_delete'),
]