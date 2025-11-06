from django.shortcuts import render
from django.core.mail import send_mail
from django.conf import settings
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
        print(f"❌ E-postfel: {e}")


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

            # Mejlets innehåll till dig
            full_message = f"Från: {sender}\n\n{message}"

            # Skicka mejl till dig (Johan)
            thread = threading.Thread(
                target=send_email_async,
                args=(
                    subject,
                    full_message,
                    settings.DEFAULT_FROM_EMAIL,          # ← från info@johans-digital-forge.se
                    ["info@johans-digital-forge.se"]      # ← till dig själv
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
                    settings.DEFAULT_FROM_EMAIL,          # Samma avsändaradress
                    [sender],                             # Till kunden
                )
            )
            thread_confirm.daemon = True
            thread_confirm.start()

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
                "Tack för din offertförfrågan! 🙏\n"
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

            return render(request, "contact/quote.html", {"form": QuoteForm(), "success": True})

    else:
        form = QuoteForm()

    return render(request, "contact/quote.html", {"form": form})
