import requests
from django.conf import settings

_API_URL = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'
_TIMEOUT = 30


def check_pagespeed(url: str) -> dict | None:
    """
    Anropar PageSpeed Insights API för desktop + mobile.
    Returnerar None om PAGESPEED_API_KEY inte är konfigurerad.
    Gratis-tier: 25 000 anrop/dag (2 per analys → 12 500 analyser/dag).
    """
    api_key = getattr(settings, 'PAGESPEED_API_KEY', '')
    if not api_key:
        return None

    results = {}
    for strategy in ('desktop', 'mobile'):
        try:
            resp = requests.get(
                _API_URL,
                params={'url': url, 'strategy': strategy, 'key': api_key},
                timeout=_TIMEOUT,
            )
            if resp.status_code != 200:
                results[strategy] = {'error': f'HTTP {resp.status_code}'}
                continue

            data = resp.json()
            cats   = data.get('lighthouseResult', {}).get('categories', {})
            audits = data.get('lighthouseResult', {}).get('audits', {})

            raw_score = cats.get('performance', {}).get('score')
            perf_score = int(raw_score * 100) if raw_score is not None else None

            def _ms(key):
                v = audits.get(key, {}).get('numericValue')
                return round(v) if v is not None else None

            def _float(key, decimals=3):
                v = audits.get(key, {}).get('numericValue')
                return round(v, decimals) if v is not None else None

            results[strategy] = {
                'score':  perf_score,
                'lcp_ms': _ms('largest-contentful-paint'),
                'cls':    _float('cumulative-layout-shift'),
                'inp_ms': _ms('interaction-to-next-paint'),
                'fcp_ms': _ms('first-contentful-paint'),
                'tbt_ms': _ms('total-blocking-time'),
            }
        except Exception as e:
            results[strategy] = {'error': str(e)}

    return results or None
