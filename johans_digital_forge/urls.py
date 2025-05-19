"""
URL configuration for johans_digital_forge project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from home import views as home_views
from service import views as service_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_views.home_sv, name='home_sv'),
    path('en/', home_views.home_en, name='home_en'),
    path('en/service/', service_views.service_en, name='service_en'),
    path('service/', service_views.service_sv, name='service_sv'),
]