import calendar
import json
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import FieldDoesNotExist
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import gym_user_required
from apps.accounts.signals import ensure_role_profile
from apps.coach.models import AssignedWorkoutPlan, WorkoutPlan
from apps.health_advisor.models import DietPlan, Recommendation
from lazyfitness.view_helpers import safe_back_url, safe_next_url

from .forms import (
    ActivityLogForm,
    BodyMeasurementForm,
    FitnessGoalForm,
    GymUserProfileForm,
    MessageForm,
    MonthlyWorkoutScheduleForm,
    WorkoutScheduleForm,
)
from .messaging import (
    care_team_ready,
    conversation_unread_count,
    get_or_create_conversation,
    mark_conversation_read,
    notify_conversation_participants,
)
from .models import BodyMeasurement, FitnessGoal, GymUser, MonthlyWorkoutSchedule, WorkoutSchedule


def _gym_profile(request, require_completed=True):
    profile = ensure_role_profile(request.user)
    if require_completed and profile and not profile.profile_completed:
        messages.info(request, 'Complete your profile first so your BMI and recommendations are accurate.')
        return None
    return profile


def _bmi_badge_class(category):
    return {
        'Healthy': 'success',
        'Underweight': 'warning',
        'Overweight': 'warning',
        'Obese': 'danger',
    }.get(category, 'secondary')


def _next_or(request, fallback_name='gym_user:dashboard'):
    fallback = reverse(fallback_name)
    return safe_next_url(request.POST.get('next') or request.GET.get('next'), fallback)


def _goal_summary(gym_user):
    goals = gym_user.goals.all()
    active_count = 0
    summary = {
        'not_started': goals.filter(status=FitnessGoal.STATUS_NOT_STARTED).count(),
        'active': goals.filter(status=FitnessGoal.STATUS_ACTIVE).count(),
        'completed': goals.filter(status=FitnessGoal.STATUS_COMPLETED).count(),
        'cancelled': goals.filter(status=FitnessGoal.STATUS_CANCELLED).count(),
        'overdue': 0,
    }
    for goal in goals:
        if goal.is_overdue:
            summary['overdue'] += 1
        if goal.status not in [FitnessGoal.STATUS_COMPLETED, FitnessGoal.STATUS_CANCELLED]:
            active_count += 1
    summary['active_total'] = active_count
    return summary


def _month_calendar(gym_user, today):
    first_weekday, _days_in_month = calendar.monthrange(today.year, today.month)
    first_date = today.replace(day=1)
    start = first_date - timedelta(days=first_weekday)
    end = start + timedelta(days=42)
    items = gym_user.monthly_schedules.filter(date__gte=start, date__lt=end)
    schedules_by_date = _monthly_schedule_by_date(items)
    weeks = []
    current = start
    for _week in range(6):
        days = []
        for _day in range(7):
            days.append({
                'date': current,
                'in_month': current.month == today.month,
                'is_today': current == today,
                'items': schedules_by_date.get(current, []),
            })
            current += timedelta(days=1)
        weeks.append(days)
    return weeks


def _week_calendar(gym_user):
    schedules_by_day = _schedule_by_day(gym_user.schedules.all())
    week_days = []
    for day_name in calendar.day_name:
        week_days.append({
            'day_name': day_name,
            'items': schedules_by_day.get(day_name, []),
        })
    return week_days


def _model_has_field(model, field_name):
    try:
        model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return False
    return True


def _as_date(value):
    if not value:
        return None
    if hasattr(value, 'date'):
        return value.date()
    return value


def _date_text(value):
    date_value = _as_date(value)
    return date_value.isoformat() if date_value else 'Not set'


def _fullcalendar_end_date(start_date, end_date):
    if not end_date:
        return None
    if start_date and end_date < start_date:
        return None
    return (end_date + timedelta(days=1)).isoformat()


def _event_details(*lines):
    return '\n'.join(str(line) for line in lines if line not in [None, ''])


def _assigned_diet_plans_for_user(gym_user):
    queryset = DietPlan.objects.select_related('advisor')
    if _model_has_field(DietPlan, 'gym_users'):
        return queryset.filter(gym_users=gym_user).distinct()
    if _model_has_field(DietPlan, 'gym_user'):
        return queryset.filter(gym_user=gym_user)
    return queryset.none()


def _diet_plan_events(gym_user):
    events = []
    for plan in _assigned_diet_plans_for_user(gym_user):
        start_date = plan.start_date or plan.end_date or _as_date(getattr(plan, 'created_at', None))
        if not start_date:
            continue
        end_date = plan.end_date if plan.start_date else None
        details = _event_details(
            'Plan type: Diet Plan',
            f'Title: {plan.title}',
            f'Health advisor: {plan.advisor.advisor_name if plan.advisor_id else "Not assigned"}',
            f'Status: {plan.get_status_display()}',
            f'Target goal: {plan.target_goal or "Not set"}',
            f'Daily calorie target: {plan.daily_calorie_target or "Not set"}',
            f'Start date: {_date_text(plan.start_date)}',
            f'End date: {_date_text(plan.end_date)}',
            f'Description: {plan.description or "No description provided"}',
            f'Meal details: {plan.meal_notes or "No meal details provided"}',
            f'Restrictions/allergies: {plan.restrictions_allergies or "None stated"}',
        )
        event = {
            'title': f'Diet Plan: {plan.title}',
            'start': start_date.isoformat(),
            'extendedProps': {'details': details},
        }
        end_value = _fullcalendar_end_date(start_date, end_date)
        if end_value:
            event['end'] = end_value
        events.append(event)
    return events


def _workout_summary(plan):
    workouts = []
    for workout in plan.workouts.all():
        exercises = [
            f'{exercise.exercise_name} ({exercise.sets} sets x {exercise.exercise_reps} reps)'
            for exercise in workout.exercises.all()
        ]
        if exercises:
            workouts.append(f'{workout.workout_name}: ' + '; '.join(exercises))
        else:
            workouts.append(workout.workout_name)
    return '\n'.join(workouts) if workouts else 'No workout details provided'


def _workout_plan_events(gym_user):
    assignments = AssignedWorkoutPlan.objects.filter(
        gym_user=gym_user,
    ).exclude(status='cancelled').select_related(
        'plan', 'assigned_by'
    ).prefetch_related(
        'plan__workouts__exercises'
    ).distinct()

    events = []
    for assignment in assignments:
        plan = assignment.plan
        start_date = assignment.started_at or _as_date(assignment.assigned_at)
        if not start_date:
            continue
        end_date = assignment.completed_at
        details = _event_details(
            'Plan type: Workout Plan',
            f'Title: {plan.plan_name}',
            f'Coach: {assignment.assigned_by.coach_name if assignment.assigned_by_id else "Not assigned"}',
            f'Status: {assignment.get_status_display()}',
            f'Difficulty: {plan.get_difficulty_display()}',
            f'Target goal: {plan.get_target_goal_display()}',
            f'Duration: {plan.duration_weeks} week(s)',
            f'Assigned date: {_date_text(assignment.assigned_at)}',
            f'Start date: {_date_text(assignment.started_at)}',
            f'Completed date: {_date_text(assignment.completed_at)}',
            f'Description: {plan.description or "No description provided"}',
            f'Assignment notes: {assignment.notes or "No notes provided"}',
            'Workout details:',
            _workout_summary(plan),
        )
        event = {
            'title': f'Workout Plan: {plan.plan_name}',
            'start': start_date.isoformat(),
            'extendedProps': {'details': details},
        }
        end_value = _fullcalendar_end_date(start_date, end_date)
        if end_value:
            event['end'] = end_value
        events.append(event)
    return events

def _monthly_schedule_by_date(schedules):
    grouped = {}
    for item in schedules:
        grouped.setdefault(item.date, []).append(item)
    return grouped


def _schedule_by_day(schedules):
    grouped = {choice[0]: [] for choice in WorkoutSchedule.DAY_CHOICES}
    for item in schedules:
        grouped.setdefault(item.day, []).append(item)
    return grouped


@gym_user_required
def dashboard(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    can_message = care_team_ready(gym_user)
    conversation = get_or_create_conversation(gym_user) if can_message else getattr(gym_user, 'conversation', None)
    unread_messages = conversation_unread_count(conversation, request.user) if conversation else 0
    recent_messages = conversation.messages.select_related('sender').order_by('-created_at')[:5] if conversation else []
    bmi_category = gym_user.bmi_category()
    logs = gym_user.logs.select_related('plan').order_by('-logged_at')[:8]
    assignments = gym_user.assigned_workout_plans.select_related('plan', 'assigned_by')[:5]
    latest_measurement = gym_user.measurements.first()
    context = {
        'gym_user': gym_user,
        'bmi': gym_user.calculate_bmi(),
        'bmi_category': bmi_category,
        'bmi_badge_class': _bmi_badge_class(bmi_category),
        'goals': gym_user.goals.exclude(status__in=['completed', 'cancelled'])[:3],
        'completed_goals': gym_user.goals.filter(status='completed')[:3],
        'goal_summary': _goal_summary(gym_user),
        'recent_logs': logs,
        'schedule': gym_user.schedules.all()[:7],
        'latest_log': logs[0] if logs else None,
        'latest_measurement': latest_measurement,
        'assigned_coach': gym_user.assigned_coach,
        'assigned_advisor': gym_user.assigned_advisor,
        'assigned_workout_plans': assignments,
        'diet_plans': gym_user.diet_plans.select_related('advisor').exclude(status='cancelled')[:3],
        'unread_messages': unread_messages,
        'message_conversation': conversation,
        'recent_messages': recent_messages,
        'can_message': can_message,
        'recommendations': gym_user.recommendations.exclude(status='cancelled')[:5],
    }
    return render(request, 'gym_user/dashboard.html', context)


@gym_user_required
def goal_list(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    goals = gym_user.goals.all()
    return render(request, 'gym_user/goal_list.html', {
        'gym_user': gym_user,
        'goals': goals,
        'summary': _goal_summary(gym_user),
    })


@gym_user_required
def goal_create(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    if request.method == 'POST':
        form = FitnessGoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = gym_user
            goal.save()
            messages.success(request, 'Fitness goal added successfully.')
            return redirect('gym_user:goal_list')
        messages.error(request, 'Please correct the highlighted goal errors.')
    else:
        form = FitnessGoalForm(initial={'status': FitnessGoal.STATUS_ACTIVE})
    return render(request, 'gym_user/goal_form.html', {'form': form, 'mode': 'Create'})


@gym_user_required
def goal_edit(request, goal_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    goal = get_object_or_404(FitnessGoal, pk=goal_id, user=gym_user)
    if request.method == 'POST':
        form = FitnessGoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fitness goal updated successfully.')
            return redirect('gym_user:goal_list')
        messages.error(request, 'Please correct the highlighted goal errors.')
    else:
        form = FitnessGoalForm(instance=goal)
    return render(request, 'gym_user/goal_form.html', {'form': form, 'mode': 'Edit', 'goal': goal})


@gym_user_required
@require_POST
def goal_complete(request, goal_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    goal = get_object_or_404(FitnessGoal, pk=goal_id, user=gym_user)
    goal.status = FitnessGoal.STATUS_COMPLETED
    goal.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Goal marked as completed.')
    return redirect(_next_or(request, 'gym_user:goal_list'))


@gym_user_required
@require_POST
def goal_uncomplete(request, goal_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    goal = get_object_or_404(FitnessGoal, pk=goal_id, user=gym_user)
    goal.status = FitnessGoal.STATUS_ACTIVE
    goal.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Goal unmarked as completed.')
    return redirect(_next_or(request, 'gym_user:goal_list'))


@gym_user_required
@require_POST
def goal_cancel(request, goal_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    goal = get_object_or_404(FitnessGoal, pk=goal_id, user=gym_user)
    goal.status = FitnessGoal.STATUS_CANCELLED
    goal.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Goal cancelled.')
    return redirect(_next_or(request, 'gym_user:goal_list'))


@gym_user_required
def schedule_view(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    return render(request, 'gym_user/schedule.html', {'gym_user': gym_user})


@gym_user_required
def calendar_events(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return JsonResponse([], safe=False)
    events = _diet_plan_events(gym_user) + _workout_plan_events(gym_user)
    return JsonResponse(events, safe=False)


@gym_user_required
def monthly_schedule_create(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    if request.method == 'POST':
        form = MonthlyWorkoutScheduleForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = gym_user
            item.save()
            messages.success(request, 'Monthly date-specific plan created.')
            return redirect('gym_user:schedule')
        messages.error(request, 'Please correct the highlighted monthly plan errors.')
    else:
        form = MonthlyWorkoutScheduleForm()
    return render(request, 'gym_user/schedule_form.html', {
        'form': form,
        'mode': 'Create',
        'schedule_kind': 'Monthly Plan',
        'schedule_help': 'Monthly plans are date-by-date items. They happen only on the exact date selected and do not repeat weekly.',
        'cancel_url': reverse('gym_user:schedule'),
    })


@gym_user_required
def monthly_schedule_edit(request, schedule_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    item = get_object_or_404(MonthlyWorkoutSchedule, pk=schedule_id, user=gym_user)
    if request.method == 'POST':
        form = MonthlyWorkoutScheduleForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Monthly date-specific plan updated.')
            return redirect('gym_user:schedule')
        messages.error(request, 'Please correct the highlighted monthly plan errors.')
    else:
        form = MonthlyWorkoutScheduleForm(instance=item)
    return render(request, 'gym_user/schedule_form.html', {
        'form': form,
        'mode': 'Edit',
        'schedule_kind': 'Monthly Plan',
        'schedule_item': item,
        'schedule_help': 'This item is linked to one exact calendar date only.',
        'cancel_url': reverse('gym_user:schedule'),
    })


@gym_user_required
def monthly_schedule_delete(request, schedule_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    item = get_object_or_404(MonthlyWorkoutSchedule, pk=schedule_id, user=gym_user)
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Monthly date-specific plan deleted.')
        return redirect('gym_user:schedule')
    return render(request, 'gym_user/schedule_confirm_delete.html', {
        'schedule_item': item,
        'schedule_kind': 'Monthly Plan',
        'item_summary': f'{item.date:%Y-%m-%d}' + (f' at {item.time:%H:%M}' if item.time else ''),
        'cancel_url': reverse('gym_user:schedule'),
    })


@gym_user_required
def weekly_schedule(request):
    return redirect('gym_user:schedule')


@gym_user_required
def weekly_schedule_create(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    if request.method == 'POST':
        form = WorkoutScheduleForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = gym_user
            item.save()
            messages.success(request, 'Weekly recurring routine created.')
            return redirect('gym_user:weekly_schedule')
        messages.error(request, 'Please correct the highlighted weekly routine errors.')
    else:
        form = WorkoutScheduleForm()
    return render(request, 'gym_user/schedule_form.html', {
        'form': form,
        'mode': 'Create',
        'schedule_kind': 'Weekly Routine',
        'schedule_help': 'Weekly routines repeat every week on the selected weekday.',
        'cancel_url': reverse('gym_user:weekly_schedule'),
    })


@gym_user_required
def weekly_schedule_edit(request, schedule_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    item = get_object_or_404(WorkoutSchedule, pk=schedule_id, user=gym_user)
    if request.method == 'POST':
        form = WorkoutScheduleForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Weekly recurring routine updated.')
            return redirect('gym_user:weekly_schedule')
        messages.error(request, 'Please correct the highlighted weekly routine errors.')
    else:
        form = WorkoutScheduleForm(instance=item)
    return render(request, 'gym_user/schedule_form.html', {
        'form': form,
        'mode': 'Edit',
        'schedule_kind': 'Weekly Routine',
        'schedule_item': item,
        'schedule_help': 'This item repeats weekly on the selected weekday.',
        'cancel_url': reverse('gym_user:weekly_schedule'),
    })


@gym_user_required
def weekly_schedule_delete(request, schedule_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    item = get_object_or_404(WorkoutSchedule, pk=schedule_id, user=gym_user)
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Weekly recurring routine deleted.')
        return redirect('gym_user:weekly_schedule')
    return render(request, 'gym_user/schedule_confirm_delete.html', {
        'schedule_item': item,
        'schedule_kind': 'Weekly Routine',
        'item_summary': f'every {item.day} at {item.time:%H:%M}',
        'cancel_url': reverse('gym_user:weekly_schedule'),
    })


# Backward-compatible aliases for older links/tests. They now point to the weekly routine workflow
# because the original WorkoutSchedule model stores recurring weekday schedules.
schedule_create = weekly_schedule_create
schedule_edit = weekly_schedule_edit
schedule_delete = weekly_schedule_delete


@gym_user_required
def workout_select(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    assignments = gym_user.assigned_workout_plans.select_related('plan', 'assigned_by').prefetch_related(
        'plan__workouts__exercises'
    )
    active_assignments = assignments.filter(status__in=['assigned', 'in_progress', 'completed'])
    if request.method == 'POST':
        assignment_id = request.POST.get('assignment')
        assignment = active_assignments.filter(pk=assignment_id).first()
        if assignment:
            if assignment.status == 'assigned':
                assignment.status = 'in_progress'
                assignment.started_at = timezone.localdate()
                assignment.save(update_fields=['status', 'started_at'])
            messages.success(request, 'Workout plan selected. Log your activity when you complete it.')
            return redirect(f"{reverse('gym_user:log_activity')}?plan={assignment.plan_id}")
        messages.error(request, 'Please choose a valid assigned workout plan.')
    can_message = care_team_ready(gym_user)
    conversation = get_or_create_conversation(gym_user) if can_message else getattr(gym_user, 'conversation', None)
    recent_messages = conversation.messages.select_related('sender').order_by('-created_at')[:5] if conversation else []
    return render(request, 'gym_user/workout_select.html', {
        'gym_user': gym_user,
        'assignments': active_assignments,
        'can_message': can_message,
        'recent_messages': recent_messages,
    })


@gym_user_required
@require_POST
def assigned_plan_complete(request, assignment_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    assignment = get_object_or_404(AssignedWorkoutPlan, pk=assignment_id, gym_user=gym_user)
    assignment.status = 'completed'
    assignment.completed_at = timezone.localdate()
    assignment.save(update_fields=['status', 'completed_at'])
    messages.success(request, 'Workout plan marked as completed.')
    return redirect('gym_user:workout_select')


@gym_user_required
@require_POST
def assigned_plan_uncomplete(request, assignment_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    assignment = get_object_or_404(AssignedWorkoutPlan, pk=assignment_id, gym_user=gym_user)
    assignment.status = 'in_progress'
    assignment.completed_at = None
    assignment.save(update_fields=['status', 'completed_at'])
    messages.success(request, 'Workout plan unmarked as completed.')
    return redirect('gym_user:workout_select')


@gym_user_required
def log_activity(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    selected_plan = None
    if request.GET.get('plan'):
        selected_plan = get_object_or_404(
            WorkoutPlan,
            pk=request.GET.get('plan'),
            assignments__gym_user=gym_user,
        )
    if request.method == 'POST':
        form = ActivityLogForm(request.POST, gym_user=gym_user)
        if form.is_valid():
            log = form.save(commit=False)
            log.user = gym_user
            log.save()
            messages.success(request, 'Activity logged successfully.')
            return redirect('gym_user:progress')
        messages.error(request, 'Please correct the highlighted activity log errors.')
    else:
        form = ActivityLogForm(selected_plan=selected_plan, gym_user=gym_user)
    return render(request, 'gym_user/log_activity.html', {
        'form': form,
        'selected_plan': selected_plan,
    })


@gym_user_required
def progress_view(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    logs = list(gym_user.logs.select_related('plan').order_by('logged_at', 'id'))
    measurements = list(gym_user.measurements.order_by('recorded_at', 'id'))
    measurement_form = BodyMeasurementForm(gym_user=gym_user)
    chart_labels = [log.logged_at.strftime('%d %b') for log in logs]
    duration_data = [log.workout_duration for log in logs]
    reps_data = [log.reps_completed for log in logs]
    streak_data = [log.workout_streak for log in logs]
    total_duration = sum(duration_data)
    total_reps = sum(reps_data)
    total_workouts = sum(log.workouts_completed for log in logs)
    best_streak = max(streak_data) if streak_data else 0
    measurement_labels = [m.recorded_at.strftime('%d %b') for m in measurements]
    weight_data = [m.weight for m in measurements]
    waist_data = [m.waist_in_cm for m in measurements]
    return render(request, 'gym_user/progress.html', {
        'gym_user': gym_user,
        'logs': reversed(logs),
        'measurements': reversed(measurements),
        'measurement_form': measurement_form,
        'chart_labels': json.dumps(chart_labels),
        'duration_data': json.dumps(duration_data),
        'reps_data': json.dumps(reps_data),
        'streak_data': json.dumps(streak_data),
        'measurement_labels': json.dumps(measurement_labels),
        'weight_data': json.dumps(weight_data),
        'waist_data': json.dumps(waist_data),
        'total_duration': total_duration,
        'total_reps': total_reps,
        'total_workouts': total_workouts,
        'best_streak': best_streak,
        'goal_summary': _goal_summary(gym_user),
    })


@gym_user_required
def measurement_create(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    if request.method == 'POST':
        form = BodyMeasurementForm(request.POST, gym_user=gym_user)
        if form.is_valid():
            measurement = form.save(commit=False)
            measurement.gym_user = gym_user
            measurement.save()
            gym_user.weight = measurement.weight
            gym_user.waist_in_cm = measurement.waist_in_cm
            gym_user.neck_in_cm = measurement.neck_in_cm
            gym_user.calorie_intake = measurement.calorie_intake
            gym_user.save(update_fields=['weight', 'waist_in_cm', 'neck_in_cm', 'calorie_intake'])
            messages.success(request, 'Body measurement saved.')
            return redirect('gym_user:progress')
        messages.error(request, 'Please correct the highlighted measurement errors.')
        logs = gym_user.logs.select_related('plan').order_by('-logged_at', '-id')
        return render(request, 'gym_user/progress.html', {
            'gym_user': gym_user,
            'logs': logs,
            'measurements': gym_user.measurements.all(),
            'measurement_form': form,
            'chart_labels': '[]',
            'duration_data': '[]',
            'reps_data': '[]',
            'streak_data': '[]',
            'measurement_labels': '[]',
            'weight_data': '[]',
            'waist_data': '[]',
            'total_duration': 0,
            'total_reps': 0,
            'total_workouts': 0,
            'best_streak': 0,
            'goal_summary': _goal_summary(gym_user),
        })
    return redirect('gym_user:progress')


@gym_user_required
def profile_view(request):
    gym_user = _gym_profile(request, require_completed=False)
    if request.method == 'POST':
        form = GymUserProfileForm(request.POST, instance=gym_user)
        if form.is_valid():
            profile = form.save()
            BodyMeasurement.objects.get_or_create(
                gym_user=profile,
                recorded_at=timezone.localdate(),
                defaults={
                    'weight': profile.weight,
                    'waist_in_cm': profile.waist_in_cm,
                    'neck_in_cm': profile.neck_in_cm,
                    'calorie_intake': profile.calorie_intake,
                    'notes': 'Profile update snapshot',
                },
            )
            messages.success(request, 'Profile saved successfully.')
            return redirect('gym_user:dashboard')
        messages.error(request, 'Please correct the highlighted profile errors.')
    else:
        form = GymUserProfileForm(instance=gym_user)
    return render(request, 'gym_user/profile.html', {
        'gym_user': gym_user,
        'form': form,
        'bmi': gym_user.calculate_bmi(),
        'is_new_profile': not gym_user.profile_completed,
    })


@gym_user_required
def messages_view(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    if not care_team_ready(gym_user):
        return render(request, 'gym_user/messages.html', {
            'gym_user': gym_user,
            'conversation': None,
            'messages_list': [],
            'form': None,
            'missing_team': True,
            'unread_count': 0,
        })
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
            messages.success(request, 'Message sent to your shared care team.')
            return redirect(safe_back_url(request, reverse('gym_user:messages')))
        messages.error(request, 'Please enter a valid message or attachment.')
    else:
        form = MessageForm()
    mark_conversation_read(conversation, request.user)
    return render(request, 'shared/conversation_thread.html', {
        'page_title': 'Care Team Messages',
        'heading': 'Care Team Messages',
        'subtitle': 'A WhatsApp-like shared conversation between you, your coach, and your health advisor.',
        'conversation': conversation,
        'messages_list': conversation.messages.select_related('sender').all(),
        'form': form,
        'gym_user': gym_user,
        'back_url_name': 'gym_user:dashboard',
    })


@gym_user_required
def recommendation_list(request):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    recommendations = gym_user.recommendations.select_related('advisor', 'advisor__user').order_by('-created_at')
    return render(request, 'gym_user/recommendation_list.html', {
        'gym_user': gym_user,
        'recommendations': recommendations,
    })


@gym_user_required
@require_POST
def recommendation_mark_read(request, recommendation_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    rec = get_object_or_404(Recommendation, pk=recommendation_id, gym_user=gym_user)
    if rec.status == Recommendation.STATUS_UNREAD:
        rec.status = Recommendation.STATUS_READ
        rec.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Recommendation marked as read.')
    return redirect('gym_user:recommendation_list')


@gym_user_required
@require_POST
def recommendation_unmark_read(request, recommendation_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    rec = get_object_or_404(Recommendation, pk=recommendation_id, gym_user=gym_user)
    if rec.status == Recommendation.STATUS_READ:
        rec.status = Recommendation.STATUS_UNREAD
        rec.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Recommendation unmarked as read.')
    return redirect('gym_user:recommendation_list')


@gym_user_required
@require_POST
def recommendation_mark_completed(request, recommendation_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    rec = get_object_or_404(Recommendation, pk=recommendation_id, gym_user=gym_user)
    rec.status = Recommendation.STATUS_COMPLETED
    rec.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Recommendation marked as completed.')
    return redirect('gym_user:recommendation_list')


@gym_user_required
@require_POST
def recommendation_unmark_completed(request, recommendation_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    rec = get_object_or_404(Recommendation, pk=recommendation_id, gym_user=gym_user)
    if rec.status == Recommendation.STATUS_COMPLETED:
        rec.status = Recommendation.STATUS_READ
        rec.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Recommendation unmarked as completed.')
    return redirect('gym_user:recommendation_list')


@gym_user_required
@require_POST
def recommendation_cancel(request, recommendation_id):
    gym_user = _gym_profile(request)
    if not gym_user:
        return redirect('gym_user:profile')
    rec = get_object_or_404(Recommendation, pk=recommendation_id, gym_user=gym_user)
    rec.status = Recommendation.STATUS_CANCELLED
    rec.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Recommendation dismissed.')
    return redirect('gym_user:recommendation_list')
