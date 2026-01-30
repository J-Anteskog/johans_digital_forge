from django.http import HttpResponsePermanentRedirect
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
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://www.googletagmanager.com https://www.google-analytics.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https://res.cloudinary.com https://www.google-analytics.com https://www.googletagmanager.com; "
            "connect-src 'self' https://cdn.jsdelivr.net https://*.google-analytics.com https://*.analytics.google.com https://*.googletagmanager.com;"
            "frame-ancestors 'none'"
        )

        return response
