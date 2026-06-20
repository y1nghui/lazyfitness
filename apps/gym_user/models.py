from django.db import models
from django.utils import timezone

from apps.accounts.models import User


class GymUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    user_name = models.CharField(max_length=255)
    age = models.IntegerField()
    gender = models.CharField(max_length=20)
    weight = models.FloatField(help_text="in kg")
    height = models.FloatField(help_text="in cm")
    neck_in_cm = models.IntegerField()
    waist_in_cm = models.IntegerField()
    calorie_intake = models.IntegerField(help_text="daily target kcal")
    medical_condition = models.TextField(blank=True, null=True)
    profile_completed = models.BooleanField(default=False)
    assigned_coach = models.ForeignKey(
        'coach.Coach',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_gym_users',
        help_text='Fitness coach assigned by admin.',
    )
    assigned_advisor = models.ForeignKey(
        'health_advisor.HealthAdvisor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_gym_users',
        help_text='Health advisor assigned by admin.',
    )

    def calculate_bmi(self):
        if not self.height or self.height <= 0 or not self.weight or self.weight <= 0:
            return None
        h_m = self.height / 100
        return round(self.weight / (h_m ** 2), 2)

    def bmi_category(self):
        bmi = self.calculate_bmi()
        if bmi is None:
            return 'Unknown'
        if bmi < 18.5:
            return 'Underweight'
        if bmi < 25:
            return 'Healthy'
        if bmi < 30:
            return 'Overweight'
        return 'Obese'

    def __str__(self):
        return f"GymUser: {self.user_name}"


class BodyMeasurement(models.Model):
    gym_user = models.ForeignKey(GymUser, on_delete=models.CASCADE, related_name='measurements')
    weight = models.FloatField(help_text='Weight in kg')
    waist_in_cm = models.FloatField(help_text='Waist circumference in cm')
    neck_in_cm = models.FloatField(help_text='Neck circumference in cm')
    calorie_intake = models.PositiveIntegerField(help_text='Daily calorie target')
    notes = models.TextField(blank=True)
    recorded_at = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at', '-created_at']

    def __str__(self):
        return f"{self.gym_user.user_name} measurement on {self.recorded_at}"


class FitnessGoal(models.Model):
    STATUS_NOT_STARTED = 'not_started'
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_OVERDUE = 'overdue'

    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, 'Not Started'),
        (STATUS_ACTIVE, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_OVERDUE, 'Overdue'),
    ]

    user = models.ForeignKey(GymUser, on_delete=models.CASCADE, related_name='goals')
    goal_name = models.CharField(max_length=255)
    goal_description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    target_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['status', '-created_at']

    @property
    def is_overdue(self):
        return bool(
            self.target_date
            and self.target_date < timezone.localdate()
            and self.status not in [self.STATUS_COMPLETED, self.STATUS_CANCELLED]
        )

    @property
    def effective_status(self):
        return self.STATUS_OVERDUE if self.is_overdue else self.status

    @property
    def effective_status_label(self):
        return dict(self.STATUS_CHOICES).get(self.effective_status, self.status.title())

    def __str__(self):
        return f"{self.goal_name} ({self.user.user_name})"


class WorkoutSchedule(models.Model):
    DAY_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]
    user = models.ForeignKey(GymUser, on_delete=models.CASCADE, related_name='schedules')
    day = models.CharField(max_length=20, choices=DAY_CHOICES)
    time = models.TimeField()
    title = models.CharField(max_length=120, blank=True, default='Workout')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['day', 'time']

    def __str__(self):
        return f"{self.user.user_name} — {self.day} {self.time}"


class MonthlyWorkoutSchedule(models.Model):
    user = models.ForeignKey(GymUser, on_delete=models.CASCADE, related_name='monthly_schedules')
    title = models.CharField(max_length=120)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'time', 'title']

    def __str__(self):
        when = self.date.strftime('%Y-%m-%d')
        if self.time:
            when = f"{when} {self.time.strftime('%H:%M')}"
        return f"{self.user.user_name} — {when} — {self.title}"


class ActivityLog(models.Model):
    user = models.ForeignKey(GymUser, on_delete=models.CASCADE, related_name='logs')
    plan = models.ForeignKey(
        'coach.WorkoutPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
    )
    workouts_completed = models.IntegerField(default=0)
    reps_completed = models.IntegerField(default=0)
    workout_duration = models.IntegerField(default=0, help_text="minutes")
    workout_streak = models.IntegerField(default=0, help_text="consecutive days")
    logged_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Log {self.id} — {self.user.user_name} on {self.logged_at}"


class Conversation(models.Model):
    gym_user = models.OneToOneField(
        GymUser,
        on_delete=models.CASCADE,
        related_name='conversation',
        null=True,
        blank=True,
    )
    coach = models.ForeignKey(
        'coach.Coach',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
    )
    health_advisor = models.ForeignKey(
        'health_advisor.HealthAdvisor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
    )
    title = models.CharField(max_length=160, blank=True)
    is_group = models.BooleanField(default=False)
    participants = models.ManyToManyField(User, blank=True, related_name='conversations')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_conversations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        if self.title:
            return self.title
        if self.gym_user_id:
            return f"Conversation for {self.gym_user.user_name}"
        return f"Conversation #{self.pk}"

    @property
    def display_title(self):
        return self.title or str(self)

    def sync_team(self):
        if not self.gym_user_id:
            return self
        changed = False
        if self.coach_id != self.gym_user.assigned_coach_id:
            self.coach = self.gym_user.assigned_coach
            changed = True
        if self.health_advisor_id != self.gym_user.assigned_advisor_id:
            self.health_advisor = self.gym_user.assigned_advisor
            changed = True
        if changed:
            self.save(update_fields=['coach', 'health_advisor', 'updated_at'])
        participant_ids = [self.gym_user.user_id]
        if self.coach_id:
            participant_ids.append(self.coach.user_id)
        if self.health_advisor_id:
            participant_ids.append(self.health_advisor.user_id)
        if participant_ids:
            self.participants.add(*participant_ids)
        return self


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    body = models.TextField(blank=True)
    attachment_url = models.URLField(blank=True, null=True)
    attachment = models.FileField(upload_to='message_attachments/', blank=True, null=True)
    is_read = models.BooleanField(default=False)
    read_by = models.ManyToManyField(User, blank=True, related_name='read_messages')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    @property
    def has_attachment(self):
        return bool(self.attachment or self.attachment_url)

    def __str__(self):
        return f"Message by {self.sender.username} on {self.created_at:%Y-%m-%d %H:%M}"


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=160)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    is_opened = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"
