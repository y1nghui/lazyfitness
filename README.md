# LazyFitness

LazyFitness is a Django 4.2 student assignment web application for gym users, fitness coaches, health advisors, and platform admins. It uses a custom role-based user model, SQLite, plain HTML, CSS and JavaScript, and a dark red/black theme.

## Stack

- Python 3.11
- Django 4.2
- SQLite
- plain HTML, CSS and JavaScript
- Apps: `accounts`, `gym_user`, `coach`, `health_advisor`, `admin_panel`

## Setup

```bash
cd LazyFitness
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install and run:

```bash
pip install -r requirements.txt
python manage.py makemigrations accounts gym_user coach health_advisor admin_panel
python manage.py migrate
python manage.py runserver

To create superuser
(this is for your login into the database by http://127.0.0.1:8000/django-admin):
python manage.py createsuperuser

```

Open: <http://127.0.0.1:8000/>


## Important URLs

| Page | URL |
|---|---|
| Landing / Meet Our Team | `/` |
| Login | `/accounts/login/` |
| Register gym user | `/accounts/register/` |
| Account edit | `/accounts/account/` |
| Change password | `/accounts/password/change/` |
| Gym dashboard | `/gym/dashboard/` |
| Gym recommendations | `/gym/recommendations/` |
| Coach assigned users | `/coach/assigned-users/` |
| Advisor assigned users | `/advisor/users/` |
| Admin dashboard | `/admin-panel/dashboard/` |
| Admin users | `/admin-panel/users/` |
| Login activity | `/admin-panel/login-activity/` |
| CSV users export | `/admin-panel/export/users/` |

## Role walkthrough

### Public visitor

- View landing page.
- See Meet Our Coaches and Meet Our Health Advisors.
- Register as a gym user only.

### Gym user

- Complete gym profile after first login.
- View BMI, assigned coach/advisor, goals, schedule, activity logs, progress, recommendations, and messages.
- Upload/remove profile picture from Account page.
- Change own password.

### Fitness coach

- View assigned users only.
- Filter assigned users by search, BMI, unread messages, and recent activity.
- Create/edit/delete workout plans, workouts, and exercises.
- Monitor assigned activity logs and give professional feedback.
- Use shared messages.

### Health advisor

- View assigned users only.
- Filter assigned users by search, BMI, unread messages, diet report status, and recommendation status.
- Create diet plan and recommendations for assigned users.
- Monitor user health metrics, workout logs, diet plan history.
- Use shared messages.

### Admin

- Manage users from the custom admin panel.
- Add gym users, coaches, and health advisors.
- Only Django superusers can create/edit another admin account.
- Admin cannot delete self or delete admin accounts.
- Assign coach/advisor to gym users and track assignment history.
- View login activity, system logs, feedback, CSV exports, and assignment history.

## Admin safety rules

- Public registration is gym-user only.
- State-changing actions use POST + CSRF.
- Activate/deactivate preserves the page the admin came from.
- Assignment cancel uses a safe internal `next` URL.
- Inactive users are logged out/blocked.
- Wrong-role users are redirected with friendly messages.

## Media uploads

Profile pictures are stored in `MEDIA_ROOT` under `profile_pictures/`. Supported formats are jpg, jpeg, png, and webp. Maximum size is 2 MB. Old unused profile pictures are removed when a user uploads a replacement or removes their picture.

## CSV exports

Admins can export:

- Users: `/admin-panel/export/users/`
- Login activity: `/admin-panel/export/login-activity/`
- Feedback: `/admin-panel/export/feedback/`

## Testing and checks

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test
```

## Known assumptions

- Shared messaging becomes fully active when a gym user has both an assigned coach and health advisor.
- Chat is limited to the original care-team thread: gym user, assigned coach, and assigned health advisor. Group chat creation is intentionally disabled.
- Admin can view conversation summaries but does not need to participate in chat.
- The included demo data is presentation-safe and uses `.test` email addresses.


## Latest improvements

- Progress analytics dashboard with workout and body measurement trends.
- Body measurement history for weight, waist, neck, calorie target, and notes.
- Workout plan assignment from coaches to assigned gym users.
- Diet plan creation, editing, viewing, and assignment for health advisors.
- Care-team-only WhatsApp-like chat bubbles with role indicators, uploaded attachment validation, own messages on the right, and other users on the left; user-facing attachment URL fields and group chat creation were removed.
- Notification center with separate read and opened states, unopened dot indicators, mark-all actions, and auto-dismissing success toasts.
- Fitness goal editing, cancelling, completion and unmarking actions.
- Separated monthly date-specific plans from weekly recurring routines, with Monthly Plan as the default schedule view.
- Forgot password page explains admin force-reset flow instead of email reset.
- Demo guide and system health pages were removed as requested.
