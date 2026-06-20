from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('gym_user', '0004_conversation_message'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='fitnessgoal',
            name='status',
            field=models.CharField(choices=[('active', 'Active'), ('completed', 'Completed')], default='active', max_length=12),
        ),
        migrations.AddField(
            model_name='fitnessgoal',
            name='target_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='workoutschedule',
            name='title',
            field=models.CharField(blank=True, default='Workout', max_length=120),
        ),
        migrations.AddField(
            model_name='workoutschedule',
            name='notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='message',
            name='read_by',
            field=models.ManyToManyField(blank=True, related_name='read_messages', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterModelOptions(
            name='fitnessgoal',
            options={'ordering': ['status', '-created_at']},
        ),
        migrations.AlterModelOptions(
            name='workoutschedule',
            options={'ordering': ['day', 'time']},
        ),
    ]
