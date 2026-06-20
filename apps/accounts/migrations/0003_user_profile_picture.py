# Generated manually for LazyFitness account profile picture uploads.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_username'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='profile_picture',
            field=models.ImageField(blank=True, help_text='Optional profile picture used across LazyFitness.', null=True, upload_to='profile_pictures/'),
        ),
    ]
