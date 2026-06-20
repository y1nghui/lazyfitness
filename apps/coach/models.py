"""
SUBSYSTEM 2 – FITNESS COACH
Assigned to: Chong Jia Zhen
Models: Coach, WorkoutPlan, Workout, Exercise, ProfessionalFeedback, AssignedWorkoutPlan
"""
from django.db import models
from django.utils import timezone

from apps.accounts.models import User


class Coach(models.Model):
    """Table 3: coach profile."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    coach_name = models.CharField(max_length=255)
    specialty = models.CharField(
        max_length=120,
        blank=True,
        help_text='Public specialty shown on the Meet Our Coaches section.',
    )
    years_experience = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Optional years of coaching experience for the public team card.',
    )
    bio = models.TextField(
        blank=True,
        help_text='Short public bio shown to prospective gym users.',
    )

    def __str__(self):
        return f"Coach: {self.coach_name}"


class WorkoutPlan(models.Model):
    """Table 8: workoutPlan — top-level plan created by a coach."""
    DIFFICULTY_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    GOAL_CHOICES = [
        ('general', 'General Fitness'),
        ('weight_loss', 'Weight Loss'),
        ('strength', 'Strength'),
        ('endurance', 'Endurance'),
        ('mobility', 'Mobility'),
    ]

    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name='plans')
    plan_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='beginner')
    target_goal = models.CharField(max_length=40, choices=GOAL_CHOICES, default='general')
    duration_weeks = models.PositiveIntegerField(default=4)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['plan_name']

    def __str__(self):
        return f"{self.plan_name} by {self.coach.coach_name}"


class AssignedWorkoutPlan(models.Model):
    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    plan = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, related_name='assignments')
    gym_user = models.ForeignKey('gym_user.GymUser', on_delete=models.CASCADE, related_name='assigned_workout_plans')
    assigned_by = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name='workout_assignments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    notes = models.TextField(blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateField(null=True, blank=True)
    completed_at = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-assigned_at']
        unique_together = ('plan', 'gym_user')

    def mark_completed(self):
        self.status = 'completed'
        self.completed_at = timezone.localdate()
        self.save(update_fields=['status', 'completed_at'])

    def __str__(self):
        return f"{self.plan.plan_name} assigned to {self.gym_user.user_name}"


class Workout(models.Model):
    """Table 9: workout — a specific session inside a plan."""
    plan = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, related_name='workouts')
    workout_name = models.CharField(max_length=255)
    status = models.BooleanField(default=True, help_text="True = available")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.workout_name} ({self.plan.plan_name})"


class Exercise(models.Model):
    """Table 10: exercise — individual exercise inside a workout."""
    workout = models.ForeignKey(Workout, on_delete=models.CASCADE, related_name='exercises')
    exercise_name = models.CharField(max_length=255)
    exercise_reps = models.IntegerField()
    sets = models.PositiveIntegerField(default=3)
    rest_seconds = models.PositiveIntegerField(default=60)
    video_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.exercise_name} x{self.exercise_reps}"


class ProfessionalFeedback(models.Model):
    """
    Table 12: professionalFeedback
    Coach gives a rating + comment on a specific ActivityLog entry.
    """
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name='feedbacks')
    gym_user = models.ForeignKey(
        'gym_user.GymUser', on_delete=models.CASCADE, related_name='coach_feedbacks'
    )
    activity_log = models.ForeignKey(
        'gym_user.ActivityLog', on_delete=models.CASCADE, related_name='coach_feedbacks'
    )
    rating = models.IntegerField(help_text="1–10")
    comment = models.TextField()
    attachment_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Feedback by {self.coach.coach_name} → {self.gym_user.user_name}"
