from django import forms

from apps.gym_user.models import GymUser

from .models import DietPlan, HealthReport, Recommendation


def apply_plain_ui(form):
    for name, field in form.fields.items():
        css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
        existing = field.widget.attrs.get('class', '')
        field.widget.attrs['class'] = f'{existing} {css_class}'.strip()
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs.setdefault('rows', 5)


class HealthReportForm(forms.ModelForm):
    class Meta:
        model = HealthReport
        fields = ['diet_plan', 'notes']
        widgets = {
            'diet_plan': forms.Textarea(attrs={'rows': 8}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {'diet_plan': 'Diet plan', 'notes': 'Advisor notes'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)


class DietPlanForm(forms.ModelForm):
    gym_users = forms.ModelMultipleChoiceField(
        queryset=GymUser.objects.none(),
        label='Assign to users (optional)',
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        help_text='Leave blank to save this diet plan as an unassigned reusable template.',
    )

    class Meta:
        model = DietPlan
        fields = [
            'gym_users',
            'title',
            'description',
            'target_goal',
            'daily_calorie_target',
            'meal_notes',
            'restrictions_allergies',
            'start_date',
            'end_date',
            'status',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'meal_notes': forms.Textarea(attrs={'rows': 5}),
            'restrictions_allergies': forms.Textarea(attrs={'rows': 3}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'target_goal': 'Target goal',
            'daily_calorie_target': 'Daily calorie target',
            'restrictions_allergies': 'Restrictions / allergies',
        }

    def __init__(self, *args, advisor=None, initial_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        users = advisor.assigned_gym_users.select_related('user').order_by('user_name') if advisor else GymUser.objects.none()
        self.fields['gym_users'].queryset = users
        self.fields['gym_users'].label_from_instance = lambda obj: obj.user_name
        if initial_user and not self.is_bound:
            self.fields['gym_users'].initial = [initial_user.pk]
        apply_plain_ui(self)
        self.fields['gym_users'].widget.attrs.pop('class', None)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        calories = cleaned.get('daily_calorie_target')
        if start and end and end < start:
            self.add_error('end_date', 'End date cannot be earlier than start date.')
        if calories is not None and calories <= 0:
            self.add_error('daily_calorie_target', 'Calories must be greater than 0.')
        return cleaned


class RecommendationForm(forms.ModelForm):
    class Meta:
        model = Recommendation
        fields = ['subject', 'advice']
        widgets = {'advice': forms.Textarea(attrs={'rows': 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)

    def clean(self):
        cleaned = super().clean()
        advice = (cleaned.get('advice') or '').lower()
        risky_terms = ['starvation', 'do not eat', 'steroid cycle', 'unsafe', 'extreme dehydration']
        if any(term in advice for term in risky_terms):
            raise forms.ValidationError(
                'Please rewrite the recommendation in a safe, supportive and medically responsible way.'
            )
        return cleaned
