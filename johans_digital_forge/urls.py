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
from django.conf import settings
from django.urls import path, include
from home import views as home_views
from service import views as service_views
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", include("custom_admin.urls")),  # ditt nya admin
    path("login/", auth_views.LoginView.as_view(template_name="account/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("home.urls")),                # din front-end
    path('service/', include('service.urls')),
    path('contact/', include('contact.urls')),
    path('portfolio/', include('portfolio.urls')),
    path('dashboard/', include('custom_admin.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)