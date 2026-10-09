"""
Säkra HTTP-anrop mot analyserade webbplatser (SSRF-skydd).

Alla anrop som går till en adress som kommer från den analyserade sidan
(sidan själv, omdirigeringar, bilder, CSS-filer, undersidor, robots.txt …)
ska gå via safe_request() / fetch_limited():

  1. URL:en kontrolleras (schema, port, blockerade värdnamn) – även vid
     varje omdirigering, som följs manuellt.
  2. Vid själva TCP-uppkopplingen slås namnet upp och VARJE IP kontrolleras
     med check_ip_allowed(). Anslutningen görs sedan direkt mot det
     godkända IP:t, så att en DNS-post inte kan bytas mellan kontroll och
     anslutning (DNS rebinding).
  3. Proxy-inställningar från miljön ignoreras (trust_env=False).

Hänsyn till den analyserade servern (per session och värd):
  - minst MIN_HOST_INTERVAL sekunder mellan anrop till samma värd
    (längre om robots.txt anger Crawl-delay, se set_host_interval)
  - GET/HEAD görs om vid anslutningsfel/timeout med backoff (RETRY_BACKOFF),
    och en gång vid 429/503 med kort Retry-After
  - efter HOST_FAILURE_LIMIT misslyckade anrop i rad slutar vi anropa värden
    (HostUnavailableError) i stället för att fortsätta belasta den

Alla fel loggas (logger "analysis.net") med hela felkedjan, men nycklar och
liknande parametrar i URL:er tas bort först (redact).
"""

import logging
import random
import re
import socket
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from django.core.exceptions import ValidationError
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError

from .validators import resolve_public_ips, validate_url_syntax

logger = logging.getLogger('analysis.net')

UA = 'Mozilla/5.0 (compatible; JDF-Webbanalys/1.1; +https://www.johans-digital-forge.se/analys/bot/)'
ROBOTS_AGENT = 'JDF-Webbanalys'   # namnet vi matchar mot i robots.txt
MAX_REDIRECTS = 5
_REDIRECT_CODES = {301, 302, 303, 307, 308}

MIN_HOST_INTERVAL = 0.3        # sekunder mellan anrop till samma värd
RETRY_BACKOFF = (1.0, 3.0)     # väntetid före försök 2 och 3
RETRY_JITTER = 0.3             # slumpmässigt tillägg till väntetiden
MAX_RETRY_AFTER = 10           # följ Retry-After (429/503) bara om den är kort
HOST_FAILURE_LIMIT = 2         # misslyckade anrop i rad innan vi slutar anropa värden
_RETRY_METHODS = {'GET', 'HEAD'}

# Byts ut i testerna
_sleep = time.sleep
_now = time.monotonic

# Parametrar som kan innehålla nycklar eller lösenord – värdet ersätts med ***
_SENSITIVE = re.compile(
    r'((?<![\w-])(?:key|api_?key|api-key|apikey|token|access_?token|auth|secret|client_?secret|'
    r'password|passwd|pwd|signature|sig)=)[^&\s\'"<>)]+',
    re.IGNORECASE,
)


def redact(text) -> str:
    """Tar bort värdet på nyckel-/lösenordsparametrar ur en text (t.ex. en URL i ett felmeddelande)."""
    return _SENSITIVE.sub(r'\1***', str(text))


class BlockedAddressError(requests.exceptions.ConnectionError):
    """Anropet stoppades eftersom adressen inte är publik."""


class HostUnavailableError(requests.exceptions.ConnectionError):
    """Vi har slutat anropa värden efter upprepade fel i rad."""


# ── Anslutning som validerar IP:t den faktiskt kopplar upp mot ────────────

class _BlockedConnectionError(NewConnectionError):
    pass


def _safe_new_conn(conn):
    try:
        ips = resolve_public_ips(conn._dns_host.rstrip('.'), conn.port)
    except ValidationError as e:
        raise _BlockedConnectionError(conn, f'Blockerad adress: {e.messages[0]}') from e

    # Anslut direkt till det godkända IP:t – ingen ny DNS-uppslagning
    timeout = conn.timeout if isinstance(conn.timeout, (int, float)) else None
    last_err = None
    for ip in ips:
        sock = None
        try:
            family = socket.AF_INET6 if ':' in ip else socket.AF_INET
            sock = socket.socket(family, socket.SOCK_STREAM)
            for opt in conn.socket_options or []:
                sock.setsockopt(*opt)
            sock.settimeout(timeout)
            if conn.source_address:
                sock.bind(conn.source_address)
            sock.connect((ip, conn.port))
            return sock
        except OSError as e:
            last_err = e
            if sock is not None:
                sock.close()
    raise NewConnectionError(conn, f'Kunde inte ansluta: {last_err}')


class _SafeHTTPConnection(HTTPConnection):
    def _new_conn(self):
        return _safe_new_conn(self)


class _SafeHTTPSConnection(HTTPSConnection):
    def _new_conn(self):
        return _safe_new_conn(self)


class _SafeHTTPPool(HTTPConnectionPool):
    ConnectionCls = _SafeHTTPConnection


class _SafeHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _SafeHTTPSConnection


class _SafeAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            'http': _SafeHTTPPool,
            'https': _SafeHTTPSPool,
        }


def safe_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.headers['User-Agent'] = UA
    adapter = _SafeAdapter()
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    return s


# ── Hänsyn till servern: paus, retry och spärr per värd ──────────────────

def _host_state(session, host: str) -> dict:
    hosts = getattr(session, 'jdf_hosts', None)
    if hosts is None:
        hosts = session.jdf_hosts = {}
    return hosts.setdefault(host, {'last': None, 'failures': 0, 'down': False,
                                   'interval': MIN_HOST_INTERVAL})


def set_host_interval(session, host: str, seconds: float) -> None:
    """Minsta tid mellan anrop till värden (t.ex. robots.txt Crawl-delay)."""
    state = _host_state(session, host.lower())
    state['interval'] = max(MIN_HOST_INTERVAL, seconds)


def host_is_down(session, host: str) -> bool:
    return _host_state(session, host.lower())['down']


def _throttle(state: dict) -> None:
    if state['last'] is not None:
        wait = state['interval'] - (_now() - state['last'])
        if wait > 0:
            _sleep(wait)
    state['last'] = _now()


def _retry_after_seconds(value) -> float | None:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None   # HTTP-datum stöds inte – då görs inget nytt försök


def describe_error(exc) -> str:
    """Hela felkedjan som en rad, utan nycklar – för logg och teknisk vy."""
    parts, seen, cur = [], set(), exc
    while cur is not None and id(cur) not in seen and len(parts) < 6:
        seen.add(id(cur))
        parts.append(f'{type(cur).__name__}: {cur}')
        cur = cur.__cause__ or cur.__context__ or getattr(cur, 'reason', None)
        if not isinstance(cur, BaseException):
            cur = None
    return redact(' <- '.join(parts))


def _send(s, method: str, url: str, timeout, stream: bool):
    """Ett anrop (utan omdirigeringar) med paus, retry och spärr per värd."""
    host = (urlparse(url).hostname or '').lower()
    state = _host_state(s, host)
    if state['down']:
        raise HostUnavailableError(f'{host} slutade svara – inga fler anrop')

    max_attempts = 1 + len(RETRY_BACKOFF) if method in _RETRY_METHODS else 1
    attempt, retry_after_used = 0, False
    while True:
        attempt += 1
        _throttle(state)
        try:
            resp = s.request(method, url, timeout=timeout, allow_redirects=False, stream=stream)
        except requests.exceptions.SSLError:
            raise   # certifikatfel blir inte bättre av ett nytt försök
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            reason = getattr(e.args[0] if e.args else None, 'reason', None)
            if isinstance(reason, _BlockedConnectionError):
                raise BlockedAddressError(reason._message) from e
            logger.warning('Anrop misslyckades (försök %d av %d): %s %s – %s',
                           attempt, max_attempts, method, redact(url), describe_error(e))
            if attempt < max_attempts:
                _sleep(RETRY_BACKOFF[attempt - 1] + random.uniform(0, RETRY_JITTER))
                continue
            state['failures'] += 1
            if state['failures'] >= HOST_FAILURE_LIMIT and not state['down']:
                state['down'] = True
                logger.warning('Slutar anropa %s efter %d misslyckade anrop i rad', host, state['failures'])
            raise

        if (resp.status_code in (429, 503) and method in _RETRY_METHODS and not retry_after_used):
            wait = _retry_after_seconds(resp.headers.get('Retry-After'))
            if wait is not None and wait <= MAX_RETRY_AFTER:
                retry_after_used = True
                logger.info('%s svarade %d med Retry-After %s s – väntar och försöker igen',
                            host, resp.status_code, wait)
                resp.close()
                _sleep(wait)
                continue
        state['failures'] = 0
        return resp


# ── Publika hjälpfunktioner ───────────────────────────────────────────────

def safe_request(method: str, url: str, *, timeout=10, session=None,
                 stream=False, max_redirects=MAX_REDIRECTS) -> requests.Response:
    """
    Gör ett anrop och följer omdirigeringar manuellt; varje steg valideras.
    Returnerar sista svaret med .history satt till tidigare svar.
    Raises BlockedAddressError om någon adress i kedjan är otillåten.
    """
    own_session = session is None
    s = session or safe_session()
    history = []
    current = url
    try:
        for _ in range(max_redirects + 1):
            try:
                validate_url_syntax(current)
            except ValidationError as e:
                raise BlockedAddressError(f'Blockerad adress: {e.messages[0]}')
            resp = _send(s, method, current, timeout, stream)
            if resp.status_code in _REDIRECT_CODES and resp.headers.get('Location'):
                history.append(resp)
                current = urljoin(resp.url, resp.headers['Location'])
                resp.close()
                if resp.status_code == 303:
                    method = 'GET'
                continue
            resp.history = history
            return resp
        raise requests.exceptions.TooManyRedirects(f'Fler än {max_redirects} omdirigeringar')
    finally:
        if own_session and not stream:
            s.close()


@dataclass
class FetchResult:
    url: str
    final_url: str = ''
    status_code: int | None = None
    headers: dict = field(default_factory=dict)
    content: bytes = b''
    redirect_chain: list = field(default_factory=list)
    ttfb_ms: int | None = None
    total_ms: int | None = None
    truncated: bool = False
    encoding: str | None = None
    error: str | None = None        # teknisk text (utan nycklar) – bara för logg och teknisk vy
    error_kind: str | None = None   # 'blocked' | 'timeout' | 'ssl' | 'connection' | 'host_unavailable'
                                    # | 'too_large' | 'other'


def fetch_limited(url: str, *, max_bytes: int, timeout=(5, 15), session=None,
                  fail_on_too_large=False) -> FetchResult:
    """
    GET med storleksgräns. Fel fångas och returneras i FetchResult.error.
    Med fail_on_too_large=False kapas svaret vid max_bytes (truncated=True).
    """
    res = FetchResult(url=url)
    start = time.monotonic()
    try:
        resp = safe_request('GET', url, timeout=timeout, session=session, stream=True)
        try:
            res.ttfb_ms = int(resp.elapsed.total_seconds() * 1000)
            res.status_code = resp.status_code
            res.final_url = resp.url
            res.headers = {k.lower(): v for k, v in resp.headers.items()}
            res.redirect_chain = [r.url for r in resp.history] + [resp.url]
            res.encoding = requests.utils.get_encoding_from_headers(resp.headers) \
                if 'charset' in resp.headers.get('Content-Type', '').lower() else None
            buf = bytearray()
            for chunk in resp.iter_content(chunk_size=16384):
                buf += chunk
                if len(buf) > max_bytes:
                    if fail_on_too_large:
                        res.error = f'Svaret är för stort (>{max_bytes // 1000} kB).'
                        res.error_kind = 'too_large'
                        buf = bytearray()
                    else:
                        res.truncated = True
                        del buf[max_bytes:]
                    break
            res.content = bytes(buf)
        finally:
            resp.close()
    except BlockedAddressError as e:
        res.error, res.error_kind = redact(e), 'blocked'
    except HostUnavailableError as e:
        res.error, res.error_kind = redact(e), 'host_unavailable'
    except requests.exceptions.SSLError as e:
        res.error, res.error_kind = f'SSL-fel: {describe_error(e)}', 'ssl'
    except requests.exceptions.Timeout as e:
        res.error, res.error_kind = f'Timeout: {describe_error(e)}', 'timeout'
    except requests.exceptions.ConnectionError as e:
        res.error, res.error_kind = f'Anslutningsfel: {describe_error(e)}', 'connection'
    except Exception as e:  # noqa: BLE001 – rapporteras i resultatet
        res.error, res.error_kind = describe_error(e), 'other'
    if res.error and res.error_kind not in ('blocked', 'host_unavailable', 'too_large'):
        logger.warning('Hämtning misslyckades: %s – %s', redact(url), res.error)
    res.total_ms = int((time.monotonic() - start) * 1000)
    return res
