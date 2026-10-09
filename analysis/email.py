"""
E-postfunktioner för analysmodulen.
"""

import threading

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .report import build_categories


_FROM = 'Johan @ Johans Digital Forge <analys@johans-digital-forge.se>'
_REPLY_TO = 'analys@johans-digital-forge.se'


def _send(to: str, subject: str, html: str, text: str) -> None:
    """Skickar e-post via AhaSend SMTP. Körs alltid i bakgrundstråd."""
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=_FROM,
            to=[to],
            reply_to=[_REPLY_TO],
        )
        msg.attach_alternative(html, 'text/html')
        msg.send()
    except Exception as e:
        print(f'[analysis] E-postfel: {e}')


def send_report_email(analysis) -> None:
    """Skickar rapport-e-post till analysis.email i bakgrundstråd."""
    categories = build_categories(analysis)
    ctx = {'obj': analysis, 'r': analysis.results or {}, 'categories': categories}
    html = render_to_string('analysis/email_report.html', ctx)
    score_lines = ''.join(
        f"{c['label']}: {c['score'] if c['measured'] else 'ej mätt'}\n" for c in categories
    )

    domain = analysis.domain or analysis.url
    subject = f'Din webbplatsanalys – {domain}'
    text = (
        f'Hej!\n\n'
        f'Här är din analys av {analysis.url}.\n\n'
        f'Sammanlagt betyg: {analysis.score_overall}/100 ({analysis.grade})\n'
        f'{score_lines}\n'
        f'Se hela rapporten: https://www.johans-digital-forge.se/analys/r/{analysis.id}/\n\n'
        f'– Johan\nJohans Digital Forge\njohans-digital-forge.se'
    )

    threading.Thread(
        target=_send,
        args=(analysis.email, subject, html, text),
        daemon=True,
    ).start()


def send_followup_email(analysis, sync=False) -> None:
    """Skickar uppföljningsmejl dag 3. sync=True för management commands."""
    ctx = {'obj': analysis, 'categories': build_categories(analysis)}
    html = render_to_string('analysis/email_followup.html', ctx)

    domain = analysis.domain or analysis.url
    subject = f'Behöver ni hjälp med {domain}?'
    text = (
        f'Hej!\n\n'
        f'Såg att du körde en analys på {domain} för några dagar sedan – '
        f'betyget landade på {analysis.score_overall}/100.\n\n'
        f'Behöver ni hjälp att åtgärda något av det vi hittade? '
        f'Jag hjälper gärna till med konkreta förbättringar.\n\n'
        f'Svara på det här mejlet så pratar vi vidare.\n\n'
        f'– Johan\nJohans Digital Forge\njohans-digital-forge.se'
    )

    if sync:
        _send(analysis.email, subject, html, text)
    else:
        threading.Thread(
            target=_send,
            args=(analysis.email, subject, html, text),
            daemon=True,
        ).start()
