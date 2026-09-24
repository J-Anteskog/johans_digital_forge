import os

from django.conf import settings


def static_version(request):
    """Cache-busting query param for static/css/base.css.

    Uses the file's mtime so every deploy that changes base.css
    automatically gets a new URL, instead of browsers reusing an old
    cached copy after a soft navigation.
    """
    css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'base.css')
    try:
        version = int(os.path.getmtime(css_path))
    except OSError:
        version = 0
    return {'static_version': version}
