import threading
import time

import requests as http_requests
import resend
from django.conf import settings
from django.core import signing
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from .forms import ProjectBriefForm

_ANALYTICS_TOKEN = 'ea5a5e56-7959-4a57-b643-c98797856fa9'
_ADMIN_EMAIL = 'info@johans-digital-forge.se'

# --- Hjälpfunktioner -------------------------------------------------------

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
    return int(time.time()) - submitted_at >= 3


def _verify_turnstile(token, remote_ip=''):
    """
    Verifiera Cloudflare Turnstile-token server-side.
    Hoppa över om TURNSTILE_SECRET_KEY inte är konfigurerad (fail-open).
    """
    secret = getattr(settings, 'TURNSTILE_SECRET_KEY', '')
    if not secret:
        return True
    try:
        r = http_requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={'secret': secret, 'response': token, 'remoteip': remote_ip},
            timeout=5,
        )
        return r.json().get('success', False)
    except Exception:
        return True  # Fail-open: blockera inte legitima användare vid API-fel


def _send_html_email(subject, html, text, recipient):
    """Skicka HTML-e-post via Resend API (körs i bakgrundstråd)."""
    try:
        resend.api_key = settings.EMAIL_HOST_PASSWORD
        resend.Emails.send({
            'from': f'Johans Digital Forge <{settings.DEFAULT_FROM_EMAIL}>',
            'to': [recipient],
            'subject': subject,
            'html': html,
            'text': text,
        })
    except Exception as e:
        print(f'[brief] E-postfel: {e}')


def _fire_analytics_event(request, brief):
    """Skicka server-side event till Shynet vid lyckad inlämning."""
    try:
        http_requests.post(
            f'https://analytics.johans-digital-forge.se/ingress/{_ANALYTICS_TOKEN}/event',
            json={'name': 'brief_submitted', 'url': request.build_absolute_uri()},
            headers={'X-Forwarded-For': request.META.get('REMOTE_ADDR', '')},
            timeout=3,
        )
    except Exception:
        pass


def _first_error_step(form):
    """Returnera steg-numret där det första felet finns (för att öppna rätt steg)."""
    step1 = {'goals', 'goals_other', 'budget', 'timeline', 'timeline_specific'}
    step2 = {'has_existing_site', 'num_pages', 'features', 'features_other'}
    for field in form.errors:
        if field in step1:
            return 1
        if field in step2:
            return 2
    return 3


# --- Views -----------------------------------------------------------------

def _load_analysis_prefill(request):
    """
    Looks up a SiteAnalysis by UUID from query params.
    Returns (initial_dict, prefill_ctx) or ({}, {}) if invalid/missing.
    """
    if request.GET.get('ref') != 'analysis':
        return {}, {}
    analysis_id = request.GET.get('analysis_id', '').strip()
    if not analysis_id:
        return {}, {}
    try:
        from analysis.models import SiteAnalysis
        from analysis.utils import build_brief_initial_from_analysis
        analysis = SiteAnalysis.objects.get(pk=analysis_id, status='complete')
        initial = build_brief_initial_from_analysis(analysis)
        prefill_ctx = {
            'from_analysis': True,
            'analyzed_url': analysis.url,
            'analysis_grade': analysis.grade,
            'analysis_score': analysis.score_overall,
            'analysis_id': str(analysis.id),
        }
        return initial, prefill_ctx
    except Exception:
        return {}, {}


def _brief_view(request, language):
    is_english = language == 'en'
    ctx_base = {'language': language, 'is_english': is_english}

    if request.method == 'POST':
        form = ProjectBriefForm(request.POST)

        turnstile_ok = _verify_turnstile(
            request.POST.get('cf-turnstile-response', ''),
            request.META.get('REMOTE_ADDR', ''),
        )
        timestamp_ok = _check_timestamp(request)

        if not (turnstile_ok and timestamp_ok):
            return render(request, 'brief/form.html', {
                **ctx_base,
                'form': form,
                'spam_error': True,
                'form_token': _generate_form_token(),
                'initial_step': 1,
                'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', ''),
            })

        if form.is_valid():
            brief = form.save(commit=False)
            brief.language = language

            # Prioritise analysis link; fall back to utm_source / HTTP Referer
            posted_analysis_id = request.POST.get('analysis_id', '').strip()
            if posted_analysis_id:
                brief.referrer = f'analysis:{posted_analysis_id}'
            else:
                brief.referrer = (
                    request.GET.get('utm_source', '')
                    or request.META.get('HTTP_REFERER', '')[:255]
                )
            brief.save()

            threading.Thread(
                target=_fire_analytics_event, args=(request, brief), daemon=True
            ).start()

            ctx_mail = {'brief': brief, 'is_english': is_english}
            if is_english:
                customer_subject = 'Thank you for your project brief – Johans Digital Forge'
                admin_subject = f'New project brief ({brief.score()}p) – {brief.contact_name}'
            else:
                customer_subject = 'Tack för din offertbrief – Johans Digital Forge'
                admin_subject = f'Ny offertbrief ({brief.score()}p) – {brief.contact_name}'

            customer_html = render_to_string('brief/email_customer.html', ctx_mail)
            admin_html = render_to_string('brief/email_admin.html', ctx_mail)

            customer_text = (
                f"Thank you {brief.contact_name}!\n\nI'll get back to you within 24 hours.\n\n// Johan"
                if is_english else
                f"Tack {brief.contact_name}!\n\nJag återkommer inom 24 timmar.\n\n// Johan"
            )
            admin_text = (
                f"Brief: {brief.contact_name} <{brief.contact_email}>\n"
                f"Score: {brief.score()}/100\nBudget: {brief.get_budget_display()}\n"
                f"Tidslinje: {brief.get_timeline_display()}"
            )

            threading.Thread(
                target=_send_html_email,
                args=(customer_subject, customer_html, customer_text, brief.contact_email),
                daemon=True,
            ).start()
            threading.Thread(
                target=_send_html_email,
                args=(admin_subject, admin_html, admin_text, _ADMIN_EMAIL),
                daemon=True,
            ).start()

            return redirect('brief_thanks_en' if is_english else 'brief_thanks')

        return render(request, 'brief/form.html', {
            **ctx_base,
            'form': form,
            'form_token': _generate_form_token(),
            'initial_step': _first_error_step(form),
            'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', ''),
        })

    initial, prefill_ctx = _load_analysis_prefill(request)
    initial.setdefault('language', language)
    form = ProjectBriefForm(initial=initial)
    return render(request, 'brief/form.html', {
        **ctx_base,
        **prefill_ctx,
        'form': form,
        'form_token': _generate_form_token(),
        'initial_step': 1,
        'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', ''),
    })


def brief_form_sv(request):
    return _brief_view(request, language='sv')


def brief_form_en(request):
    return _brief_view(request, language='en')


def brief_thanks_sv(request):
    return render(request, 'brief/thanks.html', {'language': 'sv', 'is_english': False})


def brief_thanks_en(request):
    return render(request, 'brief/thanks.html', {'language': 'en', 'is_english': True})
