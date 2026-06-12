from django.shortcuts import render
from django.core.mail import send_mail
from django.conf import settings
from django.core import signing
from .forms import ContactForm, QuoteForm
import threading
import resend
import time
import requests
import os


def generate_form_token():
    """Generera ett signerat token som innehåller aktuell Unix-tidsstämpel."""
    return signing.dumps(int(time.time()))


def check_spam_protection(request):
    """
    Kontrollera honeypot och tidsstämpel.
    Returnerar True om inlämningen ser legitim ut, annars False.
    Avslöjar inte vilken kontroll som utlöste avvisningen.
    """
    # Honeypot: 'website'-fältet måste vara tomt
    if request.POST.get('website', ''):
        return False

    # Tidsstämpel: validera signerat token och förfluten tid
    token = request.POST.get('form_token', '')
    if not token:
        return False

    try:
        submitted_at = signing.loads(token, max_age=3600)
    except (signing.BadSignature, signing.SignatureExpired):
        return False

    if int(time.time()) - submitted_at < 3:
        return False  # Skickades för snabbt (trolig bot)

    return True


def send_email_notification(from_name, from_email, subject, body_text, body_html=""):
    """Skicka notis via Postal HTTP API"""
    try:
        requests.post(
            "https://email.johans-digital-forge.se/api/incoming/",
            headers={
                "Authorization": f"Bearer {os.environ.get('NOTIFICATION_API_KEY', '')}",
                "Content-Type": "application/json",
            },
            json={
                "from_email": from_email,
                "from_name": from_name,
                "to_email": "info@johans-digital-forge.se",
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
            },
            timeout=5,
        )
    except Exception:
        pass  # Låt inte ett misslyckat notis-anrop krascha formuläret


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
    is_english = request.path.startswith('/en/')
    subject_text = request.GET.get("subject", "")
    if is_english:
        initial_subject = f"🧾 I'm interested in: {subject_text}" if subject_text else ""
    else:
        initial_subject = f"🧾 Jag är intresserad av: {subject_text}" if subject_text else ""

    lang = 'en' if is_english else 'sv'
    form = ContactForm(language=lang, initial={"subject": initial_subject})

    if request.method == "POST":
        form = ContactForm(request.POST, language=lang)

        if not check_spam_protection(request):
            return render(request, "contact/contact.html", {
                "form": form,
                "spam_error": True,
                "is_english": is_english,
                "form_token": generate_form_token(),
            })

        if form.is_valid():
            subject = form.cleaned_data["subject"]
            message = form.cleaned_data["message"]
            sender = form.cleaned_data["email"]

            discount_code = form.cleaned_data.get("discount_code", "")

            full_message = f"Från: {sender}\n\n{message}"
            if discount_code:
                full_message += f"\n\nRabattkod: {discount_code}"

            send_email_notification(
                from_name=form.cleaned_data["name"] if "name" in form.cleaned_data else sender,
                from_email=sender,
                subject=subject,
                body_text=full_message,
            )

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

            if is_english:
                confirm_subject = "Thank you for your message – Johan's Digital Forge"
                confirm_message = (
                    "Hi!\n\nThank you for contacting Johan's Digital Forge.\n\n"
                    "We have received your message and will get back to you as soon as possible.\n\n"
                    "Best regards,\nJohan Anteskog"
                )
            else:
                confirm_subject = "Tack för ditt meddelande – Johans Digital Forge"
                confirm_message = (
                    "Hej!\n\nTack för att du kontaktade Johans Digital Forge.\n\n"
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
                "form": ContactForm(language=lang),
                "success": True,
                "is_english": is_english,
                "form_token": generate_form_token(),
            })

    return render(request, "contact/contact.html", {
        "form": form,
        "is_english": is_english,
        "form_token": generate_form_token(),
    })


def quote_request(request):
    if request.method == "POST":
        form = QuoteForm(request.POST)

        if not check_spam_protection(request):
            return render(request, "contact/quote.html", {
                "form": form,
                "spam_error": True,
                "form_token": generate_form_token(),
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

            # Skicka notis via Postal
            send_email_notification(
                from_name=cleaned['name'],
                from_email=cleaned['email'],
                subject=subject,
                body_text=message,
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
                "form_token": generate_form_token(),
            })

    else:
        form = QuoteForm()

    return render(request, "contact/quote.html", {
        "form": form,
        "form_token": generate_form_token(),
    })
