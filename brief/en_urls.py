from django.urls import path
from . import views

urlpatterns = [
    path('', views.brief_form_en, name='brief_en'),
    path('thank-you/', views.brief_thanks_en, name='brief_thanks_en'),
]
