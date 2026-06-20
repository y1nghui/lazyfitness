"""Project-level public pages and error handlers."""
from django.shortcuts import render

from .public_team import get_public_care_team


def landing(request):
    """Public home page with active coach/advisor promotion cards."""
    context = get_public_care_team(limit=6)
    return render(request, 'shared/landing.html', context)


def error_page(request, title='Something went wrong', message='Please try again or return to the dashboard.', status=400):
    return render(request, 'shared/error.html', {
        'error_title': title,
        'error_message': message,
        'status_code': status,
        'back_url': request.META.get('HTTP_REFERER', '/'),
        'back_label': 'Go back',
        'error_items': [],
    }, status=status)


def bad_request(request, exception):
    return error_page(
        request,
        title='Bad Request',
        message='The submitted request could not be processed. Please check your input and try again.',
        status=400,
    )


def permission_denied(request, exception):
    return error_page(
        request,
        title='Permission Denied',
        message='You do not have permission to access this page.',
        status=403,
    )


def page_not_found(request, exception):
    return error_page(
        request,
        title='Page Not Found',
        message='The page you requested does not exist or may have been moved.',
        status=404,
    )


def server_error(request):
    return error_page(
        request,
        title='Server Error',
        message='Something unexpected happened. Please try again later.',
        status=500,
    )
