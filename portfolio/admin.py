from django.contrib import admin
from .models import Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title_sv', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title_sv', 'title_en', 'technologies')
