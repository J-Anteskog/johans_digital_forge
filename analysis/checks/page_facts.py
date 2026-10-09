"""
Fakta om sidan som flera kategorier använder. Beräknas EN gång per sida och
sparas i results['images'] / results['resources'], så att prestanda,
mobil och tillgänglighet alltid visar samma siffror.
"""

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from bs4.dammit import EncodingDetector

_MAX_LISTED = 10   # max antal URL:er som sparas per lista i rapporten
_LAZY_SRC_ATTRS = ('src', 'data-src', 'data-lazy-src', 'data-original')
_NON_JS_TYPES = {'application/ld+json', 'application/json', 'text/template',
                 'text/x-template', 'text/html', 'importmap', 'speculationrules'}


def parse_html(content: bytes, declared_encoding: str | None = None):
    """
    Parsar HTML från råa bytes med samma ordning som webbläsare:
    HTTP-headerns charset → <meta charset> → UTF-8 om giltigt → windows-1252.
    (Tidigare användes requests standardgissning ISO-8859-1 när headern saknade
    charset, vilket gav fel tecken på UTF-8-sidor.)
    """
    encoding = declared_encoding or EncodingDetector.find_declared_encoding(content, is_html=True)
    if not encoding:
        try:
            content.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            encoding = 'windows-1252'
    return BeautifulSoup(content, 'lxml', from_encoding=encoding)


# ── Bilder ────────────────────────────────────────────────────────────────

def image_src(img) -> str:
    """src, eller lazy-load-attributet om src saknas/är en data:-platshållare."""
    src = (img.get('src') or '').strip()
    if not src or src.startswith('data:'):
        for attr in _LAZY_SRC_ATTRS[1:]:
            v = (img.get(attr) or '').strip()
            if v:
                return v
    return src


def analyze_images(soup, base_url: str = '') -> dict:
    """
    Klassar varje <img>:
      - missing_alt:  alt-attribut saknas helt (fel)
      - decorative:   alt="" eller role=presentation/none eller aria-hidden=true
                      (korrekt för dekorativa bilder – kan inte avgöras automatiskt
                      om bilden verkligen är dekorativ)
      - with_alt:     alt med text
    """
    imgs = soup.find_all('img')
    missing, decorative, with_alt = [], [], []
    for img in imgs:
        src = image_src(img)
        label = urljoin(base_url, src) if (base_url and src and not src.startswith('data:')) else (src[:60] or '(utan src)')
        role = (img.get('role') or '').strip().lower()
        hidden = (img.get('aria-hidden') or '').strip().lower() == 'true'
        if img.has_attr('alt'):
            if img['alt'].strip():
                with_alt.append(label)
            else:
                decorative.append(label)
        elif role in ('presentation', 'none') or hidden:
            decorative.append(label)
        elif (img.get('aria-label') or '').strip() or (img.get('aria-labelledby') or '').strip():
            with_alt.append(label)
        else:
            missing.append(label)

    return {
        'total': len(imgs),
        'with_alt': len(with_alt),
        'decorative': len(decorative),
        'missing_alt': len(missing),
        'missing_alt_examples': missing[:_MAX_LISTED],
        'decorative_examples': decorative[:_MAX_LISTED],
    }


# ── CSS/JS-resurser ───────────────────────────────────────────────────────

def site_host(netloc_or_url: str) -> str:
    host = urlparse(netloc_or_url).hostname if '://' in netloc_or_url else netloc_or_url.split(':')[0]
    host = (host or '').lower().rstrip('.')
    return host[4:] if host.startswith('www.') else host


def is_same_site(url: str, base_url: str) -> bool:
    """Samma värd (www. räknas som samma) eller en underdomän till den."""
    h, b = site_host(url), site_host(base_url)
    return bool(h) and (h == b or h.endswith('.' + b))


def _rel(el) -> list:
    rel = el.get('rel') or []
    if isinstance(rel, str):
        rel = rel.split()
    return [r.lower() for r in rel]


def analyze_resources(soup, base_url: str) -> dict:
    """
    Räknar CSS- och JS-filer som sidan laddar, oavsett om adressen är
    relativ, absolut eller protokollrelativ. Stilmallar som laddas in i
    efterhand via data-href (vanligt i WordPress-teman) räknas också.
    """
    css, js = [], []
    seen = set()

    for link in soup.find_all('link'):
        rel = _rel(link)
        is_css = 'stylesheet' in rel or ('preload' in rel and (link.get('as') or '').lower() == 'style')
        if not is_css:
            continue
        href = (link.get('href') or '').strip() or (link.get('data-href') or '').strip()
        if not href or href.startswith('data:'):
            continue
        absolute = urljoin(base_url, href)
        if absolute in seen:
            continue
        seen.add(absolute)
        css.append(absolute)

    inline_data_scripts = 0
    render_blocking = []
    head = soup.head
    for script in soup.find_all('script'):
        src = (script.get('src') or '').strip()
        stype = (script.get('type') or '').strip().lower()
        if stype in _NON_JS_TYPES:
            continue
        if not src:
            continue
        if src.startswith('data:'):
            inline_data_scripts += 1
            continue
        absolute = urljoin(base_url, src)
        if absolute in seen:
            continue
        seen.add(absolute)
        js.append(absolute)
        in_head = head is not None and head in script.parents
        deferred = script.has_attr('async') or script.has_attr('defer') or stype == 'module'
        if in_head and not deferred:
            render_blocking.append(absolute)

    css_same = [u for u in css if is_same_site(u, base_url)]
    js_same = [u for u in js if is_same_site(u, base_url)]
    css_third = [u for u in css if u not in css_same]
    js_third = [u for u in js if u not in js_same]

    return {
        'css_files': len(css),
        'js_files': len(js),
        'total_files': len(css) + len(js),
        'css_same_site': len(css_same),
        'css_third_party': len(css_third),
        'js_same_site': len(js_same),
        'js_third_party': len(js_third),
        'third_party_hosts': sorted({site_host(u) for u in css_third + js_third}),
        'inline_data_scripts': inline_data_scripts,
        'render_blocking_scripts': len(render_blocking),
        'render_blocking_examples': render_blocking[:_MAX_LISTED],
        'css_urls': css[:30],
        'js_urls': js[:30],
    }
