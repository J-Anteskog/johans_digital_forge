import re

from .page_facts import analyze_images

# HTML5-element och motsvarande ARIA-roller
_LANDMARK_ROLES = {
    'main': 'main',
    'nav': 'navigation',
    'header': 'banner',
    'footer': 'contentinfo',
    'aside': 'complementary',
}
_SKIP_TEXT_RE = re.compile(r'skip|hoppa|gå (direkt )?till|till (huvud)?innehåll|jump to|main content', re.I)
_SKIP_LINK_POSITION = 5   # skip-länken ska vara bland de första länkarna på sidan

POINTS = {
    'lang': 15,
    'landmark_main': 10,
    'landmark_other': 5,
    'skip_nav': 10,
    'h1': 10,
    'heading_order': 10,
    'empty_headings': 5,
    'images_alt': 20,
    'interactive_divs': 15,
}


def check_accessibility(soup, images: dict | None = None) -> dict:
    """
    Grundläggande tillgänglighetskontroll baserad på parsad HTML.
    images: resultat från page_facts.analyze_images() – skickas in så att
    alt-texter räknas på exakt samma sätt i hela rapporten.
    """
    if images is None:
        images = analyze_images(soup)

    result = {
        'lang': _check_lang(soup),
        'landmarks': _check_landmarks(soup),
        'skip_nav': _check_skip_nav(soup),
        'headings': _check_headings(soup),
        'images': images,
        'interactive_divs': _check_interactive_divs(soup),
    }

    lm = result['landmarks']
    hd = result['headings']
    passed = {
        'lang': result['lang']['found'],
        'landmark_main': lm['has_main'],
        'landmark_other': bool(set(lm['found']) - {'main'}),
        'skip_nav': result['skip_nav']['found'],
        'h1': hd['h1_count'] >= 1,
        'heading_order': not hd['skipped_levels'],
        'empty_headings': hd['empty_count'] == 0,
        'images_alt': images['missing_alt'] == 0,
        'interactive_divs': result['interactive_divs']['count'] == 0,
    }
    result['passed'] = passed
    result['score'] = sum(POINTS[k] for k, ok in passed.items() if ok)
    return result


def _check_lang(soup):
    html_tag = soup.find('html')
    value = (html_tag.get('lang') or '').strip() if html_tag else ''
    return {'found': bool(value), 'value': value}


def _check_landmarks(soup):
    """Hittar landmärken både som HTML5-element och som role-attribut."""
    found = []
    via = {}
    for name, role in _LANDMARK_ROLES.items():
        el = soup.find(name) or soup.find(attrs={'role': re.compile(rf'^\s*{role}\s*$', re.I)})
        if el is not None:
            found.append(name)
            via[name] = f'<{el.name}>' if el.name == name else f'role="{role}"'
    return {
        'found': found,
        'via': via,
        'has_main': 'main' in found,
        'count': len(found),
    }


def _check_skip_nav(soup):
    """
    En skip-länk är en av de första länkarna på sidan, pekar på ett #id som
    finns i dokumentet och har text eller klass som "skip"/"hoppa till innehåll"
    (så att t.ex. en logotyp som länkar till #top inte räknas).
    """
    links = soup.find_all('a', href=True)
    for a in links[:_SKIP_LINK_POSITION]:
        href = a['href'].strip()
        if not href.startswith('#') or len(href) < 2:
            continue
        target_id = href[1:]
        target = soup.find(id=target_id) or soup.find('a', attrs={'name': target_id})
        if target is None:
            continue
        text = a.get_text(' ', strip=True)
        classes = ' '.join(a.get('class') or [])
        looks_like_skip = bool(_SKIP_TEXT_RE.search(text) or _SKIP_TEXT_RE.search(classes))
        if looks_like_skip:
            return {'found': True, 'href': href, 'text': text[:80]}
    return {'found': False, 'href': None, 'text': None}


def _heading_text(h) -> str:
    text = h.get_text(' ', strip=True)
    if not text:
        text = ' '.join((img.get('alt') or '').strip() for img in h.find_all('img')).strip()
    if not text:
        text = (h.get('aria-label') or '').strip()
    return text


def _check_headings(soup):
    """
    Rubrikhierarki: minst en H1, inga hopp nedåt (t.ex. H2 → H4) och inga
    tomma rubriker. Samma regel som Lighthouse "heading-order": bara på varandra
    följande rubriker jämförs.
    """
    headings = soup.find_all(re.compile(r'^h[1-6]$'))
    levels = [int(h.name[1]) for h in headings]
    skipped = []
    for prev, cur in zip(levels, levels[1:]):
        if cur > prev + 1:
            skipped.append(f'H{prev} → H{cur}')
    empty = [h.name.upper() for h in headings if not _heading_text(h)]
    return {
        'count': len(headings),
        'h1_count': levels.count(1),
        'first_level': levels[0] if levels else None,
        'outline': [f'H{l}' for l in levels[:30]],
        'skipped_levels': sorted(set(skipped)),
        'empty_count': len(empty),
    }


def _check_interactive_divs(soup):
    bad = soup.find_all(
        lambda tag: tag.name in ('div', 'span')
        and tag.get('onclick')
        and not tag.get('role')
    )
    return {'count': len(bad)}
