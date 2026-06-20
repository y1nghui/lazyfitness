from django.contrib import admin
from .models import AdminProfile, SystemLog, FAQ, Feedback, LoginActivity, AssignmentHistory


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('admin_name', 'user')
    search_fields = ('admin_name', 'user__username', 'user__email')


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ('event', 'module', 'performed_by', 'timestamp')
    list_filter = ('event', 'module')
    search_fields = ('description', 'performed_by__username', 'performed_by__email')


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ('username', 'role', 'successful', 'ip_address', 'login_timestamp')
    list_filter = ('successful', 'role')
    search_fields = ('username', 'user__email', 'ip_address')


admin.site.register(FAQ)
admin.site.register(Feedback)


@admin.register(AssignmentHistory)
class AssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = ('gym_user', 'old_coach', 'new_coach', 'old_health_advisor', 'new_health_advisor', 'changed_by', 'changed_at')
    list_filter = ('changed_at', 'old_coach', 'new_coach', 'old_health_advisor', 'new_health_advisor')
    search_fields = ('gym_user__user_name', 'changed_by__username', 'note')
