"""
Läsbara feltexter (aldrig råa undantag eller klassnamn för läsaren) och varningen
när färre än hälften av de funna undersidorna kunde hämtas.
"""

import re

from bs4 import BeautifulSoup
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from analysis.models import SiteAnalysis
from analysis.report import coverage_warning, error_info, site_findings
from analysis.scoring import ANALYZER_VERSION, calculate_scores

from .helpers import NoNetworkMixin
from .test_site_rules import SITE, _collect, _site_web

# Felen från bmmab.se-rapporten (0d561c2b-…)
REMOTE_DISCONNECTED = ("Anslutningsfel: ConnectionError: ('Connection aborted.', "
                       "RemoteDisconnected('Remote end closed connection without response'))")
SAFE_POOL = ("Anslutningsfel: ConnectionError: _SafeHTTPSPool(host='example-site.se', port=443): Max retries "
             "exceeded with url: /x (Caused by NewConnectionError(\"_SafeHTTPSConnection(...): Kunde inte ansluta\"))")
RAW_MARKERS = ('RemoteDisconnected', '_SafeHTTPSPool', 'Connection aborted', 'NewConnectionError',
               'Max retries', 'ConnectionError:')


def _bmmab_like_web():
    """Startsida + 5 undersidor, varav bara en kunde hämtas – som bmmab.se."""
    web = _site_web()
    html = web.pages[SITE + 'tjanster']
    start = web.pages[SITE][2].decode().replace(
        '<a href="/finns-inte">Gammal länk</a>',
        '<a href="/finns-inte">Gammal länk</a><a href="/projekt">Projekt</a>')
    web.pages[SITE] = (200, web.pages[SITE][1], start.encode())
    web.pages[SITE + 'tjanster'] = html
    web.pages[SITE + 'om-oss'] = ('error', 'connection', REMOTE_DISCONNECTED)
    web.pages[SITE + 'kontakt'] = ('error', 'connection', SAFE_POOL)
    web.pages[SITE + 'projekt'] = ('error', 'host_unavailable', 'example-site.se slutade svara – inga fler anrop')
    # /finns-inte saknas → 404
    return web


class ErrorInfoTests(SimpleTestCase):

    def test_connection_errors_get_plain_text(self):
        for kind in ('connection', 'timeout'):
            e = error_info(REMOTE_DISCONNECTED, kind)
            self.assertEqual(e['text'], 'Sidan svarade inte vid kontrollen')
            self.assertNotIn('RemoteDisconnected', e['text'] + e['kind_label'])

    def test_each_kind(self):
        self.assertEqual(error_info('x', 'host_unavailable')['text'], 'Inte kontrollerad – servern slutade svara')
        self.assertEqual(error_info('x', 'ssl')['text'], 'Säker anslutning (SSL) kunde inte upprättas')
        self.assertEqual(error_info('x', 'blocked')['text'], 'Adressen kunde inte kontrolleras')
        self.assertEqual(error_info('x', 'too_large')['text'], 'Sidan är för stor för att kontrolleras (över 2 MB)')
        self.assertEqual(error_info('x', 'something-new')['text'], 'Sidan kunde inte kontrolleras')

    def test_http_status_texts(self):
        self.assertEqual(error_info('HTTP 404', 'http', 404)['text'], 'Sidan svarade med felkod 404 (sidan finns inte)')
        self.assertEqual(error_info('HTTP 403', 'http', 403)['text'], 'Sidan svarade med felkod 403 (åtkomst nekad)')
        self.assertEqual(error_info('HTTP 502', 'http', 502)['text'], 'Sidan svarade med felkod 502 (fel på servern)')
        self.assertEqual(error_info('HTTP 404', 'http', 404, 'en')['text'],
                         'The page responded with error code 404 (page not found)')

    def test_old_reports_without_error_kind(self):
        """Rapporter före error_kind (t.ex. bmmab.se 0d561c2b) har bara texten sparad."""
        self.assertEqual(error_info("Anslutningsfel: _SafeHTTPSPool(host='bmmab.se', port=443): …")['text'],
                         'Sidan svarade inte vid kontrollen')
        self.assertEqual(error_info('HTTP 404')['text'], 'Sidan svarade med felkod 404 (sidan finns inte)')
        self.assertEqual(error_info('Timeout')['kind'], 'timeout')
        self.assertEqual(error_info('något helt annat')['text'], 'Sidan kunde inte kontrolleras')


@override_settings(PAGESPEED_API_KEY='')
class ReadableErrorRenderingTests(NoNetworkMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.r = _collect(_bmmab_like_web())
        scores = self.r.pop('scores')
        self.obj = SiteAnalysis.objects.create(
            url=SITE, domain='example-site.se', status='complete', results=self.r,
            analyzer_version=ANALYZER_VERSION, language='sv', **{f'score_{k}': v for k, v in scores.items()})

    def _html(self, name, query=''):
        return self.client.get(reverse(name, kwargs={'token': self.obj.id}) + query).content.decode()

    @staticmethod
    def _without_tech(html):
        soup = BeautifulSoup(html, 'lxml')
        for el in soup.select('.tech-only'):
            el.decompose()
        return soup.get_text(' ')

    def test_errors_are_stored_with_kind(self):
        kinds = {p['url'].rsplit('/', 1)[1]: p.get('error_kind') for p in self.r['pages'] if p.get('error')}
        self.assertEqual(kinds, {'om-oss': 'connection', 'kontakt': 'connection',
                                 'projekt': 'host_unavailable', 'finns-inte': 'http'})

    def test_regular_report_shows_plain_text_and_raw_only_in_technical_view(self):
        html = self._html('analysis_result')
        visible = self._without_tech(html)
        self.assertEqual(visible.count('Sidan svarade inte vid kontrollen'), 2)
        self.assertIn('Inte kontrollerad – servern slutade svara', visible)
        self.assertIn('Sidan svarade med felkod 404 (sidan finns inte)', visible)
        for marker in RAW_MARKERS:
            self.assertNotIn(marker, visible, marker)
        self.assertIn('RemoteDisconnected', html)                 # finns bara i teknisk vy

    def test_shared_view_never_shows_raw_exceptions_even_in_technical_view(self):
        html = self._html('analysis_shared')
        for marker in RAW_MARKERS:
            self.assertNotIn(marker, html, marker)
        self.assertIn('Sidan svarade inte vid kontrollen', html)
        # teknisk vy i delningsvyn: bara feltypen
        tech_texts = [el.get_text(strip=True) for el in BeautifulSoup(html, 'lxml').select('.tech-only')]
        self.assertIn('Anslutningsfel', tech_texts)
        self.assertIn('Servern slutade svara', tech_texts)

    def test_pdfs_never_show_raw_exceptions(self):
        for query in ('', '?delad=1'):
            html = self._html('analysis_pdf', query)
            for marker in RAW_MARKERS:
                self.assertNotIn(marker, html, f'{query} {marker}')

    def test_start_page_errors_are_readable(self):
        r = dict(self.r)
        r['http'] = dict(r['http'], status_code=None, ok=False, error=REMOTE_DISCONNECTED, error_kind='connection')
        r['ssl'] = {'valid': False, 'error': "Ogiltigt certifikat: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"}
        r['headers'] = {'headers': [], 'score': None, 'error': REMOTE_DISCONNECTED}
        r['html_fetch_error'], r['html_fetch_error_kind'] = REMOTE_DISCONNECTED, 'connection'
        SiteAnalysis.objects.filter(pk=self.obj.pk).update(results=r)
        for name in ('analysis_result', 'analysis_shared'):
            html = self._html(name)
            visible = self._without_tech(html)
            self.assertIn('Sidan svarade inte vid kontrollen', visible)
            self.assertIn('Certifikatet är ogiltigt', visible)
            self.assertNotIn('CERTIFICATE_VERIFY_FAILED', visible)
            for marker in RAW_MARKERS:
                self.assertNotIn(marker, visible, f'{name} {marker}')
        shared = self._html('analysis_shared')
        self.assertNotIn('CERTIFICATE_VERIFY_FAILED', shared)
        self.assertNotIn('RemoteDisconnected', shared)
        pdf = self._html('analysis_pdf')
        self.assertNotIn('CERTIFICATE_VERIFY_FAILED', pdf)
        self.assertNotIn('RemoteDisconnected', pdf)


class CoverageWarningTests(SimpleTestCase):

    def _r(self, ok, failed):
        pages = [{'url': f'{SITE}ok-{i}', 'seo': {'title': {'found': True}}} for i in range(ok)]
        pages += [{'url': f'{SITE}fel-{i}', 'error': 'x', 'error_kind': 'connection'} for i in range(failed)]
        return {'seo': {'title': {'found': True}}, 'pages': pages, 'http': {'final_url': SITE}}

    def test_thresholds(self):
        self.assertEqual(coverage_warning(self._r(1, 4))['text'],
                         'Genomgången bygger på färre sidor än vanligt: 1 av 5 undersidor kunde hämtas. '
                         'SEO-poängen och fynden är därför osäkrare än vanligt.')
        self.assertEqual(coverage_warning(self._r(0, 1))['text'][:72],
                         'Genomgången bygger på färre sidor än vanligt: 0 av 1 undersida kunde häm')
        self.assertIsNotNone(coverage_warning(self._r(2, 3)))      # 2 av 5 – färre än hälften
        self.assertIsNone(coverage_warning(self._r(3, 3)))         # 3 av 6 – exakt hälften
        self.assertIsNone(coverage_warning(self._r(1, 0)))
        self.assertIsNone(coverage_warning(self._r(0, 0)))         # inga undersidor hittades

    def test_warning_does_not_change_findings_or_scores(self):
        r = self._r(1, 4)
        r['seo'] = {'title': {'found': False}, 'meta_description': {'found': False}}
        r['pages'][0]['seo'] = {'title': {'found': True}, 'meta_description': {'found': False}}
        before = [(f['key'], f['severity']) for f in site_findings(r)]
        self.assertIsNotNone(coverage_warning(r))
        self.assertEqual([(f['key'], f['severity']) for f in site_findings(r)], before)
        self.assertNotIn('coverage', [f['key'] for f in site_findings(r)])


@override_settings(PAGESPEED_API_KEY='')
class CoverageRenderingTests(NoNetworkMixin, TestCase):

    def test_warning_shown_first_without_affecting_order(self):
        r = _collect(_bmmab_like_web())
        scores = r.pop('scores')
        self.assertEqual(scores, calculate_scores(r) | {'overall': scores['overall']})
        obj = SiteAnalysis.objects.create(url=SITE, domain='example-site.se', status='complete', results=r,
                                          analyzer_version=ANALYZER_VERSION, language='sv',
                                          **{f'score_{k}': v for k, v in scores.items()})
        text = 'Genomgången bygger på färre sidor än vanligt: 1 av 5 undersidor kunde hämtas.'
        for name, query in (('analysis_result', ''), ('analysis_shared', ''), ('analysis_pdf', ''),
                            ('analysis_pdf', '?delad=1')):
            with self.subTest(view=name + query):
                html = self.client.get(reverse(name, kwargs={'token': obj.id}) + query).content.decode()
                self.assertIn(text, html)
        html = self.client.get(reverse('analysis_result', kwargs={'token': obj.id})).content.decode()
        self.assertIn('osäker – få sidor kunde hämtas', html)
        soup = BeautifulSoup(html, 'lxml')
        first = soup.select_one('ul.list-unstyled.d-flex li')
        self.assertTrue(first.has_attr('data-coverage-warning'))
        badges = [b.get_text(strip=True) for b in soup.select('ul.list-unstyled.d-flex li .action-badge')]
        self.assertEqual(badges[0], 'INFO')
        # resten av listan är sorterad som tidigare: KRITISK före HÖG före MEDEL
        order = {'KRITISK': 0, 'HÖG': 1, 'MEDEL': 2}
        rest = [order[b] for b in badges[1:] if b in order]
        self.assertEqual(rest, sorted(rest))


TRACEBACK = ('Traceback (most recent call last):\n  File "/app/analysis/tasks.py", line 120, in run_analysis\n'
             "requests.exceptions.ConnectionError: _SafeHTTPSPool(host='a.se', port=443): Max retries exceeded")


class FailedAnalysisTests(TestCase):

    def test_error_page_and_status_json_never_show_traceback(self):
        obj = SiteAnalysis.objects.create(url=SITE, status='error', analyzer_version=ANALYZER_VERSION,
                                          error_message=TRACEBACK)
        html = self.client.get(reverse('analysis_result', kwargs={'token': obj.id})).content.decode()
        self.assertIn('Ett oväntat fel uppstod under analysen. Försök igen om en stund.', html)
        for marker in ('Traceback', 'tasks.py', '_SafeHTTPSPool', 'Tekniska detaljer'):
            self.assertNotIn(marker, html)
        data = self.client.get(reverse('analysis_status_json', kwargs={'token': obj.id})).json()
        self.assertEqual(data['error_message'], 'Ett oväntat fel uppstod under analysen. Försök igen om en stund.')
        obj.refresh_from_db()
        self.assertIn('Traceback', obj.error_message)               # finns kvar för admin

    def test_validation_message_is_shown_readably(self):
        obj = SiteAnalysis.objects.create(url=SITE, status='error', analyzer_version=ANALYZER_VERSION,
                                          error_message="['Privata, interna eller reserverade IP-adresser tillåts inte.']")
        self.assertEqual(obj.public_error_message, 'Privata, interna eller reserverade IP-adresser tillåts inte.')

    def test_v1_report_shows_readable_errors(self):
        obj = SiteAnalysis.objects.create(
            url='https://bmmab.se/', status='complete', analyzer_version=1, language='sv', score_overall=70,
            results={'http': {'is_https': True, 'error': REMOTE_DISCONNECTED},
                     'ssl': {'valid': False, 'error': 'Ogiltigt certifikat: [SSL: CERTIFICATE_VERIFY_FAILED]'},
                     'headers': {'headers': [{'found': False, 'label': 'HSTS', 'points': 30}], 'error': SAFE_POOL},
                     'pages': [{'url': 'https://bmmab.se/vara-tjanster', 'error': REMOTE_DISCONNECTED}],
                     'seo': {}, 'performance': {}, 'accessibility': {}, 'pagespeed': None})
        for name in ('analysis_result', 'analysis_pdf'):
            html = self.client.get(reverse(name, kwargs={'token': obj.id})).content.decode()
            for marker in RAW_MARKERS + ('CERTIFICATE_VERIFY_FAILED',):
                self.assertNotIn(marker, html, f'{name} {marker}')
        html = self.client.get(reverse('analysis_result', kwargs={'token': obj.id})).content.decode()
        self.assertIn('Sidan svarade inte vid kontrollen', html)
        self.assertIn('Certifikatet är ogiltigt', html)
