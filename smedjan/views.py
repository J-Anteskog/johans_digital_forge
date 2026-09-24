from django.shortcuts import render
from .models import ToolCard, BuildLogEntry


def smedjan_view(request):
    is_english = request.path.startswith('/en/')
    tools = ToolCard.objects.filter(is_active=True)
    log_entries = BuildLogEntry.objects.filter(is_active=True)[:6]
    return render(request, 'smedjan/smedjan.html', {
        'tools': tools,
        'log_entries': log_entries,
        'is_english': is_english,
    })
