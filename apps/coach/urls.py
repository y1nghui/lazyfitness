from django.urls import path

from . import views

app_name = 'coach'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('assigned-users/', views.assigned_users, name='assigned_users'),
    path('assigned-users/<int:user_id>/assign-plan/', views.assign_plan_to_user, name='assign_plan_to_user'),
    path('plans/', views.plan_list, name='plan_list'),
    path('plans/new/', views.plan_create, name='plan_create'),
    path('plans/<int:plan_id>/', views.plan_detail, name='plan_detail'),
    path('plans/<int:plan_id>/assign/', views.plan_assign, name='plan_assign'),
    path('plans/<int:plan_id>/edit/', views.plan_edit, name='plan_edit'),
    path('plans/<int:plan_id>/delete/', views.plan_delete, name='plan_delete'),
    path('plans/<int:plan_id>/workout/new/', views.workout_create, name='workout_create'),
    path('workouts/<int:workout_id>/edit/', views.workout_edit, name='workout_edit'),
    path('workouts/<int:workout_id>/delete/', views.workout_delete, name='workout_delete'),
    path('workouts/<int:workout_id>/exercise/new/', views.exercise_create, name='exercise_create'),
    path('exercises/<int:exercise_id>/edit/', views.exercise_edit, name='exercise_edit'),
    path('exercises/<int:exercise_id>/delete/', views.exercise_delete, name='exercise_delete'),
    path('progress/', views.monitor_progress, name='monitor_progress'),
    path('progress/<int:user_id>/', views.user_progress_detail, name='user_progress_detail'),
    path('feedback/<int:log_id>/', views.feedback_create, name='feedback_create'),
    path('messages/', views.message_list, name='messages'),
    path('messages/<int:user_id>/', views.message_thread, name='message_thread'),
]
