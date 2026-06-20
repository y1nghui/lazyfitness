from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = ('username', 'email', 'role', 'is_active', 'date_joined')
    list_filter   = ('role', 'is_active')
    ordering      = ('username',)
    search_fields = ('username', 'email')
    fieldsets = (
        (None,          {'fields': ('username', 'email', 'password', 'profile_picture')}),
        ('Role',        {'fields': ('role', 'is_active', 'is_staff')}),
        ('Permissions', {'fields': ('groups', 'user_permissions', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {'fields': ('username', 'email', 'role', 'profile_picture', 'password1', 'password2')}),
    )
