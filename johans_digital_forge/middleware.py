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
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://www.googletagmanager.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https://res.cloudinary.com https://www.google-analytics.com; "
            "connect-src 'self' https://www.google-analytics.com https://analytics.google.com; "
            "frame-ancestors 'none'"
        )

        return response
