from django.contrib import admin
from .models import Service

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title_sv', 'title_en', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title_sv', 'title_en')

    fields = (
        'title_sv', 'title_en', 
        'description_sv', 'description_en', 
        'extra_info_sv', 'extra_info_en',  # nya fält
        'price', 'icon', 'is_active'
    )
