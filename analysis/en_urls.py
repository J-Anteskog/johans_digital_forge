from django.urls import path
from . import views

urlpatterns = [
    path('', views.analysis_form_en, name='analysis_en'),
]
