# custom_admin/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from service.models import Service
from portfolio.models import Project
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from service.models import Service
from portfolio.models import Project
from django.utils.decorators import method_decorator

@login_required
def dashboard(request):
    services_count = Service.objects.count()
    projects_count = Project.objects.count()

    return render(request, "custom_admin/dashboard.html", {
        "services_count": services_count,
        "projects_count": projects_count,
    })

@method_decorator(login_required, name="dispatch")
class ServiceListView(ListView):
    model = Service
    template_name = "custom_admin/service_list.html"
    context_object_name = "services"

@method_decorator(login_required, name="dispatch")
class ServiceCreateView(CreateView):
    model = Service
    # Lägg till extra_info-fälten så du kan redigera modalens innehåll här
    fields = [
        "title_sv",
        "title_en",
        "description_sv",
        "description_en",
        "extra_info_sv",
        "extra_info_en",
        "price",
        "icon",
        "is_active",
        "order",
    ]
    template_name = "custom_admin/service_form.html"
    success_url = reverse_lazy("admin_services")

@method_decorator(login_required, name="dispatch")
class ServiceUpdateView(UpdateView):
    model = Service
    # Samma fält som i createview
    fields = [
        "title_sv",
        "title_en",
        "description_sv",
        "description_en",
        "extra_info_sv",
        "extra_info_en",
        "price",
        "icon",
        "is_active",
        "order",
    ]
    template_name = "custom_admin/service_form.html"
    success_url = reverse_lazy("admin_services")

@method_decorator(login_required, name="dispatch")
class ServiceDeleteView(DeleteView):
    model = Service
    template_name = "custom_admin/service_confirm_delete.html"
    success_url = reverse_lazy("admin_services")



@method_decorator(login_required, name="dispatch")
class ProjectListView(ListView):
    model = Project
    template_name = "custom_admin/project_list.html"
    context_object_name = "projects"