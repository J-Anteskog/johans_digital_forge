from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from analysis.models import SiteAnalysis


class Command(BaseCommand):
    help = 'Markerar analyser som fastnat i pending/running som error'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes', type=int, default=10,
            help='Hur gamla pending/running måste vara för att städas (default: 10)',
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=options['minutes'])
        stuck = SiteAnalysis.objects.filter(
            status__in=['pending', 'running'],
            created_at__lt=cutoff,
        )
        count = stuck.count()
        stuck.update(
            status='error',
            error_message='Analysen avbröts (servern startades om).',
            completed_at=timezone.now(),
        )
        self.stdout.write(
            self.style.SUCCESS(f'Städade {count} fastnade analyser')
        )
