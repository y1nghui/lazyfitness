from django.contrib import admin
from .models import HealthAdvisor, HealthReport, Recommendation


@admin.register(HealthAdvisor)
class HealthAdvisorAdmin(admin.ModelAdmin):
    list_display = ('advisor_name', 'user', 'specialty', 'years_experience')
    search_fields = ('advisor_name', 'user__username', 'specialty')
    fields = ('user', 'advisor_name', 'specialty', 'years_experience', 'bio', 'assigned_users')
    filter_horizontal = ('assigned_users',)


admin.site.register(HealthReport)
admin.site.register(Recommendation)
