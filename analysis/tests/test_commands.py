from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from analysis.models import SiteAnalysis


def _make_analysis(**kwargs):
    defaults = dict(
        url='https://example.com',
        status='pending',
        results={},
    )
    defaults.update(kwargs)
    obj = SiteAnalysis(**defaults)
    obj.save()
    return obj


def _age(obj, minutes=0, days=0):
    """Back-date created_at (and optionally completed_at) via queryset update."""
    delta = timedelta(minutes=minutes, days=days)
    SiteAnalysis.objects.filter(pk=obj.pk).update(
        created_at=timezone.now() - delta,
        completed_at=(timezone.now() - delta) if obj.completed_at else None,
    )
    obj.refresh_from_db()
    return obj


# ---------------------------------------------------------------------------
# cleanup_stuck_analyses
# ---------------------------------------------------------------------------

class CleanupStuckTests(TestCase):

    def _run(self, **kwargs):
        out = StringIO()
        call_command('cleanup_stuck_analyses', stdout=out, **kwargs)
        return out.getvalue()

    def test_old_pending_becomes_error(self):
        obj = _make_analysis(status='pending')
        _age(obj, minutes=15)
        self._run()
        obj.refresh_from_db()
        self.assertEqual(obj.status, 'error')

    def test_old_running_becomes_error(self):
        obj = _make_analysis(status='running')
        _age(obj, minutes=15)
        self._run()
        obj.refresh_from_db()
        self.assertEqual(obj.status, 'error')

    def test_error_message_is_set(self):
        obj = _make_analysis(status='pending')
        _age(obj, minutes=15)
        self._run()
        obj.refresh_from_db()
        self.assertTrue(obj.error_message)

    def test_completed_at_is_set(self):
        obj = _make_analysis(status='pending')
        _age(obj, minutes=15)
        self._run()
        obj.refresh_from_db()
        self.assertIsNotNone(obj.completed_at)

    def test_recent_pending_not_touched(self):
        obj = _make_analysis(status='pending')
        _age(obj, minutes=5)  # Only 5 min old, below default 10
        self._run()
        obj.refresh_from_db()
        self.assertEqual(obj.status, 'pending')

    def test_complete_not_touched(self):
        obj = _make_analysis(status='complete')
        _age(obj, minutes=15)
        self._run()
        obj.refresh_from_db()
        self.assertEqual(obj.status, 'complete')

    def test_custom_minutes_argument(self):
        obj = _make_analysis(status='pending')
        _age(obj, minutes=7)
        # --minutes 5: 7-min-old analysis should be cleaned
        self._run(minutes=5)
        obj.refresh_from_db()
        self.assertEqual(obj.status, 'error')

    def test_output_shows_count(self):
        obj = _make_analysis(status='pending')
        _age(obj, minutes=15)
        output = self._run()
        self.assertIn('1', output)

    def test_zero_stuck_analyses_outputs_zero(self):
        output = self._run()
        self.assertIn('0', output)


# ---------------------------------------------------------------------------
# purge_old_analyses
# ---------------------------------------------------------------------------

class PurgeOldAnalysesTests(TestCase):

    def _run(self, **kwargs):
        out = StringIO()
        call_command('purge_old_analyses', stdout=out, **kwargs)
        return out.getvalue()

    def _make_complete(self, days_old):
        obj = _make_analysis(status='complete', completed_at=timezone.now())
        SiteAnalysis.objects.filter(pk=obj.pk).update(
            created_at=timezone.now() - timedelta(days=days_old),
            completed_at=timezone.now() - timedelta(days=days_old),
        )
        obj.refresh_from_db()
        return obj

    def test_old_complete_is_deleted(self):
        obj = self._make_complete(days_old=91)
        self._run()
        self.assertFalse(SiteAnalysis.objects.filter(pk=obj.pk).exists())

    def test_recent_complete_not_deleted(self):
        obj = self._make_complete(days_old=30)
        self._run()
        self.assertTrue(SiteAnalysis.objects.filter(pk=obj.pk).exists())

    def test_pending_not_deleted(self):
        obj = _make_analysis(status='pending')
        _age(obj, days=100)
        self._run()
        self.assertTrue(SiteAnalysis.objects.filter(pk=obj.pk).exists())

    def test_dry_run_does_not_delete(self):
        obj = self._make_complete(days_old=91)
        self._run(dry_run=True)
        self.assertTrue(SiteAnalysis.objects.filter(pk=obj.pk).exists())

    def test_dry_run_output_contains_count(self):
        self._make_complete(days_old=91)
        output = self._run(dry_run=True)
        self.assertIn('1', output)
        self.assertIn('ry', output)  # "Dry run" or "dry"

    def test_custom_days_argument(self):
        obj = self._make_complete(days_old=10)
        self._run(days=7)
        self.assertFalse(SiteAnalysis.objects.filter(pk=obj.pk).exists())

    def test_output_shows_deleted_count(self):
        self._make_complete(days_old=91)
        output = self._run()
        self.assertIn('1', output)
