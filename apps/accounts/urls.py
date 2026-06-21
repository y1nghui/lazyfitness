from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('redirect/', views.redirect_view, name='redirect'),
    path('account/', views.account_edit, name='account_edit'),
    path('password/change/', views.password_change, name='password_change'),
    path('password/forgot/', views.forgot_password, name='forgot_password'),
    path('feedback/submit/', views.submit_feedback, name='submit_feedback'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/all/read/', views.notification_mark_all_read, name='notification_mark_all_read'),
    path('notifications/all/opened/', views.notification_mark_all_opened, name='notification_mark_all_opened'),
    path('notifications/<int:notification_id>/open/', views.notification_open, name='notification_open'),
    path('notifications/<int:notification_id>/read/', views.notification_mark_read, name='notification_mark_read'),
    path('notifications/<int:notification_id>/unread/', views.notification_unmark_read, name='notification_unmark_read'),
]
