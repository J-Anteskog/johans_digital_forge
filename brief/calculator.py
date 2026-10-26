"""
Förifyllning av offertbriefen från priskalkylatorn på tjänstesidan.

Kalkylatorn skickar bara *val* (paket, tillval, extra sidor, webbhotell) –
aldrig belopp. Priserna räknas om här så att sammanfattningen i mejlet till
admin inte går att manipulera. Håll tabellerna i synk med kalkylatorn i
service/templates/service/service_list.html. Alla belopp är exkl. moms.
"""
from urllib.parse import parse_qs, urlencode

EXTRA_PAGE_PRICE = 500
MAX_EXTRA_PAGES = 50

# nyckel: (namn, pris, tillval som ingår, rekommenderat webbhotell, lägsta webbhotell)
PACKAGES = {
    'foretag': ('Företagspaket', 9500, set(), 200, 0),
    'premium': ('Premium', 16500, {'seo-advanced', 'booking'}, 300, 0),
    'webshop': ('Webshop-paket', 24500, {'seo-advanced', 'booking'}, 300, 300),
}

# nyckel: (namn, engångspris, månadspris)
ADDONS = {
    'seo-advanced': ('Avancerad SEO', 3500, 0),
    'booking': ('Bokningsintegration', 3500, 0),
    'multilang': ('Flerspråkigt stöd', 3000, 0),
    'chat': ('Chatt-funktion', 0, 200),
}

HOSTING = {0: 'Inget webbhotell', 200: 'Webbhotell Liten', 300: 'Webbhotell Medium', 500: 'Webbhotell Stor'}


def _kr(n):
    return f'{n:,}'.replace(',', ' ') + ' kr'


def parse_selection(params):
    """
    Läs och validera kalkylatorval från en dict-liknande källa (request.GET).
    Returnerar None om inget giltigt paket finns.
    """
    package = params.get('package', '')
    if package not in PACKAGES:
        return None
    _, _, included, _, hosting_min = PACKAGES[package]

    try:
        pages = max(0, min(MAX_EXTRA_PAGES, int(params.get('pages', 0))))
    except (TypeError, ValueError):
        pages = 0

    addons = [a for a in params.get('addons', '').split(',') if a in ADDONS and a not in included]
    addons = sorted(set(addons), key=list(ADDONS).index)

    try:
        hosting = int(params.get('hosting', 0))
    except (TypeError, ValueError):
        hosting = 0
    if hosting not in HOSTING or hosting < hosting_min:
        hosting = PACKAGES[package][3]

    return {'package': package, 'pages': pages, 'addons': addons, 'hosting': hosting}


def encode_selection(sel):
    """Kompakt sträng för det dolda fältet i formuläret (tolkas igen vid POST)."""
    return urlencode({
        'package': sel['package'],
        'pages': sel['pages'],
        'addons': ','.join(sel['addons']),
        'hosting': sel['hosting'],
    })


def decode_selection(value):
    flat = {k: v[0] for k, v in parse_qs(value or '').items()}
    return parse_selection(flat)


def totals(sel):
    name, price, included, _, _ = PACKAGES[sel['package']]
    once = price + sel['pages'] * EXTRA_PAGE_PRICE
    monthly = sel['hosting']
    for key in sel['addons']:
        once += ADDONS[key][1]
        monthly += ADDONS[key][2]
    return once, monthly


def summary(sel):
    """Läsbar sammanfattning för admin-mejl och adminvy."""
    name, price, included, _, _ = PACKAGES[sel['package']]
    parts = [f'{name} ({_kr(price)})']
    if sel['pages']:
        parts.append(f"{sel['pages']} extra sidor ({_kr(sel['pages'] * EXTRA_PAGE_PRICE)})")
    if included:
        parts.append('Ingår: ' + ', '.join(ADDONS[k][0] for k in ADDONS if k in included))
    for key in sel['addons']:
        addon, once, monthly = ADDONS[key]
        parts.append(f'{addon} ({_kr(once) if once else _kr(monthly) + "/mån"})')
    if sel['hosting']:
        parts.append(f"{HOSTING[sel['hosting']]} ({_kr(sel['hosting'])}/mån)")
    once, monthly = totals(sel)
    return ' · '.join(parts) + f' — Totalt {_kr(once)} + {_kr(monthly)}/mån exkl. moms'


def brief_initial(sel):
    """Översätt kalkylatorval till startvärden i briefen."""
    once, _ = totals(sel)
    if once < 10000:
        budget = 'under_10k'
    elif once < 20000:
        budget = '10k_20k'
    elif once < 40000:
        budget = '20k_40k'
    else:
        budget = '40k_plus'

    package = sel['package']
    base_pages = 10 if package == 'foretag' else 20
    total_pages = base_pages + sel['pages']
    if package == 'foretag' and not sel['pages']:
        num_pages = '5-10'
    elif total_pages <= 20:
        num_pages = '10-20'
    else:
        num_pages = '20+'

    # Bara uttryckliga tillval räknas som behov – att bokning ingår i
    # Premium betyder inte att kunden behöver bokning.
    has = set(sel['addons'])
    features, goals = [], []
    if package == 'webshop':
        features.append('webbshop')
        goals.append('sell_products')
    if 'booking' in has:
        features.append('boka')
        goals.append('booking')
    if 'multilang' in has:
        features.append('flersprak')
    if 'chat' in has:
        features.append('chatt')

    initial = {'budget': budget, 'num_pages': num_pages, 'features': features}
    if goals:
        initial['goals'] = goals
    return initial
