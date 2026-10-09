"""Regel 2: mobilanpassning poängsätts bara på det som faktiskt kontrolleras."""

from django.test import SimpleTestCase

from analysis.checks.mobile import MAX_SCORE, check_mobile
from analysis.checks.page_facts import analyze_resources

from .helpers import soup_from


def _reader(css='', read=None, total=None):
    """Fejkad CSS-läsare: (css, lästa, totalt)."""
    def reader(soup, resources, session):
        n = len((resources or {}).get('css_urls', []))
        inline = '\n'.join(s.get_text() for s in soup.find_all('style'))
        return inline + css, n if read is None else read, n if total is None else total
    return reader


def _run(name, base='https://example.com/', **kw):
    soup = soup_from(name)
    return check_mobile(soup, analyze_resources(soup, base), css_reader=_reader(**kw))


class MobileTests(SimpleTestCase):

    def test_passed_basic_check_is_capped_not_100(self):
        """Alla grundkontroller godkända ger högst 90 – klickytor och textstorlek är inte mätta."""
        r = _run('mobile_good.html')
        self.assertEqual({k: c['status'] for k, c in r['checks'].items()},
                         {'viewport': 'pass', 'zoom': 'pass', 'media_queries': 'pass', 'images_scale': 'pass'})
        self.assertTrue(r['basic_passed'])
        self.assertEqual(MAX_SCORE, 90)
        self.assertEqual(r['score'], 90)

    def test_failed_check_is_not_basic_passed(self):
        r = _run('mobile_zoom_blocked.html', css='body{}')
        self.assertFalse(r['basic_passed'])

    def test_unmeasurable_things_are_always_listed_as_not_measured(self):
        r = _run('mobile_good.html')
        self.assertIn('tap_targets', r['not_measured'])
        self.assertIn('text_size', r['not_measured'])

    def test_viewport_alone_does_not_give_a_high_score(self):
        """Tidigare: viewport → 60. Nu: viewport men blockerad zoom, inga media queries."""
        r = _run('mobile_zoom_blocked.html', css='body{font-size:16px}')
        self.assertEqual(r['checks']['viewport']['status'], 'pass')
        self.assertEqual(r['checks']['zoom']['status'], 'fail')
        self.assertEqual(sorted(r['checks']['zoom']['blocked_by']), ['maximum-scale=1', 'user-scalable=no'])
        self.assertEqual(r['checks']['media_queries']['status'], 'fail')
        self.assertEqual(r['checks']['images_scale']['status'], 'fail')
        self.assertEqual(r['score'], 40)

    def test_missing_viewport(self):
        r = _run('mobile_no_viewport.html', css='@media screen and (max-width: 700px){.a{}} img{max-width:100%}')
        self.assertEqual(r['checks']['viewport']['status'], 'fail')
        self.assertFalse(r['checks']['viewport']['found'])
        self.assertEqual(r['checks']['images_scale']['status'], 'pass')
        self.assertTrue(r['checks']['images_scale']['css_max_width_rule'])
        self.assertEqual(r['score'], 60)   # 60 av 100 uppmätta poäng

    def test_unreadable_css_is_not_measured_and_excluded_from_score(self):
        r = _run('mobile_zoom_blocked.html', read=0)
        self.assertEqual(r['checks']['media_queries']['status'], 'not_measured')
        self.assertEqual(r['checks']['images_scale']['status'], 'not_measured')
        self.assertEqual(r['points_measured'], 60)             # bara viewport + zoom
        self.assertEqual(r['score'], round(100 * 40 / 60))     # viewport ok, zoom blockerad
        self.assertIn('media_queries', r['not_measured'])

    def test_no_images_is_not_applicable(self):
        soup = soup_from('a11y_html5.html')
        r = check_mobile(soup, analyze_resources(soup, 'https://example.com/'), css_reader=_reader())
        self.assertEqual(r['checks']['images_scale']['status'], 'not_applicable')

    def test_wordpress_fixture_with_theme_css(self):
        theme_css = '@media (min-width:768px){.row{display:flex}} .content img{max-width:100%;height:auto}'
        r = _run('wordpress_mesmerize.html', base='https://enbloms.example/', css=theme_css)
        self.assertEqual(r['checks']['media_queries']['status'], 'pass')
        self.assertEqual(r['checks']['images_scale']['status'], 'pass')
        self.assertTrue(r['basic_passed'])
        self.assertEqual(r['score'], 90)
