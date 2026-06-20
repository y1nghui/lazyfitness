from urllib.parse import urlparse

from django.core.paginator import Paginator
from django.urls import reverse


def paginate(request, queryset_or_list, per_page=10):
    paginator = Paginator(queryset_or_list, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return page_obj, params.urlencode()


def safe_next_url(next_url, fallback):
    """Allow only internal relative paths. Prevents open redirects."""
    if not next_url:
        return fallback
    parsed = urlparse(next_url)
    if parsed.scheme or parsed.netloc:
        return fallback
    if not next_url.startswith('/'):
        return fallback
    if next_url.startswith('//'):
        return fallback
    return next_url


def role_fallback_url(user):
    if getattr(user, 'is_authenticated', False):
        if getattr(user, 'role', '') == 'gym_user':
            return reverse('gym_user:dashboard')
        if getattr(user, 'role', '') == 'fitness_coach':
            return reverse('coach:dashboard')
        if getattr(user, 'role', '') == 'health_advisor':
            return reverse('health_advisor:dashboard')
        if getattr(user, 'role', '') == 'admin':
            return reverse('admin_panel:dashboard')
    return reverse('landing')


def safe_back_url(request, fallback=None):
    """Resolve a safe back/cancel URL from next, same-host referrer, then role fallback."""
    fallback = fallback or role_fallback_url(getattr(request, 'user', None))
    candidate = request.POST.get('next') or request.GET.get('next')
    if candidate:
        resolved = safe_next_url(candidate, fallback)
        if resolved != fallback:
            return resolved

    referrer = request.META.get('HTTP_REFERER', '')
    if referrer:
        parsed = urlparse(referrer)
        if not parsed.scheme and not parsed.netloc:
            return safe_next_url(referrer, fallback)
        if request.get_host() == parsed.netloc:
            path = parsed.path or '/'
            if parsed.query:
                path = f'{path}?{parsed.query}'
            return safe_next_url(path, fallback)
    return fallback
