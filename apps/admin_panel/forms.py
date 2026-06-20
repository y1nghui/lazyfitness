from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from apps.accounts.forms import RegistrationForm, apply_plain_ui, validate_profile_picture, delete_profile_picture_if_unused
from apps.accounts.models import User
from apps.gym_user.models import GymUser
from .models import FAQ, Feedback


class AdminUserCreationForm(RegistrationForm):
    STAFF_CREATABLE_ROLE_CHOICES = [choice for choice in RegistrationForm.Meta.model.ROLE_CHOICES if choice[0] != 'admin']

    def __init__(self, *args, **kwargs):
        self.created_by = kwargs.pop('created_by', None)
        self.creator_is_superuser = bool(getattr(self.created_by, 'is_superuser', False))
        super().__init__(*args, allow_admin=True, **kwargs)
        if not self.creator_is_superuser:
            self.fields['role'].choices = self.STAFF_CREATABLE_ROLE_CHOICES
        self.fields['role'].help_text = 'Normal admins can create gym users, coaches and advisors. Only Django superusers can create admins.'

    def clean_role(self):
        role = super().clean_role()
        if role == 'admin' and not self.creator_is_superuser:
            raise forms.ValidationError('Only a Django superuser can create another admin account.')
        return role


class AdminUserEditForm(forms.ModelForm):
    display_name = forms.CharField(max_length=255, label='Display name')
    remove_profile_picture = forms.BooleanField(required=False, label='Remove current profile picture')
    specialty = forms.CharField(max_length=120, required=False, label='Specialty')
    years_experience = forms.IntegerField(required=False, min_value=0, label='Years of experience')
    bio = forms.CharField(required=False, label='Public bio', widget=forms.Textarea(attrs={'rows': 4}))

    class Meta:
        model = User
        fields = ['display_name', 'username', 'email', 'is_active', 'profile_picture', 'remove_profile_picture']
        labels = {
            'username': 'Username',
            'email': 'Email address',
            'is_active': 'Active account',
            'profile_picture': 'Profile picture',
        }
        help_texts = {'profile_picture': 'Upload JPG, JPEG, PNG or WebP only. Maximum 2 MB.'}

    def __init__(self, *args, **kwargs):
        self.edited_by = kwargs.pop('edited_by', None)
        super().__init__(*args, **kwargs)
        self.old_profile_picture_name = self.instance.profile_picture.name if self.instance and self.instance.pk and self.instance.profile_picture else ''
        self.fields['display_name'].initial = self.instance.display_name if self.instance and self.instance.pk else ''
        if not (self.instance and self.instance.profile_picture):
            self.fields.pop('remove_profile_picture', None)
        profile = None
        if self.instance and self.instance.pk:
            try:
                profile = getattr(self.instance, 'coach' if self.instance.role == 'fitness_coach' else 'healthadvisor')
            except Exception:
                profile = None
        if self.instance and self.instance.role in ('fitness_coach', 'health_advisor') and profile is not None:
            self.fields['specialty'].initial = getattr(profile, 'specialty', '')
            self.fields['years_experience'].initial = getattr(profile, 'years_experience', None)
            self.fields['bio'].initial = getattr(profile, 'bio', '')
        else:
            self.fields.pop('specialty', None)
            self.fields.pop('years_experience', None)
            self.fields.pop('bio', None)
        if self.instance and self.instance.role == 'admin' and not getattr(self.edited_by, 'is_superuser', False):
            self.fields['is_active'].disabled = True
        apply_plain_ui(self)

    def clean_display_name(self):
        name = (self.cleaned_data.get('display_name') or '').strip()
        if not name:
            raise forms.ValidationError('Display name is required.')
        return name

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise forms.ValidationError('Username is required.')
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').lower().strip()
        if not email:
            raise forms.ValidationError('Email is required.')
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_is_active(self):
        is_active = self.cleaned_data.get('is_active')
        if self.instance and self.edited_by and self.instance.pk == self.edited_by.pk and not is_active:
            raise forms.ValidationError('You cannot deactivate your own account.')
        return is_active

    def clean_profile_picture(self):
        return validate_profile_picture(self.cleaned_data.get('profile_picture'))

    def save(self, commit=True):
        user = super().save(commit=False)
        old_name = getattr(self, 'old_profile_picture_name', '')
        remove_picture = self.cleaned_data.get('remove_profile_picture')
        uploaded_picture = self.cleaned_data.get('profile_picture')
        if remove_picture:
            user.profile_picture = None
        if commit:
            user.save()
            if old_name and (remove_picture or uploaded_picture) and old_name != (user.profile_picture.name if user.profile_picture else ''):
                delete_profile_picture_if_unused(old_name, exclude_user_id=user.pk)
        display_name = self.cleaned_data.get('display_name')
        from apps.accounts.signals import ensure_role_profile
        profile = ensure_role_profile(user)
        update_fields = []
        role_name_field = {
            'gym_user': 'user_name',
            'fitness_coach': 'coach_name',
            'health_advisor': 'advisor_name',
            'admin': 'admin_name',
        }.get(user.role)
        if profile is not None and role_name_field and display_name:
            setattr(profile, role_name_field, display_name)
            update_fields.append(role_name_field)
        if user.role in ('fitness_coach', 'health_advisor') and profile is not None:
            for field in ('specialty', 'years_experience', 'bio'):
                if field in self.cleaned_data:
                    setattr(profile, field, self.cleaned_data.get(field) or (None if field == 'years_experience' else ''))
                    update_fields.append(field)
        if profile is not None and update_fields:
            profile.save(update_fields=list(dict.fromkeys(update_fields)))
        return user


class AdminPasswordResetForm(forms.Form):
    new_password1 = forms.CharField(label='New password', widget=forms.PasswordInput, help_text='Use at least 8 characters. Avoid common passwords. Do not use the username or email. Use a mix of letters and numbers.')
    new_password2 = forms.CharField(label='Confirm new password', widget=forms.PasswordInput, help_text='Repeat the same password to confirm it.')

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password1')
        p2 = cleaned.get('new_password2')
        if p1 and p2 and p1 != p2:
            self.add_error('new_password2', 'Passwords do not match.')
        if p1:
            try:
                validate_password(p1, self.user)
            except ValidationError as exc:
                self.add_error('new_password1', exc)
        return cleaned

    def save(self):
        password = self.cleaned_data['new_password1']
        self.user.set_password(password)
        self.user.save(update_fields=['password'])
        return self.user


class GymUserAssignmentForm(forms.ModelForm):
    note = forms.CharField(required=False, max_length=255, label='Change note', widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = GymUser
        fields = ['assigned_coach', 'assigned_advisor', 'note']
        labels = {'assigned_coach': 'Fitness coach', 'assigned_advisor': 'Health advisor'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_coach'].required = False
        self.fields['assigned_advisor'].required = False
        self.fields['assigned_coach'].empty_label = 'No coach assigned'
        self.fields['assigned_advisor'].empty_label = 'No health advisor assigned'
        self.fields['assigned_coach'].queryset = self.fields['assigned_coach'].queryset.select_related('user').filter(user__is_active=True).order_by('coach_name')
        self.fields['assigned_advisor'].queryset = self.fields['assigned_advisor'].queryset.select_related('user').filter(user__is_active=True).order_by('advisor_name')
        apply_plain_ui(self)

    def save(self, commit=True):
        self.cleaned_note = self.cleaned_data.get('note', '')
        return super().save(commit=commit)


class FAQForm(forms.ModelForm):
    class Meta:
        model = FAQ
        fields = ['question', 'answer']
        widgets = {'answer': forms.Textarea(attrs={'rows': 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)


class FeedbackStatusForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)
