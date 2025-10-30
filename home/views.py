from django.shortcuts import render
from portfolio.models import Project
from django.contrib.auth.models import User

def create_admin_user():
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@example.com", "Admin123!")
        print("✅ Superuser created: admin / Admin123!")




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