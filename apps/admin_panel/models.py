from django.db import models
from apps.accounts.models import User


class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    admin_name = models.CharField(max_length=255)

    def __str__(self):
        return f"Admin: {self.admin_name}"


class SystemLog(models.Model):
    EVENT_CHOICES = [
        ('user_created', 'User Created'),
        ('user_deleted', 'User Deleted'),
        ('status_changed', 'Status Changed'),
        ('assignment_updated', 'Assignment Updated'),
        ('password_reset', 'Password Reset'),
        ('login', 'Login'),
        ('faq_updated', 'FAQ Updated'),
        ('feedback_updated', 'Feedback Updated'),
        ('export', 'CSV Export'),
    ]
    event = models.CharField(max_length=30, choices=EVENT_CHOICES)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='system_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    module = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.event}"

    @classmethod
    def record(cls, event, description, user=None, module=''):
        cls.objects.create(event=event, description=description, performed_by=user, module=module)


class LoginActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='login_activities')
    username = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, blank=True)
    login_timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    successful = models.BooleanField(default=True)

    class Meta:
        ordering = ['-login_timestamp']
        verbose_name_plural = 'Login activities'

    def __str__(self):
        status = 'Success' if self.successful else 'Failure'
        return f"{status}: {self.username or 'unknown'} at {self.login_timestamp:%Y-%m-%d %H:%M}"


class AssignmentHistory(models.Model):
    gym_user = models.ForeignKey('gym_user.GymUser', on_delete=models.CASCADE, related_name='assignment_history')
    old_coach = models.ForeignKey('coach.Coach', on_delete=models.SET_NULL, null=True, blank=True, related_name='old_assignment_records')
    new_coach = models.ForeignKey('coach.Coach', on_delete=models.SET_NULL, null=True, blank=True, related_name='new_assignment_records')
    old_health_advisor = models.ForeignKey('health_advisor.HealthAdvisor', on_delete=models.SET_NULL, null=True, blank=True, related_name='old_assignment_records')
    new_health_advisor = models.ForeignKey('health_advisor.HealthAdvisor', on_delete=models.SET_NULL, null=True, blank=True, related_name='new_assignment_records')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assignment_changes')
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name_plural = 'Assignment histories'

    def __str__(self):
        return f"Assignment update for {self.gym_user.user_name} on {self.changed_at:%Y-%m-%d %H:%M}"


class FAQ(models.Model):
    admin = models.ForeignKey(AdminProfile, on_delete=models.SET_NULL, null=True, related_name='faqs')
    question = models.CharField(max_length=500)
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.question[:80]


class Feedback(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('reviewed', 'Reviewed'), ('resolved', 'Resolved')]
    submitter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_feedbacks')
    admin = models.ForeignKey(AdminProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_feedbacks')
    comment = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Feedback #{self.id} by {self.submitter.username} [{self.status}]"
