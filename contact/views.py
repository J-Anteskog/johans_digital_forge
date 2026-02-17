from django.shortcuts import render
from django.core.mail import send_mail
from django.conf import settings
from .forms import ContactForm, QuoteForm
import threading
import resend
import urllib.request
import urllib.parse
import json



def verify_recaptcha(token):
    """Verifiera reCAPTCHA v3-token mot Googles API. Returnerar True om score >= 0.5."""
    if not token or not settings.RECAPTCHA_SECRET_KEY:
        return False
    try:
        data = urllib.parse.urlencode({
            'secret': settings.RECAPTCHA_SECRET_KEY,
            'response': token,
        }).encode('utf-8')
        req = urllib.request.Request('https://www.google.com/recaptcha/api/siteverify', data=data)
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        return result.get('success', False) and result.get('score', 0) >= 0.5
    except Exception as e:
        print(f"reCAPTCHA verification error: {e}")
        return False


def send_email_async(subject, message, from_email, recipient_list):
    """Skicka e-post via Resend API"""
    try:
        resend.api_key = settings.EMAIL_HOST_PASSWORD  # din Resend API-nyckel

        for recipient in recipient_list:
            resend.Emails.send({
                "from": f"Johans Digital Forge <{from_email}>",
                "to": [recipient],
                "subject": subject,
                "text": message,
            })
        print(f"✅ E-post skickad via Resend API: {subject}")
    except Exception as e:
        print(f"❌ E-postfel via Resend API: {e}")

def contact_view(request):
    subject_text = request.GET.get("subject", "")
    initial_data = {
        "subject": f"🧾 Jag är intresserad av: {subject_text}" if subject_text else ""
    }

    form = ContactForm(initial=initial_data)
    recaptcha_error = False

    if request.method == "POST":
        form = ContactForm(request.POST)

        # Verifiera reCAPTCHA
        recaptcha_token = request.POST.get('g-recaptcha-response', '')
        if not verify_recaptcha(recaptcha_token):
            recaptcha_error = True
            return render(request, "contact/contact.html", {
                "form": form,
                "recaptcha_error": True,
                "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY,
            })

        if form.is_valid():
            subject = form.cleaned_data["subject"]
            message = form.cleaned_data["message"]
            sender = form.cleaned_data["email"]

            discount_code = form.cleaned_data.get("discount_code", "")

            # Mejlets innehåll till dig
            full_message = f"Från: {sender}\n\n{message}"
            if discount_code:
                full_message += f"\n\nRabattkod: {discount_code}"

            # Skicka mejl till dig (Johan)
            thread = threading.Thread(
                target=send_email_async,
                args=(
                    subject,
                    full_message,
                    settings.DEFAULT_FROM_EMAIL,
                    ["info@johans-digital-forge.se"]
                )
            )
            thread.daemon = True
            thread.start()

            # Skicka bekräftelse till kunden
            confirm_subject = "Tack för ditt meddelande – Johans Digital Forge"
            confirm_message = (
                f"Hej!\n\nTack för att du kontaktade Johans Digital Forge.\n\n"
                "Vi har tagit emot ditt meddelande och återkommer så snart vi kan.\n\n"
                "Vänliga hälsningar,\nJohan Anteskog"
            )

            thread_confirm = threading.Thread(
                target=send_email_async,
                args=(
                    confirm_subject,
                    confirm_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [sender],
                )
            )
            thread_confirm.daemon = True
            thread_confirm.start()

            return render(request, "contact/contact.html", {
                "form": ContactForm(),
                "success": True,
                "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY,
            })

    return render(request, "contact/contact.html", {
        "form": form,
        "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY,
    })


def quote_request(request):
    if request.method == "POST":
        form = QuoteForm(request.POST)

        # Verifiera reCAPTCHA
        recaptcha_token = request.POST.get('g-recaptcha-response', '')
        if not verify_recaptcha(recaptcha_token):
            return render(request, "contact/quote.html", {
                "form": form,
                "recaptcha_error": True,
                "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY,
            })

        if form.is_valid():
            cleaned = form.cleaned_data
            subject = f"Ny offertförfrågan från {cleaned['name']}"
            message = (
                f"Namn: {cleaned['name']}\n"
                f"E-post: {cleaned['email']}\n"
                f"Telefon: {cleaned.get('phone', '')}\n"
                f"Företag: {cleaned.get('company', '')}\n"
                f"Paket: {cleaned['package']}\n"
                f"Har hemsida: {cleaned.get('has_website', '')}\n"
                f"Behöver innehåll: {cleaned.get('need_content', '')}\n"
                f"Tidslinje: {cleaned.get('timeline', '')}\n"
                f"Involvering: {cleaned.get('involvement', '')}\n"
                f"Uppdatera själv: {cleaned.get('self_update', '')}\n"
                f"Tilläggstjänster: {', '.join(cleaned.get('additional_services', []))}\n"
                f"Meddelande: {cleaned.get('message', '')}\n"
                f"Rabattkod: {cleaned.get('discount_code', '')}\n"
            )

            # Skicka mejl till dig
            thread = threading.Thread(
                target=send_email_async,
                args=(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    ["info@johans-digital-forge.se"],
                )
            )
            thread.daemon = True
            thread.start()

            # Skicka bekräftelse till kunden
            confirm_subject = "Tack för din offertförfrågan – Johans Digital Forge"
            confirm_message = (
                f"Hej {cleaned['name']},\n\n"
                "Tack för din offertförfrågan!\n"
                "Jag kommer att titta på din förfrågan och återkomma så snart jag kan.\n\n"
                "Vänliga hälsningar,\nJohan Anteskog"
            )

            thread_confirm = threading.Thread(
                target=send_email_async,
                args=(
                    confirm_subject,
                    confirm_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [cleaned['email']],
                )
            )
            thread_confirm.daemon = True
            thread_confirm.start()

            return render(request, "contact/quote.html", {
                "form": QuoteForm(),
                "success": True,
                "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY,
            })

    else:
        form = QuoteForm()

    return render(request, "contact/quote.html", {
        "form": form,
        "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY,
    })
