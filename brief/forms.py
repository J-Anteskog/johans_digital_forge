"""
SPAM-SKYDD: Honeypot-fältet 'website_url' (osynligt) + signerat tidsstämpeltoken.

CAPTCHA-REKOMMENDATION – Cloudflare Turnstile (inte reCAPTCHA v3):
  Varför Turnstile?
  - GDPR-vänlig: inga spårningscookies, ingen data till Google
  - Invisible managed mode – noll friktion för användaren
  - Gratis, kräver inget Google-konto
  - Påverkar inte Core Web Vitals
  Aktivera: sätt TURNSTILE_SITE_KEY + TURNSTILE_SECRET_KEY i .env
  (se brief/views.py _verify_turnstile() och brief/templates/brief/form.html)
"""
from django import forms
from .models import ProjectBrief


class ProjectBriefForm(forms.ModelForm):
    # JSONField-fälten mappas till MultipleChoiceField för checkbox-rendering.
    # ModelForm.save() sätter instance.goals = list → JSONField accepterar lista direkt.
    goals = forms.MultipleChoiceField(
        choices=ProjectBrief.GOAL_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='Vad ska hemsidan åstadkomma?',
        error_messages={'required': 'Välj minst ett mål.'},
    )
    features = forms.MultipleChoiceField(
        choices=ProjectBrief.FEATURE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='Vilka sidor / funktioner behöver du?',
        required=False,
    )
    style_preferences = forms.MultipleChoiceField(
        choices=ProjectBrief.STYLE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='Vilken känsla vill du ha på sidan?',
        required=False,
    )

    # Honeypot – renderas osynligt i template, ska vara tomt
    website_url = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}),
    )

    class Meta:
        model = ProjectBrief
        fields = [
            'goals', 'goals_other',
            'budget', 'timeline', 'timeline_specific',
            'has_existing_site', 'num_pages',
            'features', 'features_other',
            'has_material', 'style_preferences',
            'notes',
            'contact_name', 'contact_email', 'contact_phone',
            'referrer', 'language',
        ]
        widgets = {
            'has_existing_site': forms.RadioSelect,
            'num_pages': forms.RadioSelect,
            'budget': forms.RadioSelect,
            'timeline': forms.RadioSelect,
            'has_material': forms.RadioSelect,
            'timeline_specific': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
            'language': forms.HiddenInput,
            'referrer': forms.HiddenInput,
            'goals_other': forms.TextInput(attrs={'placeholder': 'Beskriv kortfattat...'}),
            'features_other': forms.TextInput(attrs={'placeholder': 'Beskriv kortfattat...'}),
            'contact_phone': forms.TextInput(attrs={'placeholder': '070-xxx xx xx'}),
        }
        labels = {
            'goals_other': 'Annat – beskriv gärna',
            'features_other': 'Annat – beskriv gärna',
            'has_existing_site': 'Har du en hemsida idag?',
            'num_pages': 'Hur många sidor/undersidor behöver du?',
            'has_material': 'Har du texter och bilder klara?',
            'timeline_specific': 'Vilket datum behöver du det klart?',
            'notes': 'Övriga kommentarer eller önskemål',
            'contact_name': 'Ditt namn *',
            'contact_email': 'E-postadress *',
            'contact_phone': 'Telefonnummer (valfritt)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        text_like = (forms.TextInput, forms.EmailInput, forms.Textarea, forms.DateInput)
        for field in self.fields.values():
            if isinstance(field.widget, text_like):
                cls = field.widget.attrs.get('class', '')
                if 'form-control' not in cls:
                    field.widget.attrs['class'] = f"{cls} form-control".strip()
        self.fields['contact_name'].required = True
        self.fields['contact_email'].required = True

    def clean_website_url(self):
        if self.cleaned_data.get('website_url'):
            raise forms.ValidationError('Ogiltig inlämning.')
        return ''

    def clean_goals(self):
        goals = self.cleaned_data.get('goals', [])
        if not goals:
            raise forms.ValidationError('Välj minst ett mål.')
        return goals
