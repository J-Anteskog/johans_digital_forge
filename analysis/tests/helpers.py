"""
Testhjälp för analysmodulen: sparade HTML-exempel (fixtures), en falsk webb
som ersätter alla HTTP-anrop och ett skydd som får testet att fallera om
något ändå försöker öppna en nätverksanslutning.
"""

import socket
from pathlib import Path
from unittest.mock import patch

from analysis.net import FetchResult

FIXTURES = Path(__file__).parent / 'fixtures'


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def soup_from(name: str):
    from analysis.checks.page_facts import parse_html
    return parse_html(fixture_bytes(name))


def addrinfo(ip: str):
    family = socket.AF_INET6 if ':' in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, '', (ip, 0))]


class NoNetworkMixin:
    """Stoppar och registrerar alla försök att öppna en socket-anslutning."""

    def setUp(self):
        super().setUp()
        self.connect_attempts = []

        def _blocked_connect(address, *args, **kwargs):
            self.connect_attempts.append(address)
            raise OSError('Nätverk är avstängt i testerna')

        def _blocked_sock_connect(sock, address):
            _blocked_connect(address)

        # socket.socket.connect: analysis.net (ansluter direkt till godkänt IP)
        # socket.create_connection: SSL-kontrollen
        # urllib3...create_connection: vanliga requests-anrop (t.ex. PageSpeed)
        for target in ('socket.create_connection', 'urllib3.util.connection.create_connection'):
            p = patch(target, side_effect=_blocked_connect)
            p.start()
            self.addCleanup(p.stop)
        p = patch('socket.socket.connect', _blocked_sock_connect)
        p.start()
        self.addCleanup(p.stop)

    def assertNoNetwork(self):
        self.assertEqual(self.connect_attempts, [], 'Testet försökte ansluta till nätverket')


class FakeWeb:
    """
    Ersätter fetch_limited/safe_request i analysmodulerna med svar från en
    ordbok {url: (status, headers, body_bytes)}. Okända URL:er ger 404.
    """

    def __init__(self, pages: dict, ttfb_ms=120, total_ms=300):
        self.pages = pages
        self.ttfb_ms = ttfb_ms
        self.total_ms = total_ms
        self.requested = []

    def _lookup(self, url):
        self.requested.append(url)
        return self.pages.get(url, (404, {}, b''))

    def fetch_limited(self, url, *, max_bytes, timeout=None, session=None, fail_on_too_large=False):
        value = self._lookup(url)
        if value[0] == 'error':
            # ('error', error_kind, teknisk text) – simulerar t.ex. ett anslutningsfel
            _, kind, text = value
            return FetchResult(url=url, error=text, error_kind=kind)
        status, headers, body = value
        headers = {k.lower(): v for k, v in headers.items()}
        ctype = headers.get('content-type', '')
        enc = ctype.split('charset=')[-1].strip() if 'charset=' in ctype else None
        return FetchResult(
            url=url, final_url=url, status_code=status, headers=headers,
            content=body[:max_bytes], redirect_chain=[url],
            ttfb_ms=self.ttfb_ms, total_ms=self.total_ms, encoding=enc,
        )

    def safe_request(self, method, url, **kwargs):
        status, headers, body = self._lookup(url)

        class _Resp:
            pass
        r = _Resp()
        r.status_code = status
        r.headers = headers
        r.url = url
        r.history = []
        return r

    def patches(self):
        """Alla ställen där analysen gör HTTP-anrop mot den analyserade sidan."""
        return [
            patch('analysis.checks.http.fetch_limited', side_effect=self.fetch_limited),
            patch('analysis.checks.seo.fetch_limited', side_effect=self.fetch_limited),
            patch('analysis.net.fetch_limited', side_effect=self.fetch_limited),
            patch('analysis.checks.performance.safe_request', side_effect=self.safe_request),
        ]
