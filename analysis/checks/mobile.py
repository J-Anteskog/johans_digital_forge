"""
Mobilanpassning – bara det som går att avgöra från HTML och CSS utan att
rendera sidan. Varje delkontroll får status:
  'pass' / 'fail'      – uppmätt
  'not_measured'       – kunde inte avgöras (t.ex. CSS gick inte att läsa)
  'not_applicable'     – gäller inte sidan (t.ex. inga bilder)
Poängen räknas bara på uppmätta delkontroller. Klickytor och faktisk
textstorlek kräver rendering och redovisas alltid som ej mätta – därför är
poängen högst MAX_SCORE (90), även när alla grundkontroller är godkända.
"""

import re

from .page_facts import image_src

_MAX_STYLESHEETS = 6
_MAX_CSS_BYTES = 1_000_000

_MEDIA_WIDTH_RE = re.compile(r'@media[^{]*\(\s*(?:min|max)-(?:device-)?width', re.I)
_IMG_MAX_WIDTH_RE = re.compile(r'(?:^|[},;\s>])img\s*(?:,[^{]*)?\{[^}]*max-width\s*:', re.I)

POINTS = {
    'viewport': 40,
    'zoom': 20,
    'media_queries': 20,
    'images_scale': 20,
}

NOT_MEASURED_ALWAYS = ['tap_targets', 'text_size']

# En godkänd grundkontroll ska inte se ut som full pott: klickytor och
# textstorlek är inte mätta.
MAX_SCORE = 90


def _parse_viewport(content: str) -> dict:
    out = {}
    for part in re.split(r'[,;]', content or ''):
        if '=' in part:
            k, v = part.split('=', 1)
            out[k.strip().lower()] = v.strip().lower()
    return out


def _read_css(soup, resources, session) -> tuple[str, int, int]:
    """Inline <style> + upp till _MAX_STYLESHEETS stilmallar. Returnerar (css, lästa, totalt)."""
    from ..net import fetch_limited  # sen import: gör modulen testbar utan nätverk

    css = '\n'.join(s.get_text() for s in soup.find_all('style'))
    urls = (resources or {}).get('css_urls', [])
    read = 0
    for url in urls[:_MAX_STYLESHEETS]:
        res = fetch_limited(url, max_bytes=_MAX_CSS_BYTES, timeout=(5, 8), session=session)
        if res.status_code and res.status_code < 400 and res.content:
            css += '\n' + res.content.decode(res.encoding or 'utf-8', errors='replace')
            read += 1
    return css, read, len(urls)


def check_mobile(soup, resources: dict, session=None, css_reader=None) -> dict:
    checks = {}

    # 1. Viewport med device-width
    tag = soup.find('meta', attrs={'name': re.compile(r'^viewport$', re.I)})
    vp_content = tag.get('content', '') if tag else ''
    vp = _parse_viewport(vp_content)
    checks['viewport'] = {
        'status': 'pass' if vp.get('width') == 'device-width' else 'fail',
        'found': tag is not None,
        'value': vp_content[:200] if tag else None,
    }

    # 2. Zoom inte blockerad (samma gräns som Lighthouse: maximum-scale < 5 eller user-scalable=no)
    blocked_reasons = []
    if vp.get('user-scalable') in ('no', '0'):
        blocked_reasons.append('user-scalable=no')
    try:
        if 'maximum-scale' in vp and float(vp['maximum-scale']) < 5:
            blocked_reasons.append(f"maximum-scale={vp['maximum-scale']}")
    except ValueError:
        pass
    checks['zoom'] = {
        'status': 'fail' if blocked_reasons else 'pass',
        'blocked_by': blocked_reasons,
    }

    # CSS behövs för 3 och 4
    reader = css_reader or _read_css
    css, read, total = reader(soup, resources, session)
    all_css_read = read == total
    link_media = any(
        _MEDIA_WIDTH_RE.search('@media ' + (l.get('media') or '') + '{')
        for l in soup.find_all('link') if l.get('media')
    )

    # 3. Media queries för skärmbredd
    if link_media or _MEDIA_WIDTH_RE.search(css):
        mq_status = 'pass'
    elif all_css_read:
        mq_status = 'fail'
    else:
        mq_status = 'not_measured'
    checks['media_queries'] = {
        'status': mq_status,
        'stylesheets_read': read,
        'stylesheets_total': total,
    }

    # 4. Bilder som kan skala: width+height, srcset eller en img { max-width } i CSS
    imgs = [i for i in soup.find_all('img') if image_src(i)]
    css_img_rule = bool(_IMG_MAX_WIDTH_RE.search(css))
    not_ok = [
        i for i in imgs
        if not ((i.get('width') and i.get('height')) or i.get('srcset') or css_img_rule)
    ]
    if not imgs:
        img_status = 'not_applicable'
    elif not not_ok:
        img_status = 'pass'
    elif all_css_read:
        img_status = 'fail'
    else:
        img_status = 'not_measured'
    checks['images_scale'] = {
        'status': img_status,
        'total': len(imgs),
        'without_size_or_rule': len(not_ok),
        'css_max_width_rule': css_img_rule,
    }

    earned = possible = 0
    for key, chk in checks.items():
        chk['points'] = POINTS[key]
        if chk['status'] in ('pass', 'fail'):
            possible += POINTS[key]
            if chk['status'] == 'pass':
                earned += POINTS[key]

    return {
        'checks': checks,
        'not_measured': [k for k, c in checks.items() if c['status'] == 'not_measured'] + NOT_MEASURED_ALWAYS,
        'points_measured': possible,
        'basic_passed': bool(possible) and earned == possible,
        'score': min(MAX_SCORE, round(100 * earned / possible)) if possible else None,
    }
