import json
import time
from datetime import timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from django.core import signing
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .email import send_report_email
from .forms import AnalysisForm
from .models import SiteAnalysis
from .report import (
    build_categories, pagespeed_status_text, pagespeed_summary, site_findings, site_tips,
)
from .scoring import ANALYZER_VERSION
from .tasks import start_analysis

# A/B-testbar copy för opt-in-formuläret
_OPT_IN_HEADING = 'Få en handlingsplan i din inkorg'
_OPT_IN_SUBTEXT = 'Vi skickar rapporten som PDF plus konkreta förslag på vad du bör fixa först, andra och tredje.'
_OPT_IN_BUTTON  = 'Skicka rapporten'

# Steg på väntesidan – nycklarna motsvarar tasks.PHASES
_PENDING_STEPS = [
    ('fetch', 'Hämtar sidan, HTTPS och certifikat', 'Fetching the page, HTTPS and certificate'),
    ('checks', 'SEO, mobil och tillgänglighet', 'SEO, mobile and accessibility'),
    ('crawl', 'Undersidor', 'Subpages'),
    ('pagespeed', 'Google PageSpeed (upp till 60 s)', 'Google PageSpeed (up to 60 s)'),
    ('scoring', 'Poäng och rapport', 'Scores and report'),
]

_RATE_LIMIT = 30      # analyser per IP per timme
_CACHE_HOURS = 24     # återanvänd resultat om nyare än så


_SWEDISH_TIME = ZoneInfo('Europe/Stockholm')


def _swedish_time(view):
    """
    Rapporter och historik visar tider i svensk tid (servern kör i UTC).
    Gäller bara de här vyerna – resten av sajten påverkas inte.
    """
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        with timezone.override(_SWEDISH_TIME):
            return view(request, *args, **kwargs)
    return wrapper


def _noindex(view):
    """Rapporter och historik ska inte indexeras av sökmotorer (header + meta i mallarna)."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
    return wrapper


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
                analyzer_version=ANALYZER_VERSION,   # återanvänd aldrig rapporter från äldre version
            ).order_by('-created_at').first()
            if cached:
                return redirect('analysis_result', token=cached.id)

            obj = SiteAnalysis.objects.create(
                url=url,
                requester_ip=ip,
                language=language,
                analyzer_version=ANALYZER_VERSION,
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


@_noindex
@_swedish_time
def analysis_result(request, token):
    obj = get_object_or_404(SiteAnalysis, pk=token)
    if obj.status in ('pending', 'running'):
        return render(request, 'analysis/pending.html', {'obj': obj, 'steps': _PENDING_STEPS})
    if obj.status == 'error' and set(obj.results or {}) == {'progress'}:
        obj.results = None   # avbruten mitt i (t.ex. omstart) – visa felsidan, inte en tom rapport
    if obj.status == 'complete' and not obj.email_submitted and not obj.email_form_shown:
        SiteAnalysis.objects.filter(pk=obj.pk).update(email_form_shown=True)
        obj.email_form_shown = True
    template = 'analysis/result_v1.html' if obj.is_legacy else 'analysis/result.html'
    return render(request, template, {
        'obj': obj,
        'opt_in_heading': _OPT_IN_HEADING,
        'opt_in_subtext': _OPT_IN_SUBTEXT,
        'opt_in_button': _OPT_IN_BUTTON,
        **_report_context(obj),
    })


@_noindex
@_swedish_time
def analysis_shared(request, token):
    """
    Delningsvy för utskick till företag som inte själva beställt analysen:
    fynd och uppmätta värden per kategori, utan bokstavsbetyg, totalpoäng,
    "vägen till betyg A", erbjudanden eller e-postformulär. Samma id som rapporten.
    Rör inte e-post-/spårningsfälten på analysen.
    """
    obj = get_object_or_404(SiteAnalysis, pk=token)
    reason = _shared_unavailable_reason(obj)
    if reason:
        return render(request, 'analysis/shared_unavailable.html', {'obj': obj, 'reason': reason})
    return render(request, 'analysis/shared.html', {'obj': obj, **_report_context(obj)})


def _shared_unavailable_reason(obj):
    if obj.status in ('pending', 'running'):
        return 'running'
    if obj.status != 'complete' or not obj.results:
        return 'error'
    if obj.is_legacy:
        return 'legacy'   # gamla rapporter har delvis uppskattade värden – delas inte
    return None


def _report_context(obj):
    """Gemensam kontext för v2-mallarna (webb + PDF). Tom för äldre rapporter."""
    if obj.is_legacy:
        return {}
    categories = build_categories(obj)
    return {
        'categories': categories,
        'cats': {c['key']: c for c in categories},
        'psp_status_text': pagespeed_status_text(obj.results, obj.language),
        'psp_summary': pagespeed_summary(obj.results, obj.language),
        'findings': site_findings(obj.results, obj.language),
        'tips': site_tips(obj.results, obj.language),
    }


@require_POST
def send_report(request, token):
    obj = get_object_or_404(SiteAnalysis, pk=token, status='complete')
    email = request.POST.get('email', '').strip()
    consent = request.POST.get('marketing_consent') == '1'
    phone = request.POST.get('phone', '').strip()

    if not email or '@' not in email:
        return JsonResponse({'ok': False, 'error': 'Ogiltig e-postadress'}, status=400)

    if obj.email_submitted:
        return JsonResponse({'ok': False, 'error': 'Redan skickat'}, status=400)

    obj.email = email
    obj.phone = phone
    obj.marketing_consent = consent
    obj.consent_timestamp = timezone.now()
    obj.email_submitted = True
    obj.save(update_fields=['email', 'phone', 'marketing_consent', 'consent_timestamp', 'email_submitted'])

    send_report_email(obj)
    return JsonResponse({'ok': True})


def analysis_status_json(request, token):
    obj = get_object_or_404(SiteAnalysis, pk=token)
    payload = {'status': obj.status, 'done': obj.is_done}
    if obj.status == 'running':
        progress = (obj.results or {}).get('progress') or {}
        if progress.get('phase'):
            payload['phase'] = progress['phase']
            started = parse_datetime(progress.get('started') or '')
            if started:
                payload['phase_seconds'] = max(0, int((timezone.now() - started).total_seconds()))
    if obj.status == 'error' and obj.error_message:
        payload['error_message'] = obj.error_message
    return JsonResponse(payload)


@_noindex
@_swedish_time
def domain_history(request, domain):
    analyses = (
        SiteAnalysis.objects
        .filter(domain=domain, status='complete')
        .order_by('completed_at')
    )
    chart_labels = []
    chart_overall = []
    chart_security = []
    chart_seo = []
    chart_performance = []
    chart_mobile = []
    chart_headers = []
    chart_accessibility = []
    chart_psp_mobile = []
    chart_psp_desktop = []
    rows = []

    # None (ej mätt) blir null i JSON → glapp i grafen i stället för en påhittad nolla
    for a in analyses:
        psp = (a.results or {}).get('pagespeed') or {}
        psp_mobile = (psp.get('mobile') or {}).get('score')
        psp_desktop = (psp.get('desktop') or {}).get('score')
        rows.append({'a': a, 'psp_mobile': psp_mobile, 'psp_desktop': psp_desktop})
        chart_psp_mobile.append(psp_mobile)
        chart_psp_desktop.append(psp_desktop)
        when = a.completed_at or a.created_at
        label = timezone.localtime(when).strftime('%Y-%m-%d')   # svensk tid (se _swedish_time)
        chart_labels.append(label)
        chart_overall.append(a.score_overall)
        chart_security.append(a.score_security)
        chart_seo.append(a.score_seo)
        chart_performance.append(a.score_performance)
        chart_mobile.append(a.score_mobile)
        chart_headers.append(a.score_headers)
        chart_accessibility.append(a.score_accessibility)

    return render(request, 'analysis/domain_history.html', {
        'domain': domain,
        'analyses': analyses,
        'rows': rows,
        'chart_labels': json.dumps(chart_labels),
        'chart_overall': json.dumps(chart_overall),
        'chart_security': json.dumps(chart_security),
        'chart_seo': json.dumps(chart_seo),
        'chart_performance': json.dumps(chart_performance),
        'chart_mobile': json.dumps(chart_mobile),
        'chart_headers': json.dumps(chart_headers),
        'chart_accessibility': json.dumps(chart_accessibility),
        'chart_psp_mobile': json.dumps(chart_psp_mobile),
        'chart_psp_desktop': json.dumps(chart_psp_desktop),
    })


@_noindex
@_swedish_time
def analysis_pdf(request, token):
    if request.GET.get('delad') == '1':
        # Delningsvyns PDF: samma regler som analysis_shared
        obj = get_object_or_404(SiteAnalysis, pk=token)
        reason = _shared_unavailable_reason(obj)
        if reason:
            return render(request, 'analysis/shared_unavailable.html', {'obj': obj, 'reason': reason})
        return render(request, 'analysis/report_pdf.html', {
            'obj': obj, 'r': obj.results, 'shared': True, **_report_context(obj),
        })

    obj = get_object_or_404(SiteAnalysis, pk=token, status='complete')
    template = 'analysis/report_pdf_v1.html' if obj.is_legacy else 'analysis/report_pdf.html'
    return render(request, template, {
        'obj': obj,
        'r': obj.results or {},
        **_report_context(obj),
    })
