from urllib.parse import urlparse, urljoin
import requests

_UA = 'Mozilla/5.0 (compatible; JDFAnalyser/1.0; +https://johans-digital-forge.se)'
_TIMEOUT = 8
_IMAGE_LIMIT_BYTES = 500 * 1024   # 500 KB
_MAX_IMG_TO_CHECK = 20            # cap HEAD-anrop för att hålla nere analystiden


def check_performance(base_url: str, soup) -> dict:
    """Externa resurser och grundläggande bildoptimering."""
    parsed = urlparse(base_url)
    base_netloc = parsed.netloc

    ext_css = _count_external(soup, 'link', 'href', rel='stylesheet',
                               base_netloc=base_netloc)
    ext_js  = _count_external(soup, 'script', 'src', rel=None,
                               base_netloc=base_netloc)
    imgs    = _check_images(soup, base_url)

    return {
        'external_css': ext_css,
        'external_js':  ext_js,
        'total_external_resources': ext_css + ext_js,
        'images_total':          imgs['total'],
        'images_without_alt':    imgs['without_alt'],
        'images_large':          imgs['large'],
        'images_checked_for_size': imgs['checked'],
    }


# ── helpers ────────────────────────────────────────────────────────────────

def _is_external(href: str, base_netloc: str) -> bool:
    if not href or href.startswith('data:') or href.startswith('#'):
        return False
    if href.startswith('//'):
        return True
    if href.startswith('http'):
        return base_netloc not in urlparse(href).netloc
    return False


def _count_external(soup, tag, attr, rel, base_netloc):
    count = 0
    find_kwargs = {}
    if rel:
        find_kwargs['rel'] = rel
    for el in soup.find_all(tag, **find_kwargs):
        href = el.get(attr, '')
        if _is_external(href, base_netloc):
            count += 1
    return count


def _check_images(soup, base_url):
    imgs = soup.find_all('img')
    total = len(imgs)
    without_alt = sum(1 for img in imgs if not img.get('alt', '').strip())

    large = 0
    checked = 0
    for img in imgs[:_MAX_IMG_TO_CHECK]:
        src = img.get('src', '') or img.get('data-src', '')
        if not src or src.startswith('data:'):
            continue
        img_url = urljoin(base_url, src)
        try:
            head = requests.head(
                img_url,
                timeout=_TIMEOUT,
                headers={'User-Agent': _UA},
                allow_redirects=True,
            )
            cl = int(head.headers.get('Content-Length', 0))
            if cl > _IMAGE_LIMIT_BYTES:
                large += 1
            checked += 1
        except Exception:
            pass

    return {'total': total, 'without_alt': without_alt, 'large': large, 'checked': checked}
