from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.signals import ensure_role_profile
from apps.admin_panel.models import AssignmentHistory, LoginActivity
from apps.coach.models import AssignedWorkoutPlan, Coach, WorkoutPlan
from apps.health_advisor.models import DietPlan, HealthAdvisor, Recommendation
from apps.gym_user.models import Conversation, FitnessGoal, GymUser, Message, MonthlyWorkoutSchedule, Notification, WorkoutSchedule
from apps.gym_user.messaging import get_or_create_conversation

PASSWORD = 'LazyDemo123!'


def make_user(username, role, *, active=True, superuser=False):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.test',
        password=PASSWORD,
        role=role,
        is_active=active,
        is_staff=(role == 'admin'),
        is_superuser=superuser,
    )
    profile = ensure_role_profile(user)
    if role == 'gym_user':
        profile.user_name = username.title()
        profile.age = 25
        profile.gender = 'Other'
        profile.weight = 70
        profile.height = 175
        profile.neck_in_cm = 35
        profile.waist_in_cm = 80
        profile.calorie_intake = 2000
        profile.profile_completed = True
        profile.save()
    return user


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = make_user('gym_login', 'gym_user')

    def test_login_with_username(self):
        response = self.client.post(reverse('accounts:login'), {'username': 'gym_login', 'password': PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(LoginActivity.objects.filter(username='gym_login', successful=True).exists())

    def test_login_with_email(self):
        response = self.client.post(reverse('accounts:login'), {'username': 'gym_login@example.test', 'password': PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(LoginActivity.objects.filter(username='gym_login@example.test', successful=True).exists())

    def test_wrong_password_stays_on_login_page(self):
        response = self.client.post(reverse('accounts:login'), {'username': 'gym_login', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username/email or password')
        self.assertTrue(LoginActivity.objects.filter(username='gym_login', successful=False).exists())

    def test_inactive_user_is_blocked(self):
        inactive = make_user('inactive_user', 'gym_user', active=False)
        response = self.client.post(reverse('accounts:login'), {'username': inactive.username, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username/email or password')

    def test_public_registration_only_allows_gym_users(self):
        response = self.client.post(reverse('accounts:register'), {
            'username': 'new_gym', 'email': 'new_gym@example.test', 'role': 'gym_user',
            'password': PASSWORD, 'password2': PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='new_gym', role='gym_user').exists())

    def test_public_registration_rejects_admin_coach_advisor(self):
        for role in ['admin', 'fitness_coach', 'health_advisor']:
            response = self.client.post(reverse('accounts:register'), {
                'username': f'bad_{role}', 'email': f'bad_{role}@example.test', 'role': role,
                'password': PASSWORD, 'password2': PASSWORD,
            })
            self.assertEqual(response.status_code, 200)
            self.assertFalse(User.objects.filter(username=f'bad_{role}').exists())


class RoleAccessAndAdminSafetyTests(TestCase):
    def setUp(self):
        self.gym = make_user('role_gym', 'gym_user')
        self.coach = make_user('role_coach', 'fitness_coach')
        self.advisor = make_user('role_advisor', 'health_advisor')
        self.admin = make_user('role_admin', 'admin')
        self.superadmin = make_user('role_superadmin', 'admin', superuser=True)

    def test_wrong_roles_are_blocked(self):
        self.client.login(username=self.gym.username, password=PASSWORD)
        self.assertEqual(self.client.get(reverse('coach:dashboard')).status_code, 302)
        self.assertEqual(self.client.get(reverse('admin_panel:dashboard')).status_code, 302)
        self.client.logout()
        self.client.login(username=self.coach.username, password=PASSWORD)
        self.assertEqual(self.client.get(reverse('admin_panel:dashboard')).status_code, 302)
        self.assertEqual(self.client.get(reverse('gym_user:dashboard')).status_code, 302)
        self.client.logout()
        self.client.login(username=self.advisor.username, password=PASSWORD)
        self.assertEqual(self.client.get(reverse('admin_panel:dashboard')).status_code, 302)
        self.assertEqual(self.client.get(reverse('coach:dashboard')).status_code, 302)
        self.client.logout()
        self.client.login(username=self.admin.username, password=PASSWORD)
        self.assertEqual(self.client.get(reverse('admin_panel:dashboard')).status_code, 200)

    def test_admin_safety_rules(self):
        self.client.login(username=self.admin.username, password=PASSWORD)
        self.client.post(reverse('admin_panel:user_delete', args=[self.admin.id]))
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
        other_admin = make_user('other_admin', 'admin')
        self.client.post(reverse('admin_panel:user_delete', args=[other_admin.id]))
        self.assertTrue(User.objects.filter(pk=other_admin.pk).exists())
        response = self.client.post(reverse('admin_panel:user_add'), {
            'username': 'created_admin', 'email': 'created_admin@example.test', 'role': 'admin',
            'password': PASSWORD, 'password2': PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='created_admin').exists())

    def test_superuser_can_create_admin_and_admin_can_manage_normal_users(self):
        self.client.login(username=self.superadmin.username, password=PASSWORD)
        response = self.client.post(reverse('admin_panel:user_add'), {
            'username': 'created_admin', 'email': 'created_admin@example.test', 'role': 'admin',
            'password': PASSWORD, 'password2': PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='created_admin', role='admin').exists())
        target = make_user('toggle_me', 'gym_user')
        self.client.post(reverse('admin_panel:user_toggle', args=[target.id]), {'next': reverse('admin_panel:user_list')})
        target.refresh_from_db()
        self.assertFalse(target.is_active)


class AssignmentMessagingAndExportTests(TestCase):
    def setUp(self):
        self.admin = make_user('assign_admin', 'admin')
        self.gym = make_user('assign_gym', 'gym_user')
        self.coach = make_user('assign_coach', 'fitness_coach')
        self.advisor = make_user('assign_advisor', 'health_advisor')
        self.other_gym = make_user('other_gym', 'gym_user')

    def test_assignment_history_and_assigned_visibility(self):
        coach_profile = Coach.objects.get(user=self.coach)
        advisor_profile = HealthAdvisor.objects.get(user=self.advisor)
        self.client.login(username=self.admin.username, password=PASSWORD)
        response = self.client.post(reverse('admin_panel:user_assign', args=[self.gym.id]), {
            'assigned_coach': coach_profile.pk,
            'assigned_advisor': advisor_profile.pk,
            'note': 'test assignment',
            'next': reverse('admin_panel:user_list'),
        })
        self.assertRedirects(response, reverse('admin_panel:user_list'))
        self.assertTrue(AssignmentHistory.objects.filter(gym_user__user=self.gym).exists())
        self.client.logout()
        self.client.login(username=self.coach.username, password=PASSWORD)
        response = self.client.get(reverse('coach:assigned_users'))
        self.assertContains(response, 'assign_gym')
        self.assertNotContains(response, 'other_gym')
        self.client.logout()
        self.client.login(username=self.advisor.username, password=PASSWORD)
        response = self.client.get(reverse('health_advisor:assigned_users'))
        self.assertContains(response, 'assign_gym')
        self.assertNotContains(response, 'other_gym')

    def test_shared_messaging_and_unread_flow(self):
        gym_profile = GymUser.objects.get(user=self.gym)
        gym_profile.assigned_coach = Coach.objects.get(user=self.coach)
        gym_profile.assigned_advisor = HealthAdvisor.objects.get(user=self.advisor)
        gym_profile.save()
        conversation = get_or_create_conversation(gym_profile)
        message = Message.objects.create(conversation=conversation, sender=self.coach, body='Please log your workout.')
        message.read_by.add(self.coach)
        self.client.login(username=self.gym.username, password=PASSWORD)
        response = self.client.get(reverse('gym_user:messages'))
        self.assertContains(response, 'Please log your workout.')
        message.refresh_from_db()
        self.assertTrue(message.read_by.filter(pk=self.gym.pk).exists())
        response = self.client.post(reverse('gym_user:messages'), {'body': '', 'attachment_url': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Message cannot be empty')
        self.client.logout()
        self.client.login(username=self.coach.username, password=PASSWORD)
        self.assertEqual(self.client.get(reverse('coach:message_thread', args=[gym_profile.pk])).status_code, 200)
        self.client.logout()
        self.client.login(username=self.advisor.username, password=PASSWORD)
        self.assertEqual(self.client.get(reverse('health_advisor:message_thread', args=[gym_profile.pk])).status_code, 200)

    def test_unassigned_user_empty_state_and_csv_exports(self):
        self.client.login(username=self.other_gym.username, password=PASSWORD)
        self.assertContains(self.client.get(reverse('gym_user:messages')), 'care team has not been fully assigned')
        self.client.logout()
        self.client.login(username=self.admin.username, password=PASSWORD)
        for name in ['export_users', 'export_login_activity', 'export_feedback']:
            response = self.client.get(reverse(f'admin_panel:{name}'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'text/csv')
        self.client.logout()
        self.client.login(username=self.gym.username, password=PASSWORD)
        self.assertEqual(self.client.get(reverse('admin_panel:export_users')).status_code, 302)

class FeatureImprovementTests(TestCase):
    def setUp(self):
        self.admin = make_user('feature_admin', 'admin')
        self.gym = make_user('feature_gym', 'gym_user')
        self.other_gym = make_user('feature_other_gym', 'gym_user')
        self.coach = make_user('feature_coach', 'fitness_coach')
        self.other_coach = make_user('feature_other_coach', 'fitness_coach')
        self.advisor = make_user('feature_advisor', 'health_advisor')
        self.gym_profile = GymUser.objects.get(user=self.gym)
        self.gym_profile.assigned_coach = Coach.objects.get(user=self.coach)
        self.gym_profile.assigned_advisor = HealthAdvisor.objects.get(user=self.advisor)
        self.gym_profile.save()
        self.plan = WorkoutPlan.objects.create(
            coach=self.gym_profile.assigned_coach,
            plan_name='Starter Strength',
            description='Beginner plan',
            difficulty='beginner',
            target_goal='strength',
            duration_weeks=4,
        )

    def test_login_success_uses_auto_toast_message(self):
        response = self.client.post(
            reverse('accounts:login'),
            {'username': self.gym.username, 'password': PASSWORD},
            follow=True,
        )
        self.assertContains(response, 'Login successfully')
        self.assertContains(response, 'data-lf-autohide="true"')

    def test_forgot_password_contact_admin_page(self):
        response = self.client.get(reverse('accounts:forgot_password'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'contact the admin')
        self.assertContains(response, 'force reset')

    def test_fitness_goal_edit_cancel_and_unmark_completed(self):
        self.client.login(username=self.gym.username, password=PASSWORD)
        goal = FitnessGoal.objects.create(
            user=self.gym_profile,
            goal_name='Run 5 km',
            goal_description='Build stamina',
        )
        response = self.client.post(reverse('gym_user:goal_complete', args=[goal.pk]))
        self.assertEqual(response.status_code, 302)
        goal.refresh_from_db()
        self.assertEqual(goal.status, FitnessGoal.STATUS_COMPLETED)

        self.client.post(reverse('gym_user:goal_uncomplete', args=[goal.pk]))
        goal.refresh_from_db()
        self.assertEqual(goal.status, FitnessGoal.STATUS_ACTIVE)

        self.client.post(reverse('gym_user:goal_cancel', args=[goal.pk]))
        goal.refresh_from_db()
        self.assertEqual(goal.status, FitnessGoal.STATUS_CANCELLED)

        response = self.client.post(reverse('gym_user:goal_edit', args=[goal.pk]), {
            'goal_name': 'Run 10 km',
            'goal_description': 'Updated target',
            'status': FitnessGoal.STATUS_NOT_STARTED,
            'target_date': '',
        })
        self.assertEqual(response.status_code, 302)
        goal.refresh_from_db()
        self.assertEqual(goal.goal_name, 'Run 10 km')
        self.assertEqual(goal.status, FitnessGoal.STATUS_NOT_STARTED)

    def test_monthly_and_weekly_schedule_are_separate(self):
        exact_date = timezone.localdate() + timedelta(days=3)
        MonthlyWorkoutSchedule.objects.create(
            user=self.gym_profile,
            title='Leg Day',
            date=exact_date,
            time='07:30',
        )
        WorkoutSchedule.objects.create(
            user=self.gym_profile,
            title='Cardio Routine',
            day='Monday',
            time='18:00',
        )
        self.client.login(username=self.gym.username, password=PASSWORD)

        response = self.client.get(reverse('gym_user:schedule'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Monthly Plan')
        self.assertContains(response, 'Date-by-date planning')
        self.assertContains(response, 'Leg Day')
        self.assertNotContains(response, 'Cardio Routine')
        self.assertNotContains(response, 'Repeat every')

        response = self.client.get(reverse('gym_user:weekly_schedule'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Weekly Routine')
        self.assertContains(response, 'Cardio Routine')
        self.assertNotContains(response, 'Leg Day')
        self.assertContains(response, 'Repeats weekly')

        response = self.client.get(f"{reverse('gym_user:schedule')}?view=week")
        self.assertRedirects(response, reverse('gym_user:weekly_schedule'))

    def test_monthly_schedule_crud_uses_exact_date(self):
        self.client.login(username=self.gym.username, password=PASSWORD)
        response = self.client.post(reverse('gym_user:monthly_schedule_create'), {
            'title': 'Fitness assessment',
            'date': str(timezone.localdate() + timedelta(days=5)),
            'time': '19:00',
            'notes': 'One-off assessment',
        })
        self.assertEqual(response.status_code, 302)
        item = MonthlyWorkoutSchedule.objects.get(title='Fitness assessment')
        self.assertEqual(str(item.date), str(timezone.localdate() + timedelta(days=5)))

        response = self.client.post(reverse('gym_user:monthly_schedule_edit', args=[item.pk]), {
            'title': 'Updated assessment',
            'date': str(timezone.localdate() + timedelta(days=6)),
            'time': '',
            'notes': 'Updated one-off plan',
        })
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.title, 'Updated assessment')
        self.assertEqual(str(item.date), str(timezone.localdate() + timedelta(days=6)))
        self.assertIsNone(item.time)

        self.client.post(reverse('gym_user:monthly_schedule_delete', args=[item.pk]))
        self.assertFalse(MonthlyWorkoutSchedule.objects.filter(pk=item.pk).exists())

    def test_weekly_schedule_crud_uses_weekday_recurrence(self):
        self.client.login(username=self.gym.username, password=PASSWORD)
        response = self.client.post(reverse('gym_user:weekly_schedule_create'), {
            'title': 'Strength Training',
            'day': 'Wednesday',
            'time': '18:00',
            'notes': 'Repeat every week',
        })
        self.assertEqual(response.status_code, 302)
        item = WorkoutSchedule.objects.get(title='Strength Training')
        self.assertEqual(item.day, 'Wednesday')

        response = self.client.post(reverse('gym_user:weekly_schedule_edit', args=[item.pk]), {
            'title': 'Updated Strength Training',
            'day': 'Friday',
            'time': '19:00',
            'notes': 'Updated weekly routine',
        })
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.day, 'Friday')
        self.assertEqual(item.title, 'Updated Strength Training')

        self.client.post(reverse('gym_user:weekly_schedule_delete', args=[item.pk]))
        self.assertFalse(WorkoutSchedule.objects.filter(pk=item.pk).exists())

    def test_admin_unassigned_user_filter(self):
        self.client.login(username=self.admin.username, password=PASSWORD)
        response = self.client.get(reverse('admin_panel:user_list'), {'assignment': 'both_missing'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'feature_other_gym')
        self.assertNotContains(response, 'feature_gym@example.test')

    def test_message_access_control_attachment_validation_and_group_chat_removed(self):
        get_or_create_conversation(self.gym_profile)
        self.client.login(username=self.other_coach.username, password=PASSWORD)
        response = self.client.get(reverse('coach:message_thread', args=[self.gym_profile.pk]))
        self.assertEqual(response.status_code, 404)
        self.client.logout()

        self.client.login(username=self.coach.username, password=PASSWORD)
        response = self.client.get(reverse('coach:message_thread', args=[self.gym_profile.pk]))
        self.assertNotContains(response, 'attachment_url')
        bad_file = SimpleUploadedFile('malware.exe', b'bad', content_type='application/octet-stream')
        response = self.client.post(
            reverse('coach:message_thread', args=[self.gym_profile.pk]),
            {'body': 'Please see attached', 'attachment': bad_file},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'allowed')

        with self.assertRaises(NoReverseMatch):
            reverse('accounts:group_conversation_create')
        with self.assertRaises(NoReverseMatch):
            reverse('accounts:conversation_thread', args=[1])
        response = self.client.get(reverse('coach:messages'))
        self.assertNotContains(response, 'Group Chat')
        self.assertNotContains(response, 'New Group')

    def test_workout_plan_assignment_and_gym_user_tracking(self):
        self.client.login(username=self.coach.username, password=PASSWORD)
        response = self.client.post(reverse('coach:assign_plan_to_user', args=[self.gym_profile.pk]), {
            'plan': self.plan.pk,
            'notes': 'Start this week',
        })
        self.assertEqual(response.status_code, 302)
        assignment = AssignedWorkoutPlan.objects.get(plan=self.plan, gym_user=self.gym_profile)
        self.assertEqual(assignment.status, 'assigned')

        self.client.logout()
        self.client.login(username=self.gym.username, password=PASSWORD)
        response = self.client.get(reverse('gym_user:workout_select'))
        self.assertContains(response, 'Starter Strength')
        self.client.post(reverse('gym_user:assigned_plan_complete', args=[assignment.pk]))
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'completed')
        self.client.post(reverse('gym_user:assigned_plan_uncomplete', args=[assignment.pk]))
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'in_progress')

    def test_diet_plan_creation_assignment_and_recommendation_status(self):
        advisor_profile = self.gym_profile.assigned_advisor
        self.client.login(username=self.advisor.username, password=PASSWORD)
        response = self.client.post(reverse('health_advisor:diet_plan_update', args=[self.gym_profile.pk]), {
            'gym_user': self.gym_profile.pk,
            'title': 'Balanced Cut',
            'description': 'Moderate deficit',
            'target_goal': 'Fat loss',
            'daily_calorie_target': '1900',
            'meal_notes': 'Protein with each meal',
            'restrictions_allergies': 'None',
            'start_date': '2026-06-20',
            'end_date': '2026-07-20',
            'status': 'active',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DietPlan.objects.filter(advisor=advisor_profile, gym_user=self.gym_profile, title='Balanced Cut').exists())

        response = self.client.post(reverse('health_advisor:recommendation_send', args=[self.gym_profile.pk]), {
            'subject': 'Hydration',
            'advice': 'Drink enough water and avoid extreme diets.',
            'status': Recommendation.STATUS_COMPLETED,
        })
        self.assertEqual(response.status_code, 302)
        rec = Recommendation.objects.get(subject='Hydration')
        self.assertEqual(rec.status, Recommendation.STATUS_UNREAD)

        self.client.logout()
        self.client.login(username=self.gym.username, password=PASSWORD)
        self.client.post(reverse('gym_user:recommendation_mark_read', args=[rec.pk]))
        rec.refresh_from_db()
        self.assertEqual(rec.status, Recommendation.STATUS_READ)
        self.client.post(reverse('gym_user:recommendation_unmark_read', args=[rec.pk]))
        rec.refresh_from_db()
        self.assertEqual(rec.status, Recommendation.STATUS_UNREAD)
        self.client.post(reverse('gym_user:recommendation_mark_completed', args=[rec.pk]))
        rec.refresh_from_db()
        self.assertEqual(rec.status, Recommendation.STATUS_COMPLETED)
        self.client.post(reverse('gym_user:recommendation_unmark_completed', args=[rec.pk]))
        rec.refresh_from_db()
        self.assertEqual(rec.status, Recommendation.STATUS_READ)


    def test_mini_chat_sends_message_and_selected_progress_pages(self):
        self.client.login(username=self.coach.username, password=PASSWORD)
        response = self.client.post(reverse('coach:message_thread', args=[self.gym_profile.pk]), {
            'body': 'Mini panel check-in',
            'next': reverse('coach:assigned_users'),
        })
        self.assertRedirects(response, reverse('coach:assigned_users'))
        self.assertTrue(Message.objects.filter(body='Mini panel check-in', conversation__gym_user=self.gym_profile).exists())

        response = self.client.get(reverse('coach:user_progress_detail', args=[self.gym_profile.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.gym_profile.user_name)
        self.assertNotContains(response, self.other_gym.username)

    def test_health_advisor_quick_actions_and_selected_detail(self):
        self.client.login(username=self.advisor.username, password=PASSWORD)
        response = self.client.post(reverse('health_advisor:message_thread', args=[self.gym_profile.pk]), {
            'body': 'Nutrition mini chat',
            'next': reverse('health_advisor:assigned_users'),
        })
        self.assertRedirects(response, reverse('health_advisor:assigned_users'))
        self.assertTrue(Message.objects.filter(body='Nutrition mini chat', conversation__gym_user=self.gym_profile).exists())

        response = self.client.post(reverse('health_advisor:recommendation_send', args=[self.gym_profile.pk]), {
            'subject': 'Sleep',
            'advice': 'Sleep 7 to 8 hours and keep meals balanced.',
            'next': reverse('health_advisor:assigned_users'),
        })
        self.assertRedirects(response, reverse('health_advisor:assigned_users'))
        rec = Recommendation.objects.get(subject='Sleep')
        self.assertEqual(rec.status, Recommendation.STATUS_UNREAD)

        response = self.client.get(reverse('health_advisor:user_profile', args=[self.gym_profile.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.gym_profile.user_name)
        self.assertNotContains(response, self.other_gym.username)

    def test_dashboard_and_plan_pages_show_quick_chat_and_own_bubble_side(self):
        conversation = get_or_create_conversation(self.gym_profile)
        Message.objects.create(conversation=conversation, sender=self.coach, body='Coach reminder')
        Message.objects.create(conversation=conversation, sender=self.advisor, body='Advisor reminder')
        Message.objects.create(conversation=conversation, sender=self.gym, body='I will do it')
        AssignedWorkoutPlan.objects.create(
            plan=self.plan,
            gym_user=self.gym_profile,
            assigned_by=self.gym_profile.assigned_coach,
        )

        self.client.login(username=self.gym.username, password=PASSWORD)
        response = self.client.get(reverse('gym_user:dashboard'))
        self.assertContains(response, 'dashboardChatPanel')
        self.assertContains(response, 'chat-row-out')
        self.assertContains(response, 'chat-row-in')
        self.assertContains(response, 'chat-role-gym-user')
        self.assertContains(response, 'chat-role-fitness-coach')
        self.assertContains(response, 'chat-role-health-advisor')
        self.assertContains(response, 'Gym User')
        self.assertContains(response, 'Fitness Coach')
        self.assertContains(response, 'Health Advisor')

        response = self.client.get(reverse('gym_user:messages'))
        self.assertContains(response, 'chat-row-out')
        self.assertContains(response, 'chat-row-in')
        self.assertContains(response, 'chat-role-gym-user')
        self.assertContains(response, 'chat-role-fitness-coach')
        self.assertContains(response, 'chat-role-health-advisor')

        response = self.client.get(reverse('gym_user:workout_select'))
        self.assertContains(response, 'workoutChatPanel')
        self.assertContains(response, 'Message Care Team')
        self.client.logout()

        self.client.login(username=self.coach.username, password=PASSWORD)
        response = self.client.get(reverse('coach:dashboard'))
        self.assertContains(response, f'dashboardMessage{self.gym_profile.pk}')

        response = self.client.get(reverse('coach:plan_detail', args=[self.plan.pk]))
        assignment = AssignedWorkoutPlan.objects.get(plan=self.plan, gym_user=self.gym_profile)
        self.assertContains(response, f'planMessage{assignment.pk}')

    def test_notification_read_and_opened_behavior(self):
        notification = Notification.objects.create(
            recipient=self.gym,
            title='Workout plan assigned',
            message='Open this plan.',
            url=reverse('gym_user:workout_select'),
        )
        self.client.login(username=self.gym.username, password=PASSWORD)
        response = self.client.get(reverse('accounts:notifications'))
        self.assertContains(response, 'Workout plan assigned')
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertFalse(notification.is_opened)
        self.assertContains(response, 'notification-dot')

        response = self.client.get(reverse('accounts:notification_open', args=[notification.pk]))
        self.assertRedirects(response, reverse('gym_user:workout_select'))
        notification.refresh_from_db()
        self.assertTrue(notification.is_opened)

        notification.is_read = False
        notification.is_opened = False
        notification.save(update_fields=['is_read', 'is_opened'])
        response = self.client.get(reverse('accounts:notification_mark_all_read'))
        self.assertRedirects(response, reverse('accounts:notifications'))
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertFalse(notification.is_opened)

    def test_safe_back_blocks_external_url(self):
        self.client.login(username=self.coach.username, password=PASSWORD)
        response = self.client.get(reverse('coach:plan_create'), {'next': 'https://evil.example/steal'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/coach/plans/"')

    def test_plain_ui_has_no_bootstrap_cdn_or_data_bs(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[2].parent
        combined = ''
        for folder in ['templates', 'static']:
            for item in (root / folder).rglob('*'):
                if item.is_file():
                    combined += item.read_text(errors='ignore')
        self.assertNotIn('cdn.jsdelivr', combined)
        self.assertNotIn('data-bs-', combined)

    def test_removed_demo_guide_and_system_health_links(self):
        self.assertEqual(self.client.get('/demo-guide/').status_code, 404)
        self.assertEqual(self.client.get('/admin-panel/system-health/').status_code, 404)
        self.client.login(username=self.admin.username, password=PASSWORD)
        response = self.client.get(reverse('admin_panel:dashboard'))
        self.assertNotContains(response, 'Demo Guide')
        self.assertNotContains(response, 'System Health')

    def test_plan_cancel_uses_safe_previous_page(self):
        self.client.login(username=self.coach.username, password=PASSWORD)
        response = self.client.get(
            reverse('coach:plan_create'),
            HTTP_REFERER='/coach/dashboard/',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/coach/dashboard/"')
