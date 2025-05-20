from django import forms

class ContactForm(forms.Form):
    subject = forms.CharField(label="Ämne", max_length=100, required=True)
    name = forms.CharField(label="Namn", max_length=100, required=True,)
    email = forms.EmailField(label="E-post", required=True)
    message = forms.CharField(label="Meddelande", widget=forms.Textarea, required=True)
