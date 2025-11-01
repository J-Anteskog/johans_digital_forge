from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="admin_dashboard"),
    path("services/", views.ServiceListView.as_view(), name="admin_services"),
    path("services/add/", views.ServiceCreateView.as_view(), name="admin_service_add"),
    path("services/<int:pk>/edit/", views.ServiceUpdateView.as_view(), name="admin_service_edit"),
    path("services/<int:pk>/delete/", views.ServiceDeleteView.as_view(), name="admin_service_delete"),
    # Projekt-URL:er
    path("projects/", views.ProjectListView.as_view(), name="admin_projects"),
    path("projects/add/", views.ProjectCreateView.as_view(), name="add_project"),
    path("projects/<int:pk>/edit/", views.ProjectUpdateView.as_view(), name="edit_project"),
    path("projects/<int:pk>/delete/", views.ProjectDeleteView.as_view(), name="delete_project"),
    # --- Kalender ---
    path("calendar/", views.AdminCalendarView.as_view(), name="admin_calendar"),
    path("calendar/api/", views.calendar_events_api, name="calendar_events_api"),

]
