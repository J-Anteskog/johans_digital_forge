"""
Poängsystem v3  (0–100 per kategori, eller None = ej mätt):
  HTTPS och certifikat  20 %  – HTTPS, giltigt certifikat, >30 dagar kvar
  SEO                   22 %  – titel (finns + unik), meta desc, H1, viewport, OG (startsidan 40 %,
                                undersidornas medel 60 %) + robots.txt, sitemap
  Prestanda             20 %  – PageSpeed (mobil 70 %, dator 30 %) om tillgängligt,
                                annars "Sidvikt och svarstid" (svarstid, HTML-storlek,
                                antal CSS/JS-filer, renderblockerande skript)
  Mobilanpassning       15 %  – viewport, zoom, media queries, skalbara bilder
  Säkerhetsheaders      13 %  – HSTS, CSP, X-Frame-Options, X-Content-Type, m.fl.
  Tillgänglighet        10 %  – lang, landmärken, skip-länk, rubriker, alt-texter, onclick

En kategori som inte kunde mätas (None) räknas INTE in i totalbetyget – vikterna
för de mätta kategorierna skalas om så att de summerar till 100 %.

Betyg: A ≥85 · B ≥70 · C ≥50 · D <50

Versioner:
  1 – första versionen (delvis uppskattade värden; visas med *_v1-mallarna)
  2 – ärliga kategorier; SEO bara på startsidan, PageSpeed som medel av mobil/dator
  3 – SEO över alla kontrollerade sidor, PageSpeed viktat mot mobil
"""

ANALYZER_VERSION = 3
FIRST_CURRENT_TEMPLATE_VERSION = 2   # v2+ visas med result.html / report_pdf.html

# SEO: startsidans andel av sidnivåpoängen; resten är undersidornas medelvärde
SEO_START_WEIGHT = 0.4
SEO_PAGE_MAX = 85      # titel, metabeskrivning, H1, viewport, Open Graph
SEO_SITE_MAX = 15      # robots.txt, sitemap

# PageSpeed: mobil väger tyngre (Google indexerar mobilversionen först)
PSP_WEIGHTS = {'mobile': 0.7, 'desktop': 0.3}

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

def title_key(seo: dict):
    """Jämförelsenyckel för sidtiteln (None om titel saknas)."""
    title = seo.get('title', {})
    if not title.get('found'):
        return None
    return ((title.get('value') or '').strip().lower(), title.get('length'))


def duplicate_titles(results) -> set:
    """Titlar som används på mer än en av de kontrollerade sidorna."""
    pages = [results.get('seo') or {}] + [p['seo'] for p in checked_subpages(results)]
    keys = [k for k in (title_key(s) for s in pages) if k]
    return {k for k in keys if keys.count(k) > 1}


def page_seo_points(seo: dict, duplicates: set = frozenset()) -> int:
    """
    Sidnivåns SEO-poäng för EN sida (max SEO_PAGE_MAX = 85):
      sidtitel 20 (finns 10 + unik bland de kontrollerade sidorna 10; längden är bara ett tips)
      metabeskrivning 30 (finns 20 + 50–160 tecken 10)
      H1 20 (finns 15 + exakt en 5)
      viewport 10
      Open Graph 5 (både og:title och og:image – låg prioritet)
    """
    pts = 0
    title = seo.get('title', {})
    if title.get('found'):
        pts += 10
        if title_key(seo) not in duplicates:
            pts += 10

    desc = seo.get('meta_description', {})
    if desc.get('found'):
        pts += 20
        if desc.get('ok'):        # 50–160 tecken
            pts += 10

    h1 = seo.get('h1', {})
    if h1.get('found'):
        pts += 15
        if h1.get('unique'):      # exakt 1 st
            pts += 5

    if seo.get('viewport', {}).get('found'):    pts += 10
    # Open Graph har låg prioritet (egen rad "Delning i sociala medier", inte i fyndlistan)
    if seo.get('og_title', {}).get('found') and seo.get('og_image', {}).get('found'):
        pts += 5
    return pts


def checked_subpages(results) -> list:
    """Undersidor som gick att hämta och analysera (fel och överhoppade räknas inte)."""
    return [p for p in results.get('pages') or [] if p.get('seo') and not p.get('error')]


def seo_breakdown(results) -> dict | None:
    """
    SEO = webbplatsnivå (robots.txt 10 + sitemap 5) + sidnivå (max 85), där
    sidnivån = startsidan 40 % + undersidornas medel 60 %. Utan undersidor
    räknas bara startsidan.
    """
    if not _has_html(results):
        return None
    seo = results.get('seo', {})
    site = 0
    if seo.get('robots_txt', {}).get('found'):  site += 10
    if seo.get('sitemap', {}).get('found'):     site += 5

    dups = duplicate_titles(results)
    start = page_seo_points(seo, dups)
    subs = [page_seo_points(p['seo'], dups) for p in checked_subpages(results)]
    if subs:
        sub_mean = sum(subs) / len(subs)
        page_part = SEO_START_WEIGHT * start + (1 - SEO_START_WEIGHT) * sub_mean
    else:
        sub_mean = None
        page_part = start
    return {
        'site': site,
        'start': start,
        'subpages_mean': round(sub_mean, 1) if sub_mean is not None else None,
        'subpages_count': len(subs),
        'start_weight': SEO_START_WEIGHT,
        'score': min(100, int(round(site + page_part))),
    }


def _score_seo(results):
    b = seo_breakdown(results)
    return b['score'] if b else None


# ── Prestanda (max 100) ───────────────────────────────────────────────────

def performance_source(results):
    """'pagespeed' om minst en PageSpeed-strategi gav poäng, 'basic' om vi har HTML, annars None."""
    if _psp_scores(results):
        return 'pagespeed'
    if _has_html(results) and results.get('http', {}).get('response_time_ms') is not None:
        return 'basic'
    return None


def pagespeed_breakdown(results) -> dict | None:
    """
    PageSpeed-poäng per strategi och viktad total (mobil 70 %, dator 30 %).
    Om bara en strategi gav poäng används den. 'weakest' anger vilken som drar
    ned totalen när skillnaden är minst 5 poäng.
    """
    psp = results.get('pagespeed') or {}
    scores = {s: (psp.get(s) or {}).get('score') for s in PSP_WEIGHTS}
    measured = {s: v for s, v in scores.items() if v is not None}
    if not measured:
        return None
    total_w = sum(PSP_WEIGHTS[s] for s in measured)
    score = int(round(sum(v * PSP_WEIGHTS[s] for s, v in measured.items()) / total_w))
    weakest = None
    if len(measured) == 2 and abs(measured['mobile'] - measured['desktop']) >= 5:
        weakest = min(measured, key=measured.get)
    return {'mobile': scores['mobile'], 'desktop': scores['desktop'],
            'weights': PSP_WEIGHTS, 'score': score, 'weakest': weakest}


def _score_performance(results):
    source = performance_source(results)
    if source == 'pagespeed':
        return pagespeed_breakdown(results)['score']
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
