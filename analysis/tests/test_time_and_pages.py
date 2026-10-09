"""
Svensk tid för "Analyserades" (samma som "Mätt av Google") i rapport, delningsvy,
PDF och historik – även över midnatt och under omställningsnatten till vintertid –
samt samma sidräkning i rubrik, tabell och fynd: startsidan + undersidorna som
gick att hämta.
"""

import json
from datetime import datetime, timezone as dt_timezone

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from analysis.models import SiteAnalysis
from analysis.report import page_count, site_findings
from analysis.scoring import ANALYZER_VERSION

from .helpers import NoNetworkMixin
from .test_pagespeed_time import PSP
from .test_site_rules import SITE, _collect, _site_web

COMPLETED_UTC = datetime(2026, 10, 9, 13, 5, tzinfo=dt_timezone.utc)   # 15:05 svensk sommartid


@override_settings(PAGESPEED_API_KEY='')
class SwedishTimeAndPageCountTests(NoNetworkMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.r = _collect(_site_web(), pagespeed=PSP)
        scores = self.r.pop('scores')
        self.obj = SiteAnalysis.objects.create(
            url=SITE, domain='example-site.se', status='complete', results=self.r,
            analyzer_version=ANALYZER_VERSION, language='sv',
            **{f'score_{k}': v for k, v in scores.items()})
        SiteAnalysis.objects.filter(pk=self.obj.pk).update(completed_at=COMPLETED_UTC)

    def _html(self, name, query=''):
        return self.client.get(reverse(name, kwargs={'token': self.obj.id}) + query).content.decode()

    # ── 1. Svensk tid överallt ─────────────────────────────────────────────
    def test_analysed_time_is_swedish_time_everywhere(self):
        for name, query in (('analysis_result', ''), ('analysis_shared', ''),
                            ('analysis_pdf', ''), ('analysis_pdf', '?delad=1')):
            with self.subTest(view=name + query):
                html = self._html(name, query)
                self.assertIn('2026-10-09 15:05 (svensk tid)', html)
                self.assertNotIn('2026-10-09 13:05', html)                       # inte UTC
                self.assertIn('Mätt av Google 2026-10-09 15:29 (svensk tid)', html)

    def test_history_in_swedish_time(self):
        resp = self.client.get(reverse('domain_history', kwargs={'domain': 'example-site.se'}))
        self.assertContains(resp, '2026-10-09 15:05')
        self.assertContains(resp, 'Datum <span class="fw-normal">(svensk tid)</span>', html=False)
        self.assertEqual(json.loads(resp.context['chart_labels']), ['2026-10-09'])

    def test_date_is_swedish_across_midnight(self):
        SiteAnalysis.objects.filter(pk=self.obj.pk).update(
            completed_at=datetime(2026, 10, 9, 22, 30, tzinfo=dt_timezone.utc))   # 00:30 den 10:e i Sverige
        self.assertIn('2026-10-10 00:30 (svensk tid)', self._html('analysis_result'))
        resp = self.client.get(reverse('domain_history', kwargs={'domain': 'example-site.se'}))
        self.assertEqual(json.loads(resp.context['chart_labels']), ['2026-10-10'])

    def test_swedish_time_does_not_leak_to_rest_of_site(self):
        self._html('analysis_result')
        self.assertEqual(timezone.get_current_timezone_name(), 'UTC')

    # ── 2. Samma sidräkning överallt ───────────────────────────────────────
    def test_page_count_matches_findings(self):
        pc = page_count(self.r)
        self.assertEqual((pc['subpages'], pc['total'], pc['failed']), (3, 4, 1))
        self.assertEqual(pc['text'], 'startsidan + 3 undersidor (4 sidor)')
        self.assertEqual(pc['failed_text'], '1 sida kunde inte hämtas')
        desc = next(f for f in site_findings(self.r) if f['key'] == 'desc_missing')
        self.assertIn(f'av de {pc["total"]} sidor som kontrollerades', desc['text'])

    def test_same_count_in_header_table_and_findings(self):
        for name in ('analysis_result', 'analysis_shared'):
            with self.subTest(view=name):
                html = self._html(name)
                self.assertEqual(html.count('startsidan + 3 undersidor (4 sidor)'), 2)   # rubrik + tabell
                self.assertIn('1 sida kunde inte hämtas', html)
                self.assertIn('på 1 av de 4 sidor som kontrollerades', html)
                self.assertNotIn('sidor kontrollerade', html)                          # gamla räkningen
        self.assertIn('Kontrollerade: startsidan + 3 undersidor (4 sidor)', self._html('analysis_pdf'))

    def test_start_page_is_its_own_row_in_the_table(self):
        html = self._html('analysis_result')
        table = html[html.index('Alla sidor vi kontrollerade'):]
        first_row = table[table.index('<tbody>'):table.index('</tr>', table.index('<tbody>'))]
        self.assertIn('Startsidan', first_row)
        self.assertIn(f'href="{SITE}"', first_row)
        self.assertEqual(table.count('<tr style="border-color:rgba(255,255,255,.07);">'), 5)   # 1 + 3 + 1 fel

    def test_singular_forms(self):
        r = dict(self.r, pages=[p for p in self.r['pages'] if p['url'].endswith('tjanster')])
        self.assertEqual(page_count(r)['text'], 'startsidan + 1 undersida (2 sidor)')
        self.assertEqual(page_count(dict(self.r, pages=[]))['text'], 'startsidan (1 sida)')
        self.assertEqual(page_count(r, 'en')['text'], 'home page + 1 subpage (2 pages)')


class DaylightSavingTests(TestCase):
    """Omställningsnatten till vintertid 2026-10-25: 02:00–03:00 svensk tid inträffar två gånger."""

    def _make(self, utc_hour, utc_minute, day=25):
        obj = SiteAnalysis.objects.create(url=SITE, domain='dst.example', status='complete',
                                          analyzer_version=ANALYZER_VERSION, results={})
        SiteAnalysis.objects.filter(pk=obj.pk).update(
            completed_at=datetime(2026, 10, day, utc_hour, utc_minute, tzinfo=dt_timezone.utc))
        return obj

    def test_double_hour_keeps_date_and_order(self):
        before_midnight = self._make(23, 30, day=24)   # 01:30 sommartid den 25:e
        first = self._make(0, 30)                       # 02:30 sommartid (CEST, UTC+2)
        second = self._make(1, 30)                      # 02:30 vintertid (CET, UTC+1) – en timme senare
        after = self._make(2, 30)                       # 03:30 vintertid

        resp = self.client.get(reverse('domain_history', kwargs={'domain': 'dst.example'}))
        # Alla fyra hör till den 25:e i svensk tid, i tidsordning
        self.assertEqual(json.loads(resp.context['chart_labels']), ['2026-10-25'] * 4)
        self.assertEqual([r['a'].pk for r in resp.context['rows']],
                         [before_midnight.pk, first.pk, second.pk, after.pk])

        html = resp.content.decode()
        self.assertIn('2026-10-25 01:30', html)
        self.assertEqual(html.count('2026-10-25 02:30'), 2)   # samma klockslag två gånger – korrekt svensk tid
        self.assertIn('2026-10-25 03:30', html)
        self.assertNotIn('2026-10-24', html)
        # Tabellen visar nyast först: 03:30 (vinter), 02:30 (vinter), 02:30 (sommar), 01:30
        links = [html.index(reverse('analysis_result', kwargs={'token': a.id})) for a in (after, second, first, before_midnight)]
        self.assertEqual(links, sorted(links))
