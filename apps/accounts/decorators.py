"""
Role-based access decorators.
Usage in any view:

    from apps.accounts.decorators import gym_user_required

    @gym_user_required
    def my_view(request): ...
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout


def _role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if not request.user.is_active:
                logout(request)
                messages.error(request, 'Your account is inactive. Please contact an administrator.')
                return redirect('accounts:login')
            if request.user.role != role:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('accounts:redirect')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


gym_user_required      = _role_required('gym_user')
coach_required         = _role_required('fitness_coach')
health_advisor_required = _role_required('health_advisor')
admin_required         = _role_required('admin')
