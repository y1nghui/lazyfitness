"""Small helpers for public LazyFitness promotion sections."""
from django.db.models import Count


def get_public_care_team(limit=6):
    """Return active coaches/advisors safe to show on public pages."""
    from apps.coach.models import Coach
    from apps.health_advisor.models import HealthAdvisor

    coaches = (
        Coach.objects.select_related('user')
        .filter(user__is_active=True)
        .annotate(assigned_count=Count('assigned_gym_users', distinct=True))
        .order_by('coach_name')[:limit]
    )
    advisors = (
        HealthAdvisor.objects.select_related('user')
        .filter(user__is_active=True)
        .annotate(assigned_count=Count('assigned_gym_users', distinct=True))
        .order_by('advisor_name')[:limit]
    )
    return {
        'public_coaches': coaches,
        'public_advisors': advisors,
    }
