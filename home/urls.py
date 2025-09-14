from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_sv, name='home_sv'),
    path('en/', views.home_en, name='home_en'),
]
