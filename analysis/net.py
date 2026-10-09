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
"""

import socket
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

import requests
from django.core.exceptions import ValidationError
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError

from .validators import resolve_public_ips, validate_url_syntax

UA = 'Mozilla/5.0 (compatible; JDFAnalyser/1.0; +https://johans-digital-forge.se)'
MAX_REDIRECTS = 5
_REDIRECT_CODES = {301, 302, 303, 307, 308}


class BlockedAddressError(requests.exceptions.ConnectionError):
    """Anropet stoppades eftersom adressen inte är publik."""


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
            try:
                resp = s.request(method, current, timeout=timeout,
                                 allow_redirects=False, stream=stream)
            except requests.exceptions.ConnectionError as e:
                reason = getattr(e.args[0] if e.args else None, 'reason', None)
                if isinstance(reason, _BlockedConnectionError):
                    raise BlockedAddressError(reason._message) from e
                raise
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
    error: str | None = None
    error_kind: str | None = None   # 'blocked' | 'timeout' | 'ssl' | 'connection' | 'too_large' | 'other'


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
        res.error, res.error_kind = str(e), 'blocked'
    except requests.exceptions.SSLError as e:
        res.error, res.error_kind = f'SSL-fel: {e}', 'ssl'
    except requests.exceptions.Timeout:
        res.error, res.error_kind = 'Timeout', 'timeout'
    except requests.exceptions.ConnectionError as e:
        res.error, res.error_kind = f'Anslutningsfel: {e}', 'connection'
    except Exception as e:  # noqa: BLE001 – rapporteras i resultatet
        res.error, res.error_kind = str(e), 'other'
    res.total_ms = int((time.monotonic() - start) * 1000)
    return res
