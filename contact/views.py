from django.shortcuts import render
from django.core.mail import send_mail
from django.conf import settings
from .forms import ContactForm

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
