from django.urls import path

from . import views

app_name = 'gym_user'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('goals/', views.goal_list, name='goal_list'),
    path('goals/new/', views.goal_create, name='goal_create'),
    path('goals/<int:goal_id>/edit/', views.goal_edit, name='goal_edit'),
    path('goals/<int:goal_id>/complete/', views.goal_complete, name='goal_complete'),
    path('goals/<int:goal_id>/uncomplete/', views.goal_uncomplete, name='goal_uncomplete'),
    path('goals/<int:goal_id>/cancel/', views.goal_cancel, name='goal_cancel'),
    path('schedule/', views.schedule_view, name='schedule'),
    path('schedule/events/', views.calendar_events, name='calendar_events'),
    path('schedule/monthly/new/', views.monthly_schedule_create, name='monthly_schedule_create'),
    path('schedule/monthly/<int:schedule_id>/edit/', views.monthly_schedule_edit, name='monthly_schedule_edit'),
    path('schedule/monthly/<int:schedule_id>/delete/', views.monthly_schedule_delete, name='monthly_schedule_delete'),
    path('schedule/weekly/', views.weekly_schedule, name='weekly_schedule'),
    path('schedule/weekly/new/', views.weekly_schedule_create, name='weekly_schedule_create'),
    path('schedule/weekly/<int:schedule_id>/edit/', views.weekly_schedule_edit, name='weekly_schedule_edit'),
    path('schedule/weekly/<int:schedule_id>/delete/', views.weekly_schedule_delete, name='weekly_schedule_delete'),
    path('schedule/new/', views.schedule_create, name='schedule_create'),
    path('schedule/<int:schedule_id>/edit/', views.schedule_edit, name='schedule_edit'),
    path('schedule/<int:schedule_id>/delete/', views.schedule_delete, name='schedule_delete'),
    path('workouts/', views.workout_select, name='workout_select'),
    path('workouts/assigned/<int:assignment_id>/complete/', views.assigned_plan_complete, name='assigned_plan_complete'),
    path('workouts/assigned/<int:assignment_id>/uncomplete/', views.assigned_plan_uncomplete, name='assigned_plan_uncomplete'),
    path('log/', views.log_activity, name='log_activity'),
    path('progress/', views.progress_view, name='progress'),
    path('progress/measurements/new/', views.measurement_create, name='measurement_create'),
    path('profile/', views.profile_view, name='profile'),
    path('recommendations/', views.recommendation_list, name='recommendation_list'),
    path('recommendations/<int:recommendation_id>/read/', views.recommendation_mark_read, name='recommendation_mark_read'),
    path('recommendations/<int:recommendation_id>/unread/', views.recommendation_unmark_read, name='recommendation_unmark_read'),
    path('recommendations/<int:recommendation_id>/complete/', views.recommendation_mark_completed, name='recommendation_mark_completed'),
    path('recommendations/<int:recommendation_id>/uncomplete/', views.recommendation_unmark_completed, name='recommendation_unmark_completed'),
    path('recommendations/<int:recommendation_id>/cancel/', views.recommendation_cancel, name='recommendation_cancel'),
    path('messages/', views.messages_view, name='messages'),
]
