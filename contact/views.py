from django.shortcuts import render
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
            # Hantera meddelandet
            ...
            return render(request, 'contact/contact.html', {'form': ContactForm(), 'success': True})

    return render(request, 'contact/contact.html', {'form': form})
