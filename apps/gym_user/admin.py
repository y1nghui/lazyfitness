from django.contrib import admin
from .models import ActivityLog, Conversation, FitnessGoal, GymUser, Message, MonthlyWorkoutSchedule, WorkoutSchedule


@admin.register(GymUser)
class GymUserAdmin(admin.ModelAdmin):
    list_display = ('user_name', 'user', 'profile_completed', 'assigned_coach', 'assigned_advisor')
    list_filter = ('profile_completed', 'assigned_coach', 'assigned_advisor')
    search_fields = ('user_name', 'user__username', 'user__email')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('gym_user', 'coach', 'health_advisor', 'updated_at')
    list_filter = ('coach', 'health_advisor')
    search_fields = ('gym_user__user_name', 'gym_user__user__username', 'coach__coach_name', 'health_advisor__advisor_name')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'created_at')
    search_fields = ('body', 'sender__username', 'conversation__gym_user__user_name')
    list_filter = ('created_at',)


admin.site.register(FitnessGoal)
admin.site.register(WorkoutSchedule)
admin.site.register(MonthlyWorkoutSchedule)
admin.site.register(ActivityLog)
