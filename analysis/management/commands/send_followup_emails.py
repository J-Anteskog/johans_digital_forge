"""
Skickar uppföljningsmejl dag 3 till användare som lämnat e-post.
Kör dagligen via cron: python manage.py send_followup_emails
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from analysis.email import send_followup_email
from analysis.models import SiteAnalysis


class Command(BaseCommand):
    help = 'Skickar uppföljningsmejl till analyser som är 3 dagar gamla'

    def handle(self, *args, **options):
        three_days_ago = timezone.now() - timedelta(days=3)
        four_days_ago  = timezone.now() - timedelta(days=4)

        qs = SiteAnalysis.objects.filter(
            status='complete',
            email_submitted=True,
            marketing_consent=True,
            followup_sent=False,
            completed_at__gte=four_days_ago,
            completed_at__lte=three_days_ago,
        )

        count = 0
        for analysis in qs:
            send_followup_email(analysis)
            analysis.followup_sent = True
            analysis.save(update_fields=['followup_sent'])
            count += 1
            self.stdout.write(f'  Skickade uppföljning till {analysis.email} ({analysis.domain})')

        self.stdout.write(self.style.SUCCESS(f'Klar — {count} uppföljningsmejl skickade.'))
