"""Signals that keep role-specific profiles in sync with the custom User model."""
from django.apps import apps
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


def _display_name(user):
    """Use username first, then email prefix, as a friendly safe default profile name."""
    source = getattr(user, 'username', '') or getattr(user, 'email', '').split('@')[0] or 'LazyFitness User'
    return source.replace('.', ' ').replace('_', ' ').replace('-', ' ').title()


def ensure_role_profile(user):
    """
    Create the profile required by the user's role.

    This is intentionally idempotent, so it can be called from signals, register views,
    admin-panel user creation, management commands, or a Django shell without creating duplicates.
    """
    if not user or not getattr(user, 'role', None):
        return None

    name = _display_name(user)

    if user.role == 'gym_user':
        GymUser = apps.get_model('gym_user', 'GymUser')
        profile, _ = GymUser.objects.get_or_create(
            user=user,
            defaults={
                'user_name': name,
                'age': 18,
                'gender': 'Not specified',
                'weight': 70.0,
                'height': 170.0,
                'neck_in_cm': 35,
                'waist_in_cm': 80,
                'calorie_intake': 2000,
                'medical_condition': '',
                'profile_completed': False,
            },
        )
        return profile

    if user.role == 'fitness_coach':
        Coach = apps.get_model('coach', 'Coach')
        profile, _ = Coach.objects.get_or_create(user=user, defaults={'coach_name': name})
        return profile

    if user.role == 'health_advisor':
        HealthAdvisor = apps.get_model('health_advisor', 'HealthAdvisor')
        profile, _ = HealthAdvisor.objects.get_or_create(user=user, defaults={'advisor_name': name})
        return profile

    if user.role == 'admin':
        AdminProfile = apps.get_model('admin_panel', 'AdminProfile')
        profile, _ = AdminProfile.objects.get_or_create(user=user, defaults={'admin_name': name})
        return profile

    return None


@receiver(post_save, sender=User)
def create_role_profile(sender, instance, created, **kwargs):
    # Run for both new and existing users, because an admin may change a role later.
    ensure_role_profile(instance)
