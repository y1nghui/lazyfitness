from datetime import timedelta

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import coach_required
from apps.gym_user.forms import MessageForm
from apps.gym_user.messaging import (
    care_team_ready,
    conversation_unread_count,
    get_or_create_conversation,
    mark_conversation_read,
    notify_conversation_participants,
    notify_user,
)
from apps.gym_user.models import ActivityLog, GymUser
from lazyfitness.view_helpers import paginate, safe_back_url, safe_next_url

from .forms import (
    ExerciseForm,
    ProfessionalFeedbackForm,
    WorkoutForm,
    WorkoutPlanAssignmentForm,
    WorkoutPlanForm,
)
from .models import AssignedWorkoutPlan, Coach, Exercise, Workout, WorkoutPlan


def _bmi_category(gym_user):
    return gym_user.bmi_category() if hasattr(gym_user, 'bmi_category') else 'Unknown'


def _cancel_url(request, fallback):
    return safe_back_url(request, fallback)


def _goal_summary(gym_user):
    goals = gym_user.goals.all()
    completed = goals.filter(status='completed').count()
    cancelled = goals.filter(status='cancelled').count()
    active = goals.exclude(status__in=['completed', 'cancelled']).count()
    return {
        'completed': completed,
        'cancelled': cancelled,
        'active': active,
        'total': goals.count(),
    }


@coach_required
def dashboard(request):
    coach = get_object_or_404(Coach, user=request.user)
    plans = coach.plans.prefetch_related('workouts__exercises').all()
    assigned_users = coach.assigned_gym_users.select_related('user', 'assigned_advisor')
    assigned_user_rows = []
    for gym_user in assigned_users:
        ready = care_team_ready(gym_user)
        conversation = get_or_create_conversation(gym_user) if ready else getattr(gym_user, 'conversation', None)
        assigned_user_rows.append({
            'gym_user': gym_user,
            'ready': ready,
            'conversation': conversation,
            'recent_messages': conversation.messages.select_related('sender').order_by('-created_at')[:5] if conversation else [],
            'unread_count': conversation_unread_count(conversation, request.user) if conversation else 0,
        })
    context = {
        'coach': coach,
        'plans': plans,
        'assigned_users': assigned_users,
        'assigned_user_rows': assigned_user_rows,
        'assigned_count': assigned_users.count(),
        'plan_count': plans.count(),
        'assignment_count': coach.workout_assignments.count(),
        'workout_count': Workout.objects.filter(plan__coach=coach).count(),
        'exercise_count': Exercise.objects.filter(workout__plan__coach=coach).count(),
        'recent_logs': ActivityLog.objects.filter(user__assigned_coach=coach).select_related('user', 'plan').order_by('-logged_at')[:5],
        'recent_feedback': coach.feedbacks.select_related('gym_user', 'activity_log').order_by('-created_at')[:5],
    }
    return render(request, 'coach/dashboard.html', context)


@coach_required
def assigned_users(request):
    coach = get_object_or_404(Coach, user=request.user)
    search = request.GET.get('q', '').strip()
    bmi_filter = request.GET.get('bmi', '')
    unread_filter = request.GET.get('unread', '')
    recent_filter = request.GET.get('recent', '')
    users = coach.assigned_gym_users.select_related('user', 'assigned_advisor').prefetch_related(
        'logs',
        'conversation__messages',
        'assigned_workout_plans__plan',
        'measurements',
    )
    if search:
        users = users.filter(
            Q(user__username__icontains=search)
            | Q(user__email__icontains=search)
            | Q(user_name__icontains=search)
        )
    rows = []
    recent_cutoff = timezone.localdate() - timedelta(days=7)
    plans = coach.plans.all()
    for gym_user in users:
        conversation = get_or_create_conversation(gym_user) if care_team_ready(gym_user) else getattr(gym_user, 'conversation', None)
        latest_message = conversation.messages.select_related('sender').last() if conversation else None
        recent_messages = conversation.messages.select_related('sender').order_by('-created_at')[:5] if conversation else []
        latest_log = gym_user.logs.order_by('-logged_at', '-id').first()
        unread_count = conversation_unread_count(conversation, request.user) if conversation else 0
        bmi_category = _bmi_category(gym_user)
        has_recent = bool(latest_log and latest_log.logged_at >= recent_cutoff)
        if bmi_filter and bmi_category != bmi_filter:
            continue
        if unread_filter == 'yes' and unread_count == 0:
            continue
        if unread_filter == 'no' and unread_count > 0:
            continue
        if recent_filter == 'yes' and not has_recent:
            continue
        if recent_filter == 'no' and has_recent:
            continue
        rows.append({
            'gym_user': gym_user,
            'bmi': gym_user.calculate_bmi(),
            'bmi_category': bmi_category,
            'latest_log': latest_log,
            'latest_message': latest_message,
            'recent_messages': recent_messages,
            'latest_measurement': gym_user.measurements.first(),
            'latest_assignment': gym_user.assigned_workout_plans.filter(assigned_by=coach).first(),
            'goal_summary': _goal_summary(gym_user),
            'unread_count': unread_count,
            'has_recent_activity': has_recent,
        })
    page_obj, page_query = paginate(request, rows, per_page=10)
    return render(request, 'coach/assigned_users.html', {
        'coach': coach,
        'rows': page_obj.object_list,
        'page_obj': page_obj,
        'page_query': page_query,
        'search': search,
        'bmi_filter': bmi_filter,
        'unread_filter': unread_filter,
        'recent_filter': recent_filter,
        'bmi_categories': ['Underweight', 'Healthy', 'Overweight', 'Obese', 'Unknown'],
        'plans': plans,
    })


@coach_required
def plan_list(request):
    coach = get_object_or_404(Coach, user=request.user)
    plans = coach.plans.prefetch_related('workouts__exercises', 'assignments').all()
    return render(request, 'coach/plan_list.html', {'coach': coach, 'plans': plans})


@coach_required
def plan_create(request):
    coach = get_object_or_404(Coach, user=request.user)
    cancel_url = _cancel_url(request, reverse('coach:plan_list'))
    if request.method == 'POST':
        form = WorkoutPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.coach = coach
            plan.save()
            messages.success(request, 'Workout plan created successfully.')
            return redirect('coach:plan_detail', plan_id=plan.id)
        messages.error(request, 'Please correct the highlighted workout plan errors.')
    else:
        form = WorkoutPlanForm()
    return render(request, 'coach/plan_form.html', {
        'form': form,
        'mode': 'Create',
        'cancel_url': cancel_url,
    })


@coach_required
def plan_edit(request, plan_id):
    coach = get_object_or_404(Coach, user=request.user)
    plan = get_object_or_404(WorkoutPlan, id=plan_id, coach=coach)
    cancel_url = _cancel_url(request, reverse('coach:plan_detail', args=[plan.id]))
    if request.method == 'POST':
        form = WorkoutPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, 'Workout plan updated.')
            return redirect('coach:plan_detail', plan_id=plan.id)
        messages.error(request, 'Please correct the highlighted workout plan errors.')
    else:
        form = WorkoutPlanForm(instance=plan)
    return render(request, 'coach/plan_form.html', {
        'form': form,
        'plan': plan,
        'mode': 'Edit',
        'cancel_url': cancel_url,
    })


@coach_required
def plan_delete(request, plan_id):
    coach = get_object_or_404(Coach, user=request.user)
    plan = get_object_or_404(WorkoutPlan, id=plan_id, coach=coach)
    if request.method == 'POST':
        plan.delete()
        messages.success(request, 'Workout plan deleted.')
        return redirect('coach:plan_list')
    return render(request, 'coach/plan_confirm_delete.html', {'plan': plan})


@coach_required
def plan_detail(request, plan_id):
    coach = get_object_or_404(Coach, user=request.user)
    plan = get_object_or_404(
        WorkoutPlan.objects.prefetch_related('workouts__exercises', 'assignments__gym_user'),
        id=plan_id,
        coach=coach,
    )
    assignment_rows = []
    for assignment in plan.assignments.select_related('gym_user', 'gym_user__user', 'gym_user__assigned_advisor'):
        gym_user = assignment.gym_user
        ready = care_team_ready(gym_user)
        conversation = get_or_create_conversation(gym_user) if ready else getattr(gym_user, 'conversation', None)
        assignment_rows.append({
            'assignment': assignment,
            'gym_user': gym_user,
            'ready': ready,
            'conversation': conversation,
            'recent_messages': conversation.messages.select_related('sender').order_by('-created_at')[:5] if conversation else [],
            'unread_count': conversation_unread_count(conversation, request.user) if conversation else 0,
        })
    return render(request, 'coach/plan_detail.html', {
        'coach': coach,
        'plan': plan,
        'assignment_rows': assignment_rows,
    })


@coach_required
def plan_assign(request, plan_id):
    coach = get_object_or_404(Coach, user=request.user)
    plan = get_object_or_404(WorkoutPlan, id=plan_id, coach=coach)
    initial_user = None
    if request.GET.get('user'):
        initial_user = get_object_or_404(GymUser, pk=request.GET['user'], assigned_coach=coach)
    if request.method == 'POST':
        form = WorkoutPlanAssignmentForm(request.POST, coach=coach)
        if form.is_valid():
            selected_users = form.cleaned_data['gym_users']
            notes = form.cleaned_data.get('notes', '')
            created_count = 0
            updated_count = 0
            for gym_user in selected_users:
                assignment, created = AssignedWorkoutPlan.objects.get_or_create(
                    plan=plan,
                    gym_user=gym_user,
                    defaults={
                        'assigned_by': coach,
                        'status': 'assigned',
                        'notes': notes,
                    },
                )
                if created:
                    created_count += 1
                else:
                    assignment.assigned_by = coach
                    assignment.notes = notes or assignment.notes
                    if assignment.status == 'cancelled':
                        assignment.status = 'assigned'
                    assignment.save(update_fields=['assigned_by', 'notes', 'status'])
                    updated_count += 1
                notify_user(
                    gym_user.user,
                    'Workout plan assigned',
                    f'{coach.coach_name} assigned you: {plan.plan_name}.',
                    reverse('gym_user:workout_select'),
                )
            messages.success(request, f'Plan assigned to {created_count} new user(s); {updated_count} existing assignment(s) updated.')
            return redirect('coach:plan_detail', plan_id=plan.id)
        messages.error(request, 'Please choose at least one assigned gym user.')
    else:
        form = WorkoutPlanAssignmentForm(coach=coach, initial_user=initial_user)
    return render(request, 'coach/plan_assign.html', {
        'coach': coach,
        'plan': plan,
        'form': form,
        'initial_user': initial_user,
    })


@coach_required
def assign_plan_to_user(request, user_id):
    coach = get_object_or_404(Coach, user=request.user)
    gym_user = get_object_or_404(GymUser, pk=user_id, assigned_coach=coach)
    plan = None
    if request.POST.get('plan'):
        plan = get_object_or_404(WorkoutPlan, pk=request.POST['plan'], coach=coach)
    elif request.GET.get('plan'):
        plan = get_object_or_404(WorkoutPlan, pk=request.GET['plan'], coach=coach)
    if request.method == 'POST':
        if not plan:
            messages.error(request, 'Please select a workout plan.')
            return redirect('coach:assigned_users')
        assignment, created = AssignedWorkoutPlan.objects.get_or_create(
            plan=plan,
            gym_user=gym_user,
            defaults={
                'assigned_by': coach,
                'notes': request.POST.get('notes', ''),
            },
        )
        if not created:
            assignment.assigned_by = coach
            assignment.notes = request.POST.get('notes', assignment.notes)
            assignment.status = 'assigned'
            assignment.save(update_fields=['assigned_by', 'notes', 'status'])
        notify_user(
            gym_user.user,
            'Workout plan assigned',
            f'{coach.coach_name} assigned you: {plan.plan_name}.',
            reverse('gym_user:workout_select'),
        )
        messages.success(request, f'{plan.plan_name} assigned to {gym_user.user_name}.')
        return redirect(safe_back_url(request, reverse('coach:assigned_users')))
    if plan:
        return redirect(f"{reverse('coach:plan_assign', args=[plan.id])}?user={gym_user.pk}")
    return redirect(safe_back_url(request, reverse('coach:assigned_users')))


@coach_required
def workout_create(request, plan_id):
    coach = get_object_or_404(Coach, user=request.user)
    plan = get_object_or_404(WorkoutPlan, id=plan_id, coach=coach)
    if request.method == 'POST':
        form = WorkoutForm(request.POST)
        if form.is_valid():
            workout = form.save(commit=False)
            workout.plan = plan
            workout.save()
            messages.success(request, 'Workout added to plan.')
            return redirect('coach:plan_detail', plan_id=plan.id)
        messages.error(request, 'Please correct the highlighted workout errors.')
    else:
        form = WorkoutForm(initial={'status': True})
    return render(request, 'coach/workout_form.html', {'form': form, 'plan': plan, 'mode': 'Create'})


@coach_required
def workout_edit(request, workout_id):
    coach = get_object_or_404(Coach, user=request.user)
    workout = get_object_or_404(Workout, id=workout_id, plan__coach=coach)
    if request.method == 'POST':
        form = WorkoutForm(request.POST, instance=workout)
        if form.is_valid():
            form.save()
            messages.success(request, 'Workout updated.')
            return redirect('coach:plan_detail', plan_id=workout.plan.id)
        messages.error(request, 'Please correct the highlighted workout errors.')
    else:
        form = WorkoutForm(instance=workout)
    return render(request, 'coach/workout_form.html', {
        'form': form,
        'plan': workout.plan,
        'workout': workout,
        'mode': 'Edit',
    })


@coach_required
def workout_delete(request, workout_id):
    coach = get_object_or_404(Coach, user=request.user)
    workout = get_object_or_404(Workout, id=workout_id, plan__coach=coach)
    plan_id = workout.plan.id
    if request.method == 'POST':
        workout.delete()
        messages.success(request, 'Workout deleted.')
        return redirect('coach:plan_detail', plan_id=plan_id)
    return render(request, 'coach/workout_confirm_delete.html', {'workout': workout})


@coach_required
def exercise_create(request, workout_id):
    coach = get_object_or_404(Coach, user=request.user)
    workout = get_object_or_404(Workout, id=workout_id, plan__coach=coach)
    if request.method == 'POST':
        form = ExerciseForm(request.POST)
        if form.is_valid():
            exercise = form.save(commit=False)
            exercise.workout = workout
            exercise.save()
            messages.success(request, 'Exercise added successfully.')
            return redirect('coach:plan_detail', plan_id=workout.plan.id)
        messages.error(request, 'Please correct the highlighted exercise errors.')
    else:
        form = ExerciseForm()
    return render(request, 'coach/exercise_form.html', {'form': form, 'workout': workout, 'mode': 'Create'})


@coach_required
def exercise_edit(request, exercise_id):
    coach = get_object_or_404(Coach, user=request.user)
    exercise = get_object_or_404(Exercise, id=exercise_id, workout__plan__coach=coach)
    if request.method == 'POST':
        form = ExerciseForm(request.POST, instance=exercise)
        if form.is_valid():
            form.save()
            messages.success(request, 'Exercise updated.')
            return redirect('coach:plan_detail', plan_id=exercise.workout.plan.id)
        messages.error(request, 'Please correct the highlighted exercise errors.')
    else:
        form = ExerciseForm(instance=exercise)
    return render(request, 'coach/exercise_form.html', {
        'form': form,
        'workout': exercise.workout,
        'exercise': exercise,
        'mode': 'Edit',
    })


@coach_required
def exercise_delete(request, exercise_id):
    coach = get_object_or_404(Coach, user=request.user)
    exercise = get_object_or_404(Exercise, id=exercise_id, workout__plan__coach=coach)
    plan_id = exercise.workout.plan.id
    if request.method == 'POST':
        exercise.delete()
        messages.success(request, 'Exercise deleted.')
        return redirect('coach:plan_detail', plan_id=plan_id)
    return render(request, 'coach/exercise_confirm_delete.html', {'exercise': exercise})


@coach_required
def monitor_progress(request):
    coach = get_object_or_404(Coach, user=request.user)
    users = coach.assigned_gym_users.select_related('user').prefetch_related(
        'logs__plan',
        'goals',
        'measurements',
        'assigned_workout_plans__plan',
        'coach_feedbacks',
    )
    rows = []
    for gym_user in users:
        logs = gym_user.logs.order_by('-logged_at', '-id')
        recent_logs = list(logs[:3])
        summary = _goal_summary(gym_user)
        rows.append({
            'gym_user': gym_user,
            'latest_log': recent_logs[0] if recent_logs else None,
            'recent_logs': recent_logs,
            'goal_summary': summary,
            'latest_measurement': gym_user.measurements.first(),
            'active_assignments': gym_user.assigned_workout_plans.filter(assigned_by=coach).exclude(status='cancelled')[:3],
            'latest_feedback': gym_user.coach_feedbacks.filter(coach=coach).first(),
            'total_duration': sum(log.workout_duration for log in logs),
            'total_workouts': sum(log.workouts_completed for log in logs),
        })
    page_obj, page_query = paginate(request, rows, per_page=8)
    return render(request, 'coach/monitor_progress.html', {
        'coach': coach,
        'rows': page_obj.object_list,
        'page_obj': page_obj,
        'page_query': page_query,
        'plans': coach.plans.all(),
    })


@coach_required
def user_progress_detail(request, user_id):
    coach = get_object_or_404(Coach, user=request.user)
    gym_user = get_object_or_404(
        GymUser.objects.select_related('user', 'assigned_advisor'),
        pk=user_id,
        assigned_coach=coach,
    )
    logs = gym_user.logs.select_related('plan').order_by('-logged_at', '-id')[:15]
    assignments = gym_user.assigned_workout_plans.filter(assigned_by=coach).select_related('plan')[:10]
    conversation = get_or_create_conversation(gym_user) if care_team_ready(gym_user) else None
    return render(request, 'coach/user_progress_detail.html', {
        'coach': coach,
        'gym_user': gym_user,
        'logs': logs,
        'goal_summary': _goal_summary(gym_user),
        'latest_measurement': gym_user.measurements.first(),
        'measurements': gym_user.measurements.all()[:5],
        'assignments': assignments,
        'feedbacks': gym_user.coach_feedbacks.filter(coach=coach).select_related('activity_log')[:10],
        'plans': coach.plans.all(),
        'conversation': conversation,
        'recent_messages': conversation.messages.select_related('sender').order_by('-created_at')[:5] if conversation else [],
    })


@coach_required
def feedback_create(request, log_id):
    coach = get_object_or_404(Coach, user=request.user)
    log = get_object_or_404(
        ActivityLog.objects.select_related('user', 'plan'),
        id=log_id,
        user__assigned_coach=coach,
    )
    if request.method == 'POST':
        form = ProfessionalFeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.coach = coach
            feedback.gym_user = log.user
            feedback.activity_log = log
            feedback.save()
            notify_user(
                log.user.user,
                'Coach feedback added',
                f'{coach.coach_name} added feedback for your workout log.',
                reverse('gym_user:progress'),
            )
            messages.success(request, 'Professional feedback submitted.')
            return redirect('coach:monitor_progress')
        messages.error(request, 'Please correct the highlighted feedback errors.')
    else:
        form = ProfessionalFeedbackForm()
    feedback_history = log.user.coach_feedbacks.filter(coach=coach).select_related('activity_log')[:10]
    return render(request, 'coach/feedback_form.html', {
        'form': form,
        'log': log,
        'feedback_history': feedback_history,
    })


@coach_required
def message_list(request):
    coach = get_object_or_404(Coach, user=request.user)
    users = coach.assigned_gym_users.select_related('user', 'assigned_advisor', 'assigned_advisor__user').all()
    conversations = {
        conversation.gym_user_id: conversation
        for conversation in coach.conversations.select_related('gym_user', 'gym_user__user', 'health_advisor').prefetch_related('messages')
    }
    rows = []
    for user in users:
        conversation = conversations.get(user.pk)
        rows.append({
            'gym_user': user,
            'conversation': conversation,
            'ready': care_team_ready(user),
            'unread_count': conversation_unread_count(conversation, request.user) if conversation else 0,
        })
    return render(request, 'coach/messages.html', {
        'coach': coach,
        'rows': rows,
    })


@coach_required
def message_thread(request, user_id):
    coach = get_object_or_404(Coach, user=request.user)
    gym_user = get_object_or_404(
        GymUser.objects.select_related('user', 'assigned_coach', 'assigned_advisor'),
        pk=user_id,
        assigned_coach=coach,
    )
    if not care_team_ready(gym_user):
        messages.info(request, 'This user needs both a coach and a health advisor before the shared conversation can start.')
        return redirect('coach:messages')
    conversation = get_or_create_conversation(gym_user)
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            message.read_by.add(request.user)
            conversation.save(update_fields=['updated_at'])
            notify_conversation_participants(conversation, request.user, message)
            messages.success(request, 'Message sent to the shared conversation.')
            return redirect(safe_back_url(request, reverse('coach:message_thread', args=[gym_user.pk])))
        messages.error(request, 'Please enter a valid message or attachment.')
    else:
        form = MessageForm()
    mark_conversation_read(conversation, request.user)
    return render(request, 'shared/conversation_thread.html', {
        'page_title': f'Messages — {gym_user.user_name}',
        'heading': f'Messages with {gym_user.user_name}',
        'subtitle': 'Shared thread visible to the gym user, assigned coach and assigned health advisor.',
        'conversation': conversation,
        'messages_list': conversation.messages.select_related('sender').all(),
        'form': form,
        'gym_user': gym_user,
        'back_url_name': 'coach:messages',
    })
