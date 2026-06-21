from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from .forms import AccountEditForm, RegistrationForm, LoginForm, StyledPasswordChangeForm
from .models import User
from .signals import ensure_role_profile
from lazyfitness.public_team import get_public_care_team
from apps.admin_panel.models import Feedback
from apps.gym_user.models import Notification


def _client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _record_login_activity(request, user=None, username='', successful=True):
    try:
        from apps.admin_panel.models import LoginActivity, SystemLog
        attempted_username = (username or getattr(user, 'username', '') or request.POST.get('username', '')).strip()
        activity_user = user
        if not activity_user and attempted_username:
            activity_user = User.objects.filter(username__iexact=attempted_username).first() or User.objects.filter(email__iexact=attempted_username).first()
        LoginActivity.objects.create(
            user=activity_user if activity_user else None,
            username=attempted_username,
            role=getattr(activity_user, 'role', '') if activity_user else '',
            ip_address=_client_ip(request) or None,
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            successful=successful,
        )
        if successful and user:
            SystemLog.record('login', f"{user.username} logged in successfully", user=user, module='Authentication')
    except Exception:
        pass


def _resolve_login_identifier(identifier):
    identifier = (identifier or '').strip()
    if '@' in identifier:
        match = User.objects.filter(email__iexact=identifier).first()
        if match:
            return match.username
    return identifier


def register_view(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            ensure_role_profile(user)
            messages.success(request, 'Account created! Please log in with your username or email.')
            return redirect('accounts:login')
        messages.error(request, 'Please correct the highlighted registration errors.')
    else:
        form = RegistrationForm()
    context = {'form': form}
    context.update(get_public_care_team(limit=3))
    return render(request, 'accounts/register.html', context)


def login_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        resolved_username = _resolve_login_identifier(identifier)
        mutable_data = request.POST.copy()
        mutable_data['username'] = resolved_username
        form = LoginForm(request, data=mutable_data)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                _record_login_activity(request, user=user, username=identifier, successful=False)
                messages.error(request, 'This account is deactivated. Please contact an administrator.')
                return render(request, 'accounts/login.html', {'form': form, **get_public_care_team(limit=3)})
            ensure_role_profile(user)
            login(request, user)
            _record_login_activity(request, user=user, username=identifier or user.username, successful=True)
            messages.success(request, 'Login successfully')
            return redirect('accounts:redirect')
        _record_login_activity(request, username=identifier, successful=False)
        messages.error(request, 'Invalid username/email or password.')
    else:
        form = LoginForm()
    context = {'form': form}
    context.update(get_public_care_team(limit=3))
    return render(request, 'accounts/login.html', context)


def forgot_password(request):
    """Public contact-admin page instead of email password reset."""
    context = get_public_care_team(limit=3)
    return render(request, 'accounts/forgot_password.html', context)


@login_required
def notifications(request):
    from apps.gym_user.models import Notification

    notifications_qs = list(Notification.objects.filter(recipient=request.user)[:50])
    unread_ids = [item.pk for item in notifications_qs if not item.is_read]
    if unread_ids:
        Notification.objects.filter(pk__in=unread_ids).update(is_read=True)
        for item in notifications_qs:
            item.is_read = True
    return render(request, 'accounts/notifications.html', {'notifications': notifications_qs})


@login_required
def notification_open(request, notification_id):
    from apps.gym_user.models import Notification
    from lazyfitness.view_helpers import safe_next_url, role_fallback_url

    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    notification.is_read = True
    notification.is_opened = True
    notification.save(update_fields=['is_read', 'is_opened'])
    return redirect(safe_next_url(notification.url, role_fallback_url(request.user)))


@login_required
def notification_mark_all_read(request):
    from apps.gym_user.models import Notification

    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read. New dots remain until each item is opened.')
    return redirect('accounts:notifications')


@login_required
def notification_mark_all_opened(request):
    from apps.gym_user.models import Notification

    Notification.objects.filter(recipient=request.user, is_opened=False).update(is_read=True, is_opened=True)
    messages.success(request, 'All notifications marked as opened.')
    return redirect('accounts:notifications')


@login_required
def notification_mark_read(request, notification_id):
    from apps.gym_user.models import Notification

    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return redirect('accounts:notifications')


@login_required
def notification_unmark_read(request, notification_id):
    from apps.gym_user.models import Notification

    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    notification.is_read = False
    notification.save(update_fields=['is_read'])
    return redirect('accounts:notifications')

@login_required
def submit_feedback(request):
    from apps.admin_panel.forms import FeedbackSubmissionForm
    
    if request.method == 'POST':
        form = FeedbackSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.submitter = request.user
            feedback.save()

            admins = User.objects.filter(role='admin', is_active=True)
            for admin in admins:
                Notification.objects.create(
                    recipient=admin,
                    title=f'New {feedback.get_feedback_type_display()} from {request.user.username}',
                    message=f"{feedback.title}",
                    url = reverse('admin_panel:feedback_detail', args=[feedback.id])
                )

            messages.success(request, 'Your feedback has been submitted successfully.')
            return redirect('landing')
        else:
            messages.error(request, 'Please correct the highlighted errors.')
    else:
        form = FeedbackSubmissionForm()

    return render(request, 'shared/submit_feedback.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('landing')


@login_required
def redirect_view(request):
    if not request.user.is_active:
        logout(request)
        messages.error(request, 'Your account is inactive. Please contact an administrator.')
        return redirect('accounts:login')
    profile = ensure_role_profile(request.user)
    if request.user.role == 'gym_user' and profile and not profile.profile_completed:
        messages.info(request, 'Please complete your gym profile before using your dashboard.')
        return redirect('gym_user:profile')
    role_map = {
        'gym_user': 'gym_user:dashboard',
        'fitness_coach': 'coach:dashboard',
        'health_advisor': 'health_advisor:dashboard',
        'admin': 'admin_panel:dashboard',
    }
    return redirect(role_map.get(request.user.role, 'landing'))


@login_required
def account_edit(request):
    if not request.user.is_active:
        logout(request)
        messages.error(request, 'Your account is inactive. Please contact an administrator.')
        return redirect('accounts:login')
    ensure_role_profile(request.user)
    if request.method == 'POST':
        form = AccountEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your account details were updated successfully.')
            return redirect('accounts:account_edit')
        messages.error(request, 'Please correct the highlighted account errors.')
    else:
        form = AccountEditForm(instance=request.user)
    return render(request, 'accounts/account_edit.html', {'form': form})


@login_required
def password_change(request):
    if not request.user.is_active:
        logout(request)
        messages.error(request, 'Your account is inactive. Please contact an administrator.')
        return redirect('accounts:login')
    if request.method == 'POST':
        form = StyledPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully.')
            return redirect('accounts:account_edit')
        messages.error(request, 'Please correct the highlighted password errors.')
    else:
        form = StyledPasswordChangeForm(request.user)
    return render(request, 'accounts/password_change.html', {'form': form})

