from django.shortcuts import render

# Create your views here.
def service_sv(request):
    return render(request, 'sv/service.html')

def service_en(request):
    return render(request, 'en/service.html')