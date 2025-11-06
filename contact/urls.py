from django.urls import path
from . import views

urlpatterns = [
    path('question/', views.contact_view, name='contact'),  # visar formuläret
    path('quote/', views.quote_request, name='quote_request'),
    path('test-email/', views.test_email, name='test_email'), 
]
