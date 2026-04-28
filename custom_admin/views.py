# custom_admin/views.py - Komplett version med alla views
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
from django.contrib import messages
import json

from service.models import Service
from portfolio.models import Project
from brief.models import ProjectBrief
from .models import CalendarEvent


# ---------------------------
# 📊 DASHBOARD
# ---------------------------
@login_required
def dashboard(request):
    services_count = Service.objects.count()
    projects_count = Project.objects.count()
    active_services = Service.objects.filter(is_active=True).count()
    briefs_count = ProjectBrief.objects.count()
    recent_briefs = ProjectBrief.objects.order_by('-created_at')[:8]
    
    return render(request, "custom_admin/dashboard.html", {
        "services_count": services_count,
        "projects_count": projects_count,
        "active_services": active_services,
        "briefs_count": briefs_count,
        "recent_briefs": recent_briefs,
    })


# ---------------------------
# ⚙️ FÖRBÄTTRAD SERVICE ADMIN
# ---------------------------
@method_decorator(login_required, name="dispatch")
class ServiceListView(ListView):
    model = Service
    template_name = "custom_admin/service_list.html"
    context_object_name = "services"
    paginate_by = 20
    
    def get_queryset(self):
        return Service.objects.all().order_by('order', '-id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Lägg till statistik
        context['total_services'] = Service.objects.count()
        context['active_services'] = Service.objects.filter(is_active=True).count()
        context['inactive_services'] = Service.objects.filter(is_active=False).count()
        
        return context


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
    
    def form_valid(self, form):
        messages.success(self.request, f'Tjänst "{form.cleaned_data["title_sv"]}" skapades.')
        return super().form_valid(form)


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
    
    def form_valid(self, form):
        messages.success(self.request, f'Tjänst "{form.cleaned_data["title_sv"]}" uppdaterades.')
        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class ServiceDeleteView(DeleteView):
    model = Service
    template_name = "custom_admin/service_confirm_delete.html"
    success_url = reverse_lazy("admin_services")
    
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(request, f'Tjänst "{obj.title_sv}" raderades.')
        return super().delete(request, *args, **kwargs)


# Lägg till bulk actions view
@login_required
def bulk_service_actions(request):
    """Hantera bulk-actions på tjänster"""
    if request.method == 'POST':
        action = request.POST.get('action')
        service_ids = request.POST.getlist('service_ids')
        
        if not service_ids:
            messages.error(request, 'Inga tjänster valda.')
            return redirect('admin_services')
        
        services = Service.objects.filter(id__in=service_ids)
        
        if action == 'activate':
            services.update(is_active=True)
            messages.success(request, f'{len(service_ids)} tjänster aktiverade.')
        elif action == 'deactivate':
            services.update(is_active=False)
            messages.success(request, f'{len(service_ids)} tjänster inaktiverade.')
        elif action == 'delete':
            count = services.count()
            services.delete()
            messages.success(request, f'{count} tjänster raderade.')
    
    return redirect('admin_services')


# AJAX för att uppdatera order
@login_required
def update_service_order(request):
    """AJAX för att uppdatera ordning på tjänster"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            service_orders = data.get('orders', [])
            
            for item in service_orders:
                Service.objects.filter(id=item['id']).update(order=item['order'])
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


# ---------------------------
# 💼 PROJEKT ADMIN
# ---------------------------
@method_decorator(login_required, name="dispatch")
class ProjectListView(ListView):
    model = Project
    template_name = "custom_admin/project_list.html"
    context_object_name = "projects"
    ordering = ['order', '-id']


@method_decorator(login_required, name="dispatch")
class ProjectCreateView(CreateView):
    model = Project
    template_name = "custom_admin/project_form.html"
    fields = [
        "title_sv", "title_en",
        "description_sv", "description_en",
        "technologies", "github_url", "live_url",
        "image", "is_active", "order"
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
        "image", "is_active", "order"
    ]
    success_url = reverse_lazy("admin_projects")


@method_decorator(login_required, name="dispatch")
class ProjectDeleteView(DeleteView):
    model = Project
    template_name = "custom_admin/project_confirm_delete.html"
    success_url = reverse_lazy("admin_projects")


# ---------------------------
# 🗓️ KALENDER (ADMIN HUB)
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

        # 🔨 Läs och kontrollera inkommande data
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

        # 🗑️ DELETE → Ta bort händelse
        elif request.method == "DELETE":
            CalendarEvent.objects.filter(id=body.get("id"), created_by=request.user).delete()
            return JsonResponse({"status": "deleted"})

        return JsonResponse({"error": "Ogiltig metod"}, status=405)

    except Exception as e:
        print("⚠️ FEL I calendar_events_api:", e)
        return JsonResponse({"error": str(e)}, status=500)