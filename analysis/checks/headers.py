import requests

_UA = 'Mozilla/5.0 (compatible; JDFAnalyser/1.0; +https://johans-digital-forge.se)'
_TIMEOUT = 10

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


def check_headers(url: str) -> dict:
    """Kontrollerar säkerhetsrelaterade HTTP-svarshuvuden."""
    result = {
        'headers': [],
        'score': 0,
        'error': None,
    }

    try:
        resp = requests.head(
            url,
            timeout=_TIMEOUT,
            headers={'User-Agent': _UA},
            allow_redirects=True,
        )
        response_headers = {k.lower(): v for k, v in resp.headers.items()}

        total_points = 0
        headers_detail = []
        for cfg in _HEADERS_CONFIG:
            found = cfg['key'] in response_headers
            value = response_headers.get(cfg['key'], '')
            if found:
                total_points += cfg['points']
            headers_detail.append({
                'key': cfg['key'],
                'label': cfg['label'],
                'found': found,
                'value': value,
                'points': cfg['points'],
                'description_sv': cfg['description_sv'],
                'description_en': cfg['description_en'],
            })

        result['headers'] = headers_detail
        result['score'] = min(100, total_points)

    except Exception as e:
        result['error'] = str(e)

    return result
