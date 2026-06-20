from django import forms

from .models import AssignedWorkoutPlan, Exercise, ProfessionalFeedback, Workout, WorkoutPlan


def apply_plain_ui(form):
    for name, field in form.fields.items():
        css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
        if isinstance(field.widget, forms.CheckboxInput):
            css_class = 'form-check-input'
        existing = field.widget.attrs.get('class', '')
        field.widget.attrs['class'] = f'{existing} {css_class}'.strip()
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs.setdefault('rows', 4)


class WorkoutPlanForm(forms.ModelForm):
    class Meta:
        model = WorkoutPlan
        fields = ['plan_name', 'description', 'difficulty', 'target_goal', 'duration_weeks']
        labels = {
            'plan_name': 'Plan name',
            'target_goal': 'Target goal',
            'duration_weeks': 'Duration (weeks)',
        }
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)

    def clean_duration_weeks(self):
        value = self.cleaned_data['duration_weeks']
        if value <= 0:
            raise forms.ValidationError('Duration must be greater than 0.')
        return value


class WorkoutPlanAssignmentForm(forms.Form):
    gym_users = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
        label='Assigned gym users',
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, coach=None, initial_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        users = coach.assigned_gym_users.select_related('user').order_by('user_name') if coach else []
        self.fields['gym_users'].queryset = users
        if initial_user:
            self.fields['gym_users'].initial = [initial_user]
        apply_plain_ui(self)
        self.fields['gym_users'].widget.attrs['class'] = 'form-check-input'


class AssignedWorkoutPlanStatusForm(forms.ModelForm):
    class Meta:
        model = AssignedWorkoutPlan
        fields = ['status', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)


class WorkoutForm(forms.ModelForm):
    class Meta:
        model = Workout
        fields = ['workout_name', 'status', 'notes']
        labels = {'workout_name': 'Workout/session name', 'status': 'Available to users'}
        widgets = {
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)
        self.fields['status'].widget.attrs['class'] = 'form-check-input'


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = ['exercise_name', 'sets', 'exercise_reps', 'rest_seconds', 'video_url']
        labels = {
            'exercise_name': 'Exercise name',
            'exercise_reps': 'Recommended reps',
            'rest_seconds': 'Rest time (seconds)',
            'video_url': 'Exercise video URL (optional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)

    def clean_exercise_reps(self):
        reps = self.cleaned_data['exercise_reps']
        if reps <= 0:
            raise forms.ValidationError('Reps must be greater than 0.')
        return reps


class ProfessionalFeedbackForm(forms.ModelForm):
    class Meta:
        model = ProfessionalFeedback
        fields = ['rating', 'comment', 'attachment_url']
        widgets = {'comment': forms.Textarea(attrs={'rows': 5})}
        labels = {'attachment_url': 'Attachment URL (optional)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)
        self.fields['attachment_url'].required = False

    def clean_rating(self):
        rating = self.cleaned_data['rating']
        if rating < 1 or rating > 10:
            raise forms.ValidationError('Rating must be between 1 and 10.')
        return rating
