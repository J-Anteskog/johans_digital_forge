from django.shortcuts import render

def home_sv(request):
    return render(request, 'sv/home.html')

def home_en(request):
    return render(request, 'en/home.html')
