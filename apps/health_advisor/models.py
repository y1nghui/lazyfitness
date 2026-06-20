from django.db import models

from apps.accounts.models import User


class HealthAdvisor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    advisor_name = models.CharField(max_length=255)
    specialty = models.CharField(
        max_length=120,
        blank=True,
        help_text='Public specialty shown on the Meet Our Health Advisors section.',
    )
    years_experience = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Optional years of health advisory experience for the public team card.',
    )
    bio = models.TextField(blank=True, help_text='Short public bio shown to prospective gym users.')
    assigned_users = models.ManyToManyField('gym_user.GymUser', blank=True, related_name='health_advisors')

    def __str__(self):
        return f"Advisor: {self.advisor_name}"


class HealthReport(models.Model):
    advisor = models.ForeignKey(HealthAdvisor, on_delete=models.CASCADE, related_name='reports')
    gym_user = models.ForeignKey('gym_user.GymUser', on_delete=models.CASCADE, related_name='health_reports')
    date = models.DateTimeField(auto_now_add=True)
    diet_plan = models.TextField(blank=True, help_text="Diet plan details / notes")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Report for {self.gym_user.user_name} by {self.advisor.advisor_name} on {self.date:%Y-%m-%d}"


class DietPlan(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    advisor = models.ForeignKey(HealthAdvisor, on_delete=models.CASCADE, related_name='diet_plans')
    gym_user = models.ForeignKey('gym_user.GymUser', on_delete=models.CASCADE, related_name='diet_plans')
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    target_goal = models.CharField(max_length=160, blank=True)
    daily_calorie_target = models.PositiveIntegerField(null=True, blank=True)
    meal_notes = models.TextField(blank=True)
    restrictions_allergies = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} for {self.gym_user.user_name}"


class Recommendation(models.Model):
    STATUS_UNREAD = 'sent'
    STATUS_READ = 'read'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_UNREAD, 'Unread'),
        (STATUS_READ, 'Read'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    advisor = models.ForeignKey(HealthAdvisor, on_delete=models.CASCADE, related_name='recommendations')
    gym_user = models.ForeignKey('gym_user.GymUser', on_delete=models.CASCADE, related_name='recommendations')
    subject = models.CharField(max_length=255)
    advice = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNREAD)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Rec: {self.subject} → {self.gym_user.user_name}"
