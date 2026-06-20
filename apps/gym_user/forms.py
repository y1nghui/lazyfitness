from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from .models import (
    ActivityLog,
    BodyMeasurement,
    FitnessGoal,
    GymUser,
    Message,
    MonthlyWorkoutSchedule,
    WorkoutSchedule,
)
from apps.coach.models import AssignedWorkoutPlan, WorkoutPlan

ALLOWED_MESSAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'pdf', 'txt', 'doc', 'docx']
ALLOWED_MESSAGE_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'application/pdf',
    'text/plain',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}
MAX_MESSAGE_ATTACHMENT_SIZE = 5 * 1024 * 1024


def apply_plain_ui(form):
    for name, field in form.fields.items():
        css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
        if isinstance(field.widget, forms.CheckboxInput):
            css_class = 'form-check-input'
        if isinstance(field.widget, forms.ClearableFileInput):
            css_class = 'form-control'
        existing = field.widget.attrs.get('class', '')
        field.widget.attrs['class'] = f'{existing} {css_class}'.strip()
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs.setdefault('rows', 4)


def validate_message_attachment(upload):
    if not upload:
        return upload
    FileExtensionValidator(ALLOWED_MESSAGE_EXTENSIONS)(upload)
    if upload.size > MAX_MESSAGE_ATTACHMENT_SIZE:
        raise ValidationError('Attachment must be 5 MB or smaller.')
    content_type = getattr(upload, 'content_type', '')
    if content_type and content_type not in ALLOWED_MESSAGE_CONTENT_TYPES:
        raise ValidationError('Only image, PDF, text, DOC or DOCX attachments are allowed.')
    return upload


class FitnessGoalForm(forms.ModelForm):
    class Meta:
        model = FitnessGoal
        fields = ['goal_name', 'goal_description', 'status', 'target_date']
        labels = {
            'goal_name': 'Goal name',
            'goal_description': 'Goal description',
            'target_date': 'Target date',
        }
        widgets = {'target_date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)


class BodyMeasurementForm(forms.ModelForm):
    class Meta:
        model = BodyMeasurement
        fields = ['weight', 'waist_in_cm', 'neck_in_cm', 'calorie_intake', 'recorded_at', 'notes']
        widgets = {
            'recorded_at': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'weight': 'Weight (kg)',
            'waist_in_cm': 'Waist (cm)',
            'neck_in_cm': 'Neck (cm)',
            'calorie_intake': 'Daily calorie target',
        }

    def __init__(self, *args, **kwargs):
        gym_user = kwargs.pop('gym_user', None)
        super().__init__(*args, **kwargs)
        if gym_user and not self.is_bound:
            self.fields['weight'].initial = gym_user.weight
            self.fields['waist_in_cm'].initial = gym_user.waist_in_cm
            self.fields['neck_in_cm'].initial = gym_user.neck_in_cm
            self.fields['calorie_intake'].initial = gym_user.calorie_intake
        apply_plain_ui(self)

    def clean(self):
        cleaned = super().clean()
        for field in ['weight', 'waist_in_cm', 'neck_in_cm', 'calorie_intake']:
            value = cleaned.get(field)
            if value is not None and value <= 0:
                self.add_error(field, 'Value must be greater than 0.')
        return cleaned


class ActivityLogForm(forms.ModelForm):
    class Meta:
        model = ActivityLog
        fields = ['plan', 'workouts_completed', 'reps_completed', 'workout_duration', 'workout_streak']
        labels = {
            'plan': 'Workout plan used',
            'workouts_completed': 'Workouts completed',
            'reps_completed': 'Total reps completed',
            'workout_duration': 'Duration (minutes)',
            'workout_streak': 'Current streak (days)',
        }

    def __init__(self, *args, **kwargs):
        selected_plan = kwargs.pop('selected_plan', None)
        gym_user = kwargs.pop('gym_user', None)
        super().__init__(*args, **kwargs)
        queryset = WorkoutPlan.objects.select_related('coach').none()
        if gym_user:
            assigned_plan_ids = AssignedWorkoutPlan.objects.filter(
                gym_user=gym_user,
                status__in=['assigned', 'in_progress', 'completed'],
            ).values_list('plan_id', flat=True)
            queryset = WorkoutPlan.objects.select_related('coach').filter(pk__in=assigned_plan_ids)
        self.fields['plan'].queryset = queryset
        self.fields['plan'].required = False
        self.fields['plan'].empty_label = 'No specific plan'
        if selected_plan:
            self.fields['plan'].initial = selected_plan
        apply_plain_ui(self)

    def clean(self):
        cleaned = super().clean()
        for field in ['workouts_completed', 'reps_completed', 'workout_duration', 'workout_streak']:
            value = cleaned.get(field)
            if value is not None and value < 0:
                self.add_error(field, 'Value cannot be negative.')
        return cleaned


class GymUserProfileForm(forms.ModelForm):
    class Meta:
        model = GymUser
        fields = [
            'user_name',
            'age',
            'gender',
            'weight',
            'height',
            'neck_in_cm',
            'waist_in_cm',
            'calorie_intake',
            'medical_condition',
        ]
        widgets = {'medical_condition': forms.Textarea(attrs={'rows': 4})}
        labels = {
            'user_name': 'Display name',
            'weight': 'Weight (kg)',
            'height': 'Height (cm)',
            'neck_in_cm': 'Neck circumference (cm)',
            'waist_in_cm': 'Waist circumference (cm)',
            'calorie_intake': 'Daily calorie target',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)
        self.fields['gender'].widget.attrs.setdefault('placeholder', 'e.g. Male, Female, Other')

    def clean_age(self):
        age = self.cleaned_data['age']
        if age <= 0 or age > 120:
            raise forms.ValidationError('Please enter a valid age.')
        return age

    def clean_height(self):
        height = self.cleaned_data['height']
        if height <= 0:
            raise forms.ValidationError('Height must be greater than 0.')
        return height

    def clean_weight(self):
        weight = self.cleaned_data['weight']
        if weight <= 0:
            raise forms.ValidationError('Weight must be greater than 0.')
        return weight

    def clean_neck_in_cm(self):
        value = self.cleaned_data['neck_in_cm']
        if value <= 0:
            raise forms.ValidationError('Neck circumference must be greater than 0.')
        return value

    def clean_waist_in_cm(self):
        value = self.cleaned_data['waist_in_cm']
        if value <= 0:
            raise forms.ValidationError('Waist circumference must be greater than 0.')
        return value

    def clean_calorie_intake(self):
        value = self.cleaned_data['calorie_intake']
        if value <= 0:
            raise forms.ValidationError('Calorie intake must be greater than 0.')
        return value

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.profile_completed = True
        if commit:
            profile.save()
        return profile


class WorkoutScheduleForm(forms.ModelForm):
    class Meta:
        model = WorkoutSchedule
        fields = ['title', 'day', 'time', 'notes']
        labels = {
            'title': 'Routine title',
            'day': 'Repeat every',
            'time': 'Time',
            'notes': 'Routine notes',
        }
        widgets = {
            'time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)


class MonthlyWorkoutScheduleForm(forms.ModelForm):
    class Meta:
        model = MonthlyWorkoutSchedule
        fields = ['title', 'date', 'time', 'notes']
        labels = {
            'title': 'Plan title',
            'date': 'Exact date',
            'time': 'Time (optional)',
            'notes': 'Notes',
        }
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['time'].required = False
        apply_plain_ui(self)


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['body', 'attachment']
        labels = {
            'body': 'Message',
            'attachment': 'Upload attachment',
        }
        widgets = {
            'body': forms.Textarea(
                attrs={'rows': 2, 'placeholder': 'Write a message...'}
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['body'].required = False
        self.fields['attachment'].required = False
        apply_plain_ui(self)

    def clean_attachment(self):
        return validate_message_attachment(self.cleaned_data.get('attachment'))

    def clean(self):
        cleaned = super().clean()
        body = (cleaned.get('body') or '').strip()
        attachment = cleaned.get('attachment')
        if not body and not attachment:
            self.add_error('body', 'Message cannot be empty.')
        cleaned['body'] = body
        return cleaned
