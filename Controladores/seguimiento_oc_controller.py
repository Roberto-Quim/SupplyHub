from datetime import date
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from supplyhub.models import HistorialSeguimiento, LineaOC, OrdenCompra
from supplyhub.services.permission_guard import supplyhub_route_required
from supplyhub.services.rfq_capex_service import actor_from_request
from supplyhub.services.seguimiento_oc_service import registrar_interaccion_linea


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
        respuesta_proveedor = request.POST.get("respuesta_proveedor")
        fecha_revisada_propuesta = request.POST.get("fecha_revisada_propuesta") or None
        
        linea = get_object_or_404(LineaOC, pk=linea_id)
        usuario_actor = getattr(request.user, "username", "Sistema")

        # Usar el servicio centralizado que ya corregiste:
        registrar_interaccion_linea(
            linea=linea,
            respuesta=respuesta_proveedor,
            fecha_revisada=fecha_revisada_propuesta,
            usuario=usuario_actor,
            fuente=HistorialSeguimiento.Fuente.MANUAL,
        )

        messages.success(request, f"Interacción registrada correctamente para la línea {linea.numero_linea}.")
        return redirect("supplyhub:seguimiento_oc_detalle", pk=pk)

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
    if request.method == "POST" and request.FILES.get("archivo"):
        # Importación dinámica para resolver el nombre exacto de la función
        import supplyhub.services.importacion_oc_service as imp_service
        
        # Detecta la función principal de importación automáticamente
        fn_importar = getattr(
            imp_service, 
            'importar_oc_excel', 
            getattr(imp_service, 'importar_ordenes_compra', None)
        )
        
        if fn_importar:
            resumen = fn_importar(
                request.FILES["archivo"],
                actor_from_request(request)
            )
            messages.success(
                request,
                f"Importación completada: {resumen.get('insertados', 0)} órdenes creadas, {resumen.get('actualizados', 0)} actualizadas."
            )
        else:
            messages.error(request, "Servicio de importación no encontrado.")
            
        return redirect("supplyhub:seguimiento_oc")

    return render(request, "seguimiento_oc/importar.html", {
        "page_title": "Importar QES Open PO"
    })