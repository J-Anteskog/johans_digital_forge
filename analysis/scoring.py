"""
Poängsystem v2  (0–100 per kategori, eller None = ej mätt):
  HTTPS och certifikat  20 %  – HTTPS, giltigt certifikat, >30 dagar kvar
  SEO                   22 %  – title, meta desc, H1, viewport, OG, robots, sitemap
  Prestanda             20 %  – PageSpeed (mobil + dator) om tillgängligt,
                                annars "Sidvikt och svarstid" (svarstid, HTML-storlek,
                                antal CSS/JS-filer, renderblockerande skript)
  Mobilanpassning       15 %  – viewport, zoom, media queries, skalbara bilder
  Säkerhetsheaders      13 %  – HSTS, CSP, X-Frame-Options, X-Content-Type, m.fl.
  Tillgänglighet        10 %  – lang, landmärken, skip-länk, rubriker, alt-texter, onclick

En kategori som inte kunde mätas (None) räknas INTE in i totalbetyget – vikterna
för de mätta kategorierna skalas om så att de summerar till 100 %.

Betyg: A ≥85 · B ≥70 · C ≥50 · D <50
"""

ANALYZER_VERSION = 2

WEIGHTS = {
    'security':      0.20,
    'seo':           0.22,
    'performance':   0.20,
    'mobile':        0.15,
    'headers':       0.13,
    'accessibility': 0.10,
}


def calculate_scores(results: dict) -> dict:
    scores = {
        'security':      _score_security(results),
        'seo':           _score_seo(results),
        'performance':   _score_performance(results),
        'mobile':        _score_mobile(results),
        'headers':       _score_headers(results),
        'accessibility': _score_accessibility(results),
    }
    scores['overall'] = overall_score(scores)
    return scores


def overall_score(scores: dict):
    measured = {k: v for k, v in scores.items() if k in WEIGHTS and v is not None}
    total_weight = sum(WEIGHTS[k] for k in measured)
    if not measured or total_weight == 0:
        return None
    value = sum(v * WEIGHTS[k] for k, v in measured.items()) / total_weight
    return min(100, max(0, int(round(value))))


def scoring_summary(scores: dict, results: dict) -> dict:
    """Metadata som sparas i results['scoring'] och visas i rapporten."""
    measured = [k for k in WEIGHTS if scores.get(k) is not None]
    return {
        'version': ANALYZER_VERSION,
        'measured': measured,
        'not_measured': [k for k in WEIGHTS if k not in measured],
        'measured_count': len(measured),
        'category_count': len(WEIGHTS),
        'performance_source': performance_source(results),
    }


def _has_html(results):
    return bool(results.get('seo'))


# ── HTTPS och certifikat (max 100) ─────────────────────────────────────────

def _score_security(results):
    http = results.get('http', {})
    ssl  = results.get('ssl', {})
    if http.get('status_code') is None:
        return None   # inget svar alls – inget att bedöma

    pts = 0
    if http.get('is_https'):
        pts += 50
    if ssl.get('valid'):
        pts += 30
        if not ssl.get('expires_soon'):   # >30 dagar kvar
            pts += 20
    return min(100, pts)


# ── SEO (max 100) ─────────────────────────────────────────────────────────

def _score_seo(results):
    if not _has_html(results):
        return None
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

def performance_source(results):
    """'pagespeed' om minst en PageSpeed-strategi gav poäng, 'basic' om vi har HTML, annars None."""
    if _psp_scores(results):
        return 'pagespeed'
    if _has_html(results) and results.get('http', {}).get('response_time_ms') is not None:
        return 'basic'
    return None


def _score_performance(results):
    source = performance_source(results)
    if source == 'pagespeed':
        vals = _psp_scores(results)
        return int(round(sum(vals) / len(vals)))
    if source == 'basic':
        return basic_performance_breakdown(results)['score']
    return None


def basic_performance_breakdown(results) -> dict:
    """
    "Sidvikt och svarstid" – bara sådant vi faktiskt mäter från vår server.
    Säger ingenting om hur snabbt sidan ritas upp i en webbläsare.
    """
    http = results.get('http', {})
    res  = results.get('resources', {})

    rt = http.get('response_time_ms') or 0
    if rt < 500:    rt_pts = 40
    elif rt < 1000: rt_pts = 30
    elif rt < 2000: rt_pts = 15
    else:           rt_pts = 0

    kb = (http.get('html_bytes') or 0) / 1024
    if kb < 100:   size_pts = 20
    elif kb < 300: size_pts = 10
    else:          size_pts = 0

    files = res.get('total_files', 0)
    if files <= 10:   files_pts = 20
    elif files <= 20: files_pts = 10
    else:             files_pts = 0

    blocking = res.get('render_blocking_scripts', 0)
    if blocking == 0:   block_pts = 20
    elif blocking <= 2: block_pts = 10
    else:               block_pts = 0

    parts = {
        'response_time': {'points': rt_pts, 'max': 40},
        'html_size':     {'points': size_pts, 'max': 20},
        'file_count':    {'points': files_pts, 'max': 20},
        'render_blocking': {'points': block_pts, 'max': 20},
    }
    return {'parts': parts, 'score': sum(p['points'] for p in parts.values())}


# ── Mobilanpassning (max 100) ─────────────────────────────────────────────

def _score_mobile(results):
    return (results.get('mobile') or {}).get('score')


# ── Säkerhetsheaders (max 100) ────────────────────────────────────────────

def _score_headers(results):
    hdr = results.get('headers') or {}
    if hdr.get('error') or not hdr.get('headers'):
        return None
    return hdr.get('score')


# ── Tillgänglighet (max 100) ──────────────────────────────────────────────

def _score_accessibility(results):
    if not _has_html(results):
        return None
    return (results.get('accessibility') or {}).get('score')


# ── Hjälp ────────────────────────────────────────────────────────────────

def _psp_scores(results):
    psp = results.get('pagespeed') or {}
    out = []
    for strategy in ('mobile', 'desktop'):
        s = (psp.get(strategy) or {}).get('score')
        if s is not None:
            out.append(s)
    return out
