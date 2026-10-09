"""
Hänsyn till den analyserade servern och säkra fel:
retry med backoff, paus per värd, spärr efter upprepade fel, Retry-After,
User-Agent, robots.txt och att nycklar aldrig hamnar i logg, resultat eller rapport.

Anslutningstesterna använder en lokal server på 127.0.0.1 – ingen extern trafik.
"""

import json
import socket
import threading
from contextlib import ExitStack
from unittest.mock import patch
from urllib.parse import urlparse

import requests
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from analysis import net
from analysis.checks.pagespeed import check_pagespeed
from analysis.models import SiteAnalysis
from analysis.net import (
    UA, BlockedAddressError, HostUnavailableError, fetch_limited, redact, safe_request, safe_session,
    set_host_interval,
)
from analysis.robots import RobotsRules
from analysis.scoring import ANALYZER_VERSION
from analysis.tasks import collect_results
from analysis.validators import validate_url_syntax

from .helpers import FakeWeb, NoNetworkMixin, addrinfo
from .test_site_rules import SITE, _collect, _site_web

SECRET = 'SECRET-abc123'


# ── Lokal testserver ───────────────────────────────────────────────────────

class LocalServer:
    """
    Lägen:
      ok              – svarar 200 och håller anslutningen öppen
      keepalive_close – svarar 200 men stänger anslutningen direkt efter svaret
      refuse_after    – svarar på de `n` första anropen, sedan tas inga anslutningar emot
      status          – svarar med statuskoderna i `statuses` (en per anrop)
    """

    def __init__(self, mode='ok', n=1, statuses=None, headers=None):
        self.mode, self.n = mode, n
        self.statuses = list(statuses or [])
        self.extra_headers = headers or {}
        self.requests = []          # (sökväg, User-Agent)
        self.sock = socket.socket()
        self.sock.bind(('127.0.0.1', 0))
        self.sock.listen(20)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def _accept(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            while True:
                data = conn.recv(65536)
                if not data:
                    return
                lines = data.decode('latin-1').split('\r\n')
                path = lines[0].split(' ')[1]
                ua = next((l.split(':', 1)[1].strip() for l in lines if l.lower().startswith('user-agent:')), '')
                self.requests.append((path, ua))
                if self.mode == 'refuse_after' and len(self.requests) > self.n:
                    self.close()          # tar inte emot fler anslutningar
                    conn.close()
                    return
                status = self.statuses.pop(0) if self.statuses else 200
                body = b'<html><title>ok</title></html>'
                head = f'HTTP/1.1 {status} X\r\nContent-Type: text/html\r\nContent-Length: {len(body)}\r\n'
                head += ''.join(f'{k}: {v}\r\n' for k, v in self.extra_headers.items())
                conn.sendall(head.encode() + b'\r\n' + body)
                if self.mode == 'keepalive_close':
                    conn.close()
                    return
        except OSError:
            pass


class LocalServerMixin:
    """public.example → 127.0.0.1 (godkänns bara i testerna), väntetider registreras i stället för att sova."""

    def setUp(self):
        super().setUp()
        self.sleeps = []
        real_resolve, real_syntax = net.resolve_public_ips, validate_url_syntax

        def fake_resolve(host, port=None):
            return ['127.0.0.1'] if host == 'public.example' else real_resolve(host, port)

        def fake_syntax(url):
            return urlparse(url) if urlparse(url).hostname == 'public.example' else real_syntax(url)

        for p in (patch('analysis.net.resolve_public_ips', side_effect=fake_resolve),
                  patch('analysis.net.validate_url_syntax', side_effect=fake_syntax),
                  patch('analysis.net._sleep', side_effect=self.sleeps.append)):
            p.start()
            self.addCleanup(p.stop)

    def server(self, **kw):
        srv = LocalServer(**kw)
        self.addCleanup(srv.close)
        return srv, f'http://public.example:{srv.port}/'


# ── Retry, spärr, Retry-After och User-Agent ───────────────────────────────

class RetryTests(LocalServerMixin, SimpleTestCase):

    def test_closed_keepalive_connection_is_retried(self):
        """Samma fel som 'RemoteDisconnected' hos bmmab.se: servern stänger anslutningen vi återanvänder."""
        srv, base = self.server(mode='keepalive_close')
        s = safe_session()
        codes = [safe_request('GET', f'{base}sida-{i}', timeout=3, session=s).status_code for i in range(6)]
        self.assertEqual(codes, [200] * 6)                        # utan retry: vartannat anrop misslyckades
        self.assertTrue(any(1.0 <= x <= 1.0 + net.RETRY_JITTER for x in self.sleeps))   # backoff före försök 2

    def test_host_is_given_up_after_two_failed_requests_in_a_row(self):
        srv, base = self.server(mode='refuse_after', n=1)
        s = safe_session()
        self.assertEqual(safe_request('GET', f'{base}a', timeout=2, session=s).status_code, 200)
        for path in ('b', 'c'):
            with self.assertRaises(requests.exceptions.ConnectionError):
                safe_request('GET', base + path, timeout=2, session=s)
        backoffs = [x for x in self.sleeps if x >= 1.0]
        self.assertEqual(len(backoffs), 4)                        # 2 anrop × 2 nya försök
        self.assertTrue(net.host_is_down(s, 'public.example'))
        res = fetch_limited(f'{base}d', max_bytes=1000, session=s)
        self.assertEqual(res.error_kind, 'host_unavailable')      # inget nytt anrop
        with self.assertRaises(HostUnavailableError):
            safe_request('HEAD', f'{base}e', timeout=2, session=s)

    def test_success_resets_failure_count(self):
        s = safe_session()
        state = net._host_state(s, 'public.example')
        state['failures'] = 1
        srv, base = self.server()
        safe_request('GET', base, timeout=2, session=s)
        self.assertEqual(state['failures'], 0)

    def test_short_retry_after_is_respected_once(self):
        srv, base = self.server(statuses=[429, 200], headers={'Retry-After': '2'})
        resp = safe_request('GET', base, timeout=2)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(2.0, self.sleeps)
        self.assertEqual(len(srv.requests), 2)

    def test_long_retry_after_is_not_waited_for(self):
        srv, base = self.server(statuses=[503], headers={'Retry-After': '120'})
        self.assertEqual(safe_request('GET', base, timeout=2).status_code, 503)
        self.assertEqual(len(srv.requests), 1)

    def test_user_agent_identifies_us(self):
        self.assertEqual(UA, 'Mozilla/5.0 (compatible; JDF-Webbanalys/1.1; '
                             '+https://www.johans-digital-forge.se/analys/bot/)')
        srv, base = self.server()
        safe_request('GET', base, timeout=2)
        self.assertEqual(srv.requests[0][1], UA)

    def test_pause_between_requests_to_same_host(self):
        clock = [100.0]
        with patch('analysis.net._now', side_effect=lambda: clock[0]):
            state = {'last': None, 'failures': 0, 'down': False, 'interval': net.MIN_HOST_INTERVAL}
            net._throttle(state)
            clock[0] += 0.1
            net._throttle(state)
        self.assertEqual(len(self.sleeps), 1)
        self.assertAlmostEqual(self.sleeps[0], 0.2)

    def test_crawl_delay_raises_interval_but_never_below_minimum(self):
        s = safe_session()
        set_host_interval(s, 'a.se', 4)
        self.assertEqual(net._host_state(s, 'a.se')['interval'], 4)
        set_host_interval(s, 'b.se', 0.05)
        self.assertEqual(net._host_state(s, 'b.se')['interval'], net.MIN_HOST_INTERVAL)


class NoRetryTests(NoNetworkMixin, SimpleTestCase):

    def test_blocked_address_is_never_retried(self):
        sleeps = []
        with patch('analysis.validators.socket.getaddrinfo', return_value=addrinfo('10.0.0.1')), \
             patch('analysis.net._sleep', side_effect=sleeps.append):
            with self.assertRaises(BlockedAddressError):
                safe_request('GET', 'http://intern.example/', timeout=2)
        self.assertEqual([x for x in sleeps if x >= 1.0], [])
        self.assertNoNetwork()

    def test_ssl_error_is_not_retried(self):
        s = safe_session()
        with patch.object(s, 'request', side_effect=requests.exceptions.SSLError('cert')) as req, \
             patch('analysis.net._sleep'):
            with self.assertRaises(requests.exceptions.SSLError):
                safe_request('GET', 'https://a.example/', timeout=2, session=s)
        self.assertEqual(req.call_count, 1)

    def test_post_is_not_retried(self):
        s = safe_session()
        with patch.object(s, 'request', side_effect=requests.exceptions.ConnectionError('x')) as req, \
             patch('analysis.net._sleep'):
            with self.assertRaises(requests.exceptions.ConnectionError):
                safe_request('POST', 'https://a.example/', timeout=2, session=s)
        self.assertEqual(req.call_count, 1)


# ── Nycklar i fel ──────────────────────────────────────────────────────────

class RedactionTests(NoNetworkMixin, SimpleTestCase):

    def test_redact(self):
        self.assertEqual(redact(f'https://x/run?url=a&key={SECRET}&strategy=mobile'),
                         'https://x/run?url=a&key=***&strategy=mobile')
        for param in ('api_key', 'apikey', 'token', 'access_token', 'secret', 'password', 'sig'):
            self.assertNotIn(SECRET, redact(f'?{param}={SECRET}'), param)
        self.assertEqual(redact('monkey=banana'), 'monkey=banana')

    def test_failed_fetch_never_contains_key_in_log_or_result(self):
        url = f'https://a.example/sida?key={SECRET}'
        err = requests.exceptions.ConnectionError(f"HTTPSConnectionPool(host='a.example'): Max retries exceeded with url: /sida?key={SECRET}")
        s = safe_session()
        with patch.object(s, 'request', side_effect=err), patch('analysis.net._sleep'), \
             self.assertLogs('analysis.net', level='WARNING') as logs:
            res = fetch_limited(url, max_bytes=1000, session=s)
        self.assertEqual(res.error_kind, 'connection')
        self.assertNotIn(SECRET, res.error)
        self.assertIn('key=***', res.error)
        self.assertNotIn(SECRET, '\n'.join(logs.output))
        self.assertTrue(any('försök 3 av 3' in line for line in logs.output))   # hela kedjan loggas

    @override_settings(PAGESPEED_API_KEY=SECRET)
    def test_pagespeed_error_never_contains_key(self):
        err = requests.exceptions.ConnectionError(
            f'Max retries exceeded with url: /pagespeedonline/v5/runPagespeed?url=x&key={SECRET}')
        with patch('analysis.checks.pagespeed.requests.get', side_effect=err), \
             self.assertLogs('analysis.pagespeed', level='WARNING') as logs:
            res = check_pagespeed('https://a.example/')
        self.assertNotIn(SECRET, json.dumps(res))
        self.assertNotIn(SECRET, '\n'.join(logs.output))
        self.assertIn('key=***', '\n'.join(logs.output))


@override_settings(PAGESPEED_API_KEY='')
class RedactionInReportTests(NoNetworkMixin, TestCase):

    def test_key_in_failing_url_never_reaches_saved_errors_logs_or_report(self):
        """
        Felmeddelanden (som innehåller anropets URL) får aldrig innehålla nyckeln.
        Själva adressen som användaren angav sparas som den är (final_url) – den är inget fel.
        """
        url = f'https://example-site.se/?key={SECRET}'
        err = requests.exceptions.ConnectionError(f'Max retries exceeded with url: /?key={SECRET}')
        with patch('analysis.net.requests.Session.request', side_effect=err), patch('analysis.net._sleep'), \
             patch('analysis.tasks.check_ssl', return_value={'valid': False, 'error': 'x'}), \
             self.assertLogs('analysis.net', level='WARNING') as logs:
            r = collect_results(url)
        errors = [r['http']['error'], r['html_fetch_error'], r['headers']['error']]
        self.assertTrue(all(errors))
        for e in errors:
            self.assertNotIn(SECRET, e)
        self.assertNotIn(SECRET, '\n'.join(logs.output))

        r['http']['final_url'] = r['http']['final_url'].replace(SECRET, 'x')   # adressen, inte ett fel
        scores = r.pop('scores')
        obj = SiteAnalysis.objects.create(url='https://example-site.se/?key=x', status='complete', results=r,
                                          analyzer_version=ANALYZER_VERSION, language='sv',
                                          **{f'score_{k}': v for k, v in scores.items()})
        for name in ('analysis_result', 'analysis_shared', 'analysis_pdf'):
            html = self.client.get(reverse(name, kwargs={'token': obj.id})).content.decode()
            self.assertNotIn(SECRET, html, name)


# ── robots.txt ─────────────────────────────────────────────────────────────

class _Res:
    def __init__(self, status, text=''):
        self.status_code, self.content = status, text.encode()


class RobotsRulesTests(SimpleTestCase):

    def test_rules_for_our_agent_take_precedence(self):
        rules = RobotsRules.from_fetch(_Res(200, 'User-agent: *\nDisallow: /privat/\n\n'
                                                 'User-agent: JDF-Webbanalys\nDisallow: /intern/\nCrawl-delay: 4\n'))
        self.assertFalse(rules.allowed('https://a.se/intern/x'))
        self.assertTrue(rules.allowed('https://a.se/privat/x'))   # gruppen för oss gäller, inte *
        self.assertEqual(rules.crawl_delay, 4.0)

    def test_star_rules_apply_when_we_are_not_named(self):
        rules = RobotsRules.from_fetch(_Res(200, 'User-agent: *\nDisallow: /privat/\n'))
        self.assertFalse(rules.allowed('https://a.se/privat/x'))
        self.assertTrue(rules.allowed('https://a.se/ok'))

    def test_missing_and_unreachable(self):
        self.assertTrue(RobotsRules.from_fetch(_Res(404)).allowed('https://a.se/x'))
        unreachable = RobotsRules.from_fetch(_Res(503))
        self.assertFalse(unreachable.allowed('https://a.se/x'))   # RFC 9309: tolkas som "allt förbjudet"
        self.assertEqual(unreachable.status, 'unreachable')

    def test_long_crawl_delay_means_fewer_pages(self):
        self.assertEqual(RobotsRules.from_fetch(_Res(200, 'User-agent: *\nCrawl-delay: 10\n')).max_pages(20), 6)
        self.assertEqual(RobotsRules.from_fetch(_Res(200, 'User-agent: *\nCrawl-delay: 1\n')).max_pages(20), 20)


@override_settings(PAGESPEED_API_KEY='')
class RobotsCrawlTests(NoNetworkMixin, SimpleTestCase):

    def _run(self, robots_body, status=200):
        web = _site_web()
        web.pages[SITE + 'robots.txt'] = (status, {}, robots_body.encode())
        with patch('analysis.tasks.set_host_interval') as interval:
            r = _collect(web)
        return r, web, interval

    def test_disallowed_subpages_are_not_fetched(self):
        r, web, _ = self._run('User-agent: JDF-Webbanalys\nDisallow: /om-oss\n\nUser-agent: *\nDisallow:\n')
        self.assertNotIn(SITE + 'om-oss', web.requested)
        self.assertIn({'url': 'https://example-site.se/om-oss/', 'reason': 'robots'}, r['pages_skipped'])
        self.assertIn(SITE + 'tjanster', web.requested)
        self.assertNotIn('https://example-site.se/om-oss', [p['url'] for p in r['pages']])
        self.assertNoNetwork()

    def test_crawl_delay_is_used_as_pause(self):
        r, _, interval = self._run('User-agent: *\nCrawl-delay: 2\n')
        interval.assert_called_once()
        self.assertEqual(interval.call_args.args[1:], ('example-site.se', 2.0))
        self.assertEqual(r['robots'], {'status': 'ok', 'crawl_delay': 2.0})

    def test_unreachable_robots_means_no_subpages(self):
        r, web, _ = self._run('', status=503)
        self.assertEqual(r['pages'], [])
        self.assertTrue(all(s['reason'] == 'robots' for s in r['pages_skipped'] if s['reason'] != 'duplicate'
                            and not s['url'].endswith(('.pdf', '/wp-admin/')) and 'cdn-cgi' not in s['url']
                            and 'replytocom' not in s['url']))


@override_settings(PAGESPEED_API_KEY='')
class OrderTests(NoNetworkMixin, SimpleTestCase):

    def test_subpages_are_fetched_before_image_checks(self):
        web = _site_web()
        heads = []
        orig = web.safe_request

        def spy(method, url, **kw):
            heads.append(len(web.requested))   # hur många sidor som redan hämtats när bilden kontrolleras
            return orig(method, url, **kw)
        web.safe_request = spy
        _collect(web)
        crawl_done = web.requested.index(SITE + 'kontakt') + 1
        self.assertTrue(heads)
        self.assertTrue(all(n >= crawl_done for n in heads))


class BotPageTests(TestCase):

    def test_bot_page_explains_and_gives_contact(self):
        resp = self.client.get('/analys/bot/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'JDF-Webbanalys')
        self.assertContains(resp, 'info@johans-digital-forge.se')
        self.assertContains(resp, 'högst cirka 50 anrop')
        self.assertContains(resp, 'Crawl-delay')
        self.assertIn(urlparse(UA.split('+')[1].rstrip(')')).path, ('/analys/bot/',))
