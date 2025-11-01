# custom_admin/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
import json

from service.models import Service
from portfolio.models import Project
from .models import CalendarEvent


# ---------------------------
# 📊 DASHBOARD
# ---------------------------
@login_required
def dashboard(request):
    services_count = Service.objects.count()
    projects_count = Project.objects.count()
    return render(request, "custom_admin/dashboard.html", {
        "services_count": services_count,
        "projects_count": projects_count,
    })


# ---------------------------
# ⚙️ SERVICE ADMIN
# ---------------------------
@method_decorator(login_required, name="dispatch")
class ServiceListView(ListView):
    model = Service
    template_name = "custom_admin/service_list.html"
    context_object_name = "services"


@method_decorator(login_required, name="dispatch")
class ServiceCreateView(CreateView):
    model = Service
    fields = [
        "title_sv", "title_en",
        "description_sv", "description_en",
        "extra_info_sv", "extra_info_en",
        "price", "icon", "is_active", "order"
    ]
    template_name = "custom_admin/service_form.html"
    success_url = reverse_lazy("admin_services")


@method_decorator(login_required, name="dispatch")
class ServiceUpdateView(UpdateView):
    model = Service
    fields = [
        "title_sv", "title_en",
        "description_sv", "description_en",
        "extra_info_sv", "extra_info_en",
        "price", "icon", "is_active", "order"
    ]
    template_name = "custom_admin/service_form.html"
    success_url = reverse_lazy("admin_services")


@method_decorator(login_required, name="dispatch")
class ServiceDeleteView(DeleteView):
    model = Service
    template_name = "custom_admin/service_confirm_delete.html"
    success_url = reverse_lazy("admin_services")


# ---------------------------
# 💼 PROJEKT ADMIN
# ---------------------------
@method_decorator(login_required, name="dispatch")
class ProjectListView(ListView):
    model = Project
    template_name = "custom_admin/project_list.html"
    context_object_name = "projects"
    ordering = ["-id"]


@method_decorator(login_required, name="dispatch")
class ProjectCreateView(CreateView):
    model = Project
    template_name = "custom_admin/project_form.html"
    fields = [
        "title_sv", "title_en",
        "description_sv", "description_en",
        "technologies", "github_url", "live_url",
        "image", "is_active"
    ]
    success_url = reverse_lazy("admin_projects")


@method_decorator(login_required, name="dispatch")
class ProjectUpdateView(UpdateView):
    model = Project
    template_name = "custom_admin/project_form.html"
    fields = [
        "title_sv", "title_en",
        "description_sv", "description_en",
        "technologies", "github_url", "live_url",
        "image", "is_active"
    ]
    success_url = reverse_lazy("admin_projects")


@method_decorator(login_required, name="dispatch")
class ProjectDeleteView(DeleteView):
    model = Project
    template_name = "custom_admin/project_confirm_delete.html"
    success_url = reverse_lazy("admin_projects")


# ---------------------------
# 🗓 KALENDER (ADMIN HUB)
# ---------------------------
@method_decorator([login_required, ensure_csrf_cookie], name="dispatch")
class AdminCalendarView(TemplateView):
    template_name = "custom_admin/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        events = CalendarEvent.objects.filter(created_by=self.request.user)

        context["events_json"] = mark_safe(json.dumps([
            {
                "id": e.id,
                "title": e.title,
                "start": e.start.isoformat(),
                "end": e.end.isoformat() if e.end else e.start.isoformat(),
                "description": e.description or ""
            } for e in events
        ]))
        return context


# ---------------------------
# 🔗 API för FullCalendar
# ---------------------------
@login_required
def calendar_events_api(request):
    """AJAX-API för att skapa, uppdatera och ta bort kalenderhändelser."""
    try:
        # 📦 GET → Hämta alla händelser
        if request.method == "GET":
            events = CalendarEvent.objects.filter(created_by=request.user)
            data = [{
                "id": e.id,
                "title": e.title,
                "start": e.start.isoformat(),
                "end": e.end.isoformat() if e.end else e.start.isoformat(),
                "description": e.description,
            } for e in events]
            return JsonResponse(data, safe=False)

        # 📨 Läs och kontrollera inkommande data
        if not request.body:
            return JsonResponse({"error": "Tom request body"}, status=400)

        body = json.loads(request.body.decode("utf-8"))

        # 🟢 POST → Skapa ny händelse
        if request.method == "POST":
            title = body.get("title")
            start = parse_datetime(body.get("start"))
            end = parse_datetime(body.get("end")) if body.get("end") else start
            desc = body.get("description", "")
            if not title or not start:
                return JsonResponse({"error": "Titel och start krävs"}, status=400)

            event = CalendarEvent.objects.create(
                title=title, start=start, end=end, description=desc, created_by=request.user
            )
            return JsonResponse({"id": event.id, "status": "created"}, status=201)

        # ✏️ PUT → Uppdatera händelse
        elif request.method == "PUT":
            event = CalendarEvent.objects.get(id=body["id"], created_by=request.user)
            event.title = body.get("title", event.title)
            event.description = body.get("description", event.description)
            event.start = parse_datetime(body.get("start")) or event.start
            event.end = parse_datetime(body.get("end")) or event.end
            event.save()
            return JsonResponse({"status": "updated"})

        # 🗑 DELETE → Ta bort händelse
        elif request.method == "DELETE":
            CalendarEvent.objects.filter(id=body.get("id"), created_by=request.user).delete()
            return JsonResponse({"status": "deleted"})

        return JsonResponse({"error": "Ogiltig metod"}, status=405)

    except Exception as e:
        print("❌ FEL I calendar_events_api:", e)
        return JsonResponse({"error": str(e)}, status=500)
