import uuid
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.urls import reverse

from analysis.models import SiteAnalysis
from analysis.utils import build_brief_initial_from_analysis


def _make_analysis(**kwargs):
    defaults = dict(
        url='https://example.com',
        status='complete',
        score_overall=72,
        score_security=80,
        score_seo=65,
        score_performance=70,
        score_mobile=75,
        results={},
    )
    defaults.update(kwargs)
    return SiteAnalysis.objects.create(**defaults)


class BuildBriefInitialTests(TestCase):

    def test_score_below_60_gives_redo_needed(self):
        for score in (0, 30, 59):
            with self.subTest(score=score):
                analysis = _make_analysis(score_overall=score)
                initial = build_brief_initial_from_analysis(analysis)
                self.assertEqual(initial['has_existing_site'], 'redo_needed')

    def test_score_60_to_79_gives_unhappy(self):
        for score in (60, 72, 79):
            with self.subTest(score=score):
                analysis = _make_analysis(score_overall=score)
                initial = build_brief_initial_from_analysis(analysis)
                self.assertEqual(initial['has_existing_site'], 'unhappy')

    def test_score_80_plus_does_not_set_has_existing_site(self):
        for score in (80, 92, 100):
            with self.subTest(score=score):
                analysis = _make_analysis(score_overall=score)
                initial = build_brief_initial_from_analysis(analysis)
                self.assertNotIn('has_existing_site', initial)

    def test_goals_never_set(self):
        analysis = _make_analysis(score_overall=30)
        initial = build_brief_initial_from_analysis(analysis)
        self.assertNotIn('goals', initial)

    def test_notes_contains_url(self):
        analysis = _make_analysis(url='https://mysite.se')
        initial = build_brief_initial_from_analysis(analysis)
        self.assertIn('https://mysite.se', initial['notes'])

    def test_notes_contains_grade_and_score(self):
        analysis = _make_analysis(score_overall=72)
        initial = build_brief_initial_from_analysis(analysis)
        self.assertIn('72', initial['notes'])

    def test_notes_contains_category_scores(self):
        analysis = _make_analysis(
            score_security=88, score_seo=55,
            score_performance=62, score_mobile=71,
        )
        initial = build_brief_initial_from_analysis(analysis)
        self.assertIn('88', initial['notes'])
        self.assertIn('55', initial['notes'])

    def test_notes_contains_report_link(self):
        analysis = _make_analysis()
        initial = build_brief_initial_from_analysis(analysis)
        self.assertIn(str(analysis.id), initial['notes'])


class BriefFormGetTests(TestCase):

    def test_get_without_params_shows_empty_form(self):
        resp = self.client.get(reverse('brief'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'from_analysis')
        self.assertFalse(resp.context.get('from_analysis'))

    def test_get_with_ref_but_no_id_shows_empty_form(self):
        resp = self.client.get(reverse('brief') + '?ref=analysis')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context.get('from_analysis'))

    def test_get_with_invalid_uuid_shows_empty_form(self):
        resp = self.client.get(reverse('brief') + '?ref=analysis&analysis_id=not-a-uuid')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context.get('from_analysis'))

    def test_get_with_nonexistent_uuid_shows_empty_form(self):
        resp = self.client.get(
            reverse('brief') + f'?ref=analysis&analysis_id={uuid.uuid4()}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context.get('from_analysis'))

    def test_get_with_valid_analysis_shows_banner(self):
        analysis = _make_analysis()
        resp = self.client.get(
            reverse('brief') + f'?ref=analysis&analysis_id={analysis.id}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context.get('from_analysis'))
        self.assertContains(resp, analysis.url)
        self.assertContains(resp, 'Förifyllt från analys')

    def test_banner_contains_grade_and_score(self):
        analysis = _make_analysis(score_overall=72)
        resp = self.client.get(
            reverse('brief') + f'?ref=analysis&analysis_id={analysis.id}'
        )
        self.assertContains(resp, '72')

    def test_pending_analysis_not_used_for_prefill(self):
        analysis = _make_analysis(status='pending')
        resp = self.client.get(
            reverse('brief') + f'?ref=analysis&analysis_id={analysis.id}'
        )
        self.assertFalse(resp.context.get('from_analysis'))

    def test_notes_field_prefilled_in_form(self):
        analysis = _make_analysis(url='https://prefill-test.se')
        resp = self.client.get(
            reverse('brief') + f'?ref=analysis&analysis_id={analysis.id}'
        )
        self.assertContains(resp, 'prefill-test.se')

    def test_analysis_id_hidden_input_present(self):
        analysis = _make_analysis()
        resp = self.client.get(
            reverse('brief') + f'?ref=analysis&analysis_id={analysis.id}'
        )
        self.assertContains(resp, f'value="{analysis.id}"')


class BriefFormPostTests(TestCase):

    def _valid_post(self, extra=None):
        data = {
            'goals': ['leads'],
            'budget': '10k_20k',
            'timeline': '2_3_months',
            'has_existing_site': 'unhappy',
            'num_pages': '3-5',
            'features': ['startsida', 'kontakt'],
            'has_material': 'partial',
            'contact_name': 'Test Person',
            'contact_email': 'test@example.com',
            'website_url': '',   # honeypot empty
            'language': 'sv',    # hidden field required
            'referrer': '',      # hidden field optional
            'notes': '',
        }
        if extra:
            data.update(extra)
        return data

    def _post_with_token(self, url, data):
        from django.core import signing
        import time
        token = signing.dumps(int(time.time()) - 5)
        data['form_token'] = token
        with patch('brief.views._verify_turnstile', return_value=True):
            return self.client.post(url, data)

    def test_post_with_analysis_id_saves_referrer(self):
        from brief.models import ProjectBrief
        analysis = _make_analysis()
        data = self._valid_post({'analysis_id': str(analysis.id)})
        resp = self._post_with_token(reverse('brief'), data)
        self.assertEqual(resp.status_code, 302)
        brief = ProjectBrief.objects.latest('created_at')
        self.assertEqual(brief.referrer, f'analysis:{analysis.id}')

    def test_post_without_analysis_id_does_not_set_analysis_referrer(self):
        from brief.models import ProjectBrief
        data = self._valid_post()
        resp = self._post_with_token(reverse('brief'), data)
        self.assertEqual(resp.status_code, 302)
        brief = ProjectBrief.objects.latest('created_at')
        self.assertFalse(brief.referrer.startswith('analysis:'))
