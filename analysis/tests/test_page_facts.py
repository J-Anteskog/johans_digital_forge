"""Regel 3 (CSS/JS-räkning), regel 4 (alt-text på ett ställe) och teckenkodning."""

from django.test import SimpleTestCase

from analysis.checks.accessibility import check_accessibility
from analysis.checks.page_facts import analyze_images, analyze_resources, is_same_site, parse_html

from .helpers import fixture_bytes, soup_from


class ResourceCountTests(SimpleTestCase):

    def test_wordpress_theme_files_are_counted(self):
        """enbloms-liknande sida: tidigare '0 CSS · 0 JS' – egna domänens filer räknades inte."""
        res = analyze_resources(soup_from('wordpress_mesmerize.html'), 'https://enbloms.example/')
        self.assertEqual(res['css_files'], 4)          # 2 med href + 2 via data-href
        self.assertEqual(res['js_files'], 6)
        self.assertEqual(res['total_files'], 10)
        self.assertEqual(res['css_same_site'], 3)
        self.assertEqual(res['css_third_party'], 1)    # Google Fonts
        self.assertEqual(res['third_party_hosts'], ['fonts.googleapis.com'])
        self.assertEqual(res['js_third_party'], 0)
        self.assertEqual(res['inline_data_scripts'], 3)
        self.assertEqual(res['render_blocking_scripts'], 0)  # jquery i <head> har defer, som på enbloms.se

    def test_relative_protocol_relative_and_absolute_urls(self):
        res = analyze_resources(soup_from('resources_mixed.html'), 'https://example.com/sida/')
        self.assertIn('https://example.com/sida/css/site.css', res['css_urls'])
        self.assertIn('https://example.com/static/print.css', res['css_urls'])
        self.assertIn('https://cdn.example.net/lib.css', res['css_urls'])           # //cdn… och rel="Stylesheet"
        self.assertIn('https://www.example.com/fonts.css', res['css_urls'])         # preload as=style
        self.assertIn('https://fonts.googleapis.com/css?family=Inter', res['css_urls'])  # data-href
        self.assertEqual(res['css_files'], 5)        # dubblett och data:-CSS räknas inte
        self.assertEqual(res['js_files'], 5)         # ld+json, inline och data: räknas inte som filer
        self.assertEqual(res['inline_data_scripts'], 1)
        self.assertEqual(res['render_blocking_scripts'], 1)  # bara js/app.js (async/defer/module undantas)
        self.assertEqual(res['css_same_site'], 3)    # www. och example.com räknas som samma
        self.assertEqual(res['js_same_site'], 4)     # sub.example.com räknas som samma webbplats

    def test_same_site_is_not_substring_match(self):
        self.assertFalse(is_same_site('https://evilexample.com/x.js', 'https://example.com/'))
        self.assertFalse(is_same_site('https://example.com.evil.net/x.js', 'https://example.com/'))
        self.assertTrue(is_same_site('https://www.example.com/x.js', 'https://example.com/'))


class ImageAltTests(SimpleTestCase):

    def test_classification(self):
        img = analyze_images(soup_from('images_alt.html'), 'https://example.com/')
        self.assertEqual(img['total'], 8)
        self.assertEqual(img['missing_alt'], 2)   # /a.jpg och lazy-bilden saknar alt helt
        self.assertEqual(img['decorative'], 4)    # alt="", alt="   ", role=presentation, aria-hidden
        self.assertEqual(img['with_alt'], 2)      # alt-text + aria-label
        self.assertIn('https://example.com/lazy.jpg', img['missing_alt_examples'])

    def test_empty_alt_is_decorative_not_missing(self):
        """enbloms-liknande sida: tre bilder med alt="" – ska inte räknas som saknad alt."""
        img = analyze_images(soup_from('wordpress_mesmerize.html'), 'https://enbloms.example/')
        self.assertEqual((img['total'], img['decorative'], img['missing_alt']), (3, 3, 0))

    def test_accessibility_uses_same_image_result(self):
        soup = soup_from('images_alt.html')
        images = analyze_images(soup, 'https://example.com/')
        a11y = check_accessibility(soup, images)
        self.assertIs(a11y['images'], images)
        self.assertFalse(a11y['passed']['images_alt'])


class EncodingTests(SimpleTestCase):

    def test_charset_from_header_is_used(self):
        soup = parse_html('<title>Räksmörgås</title>'.encode('cp1252'), 'cp1252')
        self.assertEqual(soup.title.get_text(), 'Räksmörgås')

    def test_meta_charset_used_when_header_has_none(self):
        """Tidigare: requests gissade ISO-8859-1 och UTF-8-sidor fick fel tecken."""
        soup = parse_html(fixture_bytes('utf8_meta_only.html'))
        self.assertEqual(soup.title.get_text(), 'Räksmörgås')
        self.assertEqual(soup.h1.get_text(), 'Åäö')

    def test_undeclared_latin1_is_detected(self):
        soup = parse_html(fixture_bytes('latin1_no_charset.html'))
        self.assertEqual(soup.title.get_text(), 'Räksmörgås')
