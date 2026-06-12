from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.cache import cache_control
from portfolio.models import Project
from urllib.parse import urlparse

# Pages with non-standard URL structures between languages
_SV_TO_EN = {
    '/': '/en/',
    '/about/': '/en/about-us/',
    '/integritetspolicy/': '/en/privacy-policy/',
}
_EN_TO_SV = {v: k for k, v in _SV_TO_EN.items()}


@cache_control(max_age=86400)
def robots_txt(request):
    """Serve robots.txt for search engine crawlers"""
    content = """# robots.txt for Johan's Digital Forge
# https://www.johans-digital-forge.se

User-agent: *
Allow: /

# Sitemap location
Sitemap: https://www.johans-digital-forge.se/sitemap.xml

# Disallow admin and private areas
Disallow: /admin/
Disallow: /dashboard/
Disallow: /login/
Disallow: /logout/

# Allow search engines to crawl all public content
Allow: /static/
Allow: /portfolio/
Allow: /service/
Allow: /contact/
Allow: /about/
Allow: /en/
"""
    return HttpResponse(content, content_type="text/plain")


def home_sv(request):
    projects = Project.objects.filter(is_active=True)[:3]
    return render(request, 'sv/home.html', {'projects': projects})

def home_en(request):
    projects = Project.objects.filter(is_active=True)[:3]
    return render(request, 'en/home.html', {'projects': projects})

def set_language(request):
    lang = request.GET.get('lang', 'sv')
    if lang not in ('sv', 'en'):
        lang = 'sv'

    referer = request.META.get('HTTP_REFERER', '')
    try:
        path = urlparse(referer).path if referer else ''
    except Exception:
        path = ''

    if lang == 'en':
        if path in _SV_TO_EN:
            redirect_to = _SV_TO_EN[path]
        elif path.startswith('/en/'):
            redirect_to = path  # already English
        elif path.startswith('/analys/'):
            redirect_to = '/en/analysis/' + path[len('/analys/'):]
        else:
            redirect_to = ('/en/' + path.lstrip('/')) if path else '/en/'
    else:
        if path in _EN_TO_SV:
            redirect_to = _EN_TO_SV[path]
        elif path.startswith('/en/analysis/'):
            redirect_to = '/analys/' + path[len('/en/analysis/'):]
        elif path.startswith('/en/'):
            redirect_to = path[3:] or '/'  # strip /en prefix
        else:
            redirect_to = path or '/'

    response = HttpResponseRedirect(redirect_to)
    response.set_cookie('lang_pref', lang, max_age=365 * 24 * 60 * 60, samesite='Lax')
    return response


def privacy_policy_sv(request):
    return render(request, "sv/privacy_policy.html")

def privacy_policy_en(request):
    return render(request, "en/privacy_policy.html")