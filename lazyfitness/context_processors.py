def lazyfitness_counts(request):
    from lazyfitness.view_helpers import role_fallback_url

    user = getattr(request, 'user', None)
    fallback = role_fallback_url(user)
    if not user or not user.is_authenticated:
        return {'nav_unread_messages': 0, 'nav_unread_notifications': 0, 'nav_back_fallback': fallback}
    try:
        from apps.gym_user.messaging import unread_count_for_user
        from apps.gym_user.models import Conversation, Notification

        conversations = Conversation.objects.none()
        if user.role == 'gym_user':
            conversations = Conversation.objects.filter(gym_user__user=user)
        elif user.role == 'fitness_coach':
            conversations = Conversation.objects.filter(coach__user=user)
        elif user.role == 'health_advisor':
            conversations = Conversation.objects.filter(health_advisor__user=user)
        else:
            conversations = Conversation.objects.filter(participants=user)
        return {
            'nav_unread_messages': unread_count_for_user(user, conversations),
            'nav_unread_notifications': Notification.objects.filter(recipient=user, is_read=False).count(),
            'nav_back_fallback': fallback,
        }
    except Exception:
        return {'nav_unread_messages': 0, 'nav_unread_notifications': 0, 'nav_back_fallback': fallback}
