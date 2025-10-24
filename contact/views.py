from django.shortcuts import redirect, render
from django.core.mail import send_mail
from django.conf import settings
from .forms import ContactForm
from .forms import QuoteForm




def contact_view(request):
    subject_text = request.GET.get("subject", "")
    initial_data = {
        'subject': f"🧾 Jag är intresserad av: {subject_text}" if subject_text else ""
    }

    form = ContactForm(initial=initial_data)

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            # Hämta data från formuläret
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            sender = form.cleaned_data['email']

            # Skicka e-post
            send_mail(
                subject,
                message,
                sender,  # Från den som skickar
                [settings.EMAIL_HOST_USER],  # Till din e-postadress
                fail_silently=False,
            )

            # Visa framgångsmeddelande
            return render(request, 'contact/contact.html', {
                'form': ContactForm(),
                'success': True
            })

    return render(request, 'contact/contact.html', {'form': form})

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
            send_mail(
                subject,
                message,
                cleaned['email'],
                [settings.EMAIL_HOST_USER],
                fail_silently=False,
            )
            return render(request, "contact/quote.html", {"form": QuoteForm(), "success": True})
        else:
            return render(request, "contact/quote.html", {"form": form})
    else:
        form = QuoteForm()
    return render(request, "contact/quote.html", {"form": form})
