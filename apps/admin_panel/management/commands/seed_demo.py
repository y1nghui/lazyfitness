from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.signals import ensure_role_profile
from apps.admin_panel.models import LoginActivity, SystemLog
from apps.gym_user.models import ActivityLog, BodyMeasurement, FitnessGoal, MonthlyWorkoutSchedule, WorkoutSchedule
from apps.gym_user.messaging import get_or_create_conversation
from apps.coach.models import AssignedWorkoutPlan, Exercise, Workout, WorkoutPlan
from apps.health_advisor.models import DietPlan, HealthReport, Recommendation

DEFAULT_PASSWORD = 'LazyDemo123!'


class Command(BaseCommand):
    help = 'Create safe LazyFitness demo data for student presentations.'

    def _user(self, username, email, role, **extra):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email, 'role': role, 'is_active': True, **extra},
        )
        changed = False
        if user.email != email:
            user.email = email
            changed = True
        if user.role != role:
            user.role = role
            changed = True
        if role == 'admin':
            user.is_staff = True
            user.is_superuser = extra.get('is_superuser', user.is_superuser)
            changed = True
        if created or not user.has_usable_password():
            user.set_password(DEFAULT_PASSWORD)
            changed = True
        if changed:
            user.save()
        ensure_role_profile(user)
        return user

    def handle(self, *args, **options):
        admin = self._user('demo_admin', 'demo_admin@lazyfitness.test', 'admin', is_staff=True, is_superuser=True)
        coaches = [
            self._user('coach_strength', 'coach_strength@lazyfitness.test', 'fitness_coach'),
            self._user('coach_cardio', 'coach_cardio@lazyfitness.test', 'fitness_coach'),
        ]
        advisors = [
            self._user('advisor_nutrition', 'advisor_nutrition@lazyfitness.test', 'health_advisor'),
            self._user('advisor_wellness', 'advisor_wellness@lazyfitness.test', 'health_advisor'),
        ]
        for user, specialty, exp, bio in [
            (coaches[0], 'Strength Training', 5, 'Helps beginners build safe strength routines.'),
            (coaches[1], 'Cardio Fitness', 4, 'Focuses on stamina, consistency and healthy habits.'),
            (advisors[0], 'Nutrition Planning', 6, 'Creates practical meal guidance for busy students.'),
            (advisors[1], 'Lifestyle Wellness', 3, 'Supports sustainable lifestyle and recovery routines.'),
        ]:
            profile = ensure_role_profile(user)
            profile.specialty = specialty
            profile.years_experience = exp
            profile.bio = bio
            profile.save()

        gym_users = [
            self._user('gym_alex', 'gym_alex@lazyfitness.test', 'gym_user'),
            self._user('gym_bella', 'gym_bella@lazyfitness.test', 'gym_user'),
            self._user('gym_chris', 'gym_chris@lazyfitness.test', 'gym_user'),
        ]
        for i, user in enumerate(gym_users):
            profile = ensure_role_profile(user)
            profile.user_name = ['Alex Tan', 'Bella Lim', 'Chris Wong'][i]
            profile.age = 22 + i
            profile.gender = ['Male', 'Female', 'Male'][i]
            profile.weight = [70, 58, 82][i]
            profile.height = [175, 164, 178][i]
            profile.neck_in_cm = [38, 32, 40][i]
            profile.waist_in_cm = [82, 70, 90][i]
            profile.calorie_intake = [2200, 1800, 2400][i]
            profile.medical_condition = 'None declared'
            profile.profile_completed = True
            profile.assigned_coach = ensure_role_profile(coaches[i % 2])
            profile.assigned_advisor = ensure_role_profile(advisors[i % 2])
            profile.save()
            profile.assigned_advisor.assigned_users.add(profile)
            FitnessGoal.objects.get_or_create(
                user=profile,
                goal_name='Build consistent routine',
                defaults={'goal_description': 'Train at least three times per week.', 'status': 'active'},
            )
            BodyMeasurement.objects.get_or_create(
                gym_user=profile,
                recorded_at=timezone.localdate(),
                defaults={
                    'weight': profile.weight,
                    'waist_in_cm': profile.waist_in_cm,
                    'neck_in_cm': profile.neck_in_cm,
                    'calorie_intake': profile.calorie_intake,
                    'notes': 'Demo starting measurement.',
                },
            )
            WorkoutSchedule.objects.get_or_create(
                user=profile,
                day='Monday',
                time='18:00',
                defaults={'title': 'Full Body Workout', 'notes': 'Focus on good form.'},
            )
            MonthlyWorkoutSchedule.objects.get_or_create(
                user=profile,
                date=timezone.localdate() + timedelta(days=i + 2),
                title='Fitness assessment' if i == 0 else 'Date-specific training plan',
                defaults={
                    'time': '18:30',
                    'notes': 'One-off monthly plan for the selected calendar date.',
                },
            )
            ActivityLog.objects.get_or_create(
                user=profile,
                workouts_completed=1,
                reps_completed=60,
                workout_duration=45,
                workout_streak=i + 1,
            )
            convo = get_or_create_conversation(profile)
            if not convo.messages.exists():
                msg = convo.messages.create(sender=user, body='Hi team, I am ready to start my LazyFitness plan!')
                msg.read_by.add(user)
            HealthReport.objects.get_or_create(
                advisor=profile.assigned_advisor,
                gym_user=profile,
                defaults={
                    'diet_plan': 'Balanced meals with protein, vegetables and hydration.',
                    'notes': 'Demo report.',
                },
            )
            DietPlan.objects.get_or_create(
                advisor=profile.assigned_advisor,
                gym_user=profile,
                title='Balanced Starter Plan',
                defaults={
                    'description': 'Simple balanced meals to support consistent training.',
                    'target_goal': 'Improve energy and recovery',
                    'daily_calorie_target': profile.calorie_intake,
                    'meal_notes': 'Include protein, vegetables, whole grains and hydration.',
                    'restrictions_allergies': 'None declared',
                    'start_date': timezone.localdate(),
                    'status': 'active',
                },
            )
            Recommendation.objects.get_or_create(
                advisor=profile.assigned_advisor,
                gym_user=profile,
                subject='Hydration reminder',
                defaults={'advice': 'Drink enough water before and after workouts.', 'status': 'sent'},
            )

        coach_profile = ensure_role_profile(coaches[0])
        plan, _ = WorkoutPlan.objects.get_or_create(
            coach=coach_profile,
            plan_name='Beginner Strength Plan',
            defaults={
                'description': 'A safe starter strength plan for beginners.',
                'difficulty': 'beginner',
                'target_goal': 'strength',
                'duration_weeks': 4,
            },
        )
        workout, _ = Workout.objects.get_or_create(
            plan=plan,
            workout_name='Day 1 Full Body',
            defaults={'status': True, 'notes': 'Keep rest moderate and form controlled.'},
        )
        Exercise.objects.get_or_create(workout=workout, exercise_name='Squat', defaults={'exercise_reps': 12, 'sets': 3})
        Exercise.objects.get_or_create(workout=workout, exercise_name='Push Up', defaults={'exercise_reps': 10, 'sets': 3})
        for user in gym_users:
            profile = ensure_role_profile(user)
            if profile.assigned_coach_id == coach_profile.pk:
                AssignedWorkoutPlan.objects.get_or_create(
                    plan=plan,
                    gym_user=profile,
                    defaults={'assigned_by': coach_profile, 'notes': 'Demo assigned workout plan.'},
                )

        for user in [admin, *coaches, *advisors, *gym_users]:
            LoginActivity.objects.get_or_create(user=user, username=user.username, role=user.role, defaults={'successful': True})
        SystemLog.record('user_created', 'Demo seed data created or refreshed', user=admin, module='Demo')

        self.stdout.write(self.style.SUCCESS('LazyFitness demo data is ready.'))
        self.stdout.write('Demo password for all accounts: ' + DEFAULT_PASSWORD)
        self.stdout.write('Try: demo_admin, coach_strength, advisor_nutrition, gym_alex')
