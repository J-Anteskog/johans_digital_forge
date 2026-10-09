"""Delningsvyn: fynd och mätvärden utan betyg, totalpoäng eller säljtext – och noindex."""

from contextlib import ExitStack
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from analysis.models import SiteAnalysis
from analysis.scoring import ANALYZER_VERSION
from analysis.tasks import collect_results

from .helpers import NoNetworkMixin
from .test_pipeline import BASE, _enbloms_web

# Text som bara får finnas i den vanliga rapporten
SALES_AND_GRADE_TEXT = [
    'Sammanlagt betyg',
    'Bygger på 6 av 6 kategorier',
    'Totalbetyget bygger på',
    'Din väg till betyg A',
    'Vägen till betyg A',
    'betyg A kräver',
    'Begär kostnadsfri offert',
    'Begär offert',
    'offertbrief',
    'Vill du att Johan',
    'Få en handlingsplan i din inkorg',
    'optin-form',
    'du missar potentiella kunder',
    'mer sårbar för attacker',
    'Visa historik',
]


@override_settings(PAGESPEED_API_KEY='')
class SharedViewTests(NoNetworkMixin, TestCase):

    def setUp(self):
        super().setUp()
        web = _enbloms_web()
        with ExitStack() as stack:
            for p in web.patches():
                stack.enter_context(p)
            stack.enter_context(patch('analysis.tasks.check_ssl', return_value={
                'valid': True, 'expiry_date': '2026-12-17', 'days_remaining': 68, 'expires_soon': False}))
            results = collect_results(BASE)
        scores = results.pop('scores')
        self.obj = SiteAnalysis.objects.create(
            url=BASE, domain='enbloms.example', status='complete', results=results,
            analyzer_version=ANALYZER_VERSION, language='sv',
            score_overall=scores['overall'], score_security=scores['security'], score_seo=scores['seo'],
            score_performance=scores['performance'], score_mobile=scores['mobile'],
            score_headers=scores['headers'], score_accessibility=scores['accessibility'],
        )
        self.assertNoNetwork()

    def _get(self, name, query=''):
        return self.client.get(reverse(name, kwargs={'token': self.obj.id}) + query)

    def test_shared_view_has_findings_but_no_grade_or_sales(self):
        resp = self._get('analysis_shared')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'analysis/shared.html')
        html = resp.content.decode()
        for text in SALES_AND_GRADE_TEXT:
            self.assertNotIn(text, html, text)
        self.assertNotIn('grade-badge', html)
        self.assertNotIn(f'>{self.obj.grade}<', html)            # bokstavsbetyget
        self.assertNotIn(f'{self.obj.score_overall}<small', html)  # totalpoängen
        # fynd, kategorier, förklaringar och poäng per kategori finns kvar
        self.assertIn('HTTPS och certifikat', html)
        self.assertIn('Sidvikt och svarstid', html)
        self.assertIn('Mäter att sidan serveras via HTTPS', html)
        self.assertIn('4 CSS', html)
        self.assertIn('Hoppa till innehåll', html)
        self.assertIn('Metabeskrivning saknas på startsidan, den enda sida som kontrollerades', html)
        self.assertIn('Rapport från Johans Digital Forge, johans-digital-forge.se', html)

    def test_shared_view_does_not_touch_tracking_fields(self):
        self._get('analysis_shared')
        self.obj.refresh_from_db()
        self.assertFalse(self.obj.email_form_shown)

    def test_regular_report_links_to_shared_view(self):
        html = self._get('analysis_result').content.decode()
        self.assertIn(reverse('analysis_shared', kwargs={'token': self.obj.id}), html)
        self.assertIn('Dela utan betyg', html)
        self.assertIn('Sammanlagt betyg', html)   # den vanliga rapporten är oförändrad

    def test_new_meta_description_wording_in_regular_report(self):
        html = self._get('analysis_result').content.decode()
        self.assertIn('ingen egen beskrivning är satt, så Google väljer själv', html)
        self.assertNotIn('Google saknar text att visa', html)

    def test_shared_pdf_has_no_grade_or_sales(self):
        resp = self._get('analysis_pdf', '?delad=1')
        self.assertTemplateUsed(resp, 'analysis/report_pdf.html')
        html = resp.content.decode()
        for text in SALES_AND_GRADE_TEXT:
            self.assertNotIn(text, html, text)
        self.assertNotIn('grade-circle bg-', html)
        self.assertIn('Rapport från Johans Digital Forge, johans-digital-forge.se', html)
        self.assertIn('HTTPS och certifikat', html)

    def test_regular_pdf_unchanged(self):
        html = self._get('analysis_pdf').content.decode()
        self.assertIn('Sammanlagt betyg', html)
        self.assertIn('Vägen till betyg A', html)

    def test_noindex_header_and_meta_everywhere(self):
        urls = [
            reverse('analysis_shared', kwargs={'token': self.obj.id}),
            reverse('analysis_result', kwargs={'token': self.obj.id}),
            reverse('analysis_pdf', kwargs={'token': self.obj.id}),
            reverse('analysis_pdf', kwargs={'token': self.obj.id}) + '?delad=1',
            reverse('domain_history', kwargs={'domain': 'enbloms.example'}),
        ]
        for url in urls:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp['X-Robots-Tag'], 'noindex, nofollow')
                self.assertContains(resp, '<meta name="robots" content="noindex, nofollow">')


class SharedViewStatusTests(TestCase):

    def test_legacy_report_gives_clear_message(self):
        obj = SiteAnalysis.objects.create(
            url='https://enbloms.se/', status='complete', analyzer_version=1, language='sv',
            results={'http': {'is_https': True}}, score_overall=61)
        for url in (reverse('analysis_shared', kwargs={'token': obj.id}),
                    reverse('analysis_pdf', kwargs={'token': obj.id}) + '?delad=1'):
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertTemplateUsed(resp, 'analysis/shared_unavailable.html')
                self.assertContains(resp, 'Rapporten kan inte visas i delningsvyn')
                self.assertContains(resp, 'äldre version av analysverktyget')
                self.assertNotContains(resp, '61')
                self.assertEqual(resp['X-Robots-Tag'], 'noindex, nofollow')

    def test_running_and_failed(self):
        running = SiteAnalysis.objects.create(url='https://a.example/', status='running', analyzer_version=2)
        failed = SiteAnalysis.objects.create(url='https://b.example/', status='error', analyzer_version=2)
        self.assertContains(self.client.get(reverse('analysis_shared', kwargs={'token': running.id})),
                            'Rapporten är inte klar ännu')
        self.assertContains(self.client.get(reverse('analysis_shared', kwargs={'token': failed.id})),
                            'Analysen kunde inte genomföras')

    def test_pending_page_has_noindex(self):
        obj = SiteAnalysis.objects.create(url='https://a.example/', status='running', analyzer_version=2)
        resp = self.client.get(reverse('analysis_result', kwargs={'token': obj.id}))
        self.assertEqual(resp['X-Robots-Tag'], 'noindex, nofollow')
        self.assertContains(resp, '<meta name="robots" content="noindex, nofollow">')
