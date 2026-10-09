_HEADERS_CONFIG = [
    {
        'key': 'strict-transport-security',
        'label': 'Strict-Transport-Security (HSTS)',
        'points': 30,
        'description_sv': 'Tvingar HTTPS-anslutningar och förhindrar nedgraderingsattacker.',
        'description_en': 'Enforces HTTPS connections and prevents downgrade attacks.',
    },
    {
        'key': 'content-security-policy',
        'label': 'Content-Security-Policy (CSP)',
        'points': 25,
        'description_sv': 'Begränsar vilka resurser webbläsaren får ladda (XSS-skydd).',
        'description_en': 'Restricts which resources the browser may load (XSS protection).',
    },
    {
        'key': 'x-frame-options',
        'label': 'X-Frame-Options',
        'points': 15,
        'description_sv': 'Förhindrar att sidan bäddas in i iframes (clickjacking-skydd).',
        'description_en': 'Prevents the page from being embedded in iframes (clickjacking protection).',
    },
    {
        'key': 'x-content-type-options',
        'label': 'X-Content-Type-Options',
        'points': 15,
        'description_sv': 'Hindrar webbläsaren från att gissa innehållstyp (MIME-sniffing).',
        'description_en': 'Prevents the browser from guessing content type (MIME sniffing).',
    },
    {
        'key': 'referrer-policy',
        'label': 'Referrer-Policy',
        'points': 10,
        'description_sv': 'Styr vilken referrer-information som skickas med länkar.',
        'description_en': 'Controls which referrer information is sent with links.',
    },
    {
        'key': 'permissions-policy',
        'label': 'Permissions-Policy',
        'points': 5,
        'description_sv': 'Begränsar webbläsar-API:er som kamera, mikrofon och geolokalisering.',
        'description_en': 'Restricts browser APIs like camera, microphone, and geolocation.',
    },
]


def check_headers(page) -> dict:
    """
    Kontrollerar säkerhetsrelaterade HTTP-svarshuvuden i samma GET-svar
    som resten av analysen bygger på (FetchResult från fetch_page).
    """
    result = {
        'headers': [],
        'score': None,
        'error': None,
    }
    if page.status_code is None:
        result['error'] = page.error or 'Inget svar från servern.'
        return result

    response_headers = page.headers
    total_points = 0
    for cfg in _HEADERS_CONFIG:
        found = cfg['key'] in response_headers
        if found:
            total_points += cfg['points']
        result['headers'].append({
            'key': cfg['key'],
            'label': cfg['label'],
            'found': found,
            'value': response_headers.get(cfg['key'], ''),
            'points': cfg['points'],
            'description_sv': cfg['description_sv'],
            'description_en': cfg['description_en'],
        })
    result['score'] = min(100, total_points)
    result['found_count'] = sum(1 for h in result['headers'] if h['found'])
    return result
