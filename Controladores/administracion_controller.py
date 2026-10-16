"""Controladores HTTP de Administración; negocio y permisos en servicios."""
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from supplyhub.models import SupplierSite, ErrorLog, AuditoriaAdministracion
from supplyhub.forms.administracion import AssignmentForm, ProfileForm, ModuleForm, ParentModuleForm, SupplierSiteForm, LogFilterForm
from supplyhub.services import administracion_service as service

ROUTES = {k: f'/administracion/{k}/' for k in ['usuarios', 'perfiles', 'modulos', 'supplier-sites', 'error-logs']}
TITLES = {'usuarios': 'Usuarios', 'perfiles': 'Perfiles', 'modulos': 'Módulos y submódulos'}


def _render(request, kind, records, form, pk=None, unavailable=False):
    q = (request.GET.get('q') or '')[:100].strip()
    state = request.GET.get('estado', '')
    rows = [x for x in records if (not q or q.casefold() in ' '.join(str(v) for v in x.values()).casefold()) and (state not in ['0','1'] or x['activo'] == (state == '1'))]
    return render(request, 'administracion/catalogo.html', dict(kind=kind, title=TITLES[kind], records=Paginator(rows, 25).get_page(request.GET.get('page')), form=form, editing=pk, q=q, estado=state,
        local_demo=service.local_demo(), unavailable=unavailable, total=len(records), active_count=sum(x['activo'] for x in records),
        parents=service.modules.list_modulos() if kind == 'modulos' and settings.DATAANALYTICS_ENABLED and not unavailable else [], parent_form=ParentModuleForm(),
        changes=AuditoriaAdministracion.objects.filter(entidad__in=[kind, {'usuarios':'Usuario','perfiles':'Perfil','modulos':'Modulo'}[kind]])[:10]))


def _index(request, kind, pk=None):
    if request.method not in ['GET', 'POST']:
        return HttpResponseNotAllowed(['GET', 'POST'])
    records, form, current, unavailable = [], None, None, False
    try:
        records = service.catalog(kind)
        if pk:
            current = next((x for x in records if x['id'] == pk), None)
            if not current:
                raise Http404
        initial = dict(current or {})
        if kind == 'usuarios':
            initial['perfil'] = initial.get('perfil_id')
            form = AssignmentForm(request.POST if request.method == 'POST' else None, initial=initial, profiles=service.catalog('perfiles'), editing=bool(pk))
            save = service.save_assignment
        elif kind == 'perfiles':
            if pk:
                initial.update(service.profile_detail(pk))
            form = ProfileForm(request.POST if request.method == 'POST' else None, initial=initial, modules=service.catalog('modulos'))
            save = service.save_profile
        else:
            initial['padre'] = initial.get('padre_id')
            form = ModuleForm(request.POST if request.method == 'POST' else None, initial=initial, parents=service.modules.list_modulos() if settings.DATAANALYTICS_ENABLED else (), central=settings.DATAANALYTICS_ENABLED)
            save = service.save_module
        if request.method == 'POST':
            action = request.POST.get('action', 'save')
            try:
                if action == 'state':
                    service.set_active(request, kind, int(request.POST['record_id']), request.POST.get('active') == '1')
                elif action == 'save' and form.is_valid():
                    save(request, form.cleaned_data, pk)
                else:
                    if action != 'save':
                        form.add_error(None, 'Acción inválida.')
                    return _render(request, kind, records, form, pk)
            except (ValidationError, IntegrityError, ValueError, KeyError) as exc:
                form.add_error(None, '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Revisa los datos; no se permiten duplicados.')
            else:
                messages.success(request, 'Cambios guardados.')
                return redirect(f'supplyhub:admin_{kind}')
    except Http404:
        raise
    except Exception:
        service.record_error('Administración.' + kind, request)
        unavailable = True
        messages.error(request, 'No se pudo consultar o guardar en DataAnalytics. No se utilizará una copia local.')
    return _render(request, kind, records, form, pk, unavailable)


@service.admin_required(ROUTES['usuarios'])
def usuarios_index(request, pk=None):
    return _index(request, 'usuarios', pk)


@service.admin_required(ROUTES['perfiles'])
def perfiles_index(request, pk=None):
    return _index(request, 'perfiles', pk)


@service.admin_required(ROUTES['modulos'])
def modulos_index(request, pk=None):
    return _index(request, 'modulos', pk)


@service.admin_required(ROUTES['modulos'])
def modulo_padre(request, pk=None):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not settings.DATAANALYTICS_ENABLED:
        messages.error(request, 'En demostración, escribe el módulo padre en el formulario del submódulo.')
        return redirect('supplyhub:admin_modulos')
    form = ParentModuleForm(request.POST)
    try:
        if form.is_valid():
            if request.POST.get('action') == 'state' and pk:
                children = service.modules.list_submodulos(id_modulo=pk)
                if request.POST.get('active') != '1' and any(x['ruta'] in service.PROTECTED_ROUTES for x in children):
                    raise ValidationError('El módulo administrativo base está protegido.')
                if not service.modules.set_modulo_active(pk, request.POST.get('active') == '1'):
                    raise ValidationError('No se pudo cambiar el estado.')
            else:
                fn = service.modules.update_modulo if pk else service.modules.create_modulo
                args = (pk, form.cleaned_data['nombre'], '#', form.cleaned_data['orden']) if pk else (form.cleaned_data['nombre'], '#', form.cleaned_data['orden'])
                service._result(fn(*args))
            service.audit(request, 'ModuloPadre', pk or form.cleaned_data['nombre'], 'GUARDAR')
            messages.success(request, 'Módulo padre guardado.')
        else:
            messages.error(request, 'Revisa el nombre y el orden del módulo padre.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('supplyhub:admin_modulos')


@service.admin_required(ROUTES['supplier-sites'])
def supplier_sites_index(request, pk=None):
    if request.method not in ['GET', 'POST']:
        return HttpResponseNotAllowed(['GET', 'POST'])
    obj = get_object_or_404(SupplierSite, pk=pk) if pk else None
    form = SupplierSiteForm(request.POST if request.method == 'POST' else None, instance=obj)
    if request.method == 'POST':
        if request.POST.get('action') == 'state':
            try:
                record_id = int(request.POST.get('record_id'))
            except (TypeError, ValueError):
                raise Http404
            item = get_object_or_404(SupplierSite, pk=record_id)
            item.activo = request.POST.get('active') == '1'
            item.save(update_fields=['activo', 'actualizado_en'])
            service.audit(request, 'SupplierSite', item.pk, 'ACTIVAR' if item.activo else 'DESACTIVAR')
            return redirect('supplyhub:admin_supplier_sites')
        if form.is_valid():
            try:
                saved = form.save()
            except IntegrityError:
                form.add_error(None, 'Ya existe ese proveedor, sitio y planta.')
            else:
                service.audit(request, 'SupplierSite', saved.pk, 'EDITAR' if pk else 'CREAR')
                messages.success(request, 'Supplier Site guardado.')
                return redirect('supplyhub:admin_supplier_sites')
    rows = SupplierSite.objects.all()
    q = (request.GET.get('q') or '')[:100]
    if q:
        rows = rows.filter(Q(proveedor__icontains=q) | Q(codigo__icontains=q) | Q(planta__icontains=q) | Q(correo__icontains=q))
    state = request.GET.get('estado', '')
    if state in ['0','1']:
        rows = rows.filter(activo=state == '1')
    return render(request, 'administracion/supplier_sites.html', dict(title='Supplier Sites', form=form, editing=pk, records=Paginator(rows,25).get_page(request.GET.get('page')), q=q, estado=state))


@service.admin_required(ROUTES['error-logs'], ti_only=True)
def error_logs_index(request):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    today = timezone.localdate()
    values = request.GET.copy()
    if not values.get('fecha_inicio'):
        values['fecha_inicio'] = today.replace(day=1).isoformat()
    if not values.get('fecha_fin'):
        values['fecha_fin'] = today.isoformat()
    form = LogFilterForm(values)
    rows = ErrorLog.objects.none()
    if form.is_valid():
        rows = ErrorLog.objects.all()
        if form.cleaned_data['fecha_inicio']:
            rows = rows.filter(fecha__date__gte=form.cleaned_data['fecha_inicio'])
        if form.cleaned_data['fecha_fin']:
            rows = rows.filter(fecha__date__lte=form.cleaned_data['fecha_fin'])
        if form.cleaned_data['q']:
            q = form.cleaned_data['q']
            rows = rows.filter(Q(origen__icontains=q) | Q(mensaje__icontains=q) | Q(usuario__icontains=q) | Q(ruta__icontains=q))
    return render(request, 'administracion/error_logs.html', dict(title='Log de Errores', form=form, q=form.data.get('q',''), records=Paginator(rows,25).get_page(request.GET.get('page'))))


def catalogos_index(request):
    return supplier_sites_index(request)
