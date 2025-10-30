from django.shortcuts import render
from portfolio.models import Project
from django.contrib.auth.models import User
from django.core.management import call_command
from django.http import HttpResponse
import os

def import_data_view(request):
    data_file = os.path.join(os.path.dirname(__file__), '..', 'data.json')
    try:
        call_command('loaddata', data_file)
        return HttpResponse("✅ Data importerad från data.json!")
    except Exception as e:
        return HttpResponse(f"⚠️ Fel vid import: {e}")



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

def create_admin_view(request):
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@example.com", "Admin123!")
        return HttpResponse("✅ Superuser skapad: admin / Admin123!")
    else:
        return HttpResponse("⚠️ Admin finns redan.")
