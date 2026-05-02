import csv

from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone

from .models import SiteAnalysis


def export_leads_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = (
        f'attachment; filename="leads-{timezone.now().strftime("%Y%m%d")}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow([
        'E-post', 'URL', 'Domän', 'Betyg', 'Score', 'Samtycke',
        'Uppföljning skickad', 'Datum',
    ])
    for obj in queryset:
        writer.writerow([
            obj.email,
            obj.url,
            obj.domain,
            obj.grade,
            obj.score_overall or '',
            'Ja' if obj.marketing_consent else 'Nej',
            'Ja' if obj.followup_sent else 'Nej',
            obj.created_at.strftime('%Y-%m-%d %H:%M') if obj.created_at else '',
        ])
    return response

export_leads_csv.short_description = 'Exportera valda som CSV'


@admin.register(SiteAnalysis)
class SiteAnalysisAdmin(admin.ModelAdmin):
    list_display = [
        'url', 'status', 'score_overall', 'score_seo',
        'score_performance', 'score_security', 'score_mobile',
        'score_headers', 'score_accessibility',
        'email', 'email_submitted', 'followup_sent',
        'language', 'requester_ip', 'created_at',
    ]
    list_filter = [
        'status', 'language', 'email_submitted', 'marketing_consent',
        'followup_sent', 'created_at',
    ]
    search_fields = ['url', 'domain', 'email', 'requester_ip']
    actions = [export_leads_csv]
    readonly_fields = [
        'id', 'created_at', 'completed_at', 'requester_ip',
        'score_overall', 'score_performance', 'score_mobile',
        'score_seo', 'score_security', 'score_headers', 'score_accessibility',
        'results', 'error_message',
        'email_form_shown', 'consent_timestamp',
    ]
    ordering = ['-created_at']

    fieldsets = [
        ('Förfrågan', {
            'fields': ['id', 'url', 'domain', 'email', 'language', 'requester_ip'],
        }),
        ('Status', {
            'fields': ['status', 'created_at', 'completed_at', 'error_message'],
        }),
        ('Poäng', {
            'fields': [
                'score_overall', 'score_performance', 'score_mobile',
                'score_seo', 'score_security', 'score_headers', 'score_accessibility',
            ],
        }),
        ('E-post & GDPR', {
            'fields': [
                'email_form_shown', 'email_submitted',
                'marketing_consent', 'consent_timestamp', 'followup_sent',
            ],
        }),
        ('Råresultat', {
            'fields': ['results'],
            'classes': ['collapse'],
        }),
    ]
