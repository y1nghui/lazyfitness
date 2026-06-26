import csv
import json
from datetime import timedelta
from django.contrib import messages
from django.db.models import OuterRef, Q, Subquery
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from apps.accounts.decorators import admin_required
from apps.accounts.models import User
from apps.accounts.signals import ensure_role_profile
from apps.gym_user.models import GymUser
from apps.gym_user.messaging import sync_conversation_for_gym_user
from .forms import AdminPasswordResetForm, AdminUserCreationForm, AdminUserEditForm, FAQForm, FeedbackStatusForm, GymUserAssignmentForm
from .models import AdminProfile, AssignmentHistory, FAQ, Feedback, LoginActivity, SystemLog
from lazyfitness.view_helpers import paginate, safe_next_url


def _admin_profile(user):
    profile = ensure_role_profile(user)
    if profile is None:
        name = user.username or user.email.split('@')[0]
        profile, _ = AdminProfile.objects.get_or_create(user=user, defaults={'admin_name': name})
    return profile


def _sync_advisor_assignment(gym_user):
    from apps.health_advisor.models import HealthAdvisor
    for advisor in HealthAdvisor.objects.filter(assigned_users=gym_user).exclude(pk=gym_user.assigned_advisor_id):
        advisor.assigned_users.remove(gym_user)
    if gym_user.assigned_advisor_id:
        gym_user.assigned_advisor.assigned_users.add(gym_user)


def _latest_login_subquery():
    return LoginActivity.objects.filter(user=OuterRef('pk'), successful=True).order_by('-login_timestamp').values('login_timestamp')[:1]


def _next_or(request, fallback):
    return safe_next_url(request.POST.get('next') or request.GET.get('next'), fallback)


@admin_required
def dashboard(request):
    week_start = timezone.now() - timedelta(days=7)
    role_labels = ['Gym Users', 'Coaches', 'Health Advisors', 'Admins']
    role_counts = [
        User.objects.filter(role='gym_user').count(),
        User.objects.filter(role='fitness_coach').count(),
        User.objects.filter(role='health_advisor').count(),
        User.objects.filter(role='admin').count(),
    ]
    assigned_gym_users = GymUser.objects.exclude(assigned_coach=None).exclude(assigned_advisor=None).count()
    total_gym_profiles = GymUser.objects.count()
    context = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'inactive_users': User.objects.filter(is_active=False).count(),
        'gym_users': role_counts[0], 'coaches': role_counts[1], 'advisors': role_counts[2], 'admins': role_counts[3],
        'assigned_gym_users': assigned_gym_users,
        'unassigned_gym_users': max(total_gym_profiles - assigned_gym_users, 0),
        'login_activity_this_week': LoginActivity.objects.filter(login_timestamp__gte=week_start).count(),
        'pending_feedback': Feedback.objects.filter(status='pending').count(),
        'recent_logs': SystemLog.objects.select_related('performed_by')[:5],
        'recent_logins': LoginActivity.objects.select_related('user')[:5],
        'role_labels': json.dumps(role_labels),
        'role_counts': json.dumps(role_counts),
    }
    return render(request, 'admin_panel/dashboard.html', context)


@admin_required
def user_list(request):
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    assignment_filter = request.GET.get('assignment', '')
    search = request.GET.get('q', '').strip()
    users = User.objects.annotate(latest_login_at=Subquery(_latest_login_subquery())).order_by('username')
    if role_filter:
        users = users.filter(role=role_filter)
    if status_filter:
        users = users.filter(is_active=(status_filter == 'active'))
    if assignment_filter:
        users = users.filter(role='gym_user')
        if assignment_filter == 'no_coach':
            users = users.filter(gymuser__assigned_coach__isnull=True)
        elif assignment_filter == 'no_advisor':
            users = users.filter(gymuser__assigned_advisor__isnull=True)
        elif assignment_filter == 'both_missing':
            users = users.filter(gymuser__assigned_coach__isnull=True, gymuser__assigned_advisor__isnull=True)
    if search:
        users = users.filter(Q(username__icontains=search) | Q(email__icontains=search))
    page_obj, page_query = paginate(request, users, per_page=10)
    gym_profiles = {
        profile.user_id: profile
        for profile in GymUser.objects.select_related('assigned_coach', 'assigned_advisor', 'user').filter(
            user_id__in=[u.id for u in page_obj.object_list]
        )
    }
    user_rows = [{'user': user, 'profile': gym_profiles.get(user.id)} for user in page_obj.object_list]
    return render(request, 'admin_panel/user_list.html', {
        'users': page_obj.object_list,
        'user_rows': user_rows,
        'page_obj': page_obj,
        'page_query': page_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'assignment_filter': assignment_filter,
        'search': search,
        'role_choices': User.ROLE_CHOICES,
        'assignment_choices': [
            ('no_coach', 'No coach assigned'),
            ('no_advisor', 'No health advisor assigned'),
            ('both_missing', 'Both coach and health advisor missing'),
        ],
    })


@admin_required
def user_detail(request, user_id):
    target = get_object_or_404(User.objects.annotate(latest_login_at=Subquery(_latest_login_subquery())), pk=user_id)
    if target.role == 'admin' and not request.user.is_superuser and target.pk != request.user.pk:
        messages.error(request, 'Only a Django superuser can view another admin account in detail.')
        return redirect('admin_panel:user_list')
    profile = ensure_role_profile(target)
    recent_logs = []
    recent_messages = []
    assignment_history = []
    conversation = None
    if target.role == 'gym_user' and profile:
        recent_logs = profile.logs.select_related('plan').order_by('-logged_at', '-id')[:5]
        conversation = getattr(profile, 'conversation', None)
        if conversation:
            recent_messages = conversation.messages.select_related('sender').order_by('-created_at')[:5]
        assignment_history = profile.assignment_history.select_related('old_coach', 'new_coach', 'old_health_advisor', 'new_health_advisor', 'changed_by')[:10]
    return render(request, 'admin_panel/user_detail.html', {
        'target': target, 'profile': profile, 'recent_logs': recent_logs,
        'recent_messages': recent_messages, 'conversation': conversation,
        'assignment_history': assignment_history,
    })


@admin_required
def user_add(request):
    if request.method == 'POST':
        form = AdminUserCreationForm(request.POST, created_by=request.user)
        if form.is_valid():
            user = form.save()
            ensure_role_profile(user)
            SystemLog.record('user_created', f"New {user.get_role_display()} account created for {user.username}", user=request.user, module='User Management')
            messages.success(request, f'User {user.username} created successfully.')
            return redirect('admin_panel:user_detail', user_id=user.id)
        messages.error(request, 'Please correct the highlighted user creation errors.')
    else:
        form = AdminUserCreationForm(created_by=request.user)
    return render(request, 'admin_panel/user_add.html', {'form': form})


@admin_required
def user_edit(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target.role == 'admin' and not request.user.is_superuser:
        messages.error(request, 'Only a Django superuser can edit admin accounts.')
        return redirect('admin_panel:user_list')
    if request.method == 'POST':
        form = AdminUserEditForm(request.POST, request.FILES, instance=target, edited_by=request.user)
        if form.is_valid():
            updated = form.save()
            ensure_role_profile(updated)
            SystemLog.record('status_changed', f"Account details updated for {updated.username}", user=request.user, module='User Management')
            messages.success(request, f'Account details updated for {updated.username}.')
            return redirect('admin_panel:user_detail', user_id=updated.id)
        messages.error(request, 'Please correct the highlighted user update errors.')
    else:
        form = AdminUserEditForm(instance=target, edited_by=request.user)
    return render(request, 'admin_panel/user_edit.html', {'form': form, 'target': target})


@admin_required
def user_reset_password(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target.role == 'admin' and not request.user.is_superuser:
        messages.error(request, 'Only a Django superuser can reset an admin password.')
        return redirect('admin_panel:user_detail', user_id=target.id)
    if request.method == 'POST':
        form = AdminPasswordResetForm(request.POST, user=target)
        if form.is_valid():
            form.save()
            SystemLog.record('password_reset', f"Password reset for {target.username}", user=request.user, module='User Management')
            messages.success(request, f'Password reset for {target.username}.')
            return redirect('admin_panel:user_detail', user_id=target.id)
        messages.error(request, 'Please correct the highlighted password reset errors.')
    else:
        form = AdminPasswordResetForm(user=target)
    return render(request, 'admin_panel/user_reset_password.html', {'form': form, 'target': target})


@admin_required
def user_assign(request, user_id):
    fallback_url = f'/admin-panel/users/{user_id}/'
    next_url = _next_or(request, fallback_url)
    target_user = get_object_or_404(User, pk=user_id, role='gym_user')
    gym_user = ensure_role_profile(target_user)
    old_coach = gym_user.assigned_coach
    old_advisor = gym_user.assigned_advisor
    if request.method == 'POST':
        form = GymUserAssignmentForm(request.POST, instance=gym_user)
        if form.is_valid():
            profile = form.save()
            _sync_advisor_assignment(profile)
            sync_conversation_for_gym_user(profile)
            if (getattr(old_coach, 'pk', None) != profile.assigned_coach_id) or (getattr(old_advisor, 'pk', None) != profile.assigned_advisor_id):
                AssignmentHistory.objects.create(
                    gym_user=profile,
                    old_coach=old_coach,
                    new_coach=profile.assigned_coach,
                    old_health_advisor=old_advisor,
                    new_health_advisor=profile.assigned_advisor,
                    changed_by=request.user,
                    note=getattr(form, 'cleaned_note', ''),
                )
            coach_name = profile.assigned_coach.coach_name if profile.assigned_coach else 'No coach'
            advisor_name = profile.assigned_advisor.advisor_name if profile.assigned_advisor else 'No advisor'
            SystemLog.record('assignment_updated', f"Assignments updated for {target_user.username}: coach={coach_name}, advisor={advisor_name}", user=request.user, module='User Management')
            messages.success(request, 'Coach and health advisor assignments updated.')
            return redirect(next_url)
        messages.error(request, 'Please correct the highlighted assignment errors.')
    else:
        form = GymUserAssignmentForm(instance=gym_user)
    history = gym_user.assignment_history.select_related('old_coach', 'new_coach', 'old_health_advisor', 'new_health_advisor', 'changed_by')[:10]
    return render(request, 'admin_panel/user_assign.html', {'form': form, 'target_user': target_user, 'gym_user': gym_user, 'history': history, 'next_url': next_url})


@admin_required
def user_delete(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    
    if target.pk == request.user.pk:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('admin_panel:user_detail', user_id=target.id)
        
    if target.role == 'admin':
        messages.error(request, 'Cannot delete an admin account.')
        return redirect('admin_panel:user_list')
        
    if request.method == 'POST':
        # --- DEPENDENCY CHECK LOGIC ---
        if target.role == 'fitness_coach':
            active_trainees = GymUser.objects.filter(assigned_coach__user=target).count()
            if active_trainees > 0:
                messages.error(request, f"Deletion blocked. This coach has {active_trainees} active trainees assigned. Please reassign them first.")
                return redirect('admin_panel:user_detail', user_id=target.id)
                
        elif target.role == 'health_advisor':
            active_trainees = GymUser.objects.filter(assigned_advisor__user=target).count()
            if active_trainees > 0:
                messages.error(request, f"Deletion blocked. This advisor has {active_trainees} active trainees assigned. Please reassign them first.")
                return redirect('admin_panel:user_detail', user_id=target.id)
        # ------------------------------

        SystemLog.record('user_deleted', f"User {target.username} deleted", user=request.user, module='User Management')
        target.delete()
        messages.success(request, 'User deleted.')
        return redirect('admin_panel:user_list')
        
    return render(request, 'admin_panel/user_confirm_delete.html', {'target': target})

@admin_required
@require_POST
def user_toggle(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    fallback = f'/admin-panel/users/{target.id}/'
    next_url = _next_or(request, fallback)
    if target.pk == request.user.pk:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect(next_url)
    if target.role == 'admin' and not request.user.is_superuser:
        messages.error(request, 'Only a Django superuser can change admin account status.')
        return redirect(next_url)
    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
    action = 'activated' if target.is_active else 'deactivated'
    SystemLog.record('status_changed', f"User {target.username} {action}", user=request.user, module='User Management')
    messages.success(request, f'User {action}.')
    return redirect(next_url)


@admin_required
def login_activity_list(request):
    activities = LoginActivity.objects.select_related('user')
    search = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    start = request.GET.get('start', '')
    end = request.GET.get('end', '')
    if search:
        activities = activities.filter(Q(username__icontains=search) | Q(user__email__icontains=search))
    if role_filter:
        activities = activities.filter(role=role_filter)
    if status_filter == 'success':
        activities = activities.filter(successful=True)
    elif status_filter == 'failure':
        activities = activities.filter(successful=False)
    if parse_date(start):
        activities = activities.filter(login_timestamp__date__gte=parse_date(start))
    if parse_date(end):
        activities = activities.filter(login_timestamp__date__lte=parse_date(end))
    page_obj, page_query = paginate(request, activities, per_page=20)
    return render(request, 'admin_panel/login_activity_list.html', {'activities': page_obj.object_list, 'page_obj': page_obj, 'page_query': page_query, 'search': search, 'role_filter': role_filter, 'status_filter': status_filter, 'start': start, 'end': end, 'role_choices': User.ROLE_CHOICES})


@admin_required
def system_log_list(request):
    logs = SystemLog.objects.select_related('performed_by').all()
    event_filter = request.GET.get('event', '')
    module_filter = request.GET.get('module', '').strip()
    search = request.GET.get('q', '').strip()
    start = request.GET.get('start', '')
    end = request.GET.get('end', '')
    if event_filter:
        logs = logs.filter(event=event_filter)
    if module_filter:
        logs = logs.filter(module__icontains=module_filter)
    if search:
        logs = logs.filter(description__icontains=search)
    if parse_date(start):
        logs = logs.filter(timestamp__date__gte=parse_date(start))
    if parse_date(end):
        logs = logs.filter(timestamp__date__lte=parse_date(end))
    page_obj, page_query = paginate(request, logs, per_page=20)
    return render(request, 'admin_panel/system_log_list.html', {'logs': page_obj.object_list, 'page_obj': page_obj, 'page_query': page_query, 'event_choices': SystemLog.EVENT_CHOICES, 'event_filter': event_filter, 'module_filter': module_filter, 'search': search, 'start': start, 'end': end})


@admin_required
def system_log_detail(request, log_id):
    log = get_object_or_404(SystemLog.objects.select_related('performed_by'), pk=log_id)
    return render(request, 'admin_panel/system_log_detail.html', {'log': log})


@admin_required
def faq_list(request):
    faqs = FAQ.objects.select_related('admin').order_by('-updated_at')
    return render(request, 'admin_panel/faq_list.html', {'faqs': faqs})


@admin_required
def faq_create(request):
    admin_profile = _admin_profile(request.user)
    if request.method == 'POST':
        form = FAQForm(request.POST)
        if form.is_valid():
            faq = form.save(commit=False)
            faq.admin = admin_profile
            faq.save()
            SystemLog.record('faq_updated', f"FAQ '{faq.question[:60]}' created", user=request.user, module='FAQ')
            messages.success(request, 'FAQ created successfully.')
            return redirect('admin_panel:faq_list')
        messages.error(request, 'Please correct the highlighted FAQ errors.')
    else:
        form = FAQForm()
    return render(request, 'admin_panel/faq_form.html', {'form': form, 'mode': 'Create'})


@admin_required
def faq_edit(request, faq_id):
    faq = get_object_or_404(FAQ, pk=faq_id)
    if request.method == 'POST':
        form = FAQForm(request.POST, instance=faq)
        if form.is_valid():
            faq = form.save(commit=False)
            faq.admin = _admin_profile(request.user)
            faq.save()
            SystemLog.record('faq_updated', f"FAQ '{faq.question[:60]}' updated", user=request.user, module='FAQ')
            messages.success(request, 'FAQ updated successfully.')
            return redirect('admin_panel:faq_list')
        messages.error(request, 'Please correct the highlighted FAQ errors.')
    else:
        form = FAQForm(instance=faq)
    return render(request, 'admin_panel/faq_form.html', {'form': form, 'faq': faq, 'mode': 'Edit'})


@admin_required
def faq_delete(request, faq_id):
    faq = get_object_or_404(FAQ, pk=faq_id)
    if request.method == 'POST':
        SystemLog.record('faq_updated', f"FAQ '{faq.question[:40]}' deleted", user=request.user, module='FAQ')
        faq.delete()
        messages.success(request, 'FAQ deleted.')
        return redirect('admin_panel:faq_list')
    return render(request, 'admin_panel/faq_confirm_delete.html', {'faq': faq})


@admin_required
def feedback_list(request):
    status = request.GET.get('status', '')
    feedbacks = Feedback.objects.select_related('submitter')
    if status:
        feedbacks = feedbacks.filter(status=status)
    page_obj, page_query = paginate(request, feedbacks, per_page=20)
    return render(request, 'admin_panel/feedback_list.html', {'feedbacks': page_obj.object_list, 'page_obj': page_obj, 'page_query': page_query, 'status': status, 'status_choices': Feedback.STATUS_CHOICES})


@admin_required
def feedback_detail(request, feedback_id):
    feedback = get_object_or_404(Feedback.objects.select_related('submitter'), pk=feedback_id)
    
    # Auto-mark as viewed on first view
    if feedback.status == 'unsolved' and not feedback.viewed_at:
        feedback.status = 'viewed'
        feedback.viewed_at = timezone.now()
        feedback.save(update_fields=['status', 'viewed_at'])
    
    if request.method == 'POST':
        form = FeedbackStatusForm(request.POST, instance=feedback)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.save()
            SystemLog.record('feedback_updated', f"Feedback #{feedback.id} marked {feedback.status}", user=request.user, module='Feedback')
            messages.success(request, f'Feedback marked as {feedback.get_status_display()}.')
            return redirect('admin_panel:feedback_detail', feedback_id=feedback.id)
        messages.error(request, 'Please correct the highlighted feedback errors.')
    else:
        form = FeedbackStatusForm(instance=feedback)
    
    return render(request, 'admin_panel/feedback_detail.html', {'feedback': feedback, 'form': form})


def _csv_response(filename):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@admin_required
def export_users(request):
    response = _csv_response('lazyfitness_users.csv')
    writer = csv.writer(response)
    writer.writerow(['username', 'email', 'role', 'active', 'date_joined', 'latest_login', 'assigned_coach', 'assigned_advisor'])
    profiles = {p.user_id: p for p in GymUser.objects.select_related('assigned_coach', 'assigned_advisor')}
    for user in User.objects.annotate(latest_login_at=Subquery(_latest_login_subquery())).order_by('username'):
        p = profiles.get(user.id)
        writer.writerow([user.username, user.email, user.get_role_display(), user.is_active, user.date_joined, getattr(user, 'latest_login_at', ''), getattr(getattr(p, 'assigned_coach', None), 'coach_name', ''), getattr(getattr(p, 'assigned_advisor', None), 'advisor_name', '')])
    SystemLog.record('export', 'Users CSV exported', user=request.user, module='CSV Export')
    return response


@admin_required
def export_login_activity(request):
    response = _csv_response('lazyfitness_login_activity.csv')
    writer = csv.writer(response)
    writer.writerow(['username', 'role', 'timestamp', 'ip_address', 'successful', 'user_agent'])
    for row in LoginActivity.objects.select_related('user'):
        writer.writerow([row.username, row.role, row.login_timestamp, row.ip_address, row.successful, row.user_agent])
    SystemLog.record('export', 'Login activity CSV exported', user=request.user, module='CSV Export')
    return response


@admin_required
def export_feedback(request):
    response = _csv_response('lazyfitness_feedback.csv')
    writer = csv.writer(response)
    writer.writerow(['id', 'submitter', 'status', 'comment', 'created_at'])
    for fb in Feedback.objects.select_related('submitter'):
        writer.writerow([fb.id, fb.submitter.username, fb.status, fb.comment, fb.created_at])
    SystemLog.record('export', 'Feedback CSV exported', user=request.user, module='CSV Export')
    return response


@admin_required
def feedback_to_faq(request, feedback_id):
    feedback = get_object_or_404(Feedback, pk=feedback_id)
    
    # Pre-fill FAQ form with feedback data
    initial_data = {
        'question': feedback.title,
        'answer': feedback.comment,
    }
    
    if request.method == 'POST':
        form = FAQForm(request.POST)
        if form.is_valid():
            faq = form.save(commit=False)
            faq.admin = _admin_profile(request.user)
            faq.save()
            feedback.status = 'solved'
            feedback.save(update_fields=['status'])
            SystemLog.record('feedback_updated', f"Feedback #{feedback.id} converted to FAQ", user=request.user, module='Feedback')
            messages.success(request, 'Feedback posted to FAQ successfully.')
            return redirect('admin_panel:faq_list')
        messages.error(request, 'Please correct the highlighted errors.')
    else:
        form = FAQForm(initial=initial_data)
    
    return render(request, 'admin_panel/faq_form.html', {'form': form, 'feedback': feedback, 'is_from_feedback': True})