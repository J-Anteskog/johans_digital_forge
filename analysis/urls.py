from django.urls import path
from . import views

urlpatterns = [
    path('', views.analysis_form_sv, name='analysis'),
    path('r/<uuid:token>/', views.analysis_result, name='analysis_result'),
    path('r/<uuid:token>/status.json', views.analysis_status_json, name='analysis_status_json'),
    path('r/<uuid:token>/rapport/', views.analysis_pdf, name='analysis_pdf'),
    path('r/<uuid:token>/skicka-rapport/', views.send_report, name='analysis_send_report'),
    path('domain/<str:domain>/', views.domain_history, name='domain_history'),
]
