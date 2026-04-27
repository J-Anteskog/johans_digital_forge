from django.contrib import admin
from .models import ProjectBrief


@admin.register(ProjectBrief)
class ProjectBriefAdmin(admin.ModelAdmin):
    list_display = [
        'contact_name', 'contact_email', 'budget', 'timeline',
        'status', 'score_display', 'language', 'created_at',
    ]
    list_filter = ['status', 'budget', 'timeline', 'language']
    search_fields = ['contact_name', 'contact_email', 'notes']
    readonly_fields = ['created_at', 'score_display']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    fieldsets = [
        ('Metadata', {
            'fields': ('created_at', 'status', 'language', 'referrer', 'score_display'),
        }),
        ('Steg 1 – Mål, budget & tidslinje', {
            'fields': ('goals', 'goals_other', 'budget', 'timeline', 'timeline_specific'),
        }),
        ('Steg 2 – Befintlig sida, storlek & funktioner', {
            'fields': ('has_existing_site', 'num_pages', 'features', 'features_other'),
        }),
        ('Steg 3 – Stil, material & kontakt', {
            'fields': (
                'has_material', 'style_preferences', 'notes',
                'contact_name', 'contact_email', 'contact_phone',
            ),
        }),
    ]

    actions = ['mark_as_reviewed', 'mark_as_quoted', 'mark_as_declined']

    @admin.display(description='Score', ordering='budget')
    def score_display(self, obj):
        score = obj.score()
        if score >= 70:
            color = '#198754'
        elif score >= 40:
            color = '#fd7e14'
        else:
            color = '#6c757d'
        return f'{score}/100'
    score_display.allow_tags = False

    @admin.action(description='Markera som granskade')
    def mark_as_reviewed(self, request, queryset):
        updated = queryset.update(status='reviewed')
        self.message_user(request, f'{updated} brief(ar) markerade som granskade.')

    @admin.action(description='Markera som offerterade')
    def mark_as_quoted(self, request, queryset):
        updated = queryset.update(status='quoted')
        self.message_user(request, f'{updated} brief(ar) markerade som offerterade.')

    @admin.action(description='Markera som avböjda')
    def mark_as_declined(self, request, queryset):
        updated = queryset.update(status='declined')
        self.message_user(request, f'{updated} brief(ar) markerade som avböjda.')
