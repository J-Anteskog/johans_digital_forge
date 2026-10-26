from django import template

register = template.Library()


@register.filter
def cl_width(url, width):
    """Låt Cloudinary skala bilden till given bredd (och välja format/kvalitet).

    Mockup-bilderna laddas upp i upp till 3840 px. Att låta webbläsaren skala
    ner dem ger suddiga, taggiga resultat – Cloudinary skalar betydligt bättre.
    Andra URL:er (t.ex. lokala media-filer) returneras oförändrade.
    """
    if not url or "res.cloudinary.com" not in url or "/upload/" not in url:
        return url
    return url.replace("/upload/", f"/upload/f_auto,q_auto,c_limit,w_{width}/", 1)
