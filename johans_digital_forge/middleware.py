from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.conf import settings


class WwwRedirectMiddleware:
    """
    Middleware som omdirigerar alla förfrågningar utan www till www-versionen.
    Detta förhindrar dubblettinnehåll och förbättrar SEO.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().lower()

        # Omdirigera endast i produktion och endast för huvuddomänen utan www
        if not settings.DEBUG and host == 'johans-digital-forge.se':
            # Bygg ny URL med www
            new_host = 'www.johans-digital-forge.se'
            protocol = 'https' if request.is_secure() else 'https'  # Alltid HTTPS
            new_url = f"{protocol}://{new_host}{request.get_full_path()}"
            return HttpResponsePermanentRedirect(new_url)

        return self.get_response(request)


class LanguageDetectionMiddleware:
    """
    Detects user's preferred language on first visit via Accept-Language header
    and redirects to the appropriate language version. Manual language selection
    (via flag click) is stored in a cookie and takes priority.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if 'lang_pref' not in request.COOKIES and request.path == '/':
            accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
            if self._prefers_english(accept_lang):
                response = HttpResponseRedirect('/en/')
                response.set_cookie('lang_pref', 'en', max_age=365 * 24 * 60 * 60, samesite='Lax')
                return response
            else:
                response = self.get_response(request)
                response.set_cookie('lang_pref', 'sv', max_age=365 * 24 * 60 * 60, samesite='Lax')
                return response

        return self.get_response(request)

    def _prefers_english(self, accept_lang):
        if not accept_lang:
            return False
        langs = []
        for part in accept_lang.split(','):
            part = part.strip()
            if ';' in part:
                lang_code, *q_parts = part.split(';')
                try:
                    q_val = float(q_parts[0].strip().replace('q=', ''))
                except (IndexError, ValueError):
                    q_val = 1.0
            else:
                lang_code = part
                q_val = 1.0
            langs.append((lang_code.strip().lower(), q_val))
        langs.sort(key=lambda x: x[1], reverse=True)
        for lang, _ in langs:
            if lang.startswith('sv'):
                return False
            if lang.startswith('en'):
                return True
        return False


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), '
            'payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()'
        )

        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://analytics.johans-digital-forge.se https://chat.johans-digital-forge.se; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https://res.cloudinary.com https://analytics.johans-digital-forge.se; "
            "connect-src 'self' https://cdn.jsdelivr.net https://analytics.johans-digital-forge.se https://chat.johans-digital-forge.se wss://chat.johans-digital-forge.se; "
            "frame-src 'none'; "
            "frame-ancestors 'none'"
        )

        return response
