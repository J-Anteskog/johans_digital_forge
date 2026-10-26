from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from brief import calculator
from brief.models import ProjectBrief


class ParseSelectionTests(TestCase):

    def test_unknown_package_gives_none(self):
        self.assertIsNone(calculator.parse_selection({'package': 'gold'}))
        self.assertIsNone(calculator.parse_selection({}))

    def test_included_and_unknown_addons_are_dropped(self):
        sel = calculator.parse_selection({'package': 'premium', 'addons': 'booking,chat,hack'})
        self.assertEqual(sel['addons'], ['chat'])

    def test_pages_are_clamped(self):
        self.assertEqual(calculator.parse_selection({'package': 'foretag', 'pages': '-3'})['pages'], 0)
        self.assertEqual(calculator.parse_selection({'package': 'foretag', 'pages': '999'})['pages'], calculator.MAX_EXTRA_PAGES)
        self.assertEqual(calculator.parse_selection({'package': 'foretag', 'pages': 'x'})['pages'], 0)

    def test_hosting_below_minimum_falls_back_to_recommended(self):
        self.assertEqual(calculator.parse_selection({'package': 'webshop', 'hosting': '200'})['hosting'], 300)
        self.assertEqual(calculator.parse_selection({'package': 'webshop', 'hosting': '500'})['hosting'], 500)
        self.assertEqual(calculator.parse_selection({'package': 'foretag', 'hosting': '0'})['hosting'], 0)


class TotalsAndInitialTests(TestCase):

    def test_totals_match_calculator(self):
        sel = calculator.parse_selection({'package': 'foretag', 'pages': '2', 'addons': 'booking,chat', 'hosting': '200'})
        self.assertEqual(calculator.totals(sel), (9500 + 1000 + 3500, 200 + 200))

    def test_budget_bands(self):
        cases = [
            ({'package': 'foretag'}, 'under_10k'),
            ({'package': 'foretag', 'addons': 'booking'}, '10k_20k'),
            ({'package': 'premium'}, '10k_20k'),
            ({'package': 'webshop'}, '20k_40k'),
            ({'package': 'webshop', 'pages': '40'}, '40k_plus'),
        ]
        for params, budget in cases:
            with self.subTest(params=params):
                sel = calculator.parse_selection(params)
                self.assertEqual(calculator.brief_initial(sel)['budget'], budget)

    def test_num_pages(self):
        cases = [
            ({'package': 'foretag'}, '5-10'),
            ({'package': 'foretag', 'pages': '5'}, '10-20'),
            ({'package': 'foretag', 'pages': '11'}, '20+'),
            ({'package': 'premium'}, '10-20'),
            ({'package': 'premium', 'pages': '1'}, '20+'),
        ]
        for params, num_pages in cases:
            with self.subTest(params=params):
                sel = calculator.parse_selection(params)
                self.assertEqual(calculator.brief_initial(sel)['num_pages'], num_pages)

    def test_features_only_from_explicit_addons(self):
        premium = calculator.brief_initial(calculator.parse_selection({'package': 'premium'}))
        self.assertNotIn('boka', premium['features'])

        shop = calculator.brief_initial(calculator.parse_selection({'package': 'webshop', 'addons': 'multilang,chat'}))
        self.assertEqual(shop['features'], ['webbshop', 'flersprak', 'chatt'])
        self.assertEqual(shop['goals'], ['sell_products'])

    def test_summary_mentions_package_and_total(self):
        sel = calculator.parse_selection({'package': 'premium', 'addons': 'chat', 'hosting': '300'})
        text = calculator.summary(sel)
        self.assertIn('Premium (16 500 kr)', text)
        self.assertIn('Ingår: Avancerad SEO, Bokningsintegration', text)
        self.assertIn('Totalt 16 500 kr + 500 kr/mån exkl. moms', text)

    def test_encode_decode_roundtrip(self):
        sel = calculator.parse_selection({'package': 'foretag', 'pages': '3', 'addons': 'chat,booking', 'hosting': '500'})
        self.assertEqual(calculator.decode_selection(calculator.encode_selection(sel)), sel)


class BriefViewCalculatorTests(TestCase):

    def test_get_prefills_form_and_shows_banner(self):
        url = reverse('brief') + '?ref=calculator&package=webshop&pages=0&addons=chat&hosting=300'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.initial['budget'], '20k_40k')
        self.assertIn('chatt', form.initial['features'])
        self.assertContains(response, 'Förifyllt från priskalkylatorn')
        self.assertContains(response, 'name="calculator_selection"')

    def test_get_without_ref_is_not_prefilled(self):
        response = self.client.get(reverse('brief') + '?package=webshop')
        self.assertNotIn('budget', response.context['form'].initial)
        self.assertNotContains(response, 'Förifyllt från priskalkylatorn')

    def test_legacy_10_plus_is_not_offered(self):
        response = self.client.get(reverse('brief'))
        keys = [k for k, _ in response.context['form'].fields['num_pages'].choices]
        self.assertNotIn('10+', keys)
        self.assertIn('10-20', keys)

    @patch('brief.views._check_timestamp', return_value=True)
    @patch('brief.views._verify_turnstile', return_value=True)
    @patch('brief.views._send_html_email')
    @patch('brief.views._fire_analytics_event')
    def test_post_saves_recomputed_summary(self, *_mocks):
        sel = calculator.parse_selection({'package': 'premium', 'pages': '2'})
        data = {
            'goals': ['leads'], 'budget': '10k_20k', 'timeline': 'no_rush',
            'has_existing_site': 'no_new', 'num_pages': '20+', 'has_material': 'all',
            'contact_name': 'Test', 'contact_email': 'test@example.com', 'language': 'sv',
            'calculator_selection': calculator.encode_selection(sel),
        }
        response = self.client.post(reverse('brief'), data)
        self.assertEqual(response.status_code, 302)
        brief = ProjectBrief.objects.get()
        self.assertEqual(brief.referrer, 'calculator')
        self.assertIn('Premium (16 500 kr)', brief.calculator_summary)
        self.assertIn('2 extra sidor (1 000 kr)', brief.calculator_summary)
