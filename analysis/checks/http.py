import ssl
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

from django.core.exceptions import ValidationError

from ..net import fetch_limited
from ..validators import resolve_public_ips

_TIMEOUT = (5, 15)
MAX_HTML_BYTES = 2_000_000  # 2 MB


def fetch_page(url: str, session=None):
    """
    Hämtar sidan EN gång (med SSRF-skydd och storleksgräns).
    Returnerar FetchResult; check_http(), säkerhetsheaders och HTML-parsningen
    använder alla samma svar.
    """
    return fetch_limited(url, max_bytes=MAX_HTML_BYTES, timeout=_TIMEOUT,
                         session=session, fail_on_too_large=True)


def check_http(page) -> dict:
    """HTTP-status, redirect-kedja och svarstid utifrån ett FetchResult."""
    result = {
        'ok': False,
        'status_code': page.status_code,
        'final_url': page.final_url or page.url,
        'redirect_chain': page.redirect_chain,
        'redirect_count': max(0, len(page.redirect_chain) - 1),
        # Tid tills hela HTML-dokumentet hämtats från vår server (ej webbläsarens laddningstid)
        'response_time_ms': None,
        'ttfb_ms': page.ttfb_ms,
        'html_bytes': len(page.content) if page.content else None,
        'is_https': (page.final_url or page.url).startswith('https://'),
        'error': None,
    }
    if page.status_code is not None:
        result['ok'] = page.status_code < 400
        result['response_time_ms'] = page.total_ms
    if page.error:
        result['error'] = page.error
        result['error_kind'] = page.error_kind
        if page.error_kind != 'too_large':
            result['response_time_ms'] = None
    return result


def check_ssl(url: str) -> dict:
    """SSL-certifikatets giltighet och utgångsdatum."""
    result = {
        'ok': False,
        'valid': False,
        'expiry_date': None,
        'days_remaining': None,
        'expires_soon': False,
        'error': None,
    }
    parsed = urlparse(url)
    if parsed.scheme != 'https':
        result['error'] = 'Sidan använder inte HTTPS – SSL-kontroll hoppades över.'
        return result

    hostname = parsed.hostname
    try:
        ip = resolve_public_ips(hostname, 443)[0]
        ctx = ssl.create_default_context()
        with socket.create_connection((ip, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

        expiry_str = cert.get('notAfter', '')
        expiry = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z').replace(
            tzinfo=timezone.utc
        )
        days_remaining = (expiry - datetime.now(timezone.utc)).days
        result.update({
            'ok': True,
            'valid': True,
            'expiry_date': expiry.strftime('%Y-%m-%d'),
            'days_remaining': days_remaining,
            'expires_soon': days_remaining < 30,
        })
    except ValidationError as e:
        result['error'] = f'Blockerad adress: {e.messages[0]}'
    except ssl.SSLCertVerificationError as e:
        result['error'] = f'Ogiltigt certifikat: {e}'
    except Exception as e:
        result['error'] = str(e)
    return result
