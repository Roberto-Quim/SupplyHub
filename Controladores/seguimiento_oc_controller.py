from datetime import date
from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed, Http404
from django.db import transaction
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from supplyhub.models import HistorialSeguimiento, LineaOC, OrdenCompra
from supplyhub.services.permission_guard import supplyhub_route_required
from supplyhub.services.rfq_capex_service import actor_from_request

def _positive_id(value):
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise Http404
    if result <= 0:
        raise Http404
    return result


class SeguimientoForm(forms.Form):
    respuesta_proveedor = forms.CharField()
    fecha_revisada_propuesta = forms.DateField(required=False)
    fecha_embarque_proveedor = forms.DateField(required=False)
    fecha_entrega_planta = forms.DateField(required=False)
    stock = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2)
    min_max = forms.CharField(required=False, max_length=50)


SEGUIMIENTO_ROUTE = "/hub/seguimiento-oc/"


@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def seguimiento_oc_index(request):
    """Controlador con filtro de plantas excluyendo Tenango para Jacqueline"""
    plantas_raw = request.GET.getlist('planta')
    comprador = (request.GET.get('comprador') or '').strip()[:150]
    proveedor = (request.GET.get('proveedor') or '').strip()[:200]

    # Excluir Macimex Tenango y ordenar por fecha_creacion
    ordenes = OrdenCompra.objects.exclude(
        planta_normalizada=OrdenCompra.PlantaNormalizada.MACIMEX_TENANGO
    ).prefetch_related('lineas').order_by('-fecha_creacion')
    
    plantas_seleccionadas = [p for p in plantas_raw if p and p != 'TODAS']
    
    if plantas_seleccionadas:
        ordenes = ordenes.filter(planta_normalizada__in=plantas_seleccionadas)
    else:
        plantas_seleccionadas = ['TODAS']

    if comprador:
        ordenes = ordenes.filter(comprador__iexact=comprador)
    if proveedor:
        ordenes = ordenes.filter(proveedor__icontains=proveedor)
    opciones_plantas = [
        choice for choice in OrdenCompra.PlantaNormalizada.choices 
        if choice[0] != OrdenCompra.PlantaNormalizada.MACIMEX_TENANGO
    ]

    return render(request, "seguimiento_oc/index.html", {
        "page_title": "Seguimiento de Órdenes de Compra",
        "ordenes": ordenes,
        "plantas_seleccionadas": plantas_seleccionadas,
        "opciones_plantas": opciones_plantas,
        "comprador": comprador, "proveedor": proveedor,
        "compradores": OrdenCompra.objects.exclude(planta_normalizada='MACIMEX_TENANGO').exclude(comprador='').values_list('comprador',flat=True).distinct().order_by('comprador'),
    })


@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def seguimiento_oc_detalle(request, pk: int):
    """Detalle de OC con registro de seguimiento por línea e historial de Jacqui"""
    if request.method not in ['GET', 'POST', 'HEAD']:
        return HttpResponseNotAllowed(['GET', 'POST', 'HEAD'])
    orden = get_object_or_404(
        OrdenCompra.objects.exclude(
            planta_normalizada=OrdenCompra.PlantaNormalizada.MACIMEX_TENANGO
        ).prefetch_related('lineas__historial'), 
        pk=pk
    )

    if request.method == "POST":
        linea_id = request.POST.get("linea_id")
        form = SeguimientoForm(request.POST)
        if linea_id and form.is_valid():
            linea = get_object_or_404(LineaOC, pk=_positive_id(linea_id), orden=orden)
            from supplyhub.services.seguimiento_oc_service import registrar_interaccion_linea
            with transaction.atomic():
                registrar_interaccion_linea(
                    linea, form.cleaned_data['respuesta_proveedor'],
                    actor_from_request(request),
                    form.cleaned_data['fecha_revisada_propuesta'],
                )
                if form.cleaned_data['fecha_embarque_proveedor']:
                    linea.fecha_embarque_proveedor = form.cleaned_data['fecha_embarque_proveedor']
                    linea.save(update_fields=['fecha_embarque_proveedor'])
                for field in ['fecha_entrega_planta','stock','min_max']:
                    if field in request.POST:
                        value = form.cleaned_data[field]
                        setattr(linea, field, value if value is not None else ('' if field == 'min_max' else None))
                linea.save()
            messages.success(request, f"Seguimiento guardado para la Línea {linea.numero_linea}.")
            return redirect("supplyhub:seguimiento_oc_detalle", pk=pk)
        messages.error(request, "Revisa la respuesta y las fechas del seguimiento.")

    lineas_evaluadas = []
    hoy = timezone.localdate()

    for linea in orden.lineas.all():
        fecha_evaluar = linea.fecha_revisada or linea.fecha_comprometida or linea.fecha_original
        vencida = False
        dias_retraso = 0

        if linea.estado_entrega not in ['ENTREGADA','CANCELADA'] and linea.cantidad_pendiente > 0 and fecha_evaluar and fecha_evaluar < hoy:
            vencida = True
            dias_retraso = (hoy - fecha_evaluar).days

        lineas_evaluadas.append({
            "objeto": linea,
            "evaluacion": {
                "vencida": vencida,
                "dias_retraso": dias_retraso,
                "surtido": linea.cantidad_pendiente <= 0,
            },
            "historial": linea.historial.all().order_by('-fecha_registro'),
        })

    from supplyhub.models import SupplierSite
    return render(request, "seguimiento_oc/detalle.html", {
        "page_title": f"Detalle OC #{orden.numero_oc}",
        "orden": orden,
        "lineas_evaluadas": lineas_evaluadas,
        "supplier_sites": SupplierSite.objects.filter(activo=True, proveedor__iexact=orden.proveedor),
    })


@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def importar_oc_view(request):
    """Vista para importar reporte Excel QES Open PO"""
    from supplyhub.forms.seguimiento_oc import ImportarOCForm
    from supplyhub.services.importacion_oc_service import importar_oracle_open_po
    form = ImportarOCForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            resumen = importar_oracle_open_po(form.cleaned_data['archivo'], actor_from_request(request))
        except (ValueError, OSError):
            form.add_error('archivo', 'No se pudo leer el archivo Excel.')
        else:
            messages.success(request, f"Importación: {resumen['insertados_oc']} órdenes creadas, {resumen['insertados_linea']} partidas creadas, {resumen['actualizados']} actualizadas.")
            for error in resumen['errores']:
                messages.error(request, error)
            return redirect("supplyhub:seguimiento_oc")
    return render(request, "seguimiento_oc/importar.html", {
        "page_title": "Importar QES Open PO", "form": form,
    })


@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def anular_historial_view(request, pk, history_pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    order = get_object_or_404(OrdenCompra.objects.exclude(planta_normalizada='MACIMEX_TENANGO'),pk=pk)
    history = get_object_or_404(HistorialSeguimiento,linea__orden=order,pk=history_pk)
    from supplyhub.services.seguimiento_oc_service import anular_historial
    try:
        anular_historial(history.linea_id, history.pk, actor_from_request(request), request.POST.get('motivo',''))
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    else:
        messages.success(request, 'Registro anulado. Su contenido y autor se conservan en auditoría.')
    return redirect('supplyhub:seguimiento_oc_detalle',pk=pk)


@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def asignar_supplier_site(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    from supplyhub.models import SupplierSite
    order = get_object_or_404(OrdenCompra.objects.exclude(planta_normalizada='MACIMEX_TENANGO'),pk=pk)
    site = get_object_or_404(SupplierSite, pk=_positive_id(request.POST.get('site_id')), activo=True, proveedor__iexact=order.proveedor)
    if site.planta not in [order.planta_original, order.planta_normalizada]:
        messages.error(request, 'El sitio no corresponde a la planta de la orden.')
    else:
        with transaction.atomic():
            order.supplier_site = site.codigo
            order.save(update_fields=['supplier_site','fecha_actualizacion'])
            if site.correo:
                order.lineas.filter(correo_proveedor='').update(correo_proveedor=site.correo)
        messages.success(request, 'Supplier Site asociado a la OC.')
    return redirect('supplyhub:seguimiento_oc_detalle',pk=pk)


@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def importar_min_max_view(request):
    from supplyhub.forms.seguimiento_oc import ImportarOCForm
    from supplyhub.services.inventario_service import importar_min_max
    form = ImportarOCForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            result = importar_min_max(form.cleaned_data['archivo'])
        except ValueError as exc:
            form.add_error('archivo', str(exc))
        else:
            messages.success(request, f"Inventario actualizado en {result['actualizados']} partidas.")
            for error in result['errores']:
                messages.error(request,error)
            return redirect('supplyhub:seguimiento_oc')
    return render(request,'seguimiento_oc/importar.html',{'page_title':'Importar inventario MIN–MAX','form':form})


@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def recordatorios_view(request):
    from supplyhub.models import RecordatorioOC
    from supplyhub.services.operacion_service import approve_reminder
    if request.method == 'POST':
        item = get_object_or_404(RecordatorioOC.objects.exclude(linea__orden__planta_normalizada='MACIMEX_TENANGO'),pk=_positive_id(request.POST.get('record_id')))
        if request.POST.get('action') == 'approve':
            try:
                accepted = approve_reminder(item.pk, actor_from_request(request))
            except ValidationError:
                messages.error(request,'Registra un correo de proveedor válido antes de aprobar.')
            else:
                messages.success(request,'Recordatorio aprobado.') if accepted else messages.error(request,'Este recordatorio ya fue revisado.')
        elif request.POST.get('action') == 'omit':
            RecordatorioOC.objects.filter(pk=item.pk,estado__in=['PROGRAMADO','GENERADO','FALLIDO']).update(estado='OMITIDO')
        return redirect('supplyhub:recordatorios')
    from django.core.paginator import Paginator
    rows = RecordatorioOC.objects.exclude(linea__orden__planta_normalizada='MACIMEX_TENANGO').select_related('linea__orden').order_by('-fecha_programada','-pk')
    return render(request,'seguimiento_oc/recordatorios.html',{'records':Paginator(rows,25).get_page(request.GET.get('page'))})


class CorregirHistorialForm(forms.Form):
    respuesta_proveedor = forms.CharField(label='Respuesta / comentario', widget=forms.Textarea(attrs={'rows':4}))
    fecha_revisada_propuesta = forms.DateField(label='Fecha revisada', required=False, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type':'date'}))
    motivo = forms.CharField(label='Motivo de la corrección', max_length=400)


@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def editar_historial_view(request, pk, history_pk):
    if request.method not in ['GET','POST']:
        return HttpResponseNotAllowed(['GET','POST'])
    order = get_object_or_404(OrdenCompra.objects.exclude(planta_normalizada='MACIMEX_TENANGO'),pk=pk)
    history = get_object_or_404(HistorialSeguimiento,linea__orden=order,pk=history_pk,activo=True)
    form = CorregirHistorialForm(request.POST if request.method == 'POST' else None,initial={
        'respuesta_proveedor':history.respuesta_proveedor,'fecha_revisada_propuesta':history.fecha_revisada_propuesta})
    if request.method == 'POST' and form.is_valid():
        from supplyhub.services.seguimiento_oc_service import corregir_historial
        try:
            corregir_historial(history.linea_id,history.pk,actor_from_request(request),form.cleaned_data['respuesta_proveedor'],form.cleaned_data['fecha_revisada_propuesta'],form.cleaned_data['motivo'])
        except ValidationError as exc:
            form.add_error(None,'; '.join(exc.messages))
        else:
            messages.success(request,'Corrección guardada. La entrada original se conserva en el historial.')
            return redirect('supplyhub:seguimiento_oc_detalle',pk=pk)
    return render(request,'seguimiento_oc/editar_historial.html',{'form':form,'orden':order,'history':history})
