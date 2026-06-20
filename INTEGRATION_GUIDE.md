# LazyFitness — Team Integration Guide
> Stack: Django 4.2 · Python 3.11 · SQLite · HTML/plain HTML, CSS and JavaScript

---

## Project Structure

```
lazyfitness/
├── manage.py
├── requirements.txt
├── lazyfitness/          ← project config (shared)
│   ├── settings.py
│   └── urls.py
├── apps/
│   ├── accounts/         ← SHARED — login/register/roles (all members use this)
│   ├── gym_user/         ← Wong Kai Jun
│   ├── coach/            ← Chong Jia Zhen
│   ├── health_advisor/   ← Ng Ying Hui
│   └── admin_panel/      ← Liew Wen Xing
├── templates/
│   ├── shared/base.html  ← SHARED base template (extends for every page)
│   ├── accounts/
│   ├── gym_user/
│   ├── coach/
│   ├── health_advisor/
│   └── admin_panel/
└── static/
    ├── css/
    └── js/
```

---

## First-Time Setup (everyone runs this once)

```bash
cd lazyfitness
pip install -r requirements.txt
python manage.py makemigrations accounts
python manage.py makemigrations gym_user coach health_advisor admin_panel
python manage.py migrate
python manage.py createsuperuser   # use role=admin
python manage.py runserver
```

---

## Migration Order (important — run in this sequence)

```bash
# accounts must migrate FIRST because every other app imports User
python manage.py makemigrations accounts
python manage.py makemigrations gym_user
python manage.py makemigrations coach        # imports gym_user models
python manage.py makemigrations health_advisor  # imports gym_user models
python manage.py makemigrations admin_panel
python manage.py migrate
```

---

## How Each Member Works

### ✅ Shared: accounts app
All members **import from** this app — do not edit unless discussing with the team.

Key things you will use:
```python
from apps.accounts.models import User
from apps.accounts.decorators import gym_user_required   # or coach_required, etc.
```

How to protect a view:
```python
@gym_user_required       # blocks anyone who isn't a gym_user
def my_view(request):
    ...
```

---

### 👤 Wong Kai Jun — Subsystem 1: Gym User (`apps/gym_user/`)

**Your models:** `GymUser`, `FitnessGoal`, `WorkoutSchedule`, `ActivityLog`

**Your TODO views (all in `views.py`):**
- `dashboard` — show BMI card, upcoming schedule, recent logs, goals summary
- `goal_create` — build a `ModelForm` for `FitnessGoal`, save on POST
- `schedule_view` — query `WorkoutSchedule.objects.filter(user=gym_user)`, render weekly grid
- `workout_select` — display `WorkoutPlan.objects.all()` cards from coach app
- `log_activity` — `ModelForm` for `ActivityLog`, link to chosen plan
- `progress_view` — pass logs as JSON to Chart.js for streak/reps graphs
- `profile_view` — edit `GymUser` fields (weight, height, etc.)

**Key cross-app import:**
```python
from apps.coach.models import WorkoutPlan   # to let gym user pick a plan
```

**Tip:** After `register`, you need to auto-create the `GymUser` profile.
Use a Django signal in `gym_user/signals.py`:
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.accounts.models import User
from .models import GymUser

@receiver(post_save, sender=User)
def create_gym_user_profile(sender, instance, created, **kwargs):
    if created and instance.role == 'gym_user':
        GymUser.objects.create(user=instance, user_name="", age=0,
            gender="", weight=0, height=0, neck_in_cm=0,
            waist_in_cm=0, calorie_intake=0)
```
Then add `ready()` in `gym_user/apps.py`.

---

### 🏋️ Chong Jia Zhen — Subsystem 2: Fitness Coach (`apps/coach/`)

**Your models:** `Coach`, `WorkoutPlan`, `Workout`, `Exercise`, `ProfessionalFeedback`

**Your TODO views:**
- `plan_create` — `ModelForm` for `WorkoutPlan` (auto-assign `coach=request.user.coach`)
- `plan_detail` — nested list of `Workout` objects, each expanding to `Exercise` list
- `workout_create` — `ModelForm` for `Workout`, `plan` passed via URL `plan_id`
- `exercise_create` — `ModelForm` for `Exercise`, `workout` passed via URL
- `monitor_progress` — filter `ActivityLog` by users who follow your plans
- `feedback_create` — `ModelForm` for `ProfessionalFeedback` linked to a specific log

**Key cross-app import:**
```python
from apps.gym_user.models import GymUser, ActivityLog
```

**Tip:** Add a signal in `coach/signals.py` the same way to auto-create `Coach` profile on registration.

---

### 🩺 Ng Ying Hui — Subsystem 3: Health Advisor (`apps/health_advisor/`)

**Your models:** `HealthAdvisor`, `HealthReport`, `Recommendation`

**Your TODO views:**
- `user_profile` — pull `GymUser` metrics + `calculate_bmi()` + latest `HealthReport`
- `diet_plan_update` — use `get_or_create` for `HealthReport`, then a form to update `diet_plan` text
- `recommendation_send` — form for `Recommendation`, do a safety-check validation in `clean()`
- `message_list` — simple message thread (you can use a `Message` model or keep it basic)

**Key cross-app import:**
```python
from apps.gym_user.models import GymUser
```

**Tip:** Assigning users to advisors is done in the Django admin panel OR you can add a view in `admin_panel` for Liew to handle. Coordinate!

---

### 🔧 Liew Wen Xing — Subsystem 4: Admin (`apps/admin_panel/`)

**Your models:** `AdminProfile`, `SystemLog`, `FAQ`, `Feedback`

**Your TODO views:**
- `dashboard` — aggregate counts (already coded), add Chart.js bar chart for user growth
- `user_add` — form using `accounts.RegistrationForm` (reuse it!), then auto-create the role profile
- `faq_create` / `faq_edit` — `ModelForm` for `FAQ`
- `feedback_detail` — POST to update `Feedback.status`, record in `SystemLog`
- `system_log_list` — add date range filter + search by event type

**Logging example (use this in any view across ALL apps):**
```python
from apps.admin_panel.models import SystemLog
SystemLog.record('user_created', f"New gym user {user.email}", user=request.user, module='User Management')
```

**Tip:** The `user_add` view should create the role profile automatically based on the selected role:
```python
if user.role == 'gym_user':
    GymUser.objects.create(user=user, ...)
elif user.role == 'fitness_coach':
    Coach.objects.create(user=user, ...)
# etc.
```

---

## Template Guide (all members)

Every template must start with:
```html
{% extends "shared/base.html" %}
{% block title %}Page Name{% endblock %}
{% block content %}
  <!-- your HTML here -->
{% endblock %}
```

The `base.html` already includes:
- plain HTML, CSS and JavaScript
- Dark red/black colour scheme (CSS variables)
- Role-aware navigation bar (auto-shows correct links per role)
- Flash messages display

Useful CSS classes from base:
```html
<h3 class="section-title">My Section</h3>  <!-- red left border accent -->
<span class="text-accent">highlight</span> <!-- red-orange text -->
<div class="card p-3">...</div>            <!-- dark card -->
<a class="btn btn-primary">Action</a>      <!-- red-orange button -->
```

---

## Cross-App Communication Rules

| If you need...                        | Import from...                     |
|---------------------------------------|------------------------------------|
| User model                            | `apps.accounts.models.User`        |
| Role decorator                        | `apps.accounts.decorators`         |
| GymUser / ActivityLog / FitnessGoal   | `apps.gym_user.models`             |
| WorkoutPlan / ProfessionalFeedback    | `apps.coach.models`                |
| HealthReport / Recommendation         | `apps.health_advisor.models`       |
| SystemLog / FAQ / Feedback            | `apps.admin_panel.models`          |

**Never** import `health_advisor` from `coach` or vice-versa — keep dependencies one-way.

---

## Git Workflow Suggestion

Each member works on their own branch:
```
git checkout -b feature/gym-user-goals       # Wong Kai Jun
git checkout -b feature/coach-plans          # Chong Jia Zhen
git checkout -b feature/health-advisor-diet  # Ng Ying Hui
git checkout -b feature/admin-dashboard      # Liew Wen Xing
```
Merge into `main` only after `python manage.py check` passes with no errors.

---

## Common Commands

```bash
# Check for errors before committing
python manage.py check

# Regenerate migrations after model changes
python manage.py makemigrations <app_name>
python manage.py migrate

# Access Django shell for quick testing
python manage.py shell

# Create a test user quickly
python manage.py shell -c "
from apps.accounts.models import User
u = User.objects.create_user('test@lf.com', 'pass1234', role='gym_user')
print('Created:', u)
"
```
