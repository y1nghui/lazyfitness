from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounts.decorators import health_advisor_required
from apps.gym_user.forms import MessageForm
from apps.gym_user.messaging import (
    care_team_ready,
    conversation_unread_count,
    get_or_create_conversation,
    mark_conversation_read,
    notify_conversation_participants,
    notify_user,
)
from apps.gym_user.models import GymUser
from lazyfitness.view_helpers import paginate, safe_back_url, safe_next_url

from .forms import DietPlanForm, HealthReportForm, RecommendationForm
from .models import DietPlan, HealthAdvisor, HealthReport, Recommendation


def _next_or(request, fallback):
    return safe_next_url(request.POST.get('next') or request.GET.get('next'), fallback)


@health_advisor_required
def dashboard(request):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    assigned = GymUser.objects.filter(assigned_advisor=advisor).select_related('user', 'assigned_coach')
    user_rows = []
    for gym_user in assigned:
        ready = care_team_ready(gym_user)
        conversation = get_or_create_conversation(gym_user) if ready else getattr(gym_user, 'conversation', None)
        user_rows.append({
            'gym_user': gym_user,
            'ready': ready,
            'conversation': conversation,
            'bmi': gym_user.calculate_bmi(),
            'bmi_category': gym_user.bmi_category(),
            'latest_report': gym_user.health_reports.filter(advisor=advisor).first(),
            'latest_diet_plan': gym_user.diet_plans.filter(advisor=advisor).first(),
            'latest_recommendation': gym_user.recommendations.filter(advisor=advisor).first(),
            'recent_messages': conversation.messages.select_related('sender').order_by('-created_at')[:5] if conversation else [],
            'unread_count': conversation_unread_count(conversation, request.user) if conversation else 0,
        })
    context = {
        'advisor': advisor,
        'assigned_users': assigned,
        'user_rows': user_rows,
        'assigned_count': assigned.count(),
        'diet_plan_count': advisor.diet_plans.count(),
        'recent_reports': advisor.reports.filter(gym_user__assigned_advisor=advisor).select_related('gym_user').order_by('-date')[:5],
        'recent_diet_plans': advisor.diet_plans.filter(gym_user__assigned_advisor=advisor).select_related('gym_user')[:5],
        'recent_recommendations': advisor.recommendations.filter(gym_user__assigned_advisor=advisor).order_by('-created_at')[:5],
    }
    return render(request, 'health_advisor/dashboard.html', context)


@health_advisor_required
def assigned_users(request):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    search = request.GET.get('q', '').strip()
    bmi_filter = request.GET.get('bmi', '')
    unread_filter = request.GET.get('unread', '')
    report_filter = request.GET.get('report', '')
    rec_status = request.GET.get('rec_status', '')
    users = GymUser.objects.filter(assigned_advisor=advisor).select_related('user', 'assigned_coach')
    if search:
        users = users.filter(
            Q(user__username__icontains=search)
            | Q(user__email__icontains=search)
            | Q(user_name__icontains=search)
        )
    rows = []
    for gym_user in users:
        conversation = get_or_create_conversation(gym_user) if care_team_ready(gym_user) else getattr(gym_user, 'conversation', None)
        unread_count = conversation_unread_count(conversation, request.user) if conversation else 0
        recent_messages = conversation.messages.select_related('sender').order_by('-created_at')[:5] if conversation else []
        bmi_category = gym_user.bmi_category()
        latest_report = gym_user.health_reports.filter(advisor=advisor).first()
        latest_diet_plan = gym_user.diet_plans.filter(advisor=advisor).first()
        latest_recommendation = gym_user.recommendations.filter(advisor=advisor).first()
        if bmi_filter and bmi_category != bmi_filter:
            continue
        if unread_filter == 'yes' and unread_count == 0:
            continue
        if unread_filter == 'no' and unread_count > 0:
            continue
        if report_filter == 'yes' and latest_diet_plan is None:
            continue
        if report_filter == 'no' and latest_diet_plan is not None:
            continue
        if rec_status and not gym_user.recommendations.filter(advisor=advisor, status=rec_status).exists():
            continue
        rows.append({
            'gym_user': gym_user,
            'bmi': gym_user.calculate_bmi(),
            'bmi_category': bmi_category,
            'latest_report': latest_report,
            'latest_diet_plan': latest_diet_plan,
            'latest_recommendation': latest_recommendation,
            'recent_messages': recent_messages,
            'unread_count': unread_count,
        })
    page_obj, page_query = paginate(request, rows, per_page=10)
    return render(request, 'health_advisor/assigned_users.html', {
        'advisor': advisor,
        'users': users,
        'rows': page_obj.object_list,
        'page_obj': page_obj,
        'page_query': page_query,
        'search': search,
        'bmi_filter': bmi_filter,
        'unread_filter': unread_filter,
        'report_filter': report_filter,
        'rec_status': rec_status,
        'bmi_categories': ['Underweight', 'Healthy', 'Overweight', 'Obese', 'Unknown'],
        'recommendation_status_choices': Recommendation.STATUS_CHOICES,
    })


@health_advisor_required
def user_profile(request, user_id):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    gym_user = get_object_or_404(GymUser, pk=user_id, assigned_advisor=advisor)
    context = {
        'advisor': advisor,
        'gym_user': gym_user,
        'bmi': gym_user.calculate_bmi(),
        'bmi_category': gym_user.bmi_category(),
        'logs': gym_user.logs.order_by('-logged_at')[:10],
        'measurements': gym_user.measurements.all()[:5],
        'latest_report': gym_user.health_reports.filter(advisor=advisor).first(),
        'reports': gym_user.health_reports.filter(advisor=advisor)[:10],
        'diet_plans': gym_user.diet_plans.filter(advisor=advisor)[:10],
        'recommendations': gym_user.recommendations.filter(advisor=advisor).order_by('-created_at')[:10],
    }
    return render(request, 'health_advisor/user_profile.html', context)


@health_advisor_required
def diet_plan_list(request):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    plans = advisor.diet_plans.filter(gym_user__assigned_advisor=advisor).select_related('gym_user').all()
    status = request.GET.get('status', '')
    if status:
        plans = plans.filter(status=status)
    page_obj, page_query = paginate(request, plans, per_page=20)
    plan_rows = []
    for plan in page_obj.object_list:
        gym_user = plan.gym_user
        ready = care_team_ready(gym_user)
        conversation = get_or_create_conversation(gym_user) if ready else getattr(gym_user, 'conversation', None)
        plan_rows.append({
            'plan': plan,
            'ready': ready,
            'conversation': conversation,
            'recent_messages': conversation.messages.select_related('sender').order_by('-created_at')[:5] if conversation else [],
            'unread_count': conversation_unread_count(conversation, request.user) if conversation else 0,
        })
    return render(request, 'health_advisor/diet_plan_list.html', {
        'advisor': advisor,
        'diet_plans': page_obj.object_list,
        'plan_rows': plan_rows,
        'page_obj': page_obj,
        'page_query': page_query,
        'status': status,
        'status_choices': DietPlan.STATUS_CHOICES,
    })


@health_advisor_required
def diet_plan_create(request, user_id=None):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    initial_user = None
    if user_id:
        initial_user = get_object_or_404(GymUser, pk=user_id, assigned_advisor=advisor)
    if request.method == 'POST':
        form = DietPlanForm(request.POST, advisor=advisor)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.advisor = advisor
            plan.save()
            HealthReport.objects.create(
                advisor=advisor,
                gym_user=plan.gym_user,
                diet_plan=plan.meal_notes or plan.description,
                notes=f'Diet plan created: {plan.title}',
            )
            notify_user(
                plan.gym_user.user,
                'Diet plan assigned',
                f'{advisor.advisor_name} assigned a diet plan: {plan.title}.',
                reverse('gym_user:dashboard'),
            )
            messages.success(request, 'Diet plan saved and assigned successfully.')
            return redirect(safe_back_url(request, reverse('health_advisor:diet_plan_detail', args=[plan.id])))
        messages.error(request, 'Please correct the highlighted diet plan errors.')
    else:
        form = DietPlanForm(advisor=advisor, initial_user=initial_user)
    return render(request, 'health_advisor/diet_plan_form.html', {
        'form': form,
        'gym_user': initial_user,
        'mode': 'Create',
        'cancel_url': safe_back_url(request, reverse('health_advisor:diet_plan_list')),
    })


@health_advisor_required
def diet_plan_update(request, user_id):
    return diet_plan_create(request, user_id=user_id)


@health_advisor_required
def diet_plan_detail(request, plan_id):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    plan = get_object_or_404(DietPlan, pk=plan_id, advisor=advisor, gym_user__assigned_advisor=advisor)
    ready = care_team_ready(plan.gym_user)
    conversation = get_or_create_conversation(plan.gym_user) if ready else getattr(plan.gym_user, 'conversation', None)
    return render(request, 'health_advisor/diet_plan_detail.html', {
        'advisor': advisor,
        'plan': plan,
        'can_message': ready,
        'recent_messages': conversation.messages.select_related('sender').order_by('-created_at')[:5] if conversation else [],
    })


@health_advisor_required
def diet_plan_edit(request, plan_id):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    plan = get_object_or_404(DietPlan, pk=plan_id, advisor=advisor, gym_user__assigned_advisor=advisor)
    if request.method == 'POST':
        form = DietPlanForm(request.POST, instance=plan, advisor=advisor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Diet plan updated successfully.')
            return redirect(safe_back_url(request, reverse('health_advisor:diet_plan_detail', args=[plan.id])))
        messages.error(request, 'Please correct the highlighted diet plan errors.')
    else:
        form = DietPlanForm(instance=plan, advisor=advisor)
    return render(request, 'health_advisor/diet_plan_form.html', {
        'form': form,
        'gym_user': plan.gym_user,
        'plan': plan,
        'mode': 'Edit',
        'cancel_url': safe_back_url(request, reverse('health_advisor:diet_plan_detail', args=[plan.id])),
    })


@health_advisor_required
def recommendation_list(request):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    recs = advisor.recommendations.filter(gym_user__assigned_advisor=advisor).select_related('gym_user').order_by('-created_at')
    status = request.GET.get('status', '')
    if status:
        recs = recs.filter(status=status)
    page_obj, page_query = paginate(request, recs, per_page=20)
    return render(request, 'health_advisor/recommendation_list.html', {
        'advisor': advisor,
        'recommendations': page_obj.object_list,
        'page_obj': page_obj,
        'page_query': page_query,
        'status': status,
        'status_choices': Recommendation.STATUS_CHOICES,
    })


@health_advisor_required
def recommendation_send(request, user_id):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    gym_user = get_object_or_404(GymUser, pk=user_id, assigned_advisor=advisor)
    if request.method == 'POST':
        form = RecommendationForm(request.POST)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.advisor = advisor
            rec.gym_user = gym_user
            rec.status = Recommendation.STATUS_UNREAD
            rec.save()
            notify_user(
                gym_user.user,
                'New health recommendation',
                rec.subject,
                reverse('gym_user:recommendation_list'),
            )
            messages.success(request, 'Recommendation sent successfully.')
            return redirect(safe_back_url(request, reverse('health_advisor:recommendation_list')))
        messages.error(request, 'Please correct the highlighted recommendation errors.')
    else:
        form = RecommendationForm()
    return render(request, 'health_advisor/recommendation_form.html', {
        'form': form,
        'gym_user': gym_user,
        'mode': 'Create',
        'cancel_url': safe_back_url(request, reverse('health_advisor:assigned_users')),
    })


@health_advisor_required
def recommendation_edit(request, recommendation_id):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    rec = get_object_or_404(Recommendation, pk=recommendation_id, advisor=advisor, gym_user__assigned_advisor=advisor)
    if request.method == 'POST':
        form = RecommendationForm(request.POST, instance=rec)
        if form.is_valid():
            form.save()
            messages.success(request, 'Recommendation content updated.')
            return redirect(safe_back_url(request, reverse('health_advisor:recommendation_list')))
        messages.error(request, 'Please correct the highlighted recommendation errors.')
    else:
        form = RecommendationForm(instance=rec)
    return render(request, 'health_advisor/recommendation_form.html', {
        'form': form,
        'gym_user': rec.gym_user,
        'recommendation': rec,
        'mode': 'Edit',
        'cancel_url': safe_back_url(request, reverse('health_advisor:recommendation_list')),
    })


@health_advisor_required
def message_list(request):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    users = GymUser.objects.filter(assigned_advisor=advisor).select_related('user', 'assigned_coach', 'assigned_coach__user')
    conversations = {
        conversation.gym_user_id: conversation
        for conversation in advisor.conversations.select_related('gym_user', 'gym_user__user', 'coach').prefetch_related('messages')
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
    return render(request, 'health_advisor/messages.html', {
        'advisor': advisor,
        'rows': rows,
    })


@health_advisor_required
def message_thread(request, user_id):
    advisor = get_object_or_404(HealthAdvisor, user=request.user)
    gym_user = get_object_or_404(
        GymUser.objects.select_related('user', 'assigned_coach', 'assigned_advisor'),
        pk=user_id,
        assigned_advisor=advisor,
    )
    if not care_team_ready(gym_user):
        messages.info(request, 'This user needs both a coach and a health advisor before the shared conversation can start.')
        return redirect('health_advisor:messages')
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
            return redirect(safe_back_url(request, reverse('health_advisor:message_thread', args=[gym_user.pk])))
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
        'back_url_name': 'health_advisor:messages',
    })
