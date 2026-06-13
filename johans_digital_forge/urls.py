"""
URL configuration for johans_digital_forge project.
"""
from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from home import views as home_views
from service import views as service_views
from portfolio import views as portfolio_views
from contact import views as contact_views
from about.views import about_us_en
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from .sitemaps import StaticViewSitemap  # <- VIKTIGT: Med punkt före sitemaps!
from home.views import robots_txt, llms_txt

sitemaps = {
    'static': StaticViewSitemap,
}

urlpatterns = [
    path("robots.txt", robots_txt, name="robots_txt"),
    path("llms.txt", llms_txt, name="llms_txt"),
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
    path('about/', include('about.urls')),
    path('en/about-us/', about_us_en, name='about_us_en'),
    path('en/service/', service_views.service_list, name='service_list_en'),
    path('en/portfolio/', portfolio_views.portfolio_view, name='portfolio_en'),
    path('en/contact/question/', contact_views.contact_view, name='contact_en'),
    path('brief/', include('brief.urls')),
    path('en/brief/', include('brief.en_urls')),
    path('analys/', include('analysis.urls')),
    path('en/analysis/', include('analysis.en_urls')),
]