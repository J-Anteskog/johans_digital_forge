# custom_admin/views.py - Förbättringar för ServiceListView

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
from .models import CalendarEvent

# ---------------------------
# 📊 DASHBOARD
# ---------------------------
@login_required
def dashboard(request):
    services_count = Service.objects.count()
    projects_count = Project.objects.count()
    active_services = Service.objects.filter(is_active=True).count()
    
    return render(request, "custom_admin/dashboard.html", {
        "services_count": services_count,
        "projects_count": projects_count,
        "active_services": active_services,
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
        # Sortera efter order först, sedan efter id
        return Service.objects.all().order_by('order', '-id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Lägg till statistik för enklare överblick
        context['total_services'] = Service.objects.count()
        context['active_services'] = Service.objects.filter(is_active=True).count()
        context['inactive_services'] = Service.objects.filter(is_active=False).count()
        
        # Kategorisera tjänster för enklare hantering
        services = Service.objects.all().order_by('order')
        context['hosting_services'] = services.filter(title_sv__icontains='Hosting')
        context['support_services'] = services.filter(title_sv__icontains='Support')
        context['content_services'] = services.filter(title_sv__icontains='Content')
        context['development_services'] = services.exclude(
            title_sv__icontains='Hosting'
        ).exclude(
            title_sv__icontains='Support'
        ).exclude(
            title_sv__icontains='Content'
        )
        
        return context

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

# Resten av dina befintliga views...
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

# Resten av dina befintliga views fortsätter här...
# [Kopiera resten av din views.py fil här]