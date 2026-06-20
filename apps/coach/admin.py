from django.contrib import admin
from .models import Coach, WorkoutPlan, Workout, Exercise, ProfessionalFeedback


@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    list_display = ('coach_name', 'user', 'specialty', 'years_experience')
    search_fields = ('coach_name', 'user__username', 'specialty')
    fields = ('user', 'coach_name', 'specialty', 'years_experience', 'bio')


admin.site.register(WorkoutPlan)
admin.site.register(Workout)
admin.site.register(Exercise)
admin.site.register(ProfessionalFeedback)
