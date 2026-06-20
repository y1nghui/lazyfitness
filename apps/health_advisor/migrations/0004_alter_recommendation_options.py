from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('health_advisor', '0003_recommendation_status_choices'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='recommendation',
            options={'ordering': ['-created_at']},
        ),
    ]
