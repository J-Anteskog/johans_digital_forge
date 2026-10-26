from django.contrib import admin
from .models import Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title_sv', 'is_active', 'is_featured')
    list_filter = ('is_active', 'is_featured')
    search_fields = ('title_sv', 'title_en', 'technologies')
