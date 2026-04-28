from django import forms

from .validators import validate_target_url


class AnalysisForm(forms.Form):
    url = forms.CharField(
        label='Webbplatsens URL',
        max_length=200,
        widget=forms.URLInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'https://din-webbplats.se',
            'autocomplete': 'url',
            'autofocus': True,
        }),
    )
    email = forms.EmailField(
        label='E-post (valfritt – få rapporten via mail)',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'din@epost.se',
            'autocomplete': 'email',
        }),
    )
    # Honeypot
    website_name = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def clean_url(self):
        url = self.cleaned_data.get('url', '').strip()
        if not url:
            raise forms.ValidationError('Ange en URL.')
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        try:
            return validate_target_url(url)
        except Exception as e:
            raise forms.ValidationError(str(e))

    def clean_website_name(self):
        if self.cleaned_data.get('website_name'):
            raise forms.ValidationError('Spam detected.')
        return ''
