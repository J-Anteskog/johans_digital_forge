from urllib.parse import urlparse
import requests

_UA = 'Mozilla/5.0 (compatible; JDFAnalyser/1.0; +https://johans-digital-forge.se)'
_TIMEOUT = 10


def check_seo(base_url: str, soup) -> dict:
    """Kör alla SEO-kontroller på en färdigparsad BeautifulSoup-instans."""
    return {
        'viewport':         _check_viewport(soup),
        'title':            _check_title(soup),
        'meta_description': _check_meta_description(soup),
        'h1':               _check_h1(soup),
        'og_title':         _check_og(soup, 'og:title'),
        'og_image':         _check_og(soup, 'og:image'),
        'robots_txt':       _check_robots_txt(base_url),
        'sitemap':          _check_sitemap(base_url),
    }


def _check_viewport(soup):
    tag = soup.find('meta', attrs={'name': 'viewport'})
    return {
        'found': tag is not None,
        'value': tag.get('content', '') if tag else None,
    }


def _check_title(soup):
    tag = soup.find('title')
    value = tag.get_text(strip=True) if tag else ''
    length = len(value)
    return {
        'found': bool(value),
        'value': value[:80],
        'length': length,
        'ok': 30 <= length <= 60,
    }


def _check_meta_description(soup):
    tag = soup.find('meta', attrs={'name': 'description'})
    value = tag.get('content', '').strip() if tag else ''
    length = len(value)
    return {
        'found': bool(value),
        'value': value[:200],
        'length': length,
        'ok': 50 <= length <= 160,
    }


def _check_h1(soup):
    h1s = soup.find_all('h1')
    texts = [h.get_text(strip=True) for h in h1s]
    return {
        'found': len(h1s) > 0,
        'count': len(h1s),
        'unique': len(h1s) == 1,
        'value': texts[0][:100] if texts else None,
    }


def _check_og(soup, property_name):
    # BeautifulSoup hittar ibland inte property= direkt; testa båda sätten
    tag = soup.find('meta', property=property_name) or \
          soup.find('meta', attrs={'property': property_name})
    value = tag.get('content', '').strip() if tag else ''
    return {
        'found': bool(value),
        'value': value[:200] if value else None,
    }


def _check_robots_txt(base_url):
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = requests.get(
            robots_url,
            timeout=_TIMEOUT,
            headers={'User-Agent': _UA},
            allow_redirects=True,
        )
        found = resp.status_code == 200
        sitemap_ref = 'sitemap' in resp.text.lower() if found else False
        return {'found': found, 'url': robots_url, 'sitemap_referenced': sitemap_ref}
    except Exception:
        return {'found': False, 'url': robots_url, 'sitemap_referenced': False}


def _check_sitemap(base_url):
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [
        f"{base}/sitemap.xml",
        f"{base}/sitemap_index.xml",
        f"{base}/sitemap/",
    ]
    for sitemap_url in candidates:
        try:
            resp = requests.get(
                sitemap_url,
                timeout=_TIMEOUT,
                headers={'User-Agent': _UA},
                allow_redirects=True,
            )
            if resp.status_code == 200:
                return {'found': True, 'url': sitemap_url}
        except Exception:
            pass
    return {'found': False, 'url': candidates[0]}
