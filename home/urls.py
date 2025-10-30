from django.urls import path
from . import views
from home.views import create_admin_view

urlpatterns = [
    path("create-admin/", create_admin_view, name="create_admin"),
    path('', views.home_sv, name='home_sv'),
    path('en/', views.home_en, name='home_en'),
    path("integritetspolicy/", views.privacy_policy_sv, name="privacy_policy_sv"),
    path("en/privacy-policy/", views.privacy_policy_en, name="privacy_policy_en"),

]
