"""Teckenkodning: HTTP-header → <meta charset> → UTF-8 → windows-1252."""

from django.test import SimpleTestCase

from analysis.checks.page_facts import parse_html

from .helpers import fixture_bytes


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
