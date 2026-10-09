"""
v3-reglerna: SEO över alla kontrollerade sidor (startsidan 40 %, undersidornas
medel 60 %), PageSpeed viktat mot mobil (70/30), tekniska adresser hoppas över
och bilder med okänd storlek visas som "kunde inte mätas".
"""

import re
from contextlib import ExitStack
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from analysis.checks.performance import check_performance
from analysis.models import SiteAnalysis
from analysis.report import category_measures, pagespeed_summary, site_findings
from analysis.scoring import ANALYZER_VERSION, calculate_scores, pagespeed_breakdown, seo_breakdown
from analysis.tasks import collect_results

from .helpers import FakeWeb, NoNetworkMixin, fixture_bytes, soup_from

SITE = 'https://example-site.se/'


def _site_web():
    html = {'Content-Type': 'text/html; charset=utf-8'}
    return FakeWeb({
        SITE: (200, html, fixture_bytes('site_start.html')),
        SITE + 'tjanster': (200, html, fixture_bytes('site_sub_good.html')),
        SITE + 'om-oss': (200, html, fixture_bytes('site_sub_nodesc.html')),
        SITE + 'kontakt': (200, html, fixture_bytes('site_sub_noh1.html')),
        SITE + 'robots.txt': (200, {}, b'User-agent: *\nSitemap: https://example-site.se/sitemap.xml'),
        SITE + 'sitemap.xml': (200, {}, b'<urlset/>'),
        # /finns-inte saknas i ordboken → 404, en riktig trasig länk
    })


def _collect(web, pagespeed=None):
    with ExitStack() as stack:
        for p in web.patches():
            stack.enter_context(p)
        stack.enter_context(patch('analysis.tasks.check_ssl', return_value={'valid': True}))
        if pagespeed is not None:
            stack.enter_context(patch('analysis.tasks.check_pagespeed', return_value=pagespeed))
        return collect_results(SITE)


@override_settings(PAGESPEED_API_KEY='')
class SiteWideSeoTests(NoNetworkMixin, SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.web = _site_web()
        self.r = _collect(self.web)

    def test_technical_addresses_are_skipped_not_errors(self):
        skipped = {s['url']: s['reason'] for s in self.r['pages_skipped']}
        self.assertEqual(skipped['https://example-site.se/cdn-cgi/l/email-protection'], 'technical')
        self.assertEqual(skipped['https://example-site.se/wp-admin/'], 'technical')
        self.assertEqual(skipped['https://example-site.se/broschyr.pdf'], 'file')
        self.assertEqual(skipped['https://example-site.se/?replytocom=5'], 'technical')
        self.assertEqual(skipped['http://www.example-site.se/'], 'duplicate')
        self.assertEqual(len(self.r['pages_skipped']), len(skipped))   # varje adress listas en gång
        # inget av dem hämtades, och inget visas som sidfel
        for url in skipped:
            self.assertNotIn(url.rstrip('/'), [u.rstrip('/') for u in self.web.requested])
        errors = [p['url'] for p in self.r['pages'] if p.get('error')]
        self.assertEqual(errors, ['https://example-site.se/finns-inte'])   # riktig 404 visas fortfarande
        self.assertNoNetwork()

    def test_duplicate_subpage_links_are_checked_once(self):
        urls = [p['url'] for p in self.r['pages']]
        self.assertEqual(urls.count('https://example-site.se/tjanster'), 1)
        self.assertEqual(sorted(urls), sorted([
            'https://example-site.se/tjanster', 'https://example-site.se/om-oss',
            'https://example-site.se/kontakt', 'https://example-site.se/finns-inte']))

    def test_seo_score_is_40_percent_home_60_percent_subpages(self):
        b = self.r['seo_breakdown']
        self.assertEqual(b['site'], 15)
        self.assertEqual(b['start'], 85)
        self.assertEqual(b['subpages_count'], 3)                       # 404-sidan räknas inte
        self.assertEqual(b['subpages_mean'], round((85 + 65 + 70) / 3, 1))
        expected = round(15 + 0.4 * 85 + 0.6 * (85 + 65 + 70) / 3)
        self.assertEqual(self.r['scores']['seo'], expected)
        self.assertLess(self.r['scores']['seo'], 100)                   # startsidan ensam hade gett 100

    def test_findings_count_pages_checked(self):
        f = {x['key']: x for x in site_findings(self.r)}
        self.assertEqual(f['desc_missing']['text'],
                         'Metabeskrivning saknas på 1 av de 4 sidor som kontrollerades')
        self.assertEqual(f['desc_missing']['pages'], ['https://example-site.se/om-oss'])
        self.assertEqual(f['h1_missing']['text'], 'H1-rubrik saknas på 1 av de 4 sidor som kontrollerades')
        self.assertEqual(f['h1_missing']['pages'], ['https://example-site.se/kontakt'])
        self.assertEqual(f['alt_missing']['text'],
                         '1 bild utan alt-attribut på 1 av de 4 sidor som kontrollerades')
        self.assertNotIn('title_missing', f)
        self.assertEqual(site_findings(self.r, 'en')[0]['text'],
                         'Meta description missing on 1 of the 4 pages checked')

    def test_seo_explanation_names_weights_and_page_count(self):
        text = category_measures('seo', self.r)
        self.assertIn('startsidan (40 %)', text)
        self.assertIn('på 3 undersidor (60 %, medelvärde)', text)


@override_settings(PAGESPEED_API_KEY='')
class HomePageOnlyTests(NoNetworkMixin, SimpleTestCase):

    def test_without_subpages_seo_equals_home_page(self):
        r = {'seo': soup_seo('site_sub_nodesc.html'), 'pages': [],
             'http': {'final_url': SITE}}
        r['seo'].update({'robots_txt': {'found': True}, 'sitemap': {'found': False}})
        b = seo_breakdown(r)
        self.assertEqual(b['subpages_count'], 0)
        self.assertEqual(b['score'], 10 + 65)
        self.assertEqual(site_findings(r)[0]['text'],
                         'Metabeskrivning saknas på startsidan, den enda sida som kontrollerades')


def soup_seo(name):
    from analysis.checks.seo import check_seo_page
    return check_seo_page(soup_from(name))


class PageSpeedWeightingTests(SimpleTestCase):

    def _r(self, mobile, desktop):
        return {'pagespeed': {'status': 'ok', 'mobile': {'score': mobile}, 'desktop': {'score': desktop}},
                'seo': {}, 'http': {}}

    def test_mobile_weighs_70_percent(self):
        self.assertEqual(pagespeed_breakdown(self._r(78, 93))['score'], round(0.7 * 78 + 0.3 * 93))
        # 0,7 × 78 + 0,3 × 93 = 82,5 → 82 (Pythons round, samma som övrig poängberäkning)
        self.assertEqual(calculate_scores(self._r(78, 93))['performance'], 82)

    def test_weakest_is_named_when_difference_is_at_least_5(self):
        s = pagespeed_summary(self._r(78, 93))
        self.assertEqual(s['weakest'], 'mobile')
        self.assertEqual(s['weakest_text'], 'Mobil (78) drar ned resultatet')
        self.assertIsNone(pagespeed_summary(self._r(76, 79))['weakest'])

    def test_only_one_strategy_measured(self):
        r = {'pagespeed': {'status': 'partial', 'mobile': {'error_kind': 'timeout'}, 'desktop': {'score': 90}}}
        b = pagespeed_breakdown(r)
        self.assertEqual((b['score'], b['mobile'], b['weakest']), (90, None, None))


class ImageSizeTests(NoNetworkMixin, SimpleTestCase):

    def test_unknown_sizes_are_counted_separately(self):
        soup = soup_from('images_alt.html')
        web = FakeWeb({'https://example.com/a.jpg': (200, {'Content-Length': '1000'}, b'')})
        with patch('analysis.checks.performance.safe_request', side_effect=web.safe_request):
            perf = check_performance('https://example.com/', soup)
        self.assertEqual(perf['images_considered'], 8)
        self.assertEqual(perf['images_checked_for_size'], 1)
        self.assertEqual(perf['images_size_unknown'], 7)    # 404 eller ingen Content-Length
        self.assertEqual(perf['images_not_checked'], 0)
        self.assertNoNetwork()

    def test_more_than_20_images_are_reported_as_not_checked(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(''.join(f'<img src="/{i}.jpg" alt="">' for i in range(25)), 'lxml')
        web = FakeWeb({})
        with patch('analysis.checks.performance.safe_request', side_effect=web.safe_request):
            perf = check_performance('https://example.com/', soup)
        self.assertEqual((perf['images_considered'], perf['images_not_checked']), (25, 5))
        self.assertEqual(len(web.requested), 20)


@override_settings(PAGESPEED_API_KEY='')
class ReportRenderingTests(NoNetworkMixin, TestCase):

    def _save(self, results, version=ANALYZER_VERSION):
        scores = results.pop('scores')
        return SiteAnalysis.objects.create(
            url=SITE, domain='example-site.se', status='complete', results=results,
            analyzer_version=version, language='sv',
            **{f'score_{k}': v for k, v in scores.items()})

    def _image_row(self, html):
        i = html.index('Bildernas filstorlek')
        row_start = html.rindex('<li', 0, i)
        return html[row_start:html.index('</li>', i)]

    def test_report_shows_site_findings_mobile_desktop_and_server_tag(self):
        psp = {'status': 'ok', 'mobile': {'score': 61}, 'desktop': {'score': 92}}
        r = _collect(_site_web(), pagespeed=psp)
        r['performance'].update(images_checked_for_size=1, images_size_unknown=2, images_large=0)
        obj = self._save(r)
        html = self.client.get(reverse('analysis_result', kwargs={'token': obj.id})).content.decode()

        self.assertIn('Metabeskrivning saknas på 1 av de 4 sidor som kontrollerades', html)
        self.assertIn('https://example-site.se/om-oss', html)          # listan över sidor
        self.assertRegex(html, r'mobil\s*<strong class="text-light">61</strong>')
        self.assertRegex(html, r'dator\s*<strong class="text-light">92</strong>')
        self.assertIn('Mobil (61) drar ned resultatet', html)
        self.assertIn('Mobil väger 70 % och dator 30 %', html)
        self.assertEqual(obj.score_performance, round(0.7 * 61 + 0.3 * 92))
        self.assertIn('kräver serverinställning (ofta hos webbhotellet)', html)
        self.assertIn('/cdn-cgi/l/email-protection', html)              # listad som överhoppad …
        self.assertIn('teknisk adress', html)
        self.assertNotIn('cdn-cgi/l/email-protection — fel', html)      # … aldrig som sidfel

        row = self._image_row(html)
        self.assertIn('2 kunde inte mätas', row)
        self.assertNotIn('fa-check-circle', row)                        # aldrig godkänd

        pdf = self.client.get(reverse('analysis_pdf', kwargs={'token': obj.id})).content.decode()
        self.assertIn('Metabeskrivning saknas på 1 av de 4 sidor som kontrollerades', pdf)
        self.assertIn('mobil 61 · dator 92', pdf)
        self.assertIn('2 kunde inte mätas', pdf)
        self.assertIn('kräver serverinställning', pdf)

    def test_headers_tag_does_not_change_score(self):
        r = _collect(_site_web())
        self.assertEqual(r['scores']['headers'], 0)
        obj = self._save(r)
        html = self.client.get(reverse('analysis_result', kwargs={'token': obj.id})).content.decode()
        self.assertRegex(html, r'kräver serverinställning \(ofta hos webbhotellet\)</span>\s*'
                               r'<span class="ms-auto text-secondary small fw-semibold">0/100')

    def test_v2_report_keeps_its_old_method_description(self):
        """Rapporter från v2 räknades med startsidan och medel av mobil/dator – texten ska säga det."""
        psp = {'status': 'ok', 'mobile': {'score': 61}, 'desktop': {'score': 92}}
        r = _collect(_site_web(), pagespeed=psp)
        r['analyzer_version'] = 2
        obj = self._save(r, version=2)
        self.assertFalse(obj.is_legacy)
        self.assertTrue(obj.is_outdated)
        html = self.client.get(reverse('analysis_result', kwargs={'token': obj.id})).content.decode()
        self.assertIn('medelvärde av mobil och dator', html)
        self.assertNotIn('Mobil väger 70 %', html)
        self.assertNotIn('startsidan (40 %)', html)
