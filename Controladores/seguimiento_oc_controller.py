from datetime import date
from django import forms
from django.db import transaction
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from supplyhub.models import HistorialSeguimiento, LineaOC, OrdenCompra
from supplyhub.services.permission_guard import supplyhub_route_required
from supplyhub.services.rfq_capex_service import actor_from_request

class SeguimientoForm(forms.Form):
    respuesta_proveedor = forms.CharField()
    fecha_revisada_propuesta = forms.DateField(required=False)
    fecha_embarque_proveedor = forms.DateField(required=False)


SEGUIMIENTO_ROUTE = "/hub/seguimiento-oc/"


@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def seguimiento_oc_index(request):
    """Controlador con filtro de plantas excluyendo Tenango para Jacqueline"""
    plantas_raw = request.GET.getlist('planta')

    # Excluir Macimex Tenango y ordenar por fecha_creacion
    ordenes = OrdenCompra.objects.exclude(
        planta_normalizada=OrdenCompra.PlantaNormalizada.MACIMEX_TENANGO
    ).prefetch_related('lineas').order_by('-fecha_creacion')
    
    plantas_seleccionadas = [p for p in plantas_raw if p and p != 'TODAS']
    
    if plantas_seleccionadas:
        ordenes = ordenes.filter(planta_normalizada__in=plantas_seleccionadas)
    else:
        plantas_seleccionadas = ['TODAS']

    opciones_plantas = [
        choice for choice in OrdenCompra.PlantaNormalizada.choices 
        if choice[0] != OrdenCompra.PlantaNormalizada.MACIMEX_TENANGO
    ]

    return render(request, "seguimiento_oc/index.html", {
        "page_title": "Seguimiento de Órdenes de Compra",
        "ordenes": ordenes,
        "plantas_seleccionadas": plantas_seleccionadas,
        "opciones_plantas": opciones_plantas,
    })


@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def seguimiento_oc_detalle(request, pk: int):
    """Detalle de OC con registro de seguimiento por línea e historial de Jacqui"""
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
            linea = get_object_or_404(LineaOC, pk=linea_id, orden=orden)
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
            messages.success(request, f"Seguimiento guardado para la Línea {linea.numero_linea}.")
            return redirect("supplyhub:seguimiento_oc_detalle", pk=pk)
        messages.error(request, "Revisa la respuesta y las fechas del seguimiento.")

    lineas_evaluadas = []
    hoy = date.today()

    for linea in orden.lineas.all():
        fecha_evaluar = linea.fecha_revisada or linea.fecha_original
        vencida = False
        dias_retraso = 0

        if linea.cantidad_pendiente > 0 and fecha_evaluar and fecha_evaluar < hoy:
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

    return render(request, "seguimiento_oc/detalle.html", {
        "page_title": f"Detalle OC #{orden.numero_oc}",
        "orden": orden,
        "lineas_evaluadas": lineas_evaluadas,
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
