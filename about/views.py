from django.shortcuts import render

def about_us(request):
    """Svenska Om oss-sidan"""
    context = {
        'page_title': 'Om oss',
        'meta_description': 'Lär känna Johan Anteskog och Johan\'s Digital Forge - din partner för webbutveckling i Fagersta.',
    }
    return render(request, 'about/about_us.html', context)

def about_us_en(request):
    """Engelska About Us-sidan"""
    context = {
        'page_title': 'About Us',
        'meta_description': 'Get to know Johan Anteskog and Johan\'s Digital Forge - your partner for web development in Fagersta, Sweden.',
    }
    return render(request, 'about/about_us_english.html', context)