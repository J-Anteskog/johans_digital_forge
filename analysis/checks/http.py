import ssl
import socket
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from django.core.exceptions import ValidationError

from ..net import BlockedAddressError, safe_request
from ..validators import resolve_public_ips

_UA = 'Mozilla/5.0 (compatible; JDFAnalyser/1.0; +https://johans-digital-forge.se)'
_TIMEOUT = 15


def check_http(url: str) -> dict:
    """HTTP-status, redirect-kedja och svarstid."""
    result = {
        'ok': False,
        'status_code': None,
        'final_url': url,
        'redirect_chain': [],
        'redirect_count': 0,
        'response_time_ms': None,
        'is_https': False,
        'error': None,
    }
    try:
        start = time.monotonic()
        # safe_request följer omdirigeringar själv och validerar varje steg + IP
        resp = safe_request('GET', url, timeout=_TIMEOUT)
        elapsed = int((time.monotonic() - start) * 1000)
        chain = [r.url for r in resp.history] + [resp.url]
        result.update({
            'ok': resp.status_code < 400,
            'status_code': resp.status_code,
            'final_url': resp.url,
            'redirect_chain': chain,
            'redirect_count': len(resp.history),
            'response_time_ms': elapsed,
            'is_https': resp.url.startswith('https://'),
        })
    except BlockedAddressError as e:
        result['error'] = str(e)
    except requests.exceptions.SSLError as e:
        result['error'] = f'SSL-fel: {e}'
    except requests.exceptions.ConnectionError as e:
        result['error'] = f'Anslutningsfel: {e}'
    except requests.exceptions.Timeout:
        result['error'] = f'Timeout efter {_TIMEOUT}s'
    except Exception as e:
        result['error'] = str(e)
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
