from django.db.models import Q
from django.urls import reverse

from .models import Conversation, Message, Notification


def care_team_ready(gym_user):
    return bool(gym_user.assigned_coach_id and gym_user.assigned_advisor_id)


def get_or_create_conversation(gym_user):
    conversation, _ = Conversation.objects.get_or_create(
        gym_user=gym_user,
        defaults={
            'coach': gym_user.assigned_coach,
            'health_advisor': gym_user.assigned_advisor,
            'title': f'Care Team — {gym_user.user_name}',
        },
    )
    return conversation.sync_team()


def sync_conversation_for_gym_user(gym_user):
    if care_team_ready(gym_user):
        return get_or_create_conversation(gym_user)
    if hasattr(gym_user, 'conversation'):
        return gym_user.conversation.sync_team()
    return None


def user_can_access_conversation(user, conversation):
    if not user or not user.is_authenticated or not conversation:
        return False
    if conversation.participants.filter(pk=user.pk).exists():
        return True
    if user.role == 'admin':
        return True
    if conversation.gym_user_id and conversation.gym_user.user_id == user.pk:
        return True
    if conversation.coach_id and conversation.coach.user_id == user.pk:
        return True
    if conversation.health_advisor_id and conversation.health_advisor.user_id == user.pk:
        return True
    return False


def unread_count_for_user(user, conversations=None):
    qs = Message.objects.exclude(sender=user).exclude(read_by=user)
    if conversations is not None:
        qs = qs.filter(conversation__in=conversations)
    else:
        qs = qs.filter(conversation__participants=user)
    return qs.distinct().count()


def conversation_unread_count(conversation, user):
    if not conversation:
        return 0
    return conversation.messages.exclude(sender=user).exclude(read_by=user).count()


def mark_conversation_read(conversation, user):
    for message in conversation.messages.exclude(sender=user).exclude(read_by=user):
        message.read_by.add(user)
    conversation.messages.filter(~Q(sender=user), is_read=False).update(is_read=True)


def notify_user(recipient, title, message='', url=''):
    if not recipient:
        return None
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        url=url,
    )


def notify_conversation_participants(conversation, sender, message_obj):
    for participant in conversation.participants.exclude(pk=sender.pk):
        notify_user(
            participant,
            'New message',
            f'{sender.display_name} sent a message in {conversation.display_title}.',
            _conversation_url_for(participant, conversation),
        )


def _conversation_url_for(user, conversation):
    if not conversation.gym_user_id:
        return reverse('accounts:notifications')
    if user.role == 'gym_user':
        return reverse('gym_user:messages')
    if user.role == 'fitness_coach' and conversation.gym_user_id:
        return reverse('coach:message_thread', args=[conversation.gym_user_id])
    if user.role == 'health_advisor' and conversation.gym_user_id:
        return reverse('health_advisor:message_thread', args=[conversation.gym_user_id])
    return reverse('accounts:notifications')
