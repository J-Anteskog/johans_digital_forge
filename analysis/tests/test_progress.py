"""Väntesidan visar vilken fas analysen faktiskt är i – även de upp till 60 s PageSpeed tar."""

from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from analysis.models import SiteAnalysis
from analysis.tasks import PHASES, _set_phase, collect_results, run_analysis
from analysis.views import _PENDING_STEPS

from .helpers import NoNetworkMixin, addrinfo
from .test_pipeline import BASE, _enbloms_web


class StatusJsonTests(TestCase):

    def test_running_analysis_reports_phase_and_seconds(self):
        obj = SiteAnalysis.objects.create(url=BASE, status='running', analyzer_version=2)
        started = (timezone.now() - timedelta(seconds=25)).isoformat()
        SiteAnalysis.objects.filter(pk=obj.pk).update(
            results={'progress': {'phase': 'pagespeed', 'started': started}})
        data = self.client.get(reverse('analysis_status_json', kwargs={'token': obj.id})).json()
        self.assertEqual(data['phase'], 'pagespeed')
        self.assertGreaterEqual(data['phase_seconds'], 25)
        self.assertFalse(data['done'])

    def test_set_phase_only_touches_running_rows(self):
        obj = SiteAnalysis.objects.create(url=BASE, status='complete', results={'http': {}},
                                          email='kund@example.com')
        _set_phase(obj.pk, 'crawl')
        obj.refresh_from_db()
        self.assertEqual(obj.results, {'http': {}})
        self.assertEqual(obj.email, 'kund@example.com')


class PendingPageTests(TestCase):

    def test_pending_page_lists_all_phases_including_pagespeed(self):
        obj = SiteAnalysis.objects.create(url=BASE, status='running', analyzer_version=2)
        resp = self.client.get(reverse('analysis_result', kwargs={'token': obj.id}))
        self.assertTemplateUsed(resp, 'analysis/pending.html')
        self.assertContains(resp, 'Google PageSpeed (upp till 60 s)')
        for key in PHASES:
            self.assertContains(resp, f'data-phase="{key}"')
        self.assertContains(resp, 'id="psp-wait"')
        self.assertContains(resp, 'aria-live="polite"')

    def test_step_keys_match_backend_phases(self):
        self.assertEqual(tuple(k for k, _, _ in _PENDING_STEPS), PHASES)

    def test_interrupted_analysis_shows_error_page_not_empty_report(self):
        obj = SiteAnalysis.objects.create(
            url=BASE, status='error', analyzer_version=2, error_message='Servern startades om',
            results={'progress': {'phase': 'pagespeed', 'started': timezone.now().isoformat()}})
        resp = self.client.get(reverse('analysis_result', kwargs={'token': obj.id}))
        self.assertContains(resp, 'Analysen misslyckades')


@override_settings(PAGESPEED_API_KEY='')
class PhaseOrderTests(NoNetworkMixin, TestCase):

    def test_phases_are_reported_in_order(self):
        seen = []
        web = _enbloms_web()
        with ExitStack() as stack:
            for p in web.patches():
                stack.enter_context(p)
            stack.enter_context(patch('analysis.tasks.check_ssl', return_value={'valid': True}))
            collect_results(BASE, progress=seen.append)
        self.assertEqual(tuple(seen), PHASES)
        self.assertNoNetwork()

    def test_error_during_run_clears_progress(self):
        obj = SiteAnalysis.objects.create(url=BASE, status='pending', analyzer_version=2)

        def boom(url, progress=None):
            progress('pagespeed')
            raise RuntimeError('PageSpeed kraschade')

        with patch('analysis.tasks.collect_results', side_effect=boom), \
             patch('analysis.validators.socket.getaddrinfo', return_value=addrinfo('93.184.216.34')):
            run_analysis(str(obj.id))
        obj.refresh_from_db()
        self.assertEqual(obj.status, 'error')
        self.assertIsNone(obj.results)
