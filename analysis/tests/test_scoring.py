"""Regel 1 (prestanda), 5 (säkerhetsheaders) och 6 (viktning när något inte kan mätas)."""

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from analysis.checks.headers import check_headers
from analysis.checks.pagespeed import check_pagespeed
from analysis.net import FetchResult
from analysis.report import category_label, pagespeed_status_text
from analysis.scoring import WEIGHTS, calculate_scores, overall_score, performance_source

from .helpers import NoNetworkMixin


def _results(**over):
    """Minimal, fullständigt uppmätt results-dict."""
    base = {
        'http': {'status_code': 200, 'is_https': True, 'response_time_ms': 400, 'html_bytes': 40_000},
        'ssl': {'valid': True, 'expires_soon': False},
        'seo': {'title': {'found': True, 'ok': True}},
        'resources': {'total_files': 8, 'render_blocking_scripts': 0},
        'mobile': {'score': 80},
        'headers': {'headers': [{'found': False}], 'score': 0, 'error': None},
        'accessibility': {'score': 70},
        'pagespeed': {'status': 'not_configured'},
    }
    base.update(over)
    return base


class PerformanceTests(SimpleTestCase):

    def test_without_pagespeed_uses_basic_measurements(self):
        r = _results()
        self.assertEqual(performance_source(r), 'basic')
        self.assertEqual(calculate_scores(r)['performance'], 100)
        self.assertEqual(category_label('performance', r), 'Sidvikt och svarstid')

    def test_basic_score_is_not_a_fixed_80_for_fast_servers(self):
        """Tidigare: svarstid <500 ms gav alltid 80, oavsett sidvikt."""
        r = _results(http={'status_code': 200, 'is_https': True, 'response_time_ms': 400, 'html_bytes': 400_000},
                     resources={'total_files': 25, 'render_blocking_scripts': 4})
        self.assertEqual(calculate_scores(r)['performance'], 40)

    def test_pagespeed_used_when_available(self):
        r = _results(pagespeed={'status': 'ok', 'mobile': {'score': 50}, 'desktop': {'score': 90}})
        self.assertEqual(performance_source(r), 'pagespeed')
        self.assertEqual(calculate_scores(r)['performance'], 62)   # 0,7 × 50 + 0,3 × 90
        self.assertEqual(category_label('performance', r), 'Prestanda (PageSpeed)')

    def test_not_measured_without_html(self):
        r = _results(seo={})
        self.assertIsNone(calculate_scores(r)['performance'])


class PageSpeedTests(NoNetworkMixin, SimpleTestCase):

    @override_settings(PAGESPEED_API_KEY='')
    def test_not_configured(self):
        self.assertEqual(check_pagespeed('https://example.com/'), {'status': 'not_configured'})
        self.assertEqual(pagespeed_status_text({'pagespeed': {'status': 'not_configured'}}),
                         'PageSpeed API är inte konfigurerat på vår server.')
        self.assertNoNetwork()

    @override_settings(PAGESPEED_API_KEY='hemlig-nyckel')
    def test_http_error_is_reported_without_leaking_key_or_ip(self):
        class _R:
            status_code = 403
            def json(self):
                return {'error': {'status': 'PERMISSION_DENIED',
                                  'message': 'IP address 2a02:1406::1 violates restriction'}}
        with patch('analysis.checks.pagespeed.requests.get', return_value=_R()):
            res = check_pagespeed('https://example.com/')
        self.assertEqual(res['status'], 'failed')
        self.assertEqual(res['mobile'], {'error_kind': 'http', 'http_status': 403, 'reason': 'PERMISSION_DENIED'})
        text = pagespeed_status_text({'pagespeed': res})
        self.assertIn('HTTP 403', text)
        self.assertNotIn('2a02', str(res))
        self.assertNotIn('hemlig-nyckel', str(res))

    @override_settings(PAGESPEED_API_KEY='hemlig-nyckel')
    def test_timeout_is_reported(self):
        import requests
        with patch('analysis.checks.pagespeed.requests.get', side_effect=requests.exceptions.Timeout()):
            res = check_pagespeed('https://example.com/')
        self.assertEqual(res['desktop'], {'error_kind': 'timeout', 'timeout_s': 60})
        self.assertIn('timeout efter 60 s', pagespeed_status_text({'pagespeed': res}))

    @override_settings(PAGESPEED_API_KEY='hemlig-nyckel')
    def test_connection_error_message_with_key_is_not_stored(self):
        import requests
        err = requests.exceptions.ConnectionError('…runPagespeed?url=x&key=hemlig-nyckel failed')
        with patch('analysis.checks.pagespeed.requests.get', side_effect=err):
            res = check_pagespeed('https://example.com/')
        self.assertNotIn('hemlig-nyckel', str(res))

    @override_settings(PAGESPEED_API_KEY='hemlig-nyckel')
    def test_success(self):
        class _R:
            status_code = 200
            def json(self):
                return {'lighthouseResult': {
                    'categories': {'performance': {'score': 0.73}},
                    'audits': {'largest-contentful-paint': {'numericValue': 2500.4}},
                }}
        with patch('analysis.checks.pagespeed.requests.get', return_value=_R()):
            res = check_pagespeed('https://example.com/')
        self.assertEqual(res['status'], 'ok')
        self.assertEqual(res['mobile']['score'], 73)
        self.assertEqual(res['mobile']['lcp_ms'], 2500)


class HeadersTests(SimpleTestCase):

    def test_zero_score_is_a_measured_zero(self):
        """enbloms: inga säkerhetsheaders → 0 (tidigare visat som '–')."""
        page = FetchResult(url='https://e.example/', status_code=200, headers={'server': 'openresty'})
        hdr = check_headers(page)
        self.assertEqual(hdr['score'], 0)
        self.assertEqual(hdr['found_count'], 0)
        self.assertEqual(calculate_scores(_results(headers=hdr))['headers'], 0)

    def test_headers_read_from_same_response(self):
        page = FetchResult(url='https://e.example/', status_code=200, headers={
            'strict-transport-security': 'max-age=31536000',
            'x-content-type-options': 'nosniff',
        })
        hdr = check_headers(page)
        self.assertEqual(hdr['score'], 45)
        self.assertEqual(hdr['found_count'], 2)

    def test_no_response_is_not_measured(self):
        hdr = check_headers(FetchResult(url='https://e.example/', error='Timeout', error_kind='timeout'))
        self.assertIsNone(hdr['score'])
        self.assertIsNone(calculate_scores(_results(headers=hdr))['headers'])

    def test_security_label_says_what_it_measures(self):
        self.assertEqual(category_label('security', {}), 'HTTPS och certifikat')


class OverallWeightingTests(SimpleTestCase):

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.0)

    def test_unmeasured_category_is_excluded_not_zero(self):
        all_80 = {k: 80 for k in WEIGHTS}
        self.assertEqual(overall_score(all_80), 80)
        self.assertEqual(overall_score({**all_80, 'headers': None}), 80)   # inte 80*0.87 = 70
        self.assertEqual(overall_score({**all_80, 'headers': 0}), 70)      # uppmätt 0 räknas

    def test_reweighting(self):
        scores = {k: None for k in WEIGHTS}
        scores.update(security=100, seo=50)
        self.assertEqual(overall_score(scores), round((100 * .20 + 50 * .22) / .42))

    def test_nothing_measured(self):
        self.assertIsNone(overall_score({k: None for k in WEIGHTS}))

    def test_html_fetch_failure_does_not_give_zeros(self):
        r = _results(seo={}, accessibility={}, mobile={}, resources={})
        s = calculate_scores(r)
        for key in ('seo', 'performance', 'mobile', 'accessibility'):
            self.assertIsNone(s[key], key)
        self.assertEqual(s['security'], 100)
