"""
Hela analysen på det enbloms-liknande exemplet (WordPress/Mesmerize) utan nätverk,
samt rendering av rapporten, äldre rapporter, cache och historik.
"""

import json
from contextlib import ExitStack
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from analysis.models import SiteAnalysis
from analysis.scoring import ANALYZER_VERSION
from analysis.tasks import collect_results

from .helpers import FakeWeb, NoNetworkMixin, addrinfo, fixture_bytes

BASE = 'https://enbloms.example/'
THEME_CSS = b'@media (min-width:768px){.row{display:flex}} .content img{max-width:100%;height:auto}'


def _enbloms_web():
    html = {'Content-Type': 'text/html; charset=UTF-8', 'Server': 'openresty'}
    return FakeWeb({
        BASE: (200, html, fixture_bytes('wordpress_mesmerize.html')),
        BASE + 'robots.txt': (200, {}, b'User-agent: *\nSitemap: https://enbloms.example/wp-sitemap.xml'),
        BASE + 'sitemap.xml': (200, {}, b'<urlset/>'),
        BASE + 'wp-content/themes/mesmerize/style.min.css': (200, {}, b'body{margin:0}'),
        BASE + 'wp-content/themes/mesmerize/assets/css/theme.bundle.min.css': (200, {}, THEME_CSS),
        BASE + 'wp-content/plugins/mesmerize-companion/theme-data/mesmerize/assets/css/companion.bundle.min.css':
            (200, {}, b'.x{}'),
        'https://fonts.googleapis.com/css?family=Open+Sans%3A300%2C400&subset=latin': (200, {}, b'@font-face{}'),
        BASE + 'wp-content/uploads/2019/05/bild-1.jpg': (200, {'Content-Length': str(600 * 1024)}, b''),
        BASE + 'wp-content/uploads/2019/05/bild-2.jpg': (200, {'Content-Length': str(90 * 1024)}, b''),
        BASE + 'wp-content/uploads/2019/05/bild-3.jpg': (200, {}, b''),   # storlek anges inte
    })


@override_settings(PAGESPEED_API_KEY='')
class EnblomsLikePipelineTests(NoNetworkMixin, TestCase):

    def _collect(self):
        web = _enbloms_web()
        ssl_ok = {'ok': True, 'valid': True, 'expiry_date': '2026-12-17', 'days_remaining': 68,
                  'expires_soon': False, 'error': None}
        with ExitStack() as stack:
            for p in web.patches():
                stack.enter_context(p)
            stack.enter_context(patch('analysis.tasks.check_ssl', return_value=ssl_ok))
            results = collect_results(BASE)
        self.assertNoNetwork()
        return results, web

    def test_results(self):
        r, web = self._collect()
        scores = r['scores']

        # 3. CSS/JS räknas (tidigare 0 CSS · 0 JS)
        self.assertEqual((r['resources']['css_files'], r['resources']['js_files']), (4, 6))
        # 4. alt="" är dekorativt, inte saknat – samma resultat i hela rapporten
        self.assertEqual((r['images']['decorative'], r['images']['missing_alt']), (3, 0))
        self.assertIs(r['accessibility']['images'], r['images'])
        self.assertNotIn('images_without_alt', r['performance'])
        # 7. skip-länken hittas; landmärken och H1 saknas verkligen
        self.assertTrue(r['accessibility']['skip_nav']['found'])
        self.assertEqual(r['accessibility']['landmarks']['found'], [])
        self.assertEqual(r['accessibility']['headings']['h1_count'], 0)
        # 1. ingen PageSpeed → "Sidvikt och svarstid" på uppmätta värden
        self.assertEqual(r['pagespeed'], {'status': 'not_configured'})
        self.assertEqual(r['scoring']['performance_source'], 'basic')
        self.assertEqual(r['performance']['images_large'], 1)
        self.assertEqual(r['performance']['images_size_unknown'], 1)
        # 2. mobil bygger på delkontroller, CSS-filerna lästes
        self.assertEqual(r['mobile']['checks']['media_queries']['stylesheets_read'], 4)
        # 5. inga säkerhetsheaders → uppmätt 0
        self.assertEqual(scores['headers'], 0)

        self.assertEqual(scores, {
            'security': 100, 'seo': 45, 'performance': 100, 'mobile': 90,   # mobil: högst 90
            'headers': 0, 'accessibility': 60,
            'overall': round(100 * .20 + 45 * .22 + 100 * .20 + 90 * .15 + 0 * .13 + 60 * .10),
        })
        # 6. alla sex kategorier uppmätta
        self.assertEqual(r['scoring']['measured_count'], 6)
        # Google Fonts-stilmallen hämtades via den säkra vägen, inte förbi den
        self.assertIn('https://fonts.googleapis.com/css?family=Open+Sans%3A300%2C400&subset=latin', web.requested)

    def _save(self, results):
        scores = results.pop('scores')
        return SiteAnalysis.objects.create(
            url=BASE, domain='enbloms.example', status='complete', results=results,
            analyzer_version=ANALYZER_VERSION, language='sv',
            score_overall=scores['overall'], score_security=scores['security'], score_seo=scores['seo'],
            score_performance=scores['performance'], score_mobile=scores['mobile'],
            score_headers=scores['headers'], score_accessibility=scores['accessibility'],
        )

    def test_report_never_claims_unmeasured_things(self):
        results, _ = self._collect()
        obj = self._save(results)
        resp = self.client.get(reverse('analysis_result', kwargs={'token': obj.id}))
        self.assertTemplateUsed(resp, 'analysis/result.html')
        html = resp.content.decode()

        self.assertIn('HTTPS och certifikat', html)
        self.assertIn('Säkerhetsheaders bedöms i en egen kategori', html)
        self.assertIn('Sidvikt och svarstid', html)
        self.assertNotIn('Prestanda (PageSpeed)', html)
        self.assertIn('PageSpeed API är inte konfigurerat på vår server.', html)
        self.assertIn('inte webbläsarens laddningstid', html)
        self.assertIn('Mobilanpassning (grundkontroll)', html)
        self.assertIn('Klickytornas storlek och faktisk textstorlek', html)
        self.assertIn('Grundkontroll godkänd.', html)
        self.assertIn('90/100', html)
        self.assertNotIn('Grundkontrollerna för mobil är uppfyllda', html)
        self.assertIn('0/100', html)                                   # säkerhetsheaders, inte "–"
        self.assertIn('4 CSS', html)
        self.assertIn('6 JS', html)
        self.assertIn('3 markerade som dekorativa', html)
        self.assertNotIn('saknar alt-text', html)
        self.assertIn('Hoppa till innehåll', html)
        self.assertIn('Bygger på 6 av 6 kategorier', html)
        self.assertNotIn('äldre version av analysverktyget', html)

        pdf = self.client.get(reverse('analysis_pdf', kwargs={'token': obj.id})).content.decode()
        self.assertIn('HTTPS och certifikat', pdf)
        self.assertIn('Sidvikt och svarstid', pdf)
        self.assertIn('Totalbetyget bygger på 6 av 6 kategorier', pdf)
        self.assertIn('3 markerade som dekorativa', pdf)
        self.assertIn('Grundkontroll godkänd.', pdf)

    def test_not_measured_is_shown_as_such(self):
        results, _ = self._collect()
        obj = self._save(results)
        SiteAnalysis.objects.filter(pk=obj.pk).update(score_headers=None, score_overall=66)
        results['headers'] = {'headers': [], 'score': None, 'error': 'Timeout'}
        results['scoring']['measured_count'] = 5
        results['scoring']['not_measured'] = ['headers']
        SiteAnalysis.objects.filter(pk=obj.pk).update(results=results)
        html = self.client.get(reverse('analysis_result', kwargs={'token': obj.id})).content.decode()
        self.assertIn('ej mätt', html)
        self.assertIn('Bygger på 5 av 6 kategorier', html)
        self.assertIn('räknas inte in', html)


class LegacyReportTests(TestCase):

    def _legacy(self):
        return SiteAnalysis.objects.create(
            url='https://enbloms.se/', domain='enbloms.se', status='complete', language='sv',
            analyzer_version=1,
            results={'http': {'is_https': True, 'response_time_ms': 442},
                     'performance': {'external_css': 0, 'external_js': 0, 'total_external_resources': 0,
                                     'images_total': 3, 'images_without_alt': 3},
                     'accessibility': {'images_without_alt': {'count': 0, 'total': 3}, 'score': 65,
                                       'landmarks': {'found': False}, 'skip_nav': {'found': False}},
                     'pagespeed': None, 'seo': {}, 'headers': {'headers': [], 'score': 0}},
            score_overall=61, score_security=100, score_seo=45, score_performance=80,
            score_mobile=60, score_headers=0, score_accessibility=65,
        )

    def test_default_version_for_existing_rows_is_1(self):
        obj = SiteAnalysis.objects.create(url='https://a.example/')
        self.assertEqual(obj.analyzer_version, 1)
        self.assertTrue(obj.is_legacy)

    def test_old_report_uses_v1_template_with_banner(self):
        obj = self._legacy()
        resp = self.client.get(reverse('analysis_result', kwargs={'token': obj.id}))
        self.assertTemplateUsed(resp, 'analysis/result_v1.html')
        html = resp.content.decode()
        self.assertIn('Den här rapporten skapades med en äldre version av analysverktyget', html)
        self.assertIn('Kör en ny analys', html)
        self.assertIn('?site=https%3A//enbloms.se/', html)

        pdf = self.client.get(reverse('analysis_pdf', kwargs={'token': obj.id}))
        self.assertTemplateUsed(pdf, 'analysis/report_pdf_v1.html')
        self.assertIn('Rapporten skapades med en äldre version av analysverktyget', pdf.content.decode())

    def test_cache_never_reuses_old_version(self):
        self._legacy()
        with patch('analysis.views._check_timestamp', return_value=True), \
             patch('analysis.views.start_analysis') as start, \
             patch('analysis.validators.socket.getaddrinfo', return_value=addrinfo('93.184.216.34')):
            resp = self.client.post(reverse('analysis'), {'url': 'https://enbloms.se/', 'form_token': 'x'})
        self.assertEqual(resp.status_code, 302)
        new = SiteAnalysis.objects.exclude(analyzer_version=1).get()
        self.assertEqual(new.analyzer_version, ANALYZER_VERSION)
        start.assert_called_once_with(str(new.id))

    def test_history_chart_uses_null_for_unmeasured(self):
        self._legacy()
        SiteAnalysis.objects.create(url='https://enbloms.se/', domain='enbloms.se', status='complete',
                                    analyzer_version=2, score_overall=70, score_headers=None, results={})
        resp = self.client.get(reverse('domain_history', kwargs={'domain': 'enbloms.se'}))
        headers = json.loads(resp.context['chart_headers'])
        self.assertEqual(sorted(headers, key=lambda v: (v is None, v)), [0, None])   # ej mätt → null, inte 0
        self.assertContains(resp, 'null')
        self.assertContains(resp, 'äldre version')
