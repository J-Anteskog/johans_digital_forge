from django.shortcuts import render

def home_sv(request):
    return render(request, 'sv/home.html')

def home_en(request):
    return render(request, 'en/home.html')


def privacy_policy_sv(request):
    return render(request, "sv/privacy_policy.html")

def privacy_policy_en(request):
    return render(request, "en/privacy_policy.html")