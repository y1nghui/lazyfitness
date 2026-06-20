from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', views.landing, name='landing'),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('gym/', include('apps.gym_user.urls', namespace='gym_user')),
    path('coach/', include('apps.coach.urls', namespace='coach')),
    path('advisor/', include('apps.health_advisor.urls', namespace='health_advisor')),
    path('admin-panel/', include('apps.admin_panel.urls', namespace='admin_panel')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = 'lazyfitness.views.bad_request'
handler403 = 'lazyfitness.views.permission_denied'
handler404 = 'lazyfitness.views.page_not_found'
handler500 = 'lazyfitness.views.server_error'
