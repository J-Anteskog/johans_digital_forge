import time
from datetime import timedelta

from django.core import signing
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AnalysisForm
from .models import SiteAnalysis
from .tasks import start_analysis

_RATE_LIMIT = 5       # analyser per IP per timme
_CACHE_HOURS = 24     # återanvänd resultat om nyare än så


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')


def _generate_form_token():
    return signing.dumps(int(time.time()))


def _check_timestamp(request):
    token = request.POST.get('form_token', '')
    if not token:
        return False
    try:
        submitted_at = signing.loads(token, max_age=3600)
    except (signing.BadSignature, signing.SignatureExpired):
        return False
    return int(time.time()) - submitted_at >= 2


def _analysis_view(request, language):
    is_english = language == 'en'

    if request.method == 'POST':
        form = AnalysisForm(request.POST)

        if not _check_timestamp(request):
            return render(request, 'analysis/form.html', {
                'form': form,
                'language': language,
                'is_english': is_english,
                'spam_error': True,
                'form_token': _generate_form_token(),
            })

        if form.is_valid():
            url = form.cleaned_data['url']
            email = form.cleaned_data.get('email', '')
            ip = _get_client_ip(request)

            one_hour_ago = timezone.now() - timedelta(hours=1)
            if SiteAnalysis.objects.filter(
                requester_ip=ip,
                created_at__gte=one_hour_ago,
            ).count() >= _RATE_LIMIT:
                return render(request, 'analysis/form.html', {
                    'form': form,
                    'language': language,
                    'is_english': is_english,
                    'rate_limit_error': True,
                    'form_token': _generate_form_token(),
                })

            # Återanvänd befintligt resultat om < 24h gammalt
            cutoff = timezone.now() - timedelta(hours=_CACHE_HOURS)
            cached = SiteAnalysis.objects.filter(
                url=url,
                created_at__gte=cutoff,
                status='complete',
            ).order_by('-created_at').first()
            if cached:
                return redirect('analysis_result', token=cached.id)

            obj = SiteAnalysis.objects.create(
                url=url,
                email=email,
                requester_ip=ip,
                language=language,
            )
            start_analysis(str(obj.id))
            return redirect('analysis_result', token=obj.id)

        return render(request, 'analysis/form.html', {
            'form': form,
            'language': language,
            'is_english': is_english,
            'form_token': _generate_form_token(),
        })

    initial_url = request.GET.get('site', '')
    form = AnalysisForm(initial={'url': initial_url} if initial_url else None)
    return render(request, 'analysis/form.html', {
        'form': form,
        'language': language,
        'is_english': is_english,
        'form_token': _generate_form_token(),
    })


def analysis_form_sv(request):
    return _analysis_view(request, language='sv')


def analysis_form_en(request):
    return _analysis_view(request, language='en')


def analysis_result(request, token):
    obj = get_object_or_404(SiteAnalysis, pk=token)
    if obj.status in ('pending', 'running'):
        return render(request, 'analysis/pending.html', {'obj': obj})
    return render(request, 'analysis/result.html', {'obj': obj})


def analysis_status_json(request, token):
    obj = get_object_or_404(SiteAnalysis, pk=token)
    return JsonResponse({'status': obj.status, 'done': obj.is_done})
