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
from django.utils import timezone

from .models import SiteAnalysis
from .checks.http import check_http, check_ssl
from .checks.seo import check_seo
from .checks.performance import check_performance
from .checks.pagespeed import check_pagespeed
from .scoring import calculate_scores

_UA = 'Mozilla/5.0 (compatible; JDFAnalyser/1.0; +https://johans-digital-forge.se)'
_HTML_TIMEOUT = 20


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
        url = obj.url
        results = {}

        # ── 1. HTTP ───────────────────────────────────────────────────────
        http_res = check_http(url)
        results['http'] = http_res
        final_url = http_res.get('final_url') or url

        # ── 2. SSL ────────────────────────────────────────────────────────
        results['ssl'] = check_ssl(final_url)

        # ── 3. Hämta + parsa HTML ─────────────────────────────────────────
        soup = None
        try:
            resp = requests.get(
                final_url,
                timeout=_HTML_TIMEOUT,
                headers={'User-Agent': _UA},
                allow_redirects=True,
            )
            soup = BeautifulSoup(resp.text, 'lxml')
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
