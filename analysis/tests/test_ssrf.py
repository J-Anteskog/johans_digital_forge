"""
SSRF-skydd: alla URL:er som kommer från den analyserade sidan (sidan själv,
omdirigeringar, bilder, CSS-filer) kontrolleras, och det är IP:t som namnet
löser upp till vid anslutningen som kontrolleras – inte bara strängen.
"""

import http.server
import threading
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from analysis import net
from analysis.checks.http import check_ssl
from analysis.checks.performance import check_performance
from analysis.net import BlockedAddressError, fetch_limited, safe_request
from analysis.validators import check_ip_allowed, resolve_public_ips

from .helpers import NoNetworkMixin, addrinfo, soup_from

PUBLIC = '93.184.216.34'


class IpCheckTests(SimpleTestCase):

    def test_public_ip_allowed(self):
        check_ip_allowed(PUBLIC)
        check_ip_allowed('2606:2800:220:1:248:1893:25c8:1946')

    def test_blocked_ranges(self):
        for ip in ('127.0.0.1', '10.1.2.3', '172.16.0.1', '192.168.0.1', '169.254.169.254',
                   '100.64.0.1',          # CGNAT / Tailscale – inte "private" men inte publik
                   '0.0.0.0', '::1', 'fd00::1', 'fe80::1',
                   '::ffff:127.0.0.1',    # IPv4-mappad loopback
                   '::ffff:10.0.0.1'):
            with self.subTest(ip=ip), self.assertRaises(ValidationError):
                check_ip_allowed(ip)

    def test_mixed_public_and_private_dns_answer_is_blocked(self):
        answer = addrinfo(PUBLIC) + addrinfo('10.0.0.7')
        with patch('analysis.validators.socket.getaddrinfo', return_value=answer):
            with self.assertRaises(ValidationError):
                resolve_public_ips('mixed.example')


class ConnectTimeCheckTests(NoNetworkMixin, SimpleTestCase):

    def test_dns_rebinding_is_stopped_at_connect(self):
        """Första uppslagningen (validering) ger publik IP, andra (anslutning) intern."""
        answers = [addrinfo(PUBLIC), addrinfo('127.0.0.1')]
        with patch('analysis.validators.socket.getaddrinfo', side_effect=answers):
            from analysis.validators import validate_target_url
            url = validate_target_url('http://rebind.example/')
            with self.assertRaises(BlockedAddressError):
                safe_request('GET', url, timeout=2)
        self.assertNoNetwork()

    def test_hostname_resolving_to_metadata_ip_is_blocked(self):
        with patch('analysis.validators.socket.getaddrinfo', return_value=addrinfo('169.254.169.254')):
            res = fetch_limited('http://metadata.example/latest/', max_bytes=1000)
        self.assertEqual(res.error_kind, 'blocked')
        self.assertNoNetwork()

    def test_literal_private_ip_and_bad_port_are_blocked(self):
        for url in ('http://10.0.0.1/', 'http://localhost/', 'http://example.com:8080/', 'file:///etc/passwd'):
            with self.subTest(url=url), self.assertRaises(BlockedAddressError):
                safe_request('GET', url, timeout=2)
        self.assertNoNetwork()

    def test_image_urls_are_validated(self):
        soup = soup_from('images_alt.html')
        soup.body.append(soup.new_tag('img', src='http://169.254.169.254/latest/meta-data/'))
        with patch('analysis.validators.socket.getaddrinfo', return_value=addrinfo('10.0.0.5')):
            perf = check_performance('https://example.com/', soup)
        self.assertEqual(perf['images_checked_for_size'], 0)   # alla bild-URL:er pekar på intern IP
        self.assertNoNetwork()

    def test_ssl_check_validates_ip(self):
        with patch('analysis.validators.socket.getaddrinfo', return_value=addrinfo('127.0.0.1')):
            res = check_ssl('https://internal.example/')
        self.assertFalse(res['valid'])
        self.assertIn('Blockerad adress', res['error'])
        self.assertNoNetwork()


class _RedirectHandler(http.server.BaseHTTPRequestHandler):
    target = ''

    def do_GET(self):
        self.send_response(302)
        self.send_header('Location', self.target)
        self.end_headers()

    def log_message(self, *args):
        pass


class RedirectTests(SimpleTestCase):
    """
    Startar en lokal server (127.0.0.1, ingen extern trafik) som omdirigerar till
    en intern adress. 'public.example' får låtsas vara publik och peka på servern.
    """

    def setUp(self):
        self.server = http.server.HTTPServer(('127.0.0.1', 0), _RedirectHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]

        real = net.resolve_public_ips

        def fake_resolve(host, port=None):
            if host == 'public.example':
                return ['127.0.0.1']
            return real(host, port)

        p1 = patch('analysis.net.resolve_public_ips', side_effect=fake_resolve)
        p2 = patch('analysis.validators.socket.getaddrinfo', return_value=addrinfo('10.0.0.9'))
        # Servern lyssnar på en slumpad port; tillåt den bara för public.example
        p3 = patch('analysis.net.validate_url_syntax', side_effect=self._syntax)
        for p in (p1, p2, p3):
            p.start()
            self.addCleanup(p.stop)

    def _syntax(self, url):
        from urllib.parse import urlparse
        from analysis.validators import validate_url_syntax
        if urlparse(url).hostname == 'public.example':
            return urlparse(url)
        return validate_url_syntax(url)

    def test_redirect_to_internal_host_is_blocked(self):
        _RedirectHandler.target = 'http://internal.example/admin'
        res = fetch_limited(f'http://public.example:{self.port}/', max_bytes=1000)
        self.assertEqual(res.error_kind, 'blocked')

    def test_redirect_to_localhost_is_blocked(self):
        _RedirectHandler.target = 'http://localhost/'
        res = fetch_limited(f'http://public.example:{self.port}/', max_bytes=1000)
        self.assertEqual(res.error_kind, 'blocked')

    def test_redirect_to_other_port_is_blocked(self):
        _RedirectHandler.target = 'http://internal.example:6379/'
        res = fetch_limited(f'http://public.example:{self.port}/', max_bytes=1000)
        self.assertEqual(res.error_kind, 'blocked')
