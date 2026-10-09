from urllib.parse import urljoin

from ..net import BlockedAddressError, safe_request
from .page_facts import image_src

_TIMEOUT = 8
_IMAGE_LIMIT_BYTES = 500 * 1024   # 500 KB
_MAX_IMG_TO_CHECK = 20            # cap HEAD-anrop för att hålla nere analystiden


def check_performance(base_url: str, soup, session=None) -> dict:
    """
    Bildstorlekar via HEAD (Content-Length). Antal CSS/JS-filer, svarstid och
    HTML-storlek finns i results['resources'] resp. results['http'].
    Bilder vars storlek servern inte anger räknas som "okänd", inte som små.
    """
    large, checked, unknown, blocked = [], 0, 0, 0
    seen = set()
    for img in soup.find_all('img'):
        if len(seen) >= _MAX_IMG_TO_CHECK:
            break
        src = image_src(img)
        if not src or src.startswith('data:'):
            continue
        img_url = urljoin(base_url, src)
        if img_url in seen:
            continue
        seen.add(img_url)
        try:
            head = safe_request('HEAD', img_url, timeout=_TIMEOUT, session=session)
            cl = head.headers.get('Content-Length')
            if head.status_code >= 400 or cl is None or not cl.isdigit():
                unknown += 1
                continue
            checked += 1
            if int(cl) > _IMAGE_LIMIT_BYTES:
                large.append({'url': img_url, 'kb': int(cl) // 1024})
        except BlockedAddressError:
            blocked += 1
        except Exception:
            unknown += 1

    return {
        'images_large': len(large),
        'images_large_examples': large[:10],
        'images_checked_for_size': checked,
        'images_size_unknown': unknown,
        'images_blocked': blocked,
        'images_size_limit_kb': _IMAGE_LIMIT_BYTES // 1024,
    }
