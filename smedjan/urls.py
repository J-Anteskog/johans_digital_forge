from django.urls import path
from . import views

urlpatterns = [
    path('', views.smedjan_view, name='smedjan'),
]
