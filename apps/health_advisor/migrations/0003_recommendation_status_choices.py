from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('health_advisor', '0002_healthadvisor_bio_healthadvisor_specialty_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recommendation',
            name='status',
            field=models.CharField(choices=[('sent', 'Sent'), ('read', 'Read'), ('completed', 'Completed'), ('archived', 'Archived')], default='sent', max_length=12),
        ),
    ]
