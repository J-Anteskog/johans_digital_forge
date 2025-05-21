from django.shortcuts import render
from .models import Project

def portfolio_view(request):
    projects = Project.objects.filter(is_active=True)
    return render(request, 'portfolio/portfolio.html', {'projects': projects})
