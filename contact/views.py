from django.shortcuts import redirect, render
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import render
from .forms import ContactForm, QuoteForm
import threading


def send_email_async(subject, message, from_email, recipient_list):
    """Skicka e-post i bakgrunden"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False
        )
        print(f"✅ E-post skickad: {subject}")
    except Exception as e:
        print(f"❌ E-post fel: {e}")


def contact_view(request):
    subject_text = request.GET.get("subject", "")
    initial_data = {
        "subject": f"🧾 Jag är intresserad av: {subject_text}" if subject_text else ""
    }

    form = ContactForm(initial=initial_data)

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data["subject"]
            message = form.cleaned_data["message"]
            sender = form.cleaned_data["email"]

            # Mejlets innehåll
            full_message = f"Från: {sender}\n\n{message}"

            # Skicka e-post i bakgrunden (blockerar inte användaren)
            thread = threading.Thread(
                target=send_email_async,
                args=(
                    subject,
                    full_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.EMAIL_HOST_USER]
                )
            )
            thread.daemon = True
            thread.start()

            return render(request, "contact/contact.html", {
                "form": ContactForm(),
                "success": True,
            })

    return render(request, "contact/contact.html", {"form": form})


def quote_request(request):
    if request.method == "POST":
        form = QuoteForm(request.POST)
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
            )

            # Skicka e-post i bakgrunden
            thread = threading.Thread(
                target=send_email_async,
                args=(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.EMAIL_HOST_USER]
                )
            )
            thread.daemon = True
            thread.start()

            return render(request, "contact/quote.html", {"form": QuoteForm(), "success": True})

    else:
        form = QuoteForm()

    return render(request, "contact/quote.html", {"form": form})