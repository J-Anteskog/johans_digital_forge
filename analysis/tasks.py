"""
Bakgrundsjobb: run_analysis() körs i en daemon-tråd startad av views.py.
Mönstret speglar det befintliga threading-upplägget i contact/views.py.

Migreringsväg till Celery: byt ut start_analysis() mot .delay()-anrop
och dekorera run_analysis med @shared_task – resten av koden är oförändrad.
"""

import threading
import traceback
from urllib.parse import urlparse, urljoin

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import SiteAnalysis
from .net import safe_session, set_host_interval
from .robots import MAX_CRAWL_DELAY, RobotsRules
from .validators import validate_target_url
from .checks.http import check_http, check_ssl, fetch_page
from .checks.page_facts import analyze_images, analyze_resources, parse_html
from .checks.seo import check_seo, check_seo_page, fetch_robots_txt
from .checks.performance import check_performance
from .checks.mobile import check_mobile
from .checks.pagespeed import check_pagespeed
from .checks.headers import check_headers
from .checks.accessibility import check_accessibility
from .scoring import (
    ANALYZER_VERSION, basic_performance_breakdown, calculate_scores, pagespeed_breakdown,
    scoring_summary, seo_breakdown,
)


# Faser som visas på väntesidan (pending.html) medan analysen körs, i körordning
PHASES = ('fetch', 'crawl', 'checks', 'pagespeed', 'scoring')


def collect_results(url: str, progress=None) -> dict:
    """
    Kör alla kontroller mot en redan validerad URL och returnerar results-dict
    inklusive 'scores'. Skriver inget till databasen (används även av
    manage.py analyse_url --dry-run).
    progress: valfri funktion som anropas med fasens namn (se PHASES).
    """
    report = progress or (lambda phase: None)
    results = {'analyzer_version': ANALYZER_VERSION}
    session = safe_session()
    try:
        report('fetch')
        # ── 1. Hämta sidan EN gång: status, redirects, headers, HTML ──────
        #      (varje omdirigering och IP valideras i analysis.net)
        page = fetch_page(url, session)
        results['http'] = check_http(page)
        final_url = results['http']['final_url'] or url

        # ── 2. SSL ────────────────────────────────────────────────────────
        results['ssl'] = check_ssl(final_url)

        # ── 3. Parsa HTML ─────────────────────────────────────────────────
        soup = None
        if page.error:
            results['html_fetch_error'] = page.error
            results['html_fetch_error_kind'] = page.error_kind
        elif page.status_code and page.status_code >= 400:
            results['html_fetch_error'] = f'HTTP {page.status_code}'
            results['html_fetch_error_kind'] = 'http'
        elif page.content:
            soup = parse_html(page.content, page.encoding)

        # ── 4. Kontroller som kräver HTML ─────────────────────────────────
        if soup:
            images    = analyze_images(soup, final_url)
            resources = analyze_resources(soup, final_url)
            results['images']        = images
            results['resources']     = resources

            # robots.txt hämtas en gång: SEO-kontrollen och crawlens regler
            robots_res = fetch_robots_txt(final_url, session)
            results['seo'] = check_seo(final_url, soup, session, robots=robots_res)
            rules = RobotsRules.from_fetch(robots_res)
            results['robots'] = rules.summary()
            if rules.crawl_delay:
                set_host_interval(session, urlparse(final_url).hostname or '',
                                  min(rules.crawl_delay, MAX_CRAWL_DELAY))

            # Undersidorna före bild-/CSS-kontrollerna: de är viktigast om
            # servern börjar neka anrop
            report('crawl')
            results['pages'], results['pages_skipped'] = _crawl_internal_pages(
                final_url, soup, session, rules=rules, max_pages=rules.max_pages(20))

            report('checks')
            results['performance']   = check_performance(final_url, soup, session)
            results['mobile']        = check_mobile(soup, resources, session)
            results['accessibility'] = check_accessibility(soup, images)
        else:
            results['seo']           = {}
            results['performance']   = {}
            results['accessibility'] = {}
            results['pages']         = []

        # ── 5. Säkerhetsheaders (från samma GET-svar som ovan) ────────────
        results['headers'] = check_headers(page)

        # ── 6. PageSpeed API (upp till 60 s – körs här i bakgrundsjobbet) ─
        report('pagespeed')
        results['pagespeed'] = check_pagespeed(final_url)
    finally:
        session.close()

    # ── 7. Beräkna poäng ─────────────────────────────────────────────────
    report('scoring')
    if results.get('seo'):
        results['performance']['basic'] = basic_performance_breakdown(results)
        results['seo_breakdown'] = seo_breakdown(results)
    results['pagespeed_breakdown'] = pagespeed_breakdown(results)
    scores = calculate_scores(results)
    results['scoring'] = scoring_summary(scores, results)
    results['scores'] = scores
    return results


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
    obj.domain = urlparse(obj.url).netloc
    obj.save(update_fields=['status', 'domain'])

    try:
        # Re-validera precis innan requests skickas
        try:
            safe_url = validate_target_url(obj.url)
        except ValidationError as e:
            obj.status = 'error'
            obj.error_message = str(e)
            obj.save(update_fields=['status', 'error_message'])
            return

        results = collect_results(safe_url, progress=lambda phase: _set_phase(obj.pk, phase))
        scores = results.pop('scores')

        obj.results               = results
        obj.analyzer_version      = ANALYZER_VERSION
        obj.score_overall         = scores['overall']
        obj.score_performance     = scores['performance']
        obj.score_mobile          = scores['mobile']
        obj.score_seo             = scores['seo']
        obj.score_security        = scores['security']
        obj.score_headers         = scores['headers']
        obj.score_accessibility   = scores['accessibility']
        obj.status                = 'complete'
        obj.completed_at          = timezone.now()
        obj.save()

    except Exception:
        obj.status        = 'error'
        obj.error_message = traceback.format_exc()[-3000:]
        obj.results       = None   # ta bort ev. fasmarkering så att felsidan visas
        obj.save(update_fields=['status', 'error_message', 'results'])


def _set_phase(pk, phase: str) -> None:
    """
    Sparar aktuell fas i results medan analysen körs, så att väntesidan kan visa
    vad som faktiskt pågår. Skrivs över av det riktiga resultatet när analysen är klar.
    Uppdaterar bara results-kolumnen (inte e-post, samtycke m.m.).
    """
    SiteAnalysis.objects.filter(pk=pk, status='running').update(
        results={'progress': {'phase': phase, 'started': timezone.now().isoformat()}},
    )


# Tekniska adresser som inte är riktiga sidor (t.ex. Cloudflares mejlskydd) –
# hoppas över och visas aldrig som sidfel
_TECHNICAL_PATH_PREFIXES = (
    '/cdn-cgi/', '/wp-admin', '/wp-login', '/wp-json', '/xmlrpc.php',
    '/wp-content/', '/wp-includes/', '/feed', '/comments/feed',
)
_TECHNICAL_QUERY_KEYS = ('replytocom', 'add-to-cart', 'share')
_FILE_EXTENSIONS = (
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.zip', '.rar',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.xml', '.json', '.txt', '.csv',
    '.mp4', '.mp3', '.mov', '.ics', '.css', '.js',
)


def _page_key(url: str) -> str:
    """Jämförelsenyckel: samma sida oavsett http/https, www. och avslutande snedstreck."""
    p = urlparse(url)
    host = (p.hostname or '').lower()
    host = host[4:] if host.startswith('www.') else host
    path = p.path.rstrip('/') or '/'
    return f'{host}{path}' + (f'?{p.query}' if p.query else '')


def _skip_reason(url: str) -> str | None:
    p = urlparse(url)
    path = p.path.lower()
    if path.startswith(_TECHNICAL_PATH_PREFIXES):
        return 'technical'
    if path.endswith(_FILE_EXTENSIONS):
        return 'file'
    query_keys = {part.split('=', 1)[0].lower() for part in p.query.split('&') if part}
    if query_keys & set(_TECHNICAL_QUERY_KEYS):
        return 'technical'
    return None


def _crawl_internal_pages(base_url: str, root_soup, session=None, max_pages: int = 20, rules=None):
    """
    Crawlar interna sidor och kör SEO + tillgänglighet på var och en.
    Returnerar (sidor, överhoppade). Tekniska adresser, filer, dubbletter av
    startsidan och sidor som robots.txt inte tillåter hoppas över och redovisas
    separat – aldrig som sidfel. Fel sparas med typ (error_kind) och teknisk
    text (error) så att rapporten kan visa en läsbar text.
    """
    base_host = urlparse(base_url).hostname or ''
    base_site = base_host[4:] if base_host.startswith('www.') else base_host

    seen = {_page_key(base_url)}
    to_visit, skipped = [], []

    for a in root_soup.find_all('a', href=True):
        href = a['href'].strip()
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue
        absolute = urljoin(base_url, href).split('#')[0]
        p = urlparse(absolute)
        host = (p.hostname or '').lower()
        if p.scheme not in ('http', 'https') or (host[4:] if host.startswith('www.') else host) != base_site:
            continue
        key = _page_key(absolute)
        if key in seen:
            if (key == _page_key(base_url) and absolute.rstrip('/') != base_url.rstrip('/')
                    and all(x['url'] != absolute for x in skipped)):
                skipped.append({'url': absolute, 'reason': 'duplicate'})
            continue
        seen.add(key)
        reason = _skip_reason(absolute)
        if not reason and rules is not None and not rules.allowed(absolute):
            reason = 'robots'
        if reason:
            skipped.append({'url': absolute, 'reason': reason})
            continue
        to_visit.append(absolute.rstrip('/'))

    pages = []
    for url in to_visit[:max_pages]:
        page = fetch_page(url, session)
        if page.error:
            pages.append({'url': url, 'error': page.error, 'error_kind': page.error_kind})
            continue
        if (page.status_code or 0) >= 400:
            pages.append({'url': url, 'error': f'HTTP {page.status_code}', 'error_kind': 'http',
                          'status_code': page.status_code})
            continue
        if not page.content:
            pages.append({'url': url, 'error': 'Tomt svar', 'error_kind': 'empty'})
            continue
        soup = parse_html(page.content, page.encoding)
        images = analyze_images(soup, url)
        pages.append({
            'url': url,
            'seo': check_seo_page(soup),
            'accessibility': check_accessibility(soup, images),
        })

    return pages, skipped[:30]


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
