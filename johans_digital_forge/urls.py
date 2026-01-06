"""
URL configuration for johans_digital_forge project.
"""
from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from home import views as home_views
from service import views as service_views
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from .sitemaps import StaticViewSitemap  # <- VIKTIGT: Med punkt före sitemaps!

sitemaps = {
    'static': StaticViewSitemap,
}

urlpatterns = [
    path("admin/", include("custom_admin.urls")),
    path("login/", auth_views.LoginView.as_view(template_name="account/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("home.urls")),
    path('service/', include('service.urls')),
    path('contact/', include('contact.urls')),
    path('portfolio/', include('portfolio.urls')),
    path('dashboard/', include('custom_admin.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, 
         name='django.contrib.sitemaps.views.sitemap'),
]