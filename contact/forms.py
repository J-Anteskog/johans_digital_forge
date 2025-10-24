from django import forms
from .forms_base import BaseForm


class ContactForm(BaseForm):
    subject = forms.CharField(label="Ämne / Subject", max_length=100, required=True)
    name = forms.CharField(label="Namn / Name", max_length=100, required=True)
    email = forms.EmailField(label="E-post / Email", required=True)
    message = forms.CharField(
        label="Meddelande / Message",
        widget=forms.Textarea,
        required=True
    )


class QuoteForm(BaseForm):
    name = forms.CharField(label="Namn / Name", max_length=100)
    email = forms.EmailField(label="E-post / Email")
    phone = forms.CharField(label="Telefonnummer / Phone", required=False)
    company = forms.CharField(label="Företag / Company", required=False)

    PACKAGE_CHOICES = [
        ('starter-package-4k', 'Startpaket / Starter Package (från 4000 SEK)'),
        ('business-package-8k', 'Företagspaket / Business Package (från 8000 SEK)'),
        ('premium-package-15k', 'Premium Package (från 15000 SEK)'),
        ('webshop-package-16k', 'Webshop-paket / E-commerce (från 16000 SEK)'),
        ('unsure', 'Osäker / Not sure - vill diskutera / want to discuss'),
    ]
    package = forms.ChoiceField(
        label="Vilket paket är du intresserad av? / Which package interests you?",
        choices=PACKAGE_CHOICES,
        widget=forms.RadioSelect
    )

  

    HAS_WEBSITE_CHOICES = [
        ('no', "Nej, vi saknar hemsida idag / No, we don't have a website"),
        ('yes-redesign', 'Ja, men vi vill bygga om eller uppdatera den / Yes, but want to redesign/update'),
        ('yes-foundation', 'Ja, vi har en hemsida som ska behållas som grund / Yes, we have one that should be kept as foundation'),
    ]
    has_website = forms.ChoiceField(label="Har ni en hemsida idag? / Do you have a website today?", choices=HAS_WEBSITE_CHOICES, widget=forms.RadioSelect)

    NEED_CONTENT_CHOICES = [
        ('yes-all', 'Ja, vi behöver hjälp med både texter och bilder / Yes, need help with both text and images'),
        ('yes-partial', 'Ja, men vi har delar av innehållet klart / Yes, but we have parts of the content ready'),
        ('no', "Nej, vi tar fram allt innehåll själva / No, we'll provide all content ourselves"),
    ]
    need_content = forms.ChoiceField(label="Behöver du hjälp med innehållet? / Need help with content?", choices=NEED_CONTENT_CHOICES, widget=forms.RadioSelect)

    TIMELINE_CHOICES = [
        ('asap', 'Snarast möjligt (0-4 veckor) / ASAP (0-4 weeks)'),
        ('1-2months', 'Inom 1-2 månader / Within 1-2 months'),
        ('flexible', "Vi är flexibla med tidsplanen / We're flexible with the timeline"),
    ]
    timeline = forms.ChoiceField(label="När behöver du ha den nya hemsidan klar? / Timeline?", choices=TIMELINE_CHOICES, widget=forms.RadioSelect)

    INVOLVEMENT_CHOICES = [
        ('hands-off', 'Jag ger dig fria händer / I give you free hands'),
        ('collaborative', 'Jag vill kunna påverka texter och bilder / I want to influence text and images'),
        ('hands-on', 'Jag vill kunna påverka hela designen / I want full control over design'),
    ]
    involvement = forms.ChoiceField(label="Hur involverad vill du vara i designprocessen? / Design involvement?", choices=INVOLVEMENT_CHOICES, widget=forms.RadioSelect)

    SELF_UPDATE_CHOICES = [
        ('yes-simple', 'Ja, vi vill uppdatera själva / Yes, need simple system'),
        ('yes-training', 'Ja, med utbildning och stöd / Yes, with training and support'),
        ('no-agency', 'Nej, ni sköter uppdateringar / No, prefer you handle updates'),
    ]
    self_update = forms.ChoiceField(label="Vill du kunna uppdatera hemsidan själv efter leverans? / Self-update capability?", choices=SELF_UPDATE_CHOICES, widget=forms.RadioSelect)

    ADDITIONAL_SERVICES_CHOICES = [
        ('seo', 'Avancerad SEO-optimering / Advanced SEO'),
        ('booking', 'Bokningssystem / Booking system'),
        ('payment', 'Betalningsintegration / Payment integration'),
        ('multilingual', 'Flerspråkig hemsida / Multilingual site'),
        ('blog', 'Bloggfunktion / Blog feature'),
        ('maintenance', 'Löpande support & underhåll / Ongoing support & maintenance'),
    ]
    additional_services = forms.MultipleChoiceField(
        label="Tilläggstjänster / Additional services (valfritt / optional)",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=ADDITIONAL_SERVICES_CHOICES
    )

    message = forms.CharField(label="Berätta mer om ditt projekt / Tell me more about your project", widget=forms.Textarea, required=False)
