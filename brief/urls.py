from django.urls import path
from . import views

urlpatterns = [
    path('', views.brief_form_sv, name='brief'),
    path('tack/', views.brief_thanks_sv, name='brief_thanks'),
]
