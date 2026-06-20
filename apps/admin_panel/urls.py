from django.urls import path

from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.user_add, name='user_add'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/reset-password/', views.user_reset_password, name='user_reset_password'),
    path('users/<int:user_id>/assign/', views.user_assign, name='user_assign'),
    path('users/<int:user_id>/delete/', views.user_delete, name='user_delete'),
    path('users/<int:user_id>/toggle/', views.user_toggle, name='user_toggle'),
    path('login-activity/', views.login_activity_list, name='login_activity_list'),
    path('logs/', views.system_log_list, name='system_log_list'),
    path('logs/<int:log_id>/', views.system_log_detail, name='system_log_detail'),
    path('faq/', views.faq_list, name='faq_list'),
    path('faq/new/', views.faq_create, name='faq_create'),
    path('faq/<int:faq_id>/edit/', views.faq_edit, name='faq_edit'),
    path('faq/<int:faq_id>/delete/', views.faq_delete, name='faq_delete'),
    path('feedback/', views.feedback_list, name='feedback_list'),
    path('feedback/<int:feedback_id>/', views.feedback_detail, name='feedback_detail'),
    path('export/users/', views.export_users, name='export_users'),
    path('export/login-activity/', views.export_login_activity, name='export_login_activity'),
    path('export/feedback/', views.export_feedback, name='export_feedback'),
]
