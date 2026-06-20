from django.urls import path

from . import views

app_name = 'health_advisor'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('users/', views.assigned_users, name='assigned_users'),
    path('users/<int:user_id>/', views.user_profile, name='user_profile'),
    path('diet-plans/', views.diet_plan_list, name='diet_plan_list'),
    path('diet-plans/new/', views.diet_plan_create, name='diet_plan_create'),
    path('diet-plans/<int:user_id>/edit/', views.diet_plan_update, name='diet_plan_update'),
    path('diet-plans/detail/<int:plan_id>/', views.diet_plan_detail, name='diet_plan_detail'),
    path('diet-plans/detail/<int:plan_id>/edit/', views.diet_plan_edit, name='diet_plan_edit'),
    path('recommendations/', views.recommendation_list, name='recommendation_list'),
    path('recommendations/<int:user_id>/new/', views.recommendation_send, name='recommendation_send'),
    path('recommendations/<int:recommendation_id>/edit/', views.recommendation_edit, name='recommendation_edit'),
    path('messages/', views.message_list, name='messages'),
    path('messages/<int:user_id>/', views.message_thread, name='message_thread'),
]
