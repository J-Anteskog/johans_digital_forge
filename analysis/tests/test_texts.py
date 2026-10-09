"""Texträttningar: böjning av "undersida" och förklaringen när sidtitel saknas."""

from django.test import SimpleTestCase

from analysis.report import category_measures, site_findings

from .test_severity import _site


class SubpageInflectionTests(SimpleTestCase):

    def _measures(self, total, lang='sv'):
        r = _site(total, 0)
        r['analyzer_version'] = 3
        return category_measures('seo', r, lang)

    def test_one_subpage(self):
        text = self._measures(2)
        self.assertIn('på 1 undersida (60 %, värdet för undersidan)', text)
        self.assertNotIn('1 undersidor', text)
        self.assertIn('on 1 subpage (60 %, its value)', self._measures(2, 'en'))

    def test_several_subpages(self):
        self.assertIn('på 5 undersidor (60 %, medelvärde)', self._measures(6))
        self.assertIn('on 5 subpages (60 %, average)', self._measures(6, 'en'))


class TitleHintTests(SimpleTestCase):

    def test_missing_title_says_google_picks_headline(self):
        r = _site(3, 0)
        r['seo']['title'] = {'found': False, 'value': '', 'length': 0, 'ok': False}
        f = next(f for f in site_findings(r) if f['key'] == 'title_missing')
        self.assertEqual(f['hint'], 'utan titel väljer Google själv vilken rubrik som visas i sökresultaten')
        self.assertNotIn('handlar om', f['hint'])
        f_en = next(f for f in site_findings(r, 'en') if f['key'] == 'title_missing')
        self.assertEqual(f_en['hint'], 'without a title, Google picks the headline shown in search results itself')
