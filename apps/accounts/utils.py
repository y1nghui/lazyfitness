"""Small shared helpers for user-friendly error pages."""
from django.shortcuts import render


def _flatten_form_errors(form):
    """Return form errors as labelled strings safe for display in templates."""
    error_items = []
    for field_name, errors in form.errors.items():
        if field_name == '__all__':
            label = 'Form error'
        else:
            field = form.fields.get(field_name)
            label = field.label if field and field.label else field_name.replace('_', ' ').title()
        for error in errors:
            error_items.append({'label': label, 'message': error})
    return error_items


def render_input_error(
    request,
    form=None,
    *,
    title='Input Error',
    message='Please correct the highlighted errors and try again.',
    back_url=None,
    back_label='Back to form',
    status=400,
):
    """Render a consistent styled error page for invalid submitted forms."""
    context = {
        'error_title': title,
        'error_message': message,
        'form': form,
        'error_items': _flatten_form_errors(form) if form is not None else [],
        'back_url': back_url,
        'back_label': back_label,
        'status_code': status,
    }
    return render(request, 'shared/error.html', context, status=status)
