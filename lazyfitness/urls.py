from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView

from . import views

urlpatterns = [
    path('admin/', RedirectView.as_view(url='/admin-panel/dashboard/', permanent=False)),
    path('admin/<path:path>/', RedirectView.as_view(url='/admin-panel/%(path)s', permanent=False)),
    path('django-admin/', admin.site.urls),
    path('', views.landing, name='landing'),
    path('faq/', views.faq_public, name='faq_public'),
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
