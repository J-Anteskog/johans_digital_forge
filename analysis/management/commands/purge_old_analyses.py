from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from analysis.models import SiteAnalysis


class Command(BaseCommand):
    help = 'Raderar gamla kompletta analyser (GDPR-städning)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=90,
            help='Ta bort complete-analyser äldre än N dagar (default: 90)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Visa antal utan att radera',
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options['days'])
        old = SiteAnalysis.objects.filter(
            status='complete',
            completed_at__lt=cutoff,
        )
        count = old.count()

        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f'Dry run: {count} analyser skulle raderas (äldre än {options["days"]} dagar)'
                )
            )
            return

        old.delete()
        self.stdout.write(
            self.style.SUCCESS(f'Raderade {count} gamla analyser')
        )
