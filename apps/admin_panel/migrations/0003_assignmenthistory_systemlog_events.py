from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('coach', '0003_coach_bio_coach_specialty_coach_years_experience'),
        ('health_advisor', '0002_healthadvisor_bio_healthadvisor_specialty_and_more'),
        ('gym_user', '0005_goal_schedule_message_reads'),
        ('admin_panel', '0002_loginactivity_assignment_log'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemlog',
            name='event',
            field=models.CharField(choices=[('user_created', 'User Created'), ('user_deleted', 'User Deleted'), ('status_changed', 'Status Changed'), ('assignment_updated', 'Assignment Updated'), ('password_reset', 'Password Reset'), ('login', 'Login'), ('faq_updated', 'FAQ Updated'), ('feedback_updated', 'Feedback Updated'), ('export', 'CSV Export')], max_length=30),
        ),
        migrations.CreateModel(
            name='AssignmentHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('note', models.CharField(blank=True, max_length=255)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assignment_changes', to=settings.AUTH_USER_MODEL)),
                ('gym_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignment_history', to='gym_user.gymuser')),
                ('new_coach', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='new_assignment_records', to='coach.coach')),
                ('new_health_advisor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='new_assignment_records', to='health_advisor.healthadvisor')),
                ('old_coach', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='old_assignment_records', to='coach.coach')),
                ('old_health_advisor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='old_assignment_records', to='health_advisor.healthadvisor')),
            ],
            options={'verbose_name_plural': 'Assignment histories', 'ordering': ['-changed_at']},
        ),
    ]
