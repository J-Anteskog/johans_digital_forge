from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="admin_dashboard"),
    path("services/", views.ServiceListView.as_view(), name="admin_services"),
    path("services/add/", views.ServiceCreateView.as_view(), name="admin_service_add"),
    path("services/<int:pk>/edit/", views.ServiceUpdateView.as_view(), name="admin_service_edit"),
    path("services/<int:pk>/delete/", views.ServiceDeleteView.as_view(), name="admin_service_delete"),

    path("projects/", views.ProjectListView.as_view(), name="admin_projects"),
]
