"""
Presentationslogik för rapporter (v2): kategorinamn, vad varje kategori mäter
och om den är uppmätt. Används av webbrapporten, PDF:en och e-posten så att
de alltid säger samma sak.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from .scoring import (
    PSP_WEIGHTS, SEO_START_WEIGHT, WEIGHTS, checked_subpages, duplicate_titles, pagespeed_breakdown,
    performance_source, title_key,
)

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
    # v2: medelvärde av mobil och dator
    'performance_pagespeed_v2': (
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


# Etikett på kategorier som webbplatsägaren oftast inte kan åtgärda själv
_TAGS = {
    'headers': ('kräver serverinställning (ofta hos webbhotellet)',
                'requires server configuration (often at the web host)'),
}


def _version(results) -> int:
    return (results or {}).get('analyzer_version') or 1


def category_measures(key: str, results: dict, lang: str = 'sv') -> str:
    """Vad kategorin mäter – för v3 med den faktiska viktningen och antalet sidor."""
    i = 1 if lang == 'en' else 0
    results = results or {}
    v3 = _version(results) >= 3
    if key == 'performance':
        src = performance_source(results) or 'none'
        if src == 'pagespeed':
            if not v3:
                return _MEASURES['performance_pagespeed_v2'][i]
            m, d = round(PSP_WEIGHTS['mobile'] * 100), round(PSP_WEIGHTS['desktop'] * 100)
            return (f'Googles PageSpeed Insights-poäng (prestanda). Mobil väger {m} % och dator {d} %, '
                    'eftersom Google i första hand bedömer mobilversionen.',
                    f'Google PageSpeed Insights performance score. Mobile weighs {m} % and desktop {d} %, '
                    'since Google primarily assesses the mobile version.')[i]
        return _MEASURES[f'performance_{src}'][i]
    if key == 'seo' and v3:
        n = len(checked_subpages(results))
        start = round(SEO_START_WEIGHT * 100)
        if n:
            return (f'Mäter sidtitel, metabeskrivning, H1, viewport och Open Graph på startsidan ({start} %) och '
                    f'på {n} undersidor ({100 - start} %, medelvärde), samt robots.txt och sitemap för hela webbplatsen.',
                    f'Measures page title, meta description, H1, viewport and Open Graph on the home page ({start} %) and '
                    f'on {n} subpages ({100 - start} %, average), plus robots.txt and sitemap for the whole site.')[i]
        return ('Mäter sidtitel, metabeskrivning, H1, viewport och Open Graph på startsidan (inga undersidor '
                'kunde kontrolleras), samt robots.txt och sitemap.',
                'Measures page title, meta description, H1, viewport and Open Graph on the home page (no subpages '
                'could be checked), plus robots.txt and sitemap.')[i]
    return _MEASURES[key][i]


def category_tag(key: str, lang: str = 'sv') -> str:
    tag = _TAGS.get(key)
    return tag[1 if lang == 'en' else 0] if tag else ''


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
            'tag': '' if legacy else category_tag(key, lang),
        })
    return out


# ── Fynd över alla kontrollerade sidor ─────────────────────────────────────

_SEVERITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2}

# (nyckel, allvarlighet, test på en sidas SEO-resultat, text sv, text en)
_PAGE_CHECKS = [
    ('title_missing', 'critical', lambda s: not s.get('title', {}).get('found'),
     'Sidtitel saknas', 'Page title missing'),
    ('desc_missing', 'high', lambda s: not s.get('meta_description', {}).get('found'),
     'Metabeskrivning saknas', 'Meta description missing'),
    ('h1_missing', 'high', lambda s: not s.get('h1', {}).get('found'),
     'H1-rubrik saknas', 'H1 heading missing'),
    ('h1_multiple', 'medium', lambda s: (s.get('h1', {}).get('count') or 0) > 1,
     'Fler än en H1-rubrik', 'More than one H1 heading'),
    ('desc_length', 'medium',
     lambda s: s.get('meta_description', {}).get('found') and not s.get('meta_description', {}).get('ok'),
     'Metabeskrivningen har inte 50–160 tecken', 'Meta description is not 50–160 characters'),
]


# Förklaring som visas efter fyndet
_HINTS = {
    'title_missing': ('sökmotorer vet inte vad sidan handlar om',
                      "search engines don't know what the page is about"),
    'desc_missing': ('ingen egen beskrivning är satt, så Google väljer själv vilken text från sidan som visas i sökresultaten',
                     'no description is set, so Google picks text from the page itself for search results'),
    'alt_missing': ('bilderna är osynliga för skärmläsare', 'the images are invisible to screen readers'),
    'title_duplicate': ('varje sida bör ha en egen titel så att den kan visas och hittas för sig i Google',
                        'each page should have its own title so it can be shown and found on its own in Google'),
}


def _where(count: int, total: int, en: bool) -> str:
    if total == 1:
        return ('on the home page, the only page checked' if en
                else 'på startsidan, den enda sida som kontrollerades')
    return (f'on {count} of the {total} pages checked' if en
            else f'på {count} av de {total} sidor som kontrollerades')


def _checked_pages(results):
    start_url = (results.get('http') or {}).get('final_url') or ''
    pages = [(start_url, results['seo'], results.get('accessibility') or {})]
    pages += [(p['url'], p['seo'], p.get('accessibility') or {}) for p in checked_subpages(results)]
    return pages


def site_findings(results: dict, lang: str = 'sv') -> list:
    """
    SEO- och alt-textfynd räknade över startsidan och alla undersidor som gick
    att kontrollera, t.ex. "Metabeskrivning saknas på 3 av de 11 sidor som
    kontrollerades". Varje fynd har listan över berörda sidor.
    """
    results = results or {}
    if not results.get('seo'):
        return []
    en = lang == 'en'
    pages = _checked_pages(results)
    total = len(pages)

    findings = []
    for key, severity, failing, sv, en_text in _PAGE_CHECKS:
        urls = [url for url, seo, _ in pages if failing(seo)]
        if urls:
            findings.append({
                'key': key, 'severity': severity, 'pages': urls,
                'text': f'{en_text if en else sv} {_where(len(urls), total, en)}',
                'hint': _HINTS.get(key, ('', ''))[1 if en else 0],
            })

    dups = duplicate_titles(results)
    dup_urls = [url for url, seo, _ in pages if title_key(seo) in dups]
    if dup_urls:
        findings.append({
            'key': 'title_duplicate', 'severity': 'medium', 'pages': dup_urls,
            'text': (f'The same page title is used on {len(dup_urls)} of the {total} pages checked' if en
                     else f'Samma sidtitel används på {len(dup_urls)} av de {total} sidor som kontrollerades'),
            'hint': _HINTS['title_duplicate'][1 if en else 0],
        })

    alt_pages = [(url, (a11y.get('images') or {}).get('missing_alt') or 0) for url, _, a11y in pages]
    alt_pages = [(u, n) for u, n in alt_pages if n]
    if alt_pages:
        n_images = sum(n for _, n in alt_pages)
        what = (f'{n_images} image{"s" if n_images != 1 else ""} without an alt attribute' if en
                else f'{n_images} bild{"er" if n_images != 1 else ""} utan alt-attribut')
        findings.append({
            'key': 'alt_missing', 'severity': 'medium', 'pages': [u for u, _ in alt_pages],
            'text': f'{what} {_where(len(alt_pages), total, en)}',
            'hint': _HINTS['alt_missing'][1 if en else 0],
        })

    findings.sort(key=lambda f: _SEVERITY_ORDER[f['severity']])
    return findings


def site_tips(results: dict, lang: str = 'sv') -> dict:
    """
    Lågprioriterade iakttagelser som INTE hör hemma i "Viktigast att åtgärda":
      social – Open Graph (titel/bild vid delning i sociala medier) per sida
      title_length – sidtitlar kortare än 30 eller längre än 60 tecken (ingår inte i poängen)
    """
    results = results or {}
    if not results.get('seo'):
        return {}
    en = lang == 'en'
    pages = _checked_pages(results)
    total = len(pages)

    og_missing = [url for url, s, _ in pages
                  if not (s.get('og_title', {}).get('found') and s.get('og_image', {}).get('found'))]
    if og_missing:
        social = {'ok': False, 'pages': og_missing,
                  'text': (f'Open Graph (title and image shown when the page is shared) is missing '
                           f'{_where(len(og_missing), total, en)}' if en else
                           f'Open Graph (titel och bild som visas när sidan delas) saknas '
                           f'{_where(len(og_missing), total, en)}')}
    else:
        social = {'ok': True, 'pages': [],
                  'text': ('Open Graph is set on all pages checked' if en
                           else 'Open Graph finns på alla sidor som kontrollerades')}

    short = [url for url, s, _ in pages if s.get('title', {}).get('found') and (s['title'].get('length') or 0) < 30]
    long_ = [url for url, s, _ in pages if s.get('title', {}).get('found') and (s['title'].get('length') or 0) > 60]
    title_tips = []
    if short:
        title_tips.append({'pages': short, 'text': (
            f'The page title is shorter than 30 characters {_where(len(short), total, en)} – '
            'a slightly longer title can describe the page better in search results' if en else
            f'Sidtiteln är kortare än 30 tecken {_where(len(short), total, en)} – '
            'en något längre titel kan beskriva sidan bättre i sökresultaten')})
    if long_:
        title_tips.append({'pages': long_, 'text': (
            f'The page title is longer than 60 characters {_where(len(long_), total, en)} – '
            'Google may shorten it in search results' if en else
            f'Sidtiteln är längre än 60 tecken {_where(len(long_), total, en)} – '
            'Google kan korta av den i sökresultaten')})
    return {'social': social, 'title_length': title_tips}


_LOCAL_TZ = ZoneInfo('Europe/Stockholm')


def _measured_at(psp: dict, lang: str) -> str:
    """Senaste tidpunkten då Google mätte (fetchTime), i svensk tid. Tom om den saknas (t.ex. v2)."""
    times = []
    for strategy in ('mobile', 'desktop'):
        raw = (psp.get(strategy) or {}).get('fetch_time')
        try:
            times.append(datetime.fromisoformat(raw.replace('Z', '+00:00')))
        except (AttributeError, ValueError):
            continue
    if not times:
        return ''
    local = max(times).astimezone(_LOCAL_TZ)
    return local.strftime('%Y-%m-%d %H:%M') + (' (Swedish time)' if lang == 'en' else ' (svensk tid)')


def pagespeed_summary(results: dict, lang: str = 'sv') -> dict | None:
    """Mobil och dator var för sig, vilken som drar ned totalen och när Google mätte."""
    b = pagespeed_breakdown(results or {})
    if not b:
        return None
    en = lang == 'en'
    names = {'mobile': ('mobil', 'mobile'), 'desktop': ('dator', 'desktop')}
    weakest_text = ''
    if b['weakest']:
        name = names[b['weakest']][1 if en else 0]
        weakest_text = (f'{name.capitalize()} ({b[b["weakest"]]}) pulls the result down' if en
                        else f'{name.capitalize()} ({b[b["weakest"]]}) drar ned resultatet')
    return {**b, 'weakest_text': weakest_text,
            'measured_at': _measured_at((results or {}).get('pagespeed') or {}, lang),
            'variation_text': ('Google’s values vary between measurements, sometimes by more than 10 points. '
                               'Look at the trend over time rather than single scores.' if en else
                               'Googles värden varierar mellan mätningar, ibland mer än 10 poäng. '
                               'Se hellre trenden över tid än enstaka poäng.')}


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
