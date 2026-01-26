from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.cache import cache_control
from portfolio.models import Project


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

def privacy_policy_sv(request):
    return render(request, "sv/privacy_policy.html")

def privacy_policy_en(request):
    return render(request, "en/privacy_policy.html")