from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('Username is required')
        if not email:
            raise ValueError('Email is required')

        username = str(username).strip()
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        if extra_fields.get('role') != 'admin':
            raise ValueError('Superuser must have role="admin".')

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Base User table.
    Authentication uses username, while email remains unique for contact and recovery.
    All role-specific profiles link back via OneToOneField.
    """
    ROLE_CHOICES = [
        ('gym_user',       'Gym User'),
        ('fitness_coach',  'Fitness Coach'),
        ('health_advisor', 'Health Advisor'),
        ('admin',          'Admin'),
    ]

    username_validator = RegexValidator(
        regex=r'^[\w.@+-]+$',
        message='Username may contain letters, numbers, and @/./+/-/_ characters only.',
    )

    username    = models.CharField(max_length=150, unique=True, validators=[username_validator])
    email       = models.EmailField(unique=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True,
        help_text='Optional profile picture used across LazyFitness.',
    )
    role        = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active   = models.BooleanField(default=True)   # userStatus
    is_staff    = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD  = 'username'
    REQUIRED_FIELDS = ['email', 'role']

    objects = UserManager()

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def display_name(self):
        """Friendly name from the role profile, falling back to username."""
        profile_fields = [
            ('gymuser', 'user_name'),
            ('coach', 'coach_name'),
            ('healthadvisor', 'advisor_name'),
            ('adminprofile', 'admin_name'),
        ]
        for relation, field in profile_fields:
            try:
                profile = getattr(self, relation)
            except Exception:
                profile = None
            value = getattr(profile, field, '') if profile else ''
            if value:
                return value
        return self.username or self.email

    @property
    def avatar_initial(self):
        name = self.display_name or self.username or self.email or '?'
        return name.strip()[:1].upper()

    @property
    def role_label(self):
        return dict(self.ROLE_CHOICES).get(self.role, 'System')

    @property
    def role_css_class(self):
        return {
            'gym_user': 'chat-role-gym-user',
            'fitness_coach': 'chat-role-fitness-coach',
            'health_advisor': 'chat-role-health-advisor',
            'admin': 'chat-role-admin',
        }.get(self.role, 'chat-role-system')

    @property
    def is_gym_user(self):
        return self.role == 'gym_user'

    @property
    def is_coach(self):
        return self.role == 'fitness_coach'

    @property
    def is_health_advisor(self):
        return self.role == 'health_advisor'

    @property
    def is_admin_user(self):
        return self.role == 'admin'
