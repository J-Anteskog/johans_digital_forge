from django.shortcuts import render
from portfolio.models import Project
from django.http import HttpResponse
from django.contrib.sites.models import Site
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def fix_site(request):
    """Temporary view för att fixa Site - TA BORT EFTER ANVÄNDNING!"""
    try:
        site = Site.objects.get(pk=1)
        site.domain = 'johans-digital-forge.se'
        site.name = 'Johans Digital Forge'
        site.save()
        return HttpResponse(f"✅ Site uppdaterat! Domain: {site.domain}")
    except Exception as e:
        return HttpResponse(f"❌ Fel: {str(e)}")

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