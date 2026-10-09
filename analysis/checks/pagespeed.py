import logging
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings

from ..net import describe_error, redact

logger = logging.getLogger('analysis.pagespeed')

_API_URL = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'
_TIMEOUT = 60
_STRATEGIES = ('mobile', 'desktop')


def check_pagespeed(url: str) -> dict:
    """
    Anropar PageSpeed Insights API för mobil + dator (parallellt).
    Körs i bakgrundsjobbet (tasks.run_analysis), aldrig i en webbförfrågan.

    Returnerar alltid ett dict med 'status':
      'not_configured' – PAGESPEED_API_KEY saknas
      'ok'             – båda strategierna gav poäng
      'partial'        – en av två gav poäng
      'failed'         – ingen gav poäng (se error_kind/http_status per strategi)
    Gratis-tier: 25 000 anrop/dag (2 per analys → 12 500 analyser/dag).
    """
    api_key = getattr(settings, 'PAGESPEED_API_KEY', '')
    if not api_key:
        return {'status': 'not_configured'}

    with ThreadPoolExecutor(max_workers=len(_STRATEGIES)) as ex:
        futures = {s: ex.submit(_run_strategy, url, s, api_key) for s in _STRATEGIES}
        results = {s: f.result() for s, f in futures.items()}

    ok = [s for s in _STRATEGIES if results[s].get('score') is not None]
    if len(ok) == len(_STRATEGIES):
        status = 'ok'
    elif ok:
        status = 'partial'
    else:
        status = 'failed'
    return {'status': status, **results}


def _run_strategy(url: str, strategy: str, api_key: str) -> dict:
    try:
        resp = requests.get(
            _API_URL,
            params={'url': url, 'strategy': strategy, 'key': api_key, 'category': 'performance'},
            timeout=_TIMEOUT,
        )
    except requests.exceptions.Timeout as e:
        logger.warning('PageSpeed %s: timeout efter %s s (%s)', strategy, _TIMEOUT, redact(url))
        return {'error_kind': 'timeout', 'timeout_s': _TIMEOUT}
    except requests.exceptions.RequestException as e:
        # Felmeddelandet innehåller anrops-URL:en med API-nyckeln: loggas utan nyckel,
        # och i resultatet sparas bara typen
        logger.warning('PageSpeed %s misslyckades: %s', strategy, describe_error(e))
        return {'error_kind': 'error', 'error': type(e).__name__}

    if resp.status_code != 200:
        reason = ''
        try:
            # Googles 'status' (t.ex. PERMISSION_DENIED) – inte 'message', som kan
            # innehålla serverns IP-adress
            reason = resp.json().get('error', {}).get('status', '')
        except ValueError:
            pass
        logger.warning('PageSpeed %s svarade HTTP %s (%s) för %s', strategy, resp.status_code, reason, redact(url))
        return {'error_kind': 'http', 'http_status': resp.status_code, 'reason': reason[:60]}

    try:
        data = resp.json()
    except ValueError:
        return {'error_kind': 'error', 'error': 'Ogiltigt svar från PageSpeed'}
    lighthouse = data.get('lighthouseResult', {})
    cats = lighthouse.get('categories', {})
    audits = lighthouse.get('audits', {})

    raw_score = cats.get('performance', {}).get('score')
    if raw_score is None:
        return {'error_kind': 'error', 'error': 'PageSpeed returnerade ingen poäng'}

    def _ms(key):
        v = audits.get(key, {}).get('numericValue')
        return round(v) if v is not None else None

    def _float(key, decimals=3):
        v = audits.get(key, {}).get('numericValue')
        return round(v, decimals) if v is not None else None

    return {
        'score':  int(round(raw_score * 100)),
        'lcp_ms': _ms('largest-contentful-paint'),
        'cls':    _float('cumulative-layout-shift'),
        'inp_ms': _ms('interaction-to-next-paint'),
        'fcp_ms': _ms('first-contentful-paint'),
        'tbt_ms': _ms('total-blocking-time'),
        'fetch_time': lighthouse.get('fetchTime'),   # när Google gjorde mätningen (UTC, ISO 8601)
    }
