from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import ProjectBrief


@admin.register(ProjectBrief)
class ProjectBriefAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'contact_name', 'contact_email', 'budget', 'timeline',
        'status', 'score_display', 'language', 'created_at',
    ]
    list_filter = ['status', 'budget', 'timeline', 'language']
    search_fields = ['contact_name', 'contact_email', 'notes']
    readonly_fields = ['created_at', 'score_display', 'referrer_link', 'admin_meta_info']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    fieldsets = [
        ('Metadata', {
            'fields': ('created_at', 'status', 'language', 'referrer_link', 'score_display', 'admin_meta_info'),
        }),
        ('Steg 1 – Mål, budget & tidslinje', {
            'fields': ('goals', 'goals_other', 'budget', 'timeline', 'timeline_specific'),
        }),
        ('Steg 2 – Befintlig sida, storlek & funktioner', {
            'fields': ('has_existing_site', 'existing_site_url', 'num_pages', 'features', 'features_other'),
        }),
        ('Steg 3 – Stil, material & kontakt', {
            'fields': (
                'has_material', 'style_preferences', 'notes',
                'contact_name', 'contact_email', 'contact_phone',
            ),
        }),
    ]

    actions = ['mark_as_reviewed', 'mark_as_quoted', 'mark_as_declined']

    @admin.display(description='Källa')
    def referrer_link(self, obj):
        if obj.referrer and obj.referrer.startswith('analysis:'):
            analysis_id = obj.referrer.split(':', 1)[1]
            try:
                url = reverse('analysis_result', kwargs={'token': analysis_id})
                return format_html('<a href="{}" target="_blank">Se analys →</a>', url)
            except Exception:
                pass
        return obj.referrer or '–'

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

    @admin.display(description='Info')
    def admin_meta_info(self, obj):
        changelist_url = reverse('admin:brief_projectbrief_changelist')
        return format_html(
            'Genererat automatiskt av offertbriefs-formuläret &middot; ID #{} &middot; <a href="{}">Öppna i admin</a>',
            obj.pk,
            changelist_url,
        )

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
