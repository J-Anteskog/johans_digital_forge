from django.urls import path
from . import views

urlpatterns = [
    path('', views.analysis_form_sv, name='analysis'),
    path('r/<uuid:token>/', views.analysis_result, name='analysis_result'),
    path('r/<uuid:token>/status.json', views.analysis_status_json, name='analysis_status_json'),
]
