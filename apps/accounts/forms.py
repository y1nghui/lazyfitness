from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from .models import User

PUBLIC_ROLE_CHOICES = [choice for choice in User.ROLE_CHOICES if choice[0] == 'gym_user']
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']
MAX_PROFILE_PICTURE_SIZE = 2 * 1024 * 1024


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
        if not field.widget.attrs.get('placeholder') and not isinstance(field.widget, (forms.Select, forms.CheckboxInput, forms.ClearableFileInput)):
            field.widget.attrs['placeholder'] = field.label or name.replace('_', ' ').title()




def delete_profile_picture_if_unused(file_name, exclude_user_id=None):
    """Delete an old profile picture only when no other user references it."""
    if not file_name:
        return
    try:
        qs = User.objects.filter(profile_picture=file_name)
        if exclude_user_id:
            qs = qs.exclude(pk=exclude_user_id)
        if qs.exists():
            return
        field = User._meta.get_field('profile_picture')
        if field.storage.exists(file_name):
            field.storage.delete(file_name)
    except Exception:
        # Media cleanup should never break account saving.
        pass

def validate_profile_picture(upload):
    if not upload:
        return upload
    extension_validator = FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS)
    extension_validator(upload)
    if upload.size > MAX_PROFILE_PICTURE_SIZE:
        raise ValidationError('Profile picture must be 2 MB or smaller.')
    content_type = getattr(upload, 'content_type', '')
    allowed_types = {'image/jpeg', 'image/png', 'image/webp'}
    if content_type and content_type not in allowed_types:
        raise ValidationError('Only JPG, JPEG, PNG or WebP images are allowed.')
    return upload


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=8, help_text='Use at least 8 characters. Avoid common passwords. Do not use your username or email. Use a mix of letters and numbers.')
    password2 = forms.CharField(widget=forms.PasswordInput, label='Confirm Password', help_text='Repeat the same password to confirm it.')

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'password', 'password2']
        labels = {'username': 'Username', 'email': 'Email address'}

    def __init__(self, *args, **kwargs):
        self.allow_admin = kwargs.pop('allow_admin', False)
        super().__init__(*args, **kwargs)
        if not self.allow_admin:
            self.fields['role'].choices = PUBLIC_ROLE_CHOICES
        apply_plain_ui(self)
        self.fields['username'].widget.attrs.update({'autofocus': True, 'placeholder': 'e.g. alex_fit'})
        self.fields['email'].widget.attrs.update({'placeholder': 'you@example.com'})
        self.fields['role'].help_text = 'Public sign-up is for gym users only. Coaches and health advisors are created by admins.'
        self.fields['password'].widget.attrs.update({'placeholder': 'At least 8 characters'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Repeat password'})

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise forms.ValidationError('Username is required.')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').lower().strip()
        if not email:
            raise forms.ValidationError('Email is required.')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_role(self):
        role = self.cleaned_data.get('role')
        if not self.allow_admin and role != 'gym_user':
            raise forms.ValidationError('Only gym users can register from the public sign-up page.')
        return role

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        password2 = cleaned.get('password2')
        if password and password2 and password != password2:
            self.add_error('password2', 'Passwords do not match.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['username']
        user.email = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password'])
        if user.role == 'admin':
            user.is_staff = True
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Username or Email', max_length=254)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)
        self.fields['username'].widget.attrs.update({'autofocus': True, 'placeholder': 'Username or email'})
        self.fields['password'].widget.attrs.update({'placeholder': 'Password'})


class AccountEditForm(forms.ModelForm):
    display_name = forms.CharField(max_length=255, label='Display name')
    remove_profile_picture = forms.BooleanField(required=False, label='Remove current profile picture')
    specialty = forms.CharField(max_length=120, required=False, label='Specialty')
    years_experience = forms.IntegerField(required=False, min_value=0, label='Years of experience')
    bio = forms.CharField(
        required=False,
        label='Public bio',
        widget=forms.Textarea(attrs={'rows': 4}),
        help_text='Shown on the public Meet Our Team section for coaches and health advisors.',
    )

    class Meta:
        model = User
        fields = ['display_name', 'username', 'email', 'profile_picture', 'remove_profile_picture']
        labels = {
            'username': 'Username',
            'email': 'Email address',
            'profile_picture': 'Profile picture',
        }
        help_texts = {
            'display_name': 'This name appears on dashboards, messages and admin screens.',
            'profile_picture': 'Upload JPG, JPEG, PNG or WebP only. Maximum 2 MB. Leave blank to keep the current picture.',
        }

    def __init__(self, *args, **kwargs):
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
        apply_plain_ui(self)
        self.fields['display_name'].widget.attrs.update({'placeholder': 'Your display name'})
        self.fields['username'].widget.attrs.update({'placeholder': 'Username'})
        self.fields['email'].widget.attrs.update({'placeholder': 'you@example.com'})

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
        from .signals import ensure_role_profile
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


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_plain_ui(self)
        for field in self.fields.values():
            field.widget.attrs.setdefault('placeholder', field.label)
        self.fields['new_password1'].help_text = 'Use at least 8 characters. Avoid common passwords. Do not use your username or email. Use a mix of letters and numbers.'
