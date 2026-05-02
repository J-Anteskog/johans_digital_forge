"""
Poängsystem  (0–100 per kategori, viktat overall):
  Säkerhet        20 %  – HTTPS, SSL-giltighet, certifikat ej snart-utgånget
  SEO             22 %  – title, meta desc, H1, viewport, OG, robots, sitemap
  Prestanda       20 %  – PageSpeed desktop (om tillgänglig) + svarstid + resurser
  Mobilanpassning 15 %  – PageSpeed mobile (om tillgänglig) + viewport
  Säkerhetsheaders 13 % – HSTS, CSP, X-Frame-Options, X-Content-Type, m.fl.
  Tillgänglighet  10 %  – lang, landmarks, skip-nav, alt-texter, onclick

Betyg: A ≥85 · B ≥70 · C ≥50 · D <50
"""


def calculate_scores(results: dict) -> dict:
    sec   = _score_security(results)
    seo   = _score_seo(results)
    perf  = _score_performance(results)
    mob   = _score_mobile(results)
    hdr   = _score_headers(results)
    a11y  = _score_accessibility(results)
    overall = int(round(
        sec  * 0.20 +
        seo  * 0.22 +
        perf * 0.20 +
        mob  * 0.15 +
        hdr  * 0.13 +
        a11y * 0.10
    ))
    return {
        'security':      sec,
        'seo':           seo,
        'performance':   perf,
        'mobile':        mob,
        'headers':       hdr,
        'accessibility': a11y,
        'overall':       min(100, max(0, overall)),
    }


# ── Säkerhet (max 100) ────────────────────────────────────────────────────

def _score_security(results):
    pts = 0
    http = results.get('http', {})
    ssl  = results.get('ssl', {})

    if http.get('is_https'):
        pts += 50
    if ssl.get('valid'):
        pts += 30
        if not ssl.get('expires_soon'):   # >30 dagar kvar
            pts += 20
    return min(100, pts)


# ── SEO (max 100) ─────────────────────────────────────────────────────────

def _score_seo(results):
    pts = 0
    seo = results.get('seo', {})

    title = seo.get('title', {})
    if title.get('found'):
        pts += 10
        if title.get('ok'):       # 30–60 tecken
            pts += 10

    desc = seo.get('meta_description', {})
    if desc.get('found'):
        pts += 10
        if desc.get('ok'):        # 50–160 tecken
            pts += 10

    h1 = seo.get('h1', {})
    if h1.get('found'):
        pts += 10
        if h1.get('unique'):      # exakt 1 st
            pts += 5

    if seo.get('viewport', {}).get('found'):    pts += 10
    if seo.get('og_title', {}).get('found'):    pts += 10
    if seo.get('og_image', {}).get('found'):    pts += 10
    if seo.get('robots_txt', {}).get('found'):  pts += 10
    if seo.get('sitemap', {}).get('found'):     pts += 5

    return min(100, pts)


# ── Prestanda (max 100) ───────────────────────────────────────────────────

def _score_performance(results):
    psp = _get_psp(results, 'desktop')

    if psp is not None:
        base = psp   # PageSpeed score är redan 0–100
    else:
        # Fallback: svarstid
        rt = results.get('http', {}).get('response_time_ms') or 9999
        if rt < 500:    base = 80
        elif rt < 1000: base = 60
        elif rt < 2000: base = 40
        else:           base = 20

    # Penalisera för många externa resurser (>5 = 2p per extra)
    ext = results.get('performance', {}).get('total_external_resources', 0)
    penalty = max(0, (ext - 5) * 2)

    return max(0, min(100, base - penalty))


# ── Mobilanpassning (max 100) ─────────────────────────────────────────────

def _score_mobile(results):
    psp = _get_psp(results, 'mobile')

    if psp is not None:
        return min(100, psp)

    # Fallback: viewport meta
    viewport = results.get('seo', {}).get('viewport', {})
    return 60 if viewport.get('found') else 20


# ── Säkerhetsheaders (max 100) ────────────────────────────────────────────

def _score_headers(results):
    hdr = results.get('headers', {})
    if hdr.get('error') or not hdr.get('headers'):
        return 0
    return hdr.get('score', 0)


# ── Tillgänglighet (max 100) ──────────────────────────────────────────────

def _score_accessibility(results):
    a11y = results.get('accessibility', {})
    return a11y.get('score', 0)


# ── Hjälp ────────────────────────────────────────────────────────────────

def _get_psp(results, strategy):
    """Hämta PageSpeed-score för en strategi, returnerar None om ej tillgänglig."""
    psp = (results.get('pagespeed') or {}).get(strategy, {})
    if psp and not psp.get('error') and psp.get('score') is not None:
        return psp['score']
    return None
