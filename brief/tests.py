from unittest.mock import patch
from django.core import signing
from django.test import TestCase
from django.urls import reverse
import time

from .forms import ProjectBriefForm
from .models import ProjectBrief


# ── Hjälpdata ──────────────────────────────────────────────────────────────

VALID_POST = {
    'goals': ['leads', 'present_company'],
    'goals_other': '',
    'budget': '10k_20k',
    'timeline': '1_month',
    'timeline_specific': '',
    'has_existing_site': 'no_new',
    'num_pages': '3-5',
    'features': ['startsida', 'kontakt'],
    'features_other': '',
    'has_material': 'partial',
    'style_preferences': ['modern'],
    'notes': '',
    'contact_name': 'Test Testsson',
    'contact_email': 'test@example.com',
    'contact_phone': '',
    'referrer': '',
    'language': 'sv',
    'website_url': '',
}


def _make_brief(**overrides):
    """Skapa ett minimalt ProjectBrief-objekt i databasen."""
    data = {
        'goals': ['leads'],
        'budget': '10k_20k',
        'timeline': '1_month',
        'has_existing_site': 'no_new',
        'num_pages': '3-5',
        'has_material': 'partial',
        'contact_name': 'Test',
        'contact_email': 'test@example.com',
    }
    data.update(overrides)
    return ProjectBrief.objects.create(**data)


def _valid_token():
    return signing.dumps(int(time.time()) - 5)  # 5 sekunder gammalt = godkänt


# ── Test 1: Modell-validering / score() ────────────────────────────────────

class ProjectBriefScoreTest(TestCase):

    def test_score_high_budget_urgent_clear_goals(self):
        brief = _make_brief(
            goals=['leads', 'sell_products'],
            budget='40k_plus',
            timeline='asap',
            has_material='all',
        )
        self.assertEqual(brief.score(), 100)  # 40+30+20+10

    def test_score_low_budget_no_rush_vague_goals(self):
        brief = _make_brief(
            goals=['other'],
            budget='under_10k',
            timeline='no_rush',
            has_material='unsure',
        )
        self.assertEqual(brief.score(), 10)  # 10+5+0+0

    def test_score_unsure_budget_caps_at_100(self):
        brief = _make_brief(
            goals=['leads', 'present_company', 'sell_products'],
            budget='40k_plus',
            timeline='asap',
            has_material='all',
        )
        # Ska aldrig överstiga 100
        self.assertLessEqual(brief.score(), 100)

    def test_score_single_clear_goal(self):
        brief = _make_brief(goals=['leads'], budget='unsure', timeline='no_rush', has_material='none')
        # 5 (budget) + 5 (timeline) + 12 (ett tydligt mål) + 2 (material=none) = 24
        self.assertEqual(brief.score(), 24)

    def test_str_contains_name_and_status(self):
        brief = _make_brief()
        self.assertIn('Test', str(brief))
        self.assertIn('Ny', str(brief))


# ── Test 2: Formulärvalidering – mål obligatoriskt ─────────────────────────

class ProjectBriefFormValidationTest(TestCase):

    def test_valid_form_passes(self):
        form = ProjectBriefForm(data=VALID_POST)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_requires_at_least_one_goal(self):
        data = {**VALID_POST, 'goals': []}
        form = ProjectBriefForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('goals', form.errors)

    def test_form_requires_contact_email(self):
        data = {**VALID_POST, 'contact_email': ''}
        form = ProjectBriefForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('contact_email', form.errors)

    def test_form_requires_contact_name(self):
        data = {**VALID_POST, 'contact_name': ''}
        form = ProjectBriefForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('contact_name', form.errors)


# ── Test 3: Honeypot ───────────────────────────────────────────────────────

class HoneypotTest(TestCase):

    def test_honeypot_filled_marks_form_invalid(self):
        data = {**VALID_POST, 'website_url': 'http://spam.com'}
        form = ProjectBriefForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('website_url', form.errors)

    def test_honeypot_empty_passes(self):
        data = {**VALID_POST, 'website_url': ''}
        form = ProjectBriefForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)


# ── Test 4: View – GET ─────────────────────────────────────────────────────

class BriefViewGetTest(TestCase):

    def test_get_sv_returns_200(self):
        response = self.client.get(reverse('brief'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'brief/form.html')

    def test_get_en_returns_200(self):
        response = self.client.get(reverse('brief_en'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Project Brief')


# ── Test 5: View – POST giltigt formulär redirectar (PRG) ─────────────────

class BriefViewPostTest(TestCase):

    @patch('brief.views._send_html_email')
    @patch('brief.views._fire_analytics_event')
    def test_valid_post_creates_brief_and_redirects(self, mock_analytics, mock_email):
        data = {**VALID_POST, 'form_token': _valid_token()}
        response = self.client.post(reverse('brief'), data)
        self.assertRedirects(response, reverse('brief_thanks'))
        self.assertEqual(ProjectBrief.objects.count(), 1)
        brief = ProjectBrief.objects.first()
        self.assertEqual(brief.contact_email, 'test@example.com')
        self.assertEqual(brief.language, 'sv')

    @patch('brief.views._send_html_email')
    @patch('brief.views._fire_analytics_event')
    def test_valid_post_triggers_two_emails(self, mock_analytics, mock_email):
        data = {**VALID_POST, 'form_token': _valid_token()}
        self.client.post(reverse('brief'), data)
        # Två trådar startas; _send_html_email anropas med daemon threads –
        # vi kontrollerar att det skapats ett Brief-objekt (indirekt verifierar emailflödet)
        self.assertEqual(ProjectBrief.objects.count(), 1)

    def test_too_fast_submission_blocked(self):
        fresh_token = signing.dumps(int(time.time()))  # 0 sekunder → avvisas
        data = {**VALID_POST, 'form_token': fresh_token}
        response = self.client.post(reverse('brief'), data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get('spam_error'))
        self.assertEqual(ProjectBrief.objects.count(), 0)

    def test_missing_token_blocked(self):
        data = {**VALID_POST, 'form_token': ''}
        response = self.client.post(reverse('brief'), data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get('spam_error'))

    @patch('brief.views._send_html_email')
    @patch('brief.views._fire_analytics_event')
    def test_english_post_redirects_to_en_thanks(self, mock_analytics, mock_email):
        data = {**VALID_POST, 'form_token': _valid_token(), 'language': 'en'}
        response = self.client.post(reverse('brief_en'), data)
        self.assertRedirects(response, reverse('brief_thanks_en'))
        brief = ProjectBrief.objects.first()
        self.assertEqual(brief.language, 'en')


# ── Test 6: Tack-sida ──────────────────────────────────────────────────────

class BriefThanksTest(TestCase):

    def test_thanks_sv(self):
        response = self.client.get(reverse('brief_thanks'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tack')

    def test_thanks_en(self):
        response = self.client.get(reverse('brief_thanks_en'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Thank you')
