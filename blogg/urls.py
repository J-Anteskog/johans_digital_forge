from django.urls import path
from . import views

urlpatterns = [
    path('', views.blogg, name='blogg'),
]