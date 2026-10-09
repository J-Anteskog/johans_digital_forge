"""
Presentationslogik för rapporter (v2): kategorinamn, vad varje kategori mäter
och om den är uppmätt. Används av webbrapporten, PDF:en och e-posten så att
de alltid säger samma sak.
"""

from .scoring import WEIGHTS, performance_source

_COLORS = {
    'security': '#ffc107',
    'seo': '#6f42c1',
    'performance': '#0d6efd',
    'mobile': '#20c997',
    'headers': '#fd7e14',
    'accessibility': '#0dcaf0',
}

_LABELS = {
    'security':      ('HTTPS och certifikat', 'HTTPS & certificate'),
    'seo':           ('SEO', 'SEO'),
    'mobile':        ('Mobilanpassning (grundkontroll)', 'Mobile-friendliness (basic check)'),
    'headers':       ('Säkerhetsheaders', 'Security headers'),
    'accessibility': ('Tillgänglighet (grundkontroll)', 'Accessibility (basic check)'),
}

_MEASURES = {
    'security': (
        'Mäter att sidan serveras via HTTPS, att certifikatet är giltigt och att det inte går ut inom 30 dagar. '
        'Säkerhetsheaders bedöms i en egen kategori.',
        'Measures that the site is served over HTTPS, that the certificate is valid and not expiring within 30 days. '
        'Security headers are scored separately.',
    ),
    'seo': (
        'Mäter sidtitel, metabeskrivning, H1, viewport, Open Graph, robots.txt och sitemap.',
        'Measures page title, meta description, H1, viewport, Open Graph, robots.txt and sitemap.',
    ),
    'performance_pagespeed': (
        'Googles PageSpeed Insights-poäng (prestanda), medelvärde av mobil och dator.',
        "Google PageSpeed Insights performance score, average of mobile and desktop.",
    ),
    'performance_basic': (
        'PageSpeed kunde inte användas. Poängen bygger bara på det vi mäter från vår server: svarstid för '
        'HTML-dokumentet, HTML-storlek, antal CSS/JS-filer och skript som blockerar visningen. '
        'Den säger inte hur snabbt sidan visas i en webbläsare.',
        'PageSpeed was not available. The score is based only on what we measure from our server: HTML response '
        'time, HTML size, number of CSS/JS files and render-blocking scripts. '
        'It does not tell how fast the page renders in a browser.',
    ),
    'performance_none': (
        'Kunde inte mätas – sidan gick inte att hämta.',
        'Could not be measured – the page could not be fetched.',
    ),
    'mobile': (
        'Kontrollerat: viewport, att zoom inte är blockerad, media queries i CSS och att bilder kan skala. '
        'Ej mätt: klickytornas storlek och faktisk textstorlek (kräver rendering i webbläsare). '
        'Därför är poängen högst 90.',
        'Checked: viewport, zoom not blocked, media queries in CSS and scalable images. '
        'Not measured: tap target size and actual text size (requires rendering in a browser). '
        'The score is therefore capped at 90.',
    ),
    'headers': (
        'Mäter vilka säkerhetsrelaterade HTTP-headers servern skickar (HSTS, CSP m.fl.).',
        'Measures which security-related HTTP headers the server sends (HSTS, CSP etc.).',
    ),
    'accessibility': (
        'Automatiska grundkontroller i HTML-koden: språk, landmärken, skip-länk, rubrikstruktur, alt-texter '
        'och klickbara element. Ersätter inte en manuell granskning.',
        'Automated basic checks of the HTML: language, landmarks, skip link, heading structure, alt texts '
        'and clickable elements. Does not replace a manual review.',
    ),
}


def category_label(key: str, results: dict, lang: str = 'sv') -> str:
    i = 1 if lang == 'en' else 0
    if key == 'performance':
        src = performance_source(results or {})
        if src == 'pagespeed':
            return ('Prestanda (PageSpeed)', 'Performance (PageSpeed)')[i]
        if src == 'basic':
            return ('Sidvikt och svarstid', 'Page weight & response time')[i]
        return ('Prestanda', 'Performance')[i]
    return _LABELS[key][i]


def category_measures(key: str, results: dict, lang: str = 'sv') -> str:
    i = 1 if lang == 'en' else 0
    if key == 'performance':
        src = performance_source(results or {}) or 'none'
        return _MEASURES[f'performance_{src}'][i]
    return _MEASURES[key][i]


_LEGACY_LABELS = {
    'security':      ('Säkerhet', 'Security'),
    'seo':           ('SEO', 'SEO'),
    'performance':   ('Prestanda', 'Performance'),
    'mobile':        ('Mobilanpassning', 'Mobile'),
    'headers':       ('Säkerhetsheaders', 'Security headers'),
    'accessibility': ('Tillgänglighet', 'Accessibility'),
}


def build_categories(obj) -> list:
    """
    Lista med en post per kategori, i rapportens ordning.
    Rapporter från äldre version får de namn de hade när de skapades.
    """
    results = obj.results or {}
    lang = obj.language
    legacy = obj.is_legacy
    out = []
    for key in WEIGHTS:
        score = getattr(obj, f'score_{key}')
        if legacy:
            label = _LEGACY_LABELS[key][1 if lang == 'en' else 0]
            measures = ''
        else:
            label = category_label(key, results, lang)
            measures = category_measures(key, results, lang)
        out.append({
            'key': key,
            'label': label,
            'measures': measures,
            'score': score,
            'measured': score is not None,
            'color': _COLORS[key],
        })
    return out


def pagespeed_status_text(results: dict, lang: str = 'sv') -> str:
    """Varför PageSpeed inte användes – visas i rapporten."""
    psp = (results or {}).get('pagespeed') or {}
    en = lang == 'en'
    status = psp.get('status')
    if status == 'not_configured':
        return 'PageSpeed API is not configured on our server.' if en else \
            'PageSpeed API är inte konfigurerat på vår server.'
    if status in ('failed', 'partial'):
        parts = []
        for strategy, name_sv, name_en in (('mobile', 'mobil', 'mobile'), ('desktop', 'dator', 'desktop')):
            r = psp.get(strategy) or {}
            if r.get('score') is not None:
                continue
            kind = r.get('error_kind')
            if kind == 'http':
                reason = f" ({r['reason']})" if r.get('reason') else ''
                detail = f"HTTP {r.get('http_status')}{reason}"
            elif kind == 'timeout':
                detail = (f"timeout after {r.get('timeout_s')} s" if en
                          else f"timeout efter {r.get('timeout_s')} s")
            else:
                detail = r.get('error') or ('unknown error' if en else 'okänt fel')
            parts.append(f"{name_en if en else name_sv}: {detail}")
        prefix = 'PageSpeed failed' if en else 'PageSpeed misslyckades'
        return f"{prefix} – {', '.join(parts)}." if parts else ''
    return ''
