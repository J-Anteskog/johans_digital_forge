from django.urls import path
from . import views

app_name = 'about'

urlpatterns = [
    path('', views.about_us, name='about_us'),
    path('en/', views.about_us_en, name='about_us_en'),  # <-- lägg till denna
]