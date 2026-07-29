from django.shortcuts import render

def about_us(request):
    """Svenska Om oss-sidan"""
    context = {
        'page_title': 'Om oss – Webbutvecklare Johan Anteskog',
        'meta_description': 'Lär känna Johan Anteskog, webbutvecklare i Fagersta, och Johan\'s Digital Forge - din partner för webbutveckling i Fagersta.',
    }
    return render(request, 'about/about_us.html', context)

def about_us_en(request):
    """Engelska About Us-sidan"""
    context = {
        'page_title': 'About Us – Web Developer Johan Anteskog',
        'meta_description': 'Get to know Johan Anteskog, web developer in Fagersta, and Johan\'s Digital Forge - your partner for web development in Fagersta, Sweden.',
    }
    return render(request, 'about/about_us_english.html', context)