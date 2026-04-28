"""
Bakgrundsjobb: run_analysis() körs i en daemon-tråd startad av views.py.
Mönstret speglar det befintliga threading-upplägget i contact/views.py.

Migreringsväg till Celery: byt ut start_analysis() mot .delay()-anrop
och dekorera run_analysis med @shared_task – resten av koden är oförändrad.
"""

import threading
import traceback

import requests
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import SiteAnalysis
from .validators import validate_target_url
from .checks.http import check_http, check_ssl
from .checks.seo import check_seo
from .checks.performance import check_performance
from .checks.pagespeed import check_pagespeed
from .scoring import calculate_scores

_UA = 'Mozilla/5.0 (compatible; JDFAnalyser/1.0; +https://johans-digital-forge.se)'
_CONNECT_TIMEOUT = 5
_READ_TIMEOUT = 15
_TIMEOUT = (_CONNECT_TIMEOUT, _READ_TIMEOUT)
_MAX_HTML_BYTES = 2_000_000  # 2 MB


def _fetch_html(url: str) -> str:
    """Hämtar HTML med storleksgräns (skydd mot zip bombs och jättesidor)."""
    resp = requests.get(
        url,
        timeout=_TIMEOUT,
        stream=True,
        headers={'User-Agent': _UA},
        allow_redirects=True,
    )
    resp.raise_for_status()

    content = b''
    for chunk in resp.iter_content(chunk_size=8192):
        content += chunk
        if len(content) > _MAX_HTML_BYTES:
            raise ValueError('Sidan är för stor för att analyseras (>2 MB).')
    return content.decode(resp.encoding or 'utf-8', errors='replace')


def run_analysis(analysis_id: str) -> None:
    """
    Huvud-runner. Anropas i bakgrundstråd.
    Uppdaterar SiteAnalysis-objektet direkt i databasen.
    """
    try:
        obj = SiteAnalysis.objects.get(pk=analysis_id)
    except SiteAnalysis.DoesNotExist:
        return

    obj.status = 'running'
    obj.save(update_fields=['status'])

    try:
        # Re-validera precis innan requests skickas (skydd mot DNS rebinding)
        try:
            safe_url = validate_target_url(obj.url)
        except ValidationError as e:
            obj.status = 'error'
            obj.error_message = str(e)
            obj.save(update_fields=['status', 'error_message'])
            return

        results = {}

        # ── 1. HTTP ───────────────────────────────────────────────────────
        http_res = check_http(safe_url)
        results['http'] = http_res
        final_url = http_res.get('final_url') or safe_url

        # Re-validera final_url efter eventuella redirects
        try:
            final_url = validate_target_url(final_url)
        except ValidationError:
            final_url = safe_url

        # ── 2. SSL ────────────────────────────────────────────────────────
        results['ssl'] = check_ssl(final_url)

        # ── 3. Hämta + parsa HTML ─────────────────────────────────────────
        soup = None
        try:
            html = _fetch_html(final_url)
            soup = BeautifulSoup(html, 'lxml')
        except Exception as e:
            results['html_fetch_error'] = str(e)

        # ── 4. SEO + prestanda (kräver HTML) ─────────────────────────────
        if soup:
            results['seo']         = check_seo(final_url, soup)
            results['performance'] = check_performance(final_url, soup)
        else:
            results['seo']         = {}
            results['performance'] = {}

        # ── 5. PageSpeed API (nätverksintensiv – sist) ───────────────────
        results['pagespeed'] = check_pagespeed(final_url)

        # ── 6. Beräkna poäng ─────────────────────────────────────────────
        scores = calculate_scores(results)

        obj.results           = results
        obj.score_overall     = scores['overall']
        obj.score_performance = scores['performance']
        obj.score_mobile      = scores['mobile']
        obj.score_seo         = scores['seo']
        obj.score_security    = scores['security']
        obj.status            = 'complete'
        obj.completed_at      = timezone.now()
        obj.save()

    except Exception:
        obj.status        = 'error'
        obj.error_message = traceback.format_exc()[-3000:]
        obj.save(update_fields=['status', 'error_message'])


def start_analysis(analysis_id: str) -> threading.Thread:
    """Startar run_analysis i en daemon-tråd och returnerar tråd-objektet."""
    t = threading.Thread(
        target=run_analysis,
        args=(str(analysis_id),),
        daemon=True,
        name=f'analysis-{analysis_id}',
    )
    t.start()
    return t
