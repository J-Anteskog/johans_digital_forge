"""
PageSpeed: tidpunkt för mätningen (fetchTime), förklaring av att värdena varierar
och mobil/dator per analys i domänhistoriken – utan fler anrop mot Google än tidigare.
"""

import json
from contextlib import ExitStack
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from analysis.checks.pagespeed import check_pagespeed
from analysis.models import SiteAnalysis
from analysis.report import pagespeed_summary
from analysis.scoring import ANALYZER_VERSION

from .helpers import NoNetworkMixin
from .test_site_rules import SITE, _collect, _site_web

FETCH_MOBILE = '2026-10-09T13:29:43.639Z'
FETCH_DESKTOP = '2026-10-09T13:29:41.120Z'
PSP = {'status': 'ok',
       'mobile': {'score': 66, 'fetch_time': FETCH_MOBILE},
       'desktop': {'score': 81, 'fetch_time': FETCH_DESKTOP}}


class _Resp:
    status_code = 200

    def __init__(self, score, fetch_time):
        self._data = {'lighthouseResult': {'fetchTime': fetch_time,
                                           'categories': {'performance': {'score': score}}, 'audits': {}}}

    def json(self):
        return self._data


class FetchTimeTests(NoNetworkMixin, SimpleTestCase):

    @override_settings(PAGESPEED_API_KEY='nyckel')
    def test_fetch_time_is_stored_and_no_extra_calls_are_made(self):
        with patch('analysis.checks.pagespeed.requests.get', return_value=_Resp(0.66, FETCH_MOBILE)) as get:
            res = check_pagespeed('https://example.com/')
        self.assertEqual(get.call_count, 2)                     # en per strategi, som tidigare
        self.assertEqual(res['mobile']['fetch_time'], FETCH_MOBILE)
        self.assertNoNetwork()

    def test_measured_at_is_shown_in_swedish_time(self):
        s = pagespeed_summary({'pagespeed': PSP})
        self.assertEqual(s['measured_at'], '2026-10-09 15:29 (svensk tid)')   # UTC+2 (sommartid)
        self.assertIn('ibland mer än 10 poäng', s['variation_text'])
        winter = pagespeed_summary({'pagespeed': {'mobile': {'score': 50, 'fetch_time': '2026-12-01T13:05:00Z'}}})
        self.assertEqual(winter['measured_at'], '2026-12-01 14:05 (svensk tid)')  # UTC+1

    def test_reports_without_fetch_time_show_no_time(self):
        s = pagespeed_summary({'pagespeed': {'mobile': {'score': 70}, 'desktop': {'score': 90}}})
        self.assertEqual(s['measured_at'], '')


@override_settings(PAGESPEED_API_KEY='')
class FetchTimeRenderingTests(NoNetworkMixin, TestCase):

    def setUp(self):
        super().setUp()
        r = _collect(_site_web(), pagespeed=PSP)
        scores = r.pop('scores')
        self.obj = SiteAnalysis.objects.create(
            url=SITE, domain='example-site.se', status='complete', results=r,
            analyzer_version=ANALYZER_VERSION, language='sv',
            **{f'score_{k}': v for k, v in scores.items()})

    def test_time_and_variation_text_in_report_shared_view_and_pdf(self):
        for name, query in (('analysis_result', ''), ('analysis_shared', ''),
                            ('analysis_pdf', ''), ('analysis_pdf', '?delad=1')):
            with self.subTest(view=name + query):
                html = self.client.get(reverse(name, kwargs={'token': self.obj.id}) + query).content.decode()
                self.assertIn('Mätt av Google 2026-10-09 15:29 (svensk tid)', html)
                self.assertIn('Googles värden varierar mellan mätningar, ibland mer än 10 poäng', html)
                self.assertNotIn('ofta 5–10 poäng', html)

    def test_history_shows_mobile_and_desktop_per_analysis(self):
        SiteAnalysis.objects.create(url=SITE, domain='example-site.se', status='complete',
                                    analyzer_version=ANALYZER_VERSION, results={'pagespeed': {'status': 'not_configured'}})
        resp = self.client.get(reverse('domain_history', kwargs={'domain': 'example-site.se'}))
        self.assertContains(resp, 'PageSpeed mobil')
        self.assertContains(resp, 'PageSpeed dator')
        self.assertContains(resp, 'Mobilanp.')
        mobile = json.loads(resp.context['chart_psp_mobile'])
        desktop = json.loads(resp.context['chart_psp_desktop'])
        self.assertEqual(sorted(mobile, key=lambda v: (v is None, v)), [66, None])   # ej mätt → null
        self.assertEqual(sorted(desktop, key=lambda v: (v is None, v)), [81, None])
        self.assertContains(resp, '<td class="px-4 py-3 text-end text-secondary">66</td>', html=False)
