from django.contrib import admin
from .models import SiteAnalysis


@admin.register(SiteAnalysis)
class SiteAnalysisAdmin(admin.ModelAdmin):
    list_display = [
        'url', 'status', 'score_overall', 'score_seo',
        'score_performance', 'score_security', 'score_mobile',
        'language', 'requester_ip', 'created_at',
    ]
    list_filter = ['status', 'language', 'created_at']
    search_fields = ['url', 'email', 'requester_ip']
    readonly_fields = [
        'id', 'created_at', 'completed_at', 'requester_ip',
        'score_overall', 'score_performance', 'score_mobile',
        'score_seo', 'score_security', 'results', 'error_message',
    ]
    ordering = ['-created_at']

    fieldsets = [
        ('Förfrågan', {
            'fields': ['id', 'url', 'email', 'language', 'requester_ip'],
        }),
        ('Status', {
            'fields': ['status', 'created_at', 'completed_at', 'error_message'],
        }),
        ('Poäng', {
            'fields': [
                'score_overall', 'score_performance',
                'score_mobile', 'score_seo', 'score_security',
            ],
        }),
        ('Råresultat', {
            'fields': ['results'],
            'classes': ['collapse'],
        }),
    ]
