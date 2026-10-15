from django.utils import timezone
from supplyhub.models import OrdenCompra, LineaOC
from supplyhub.models import LineaOC, HistorialSeguimiento
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from supplyhub.models import HistorialSeguimiento
from supplyhub.services.permission_guard import supplyhub_route_required

SEGUIMIENTO_ROUTE = "/hub/seguimiento-oc/"

SEGUIMIENTO_ROUTE = "/hub/seguimiento-oc/"

@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def seguimiento_oc_detalle(request, pk: int):
    orden = get_object_or_404(
        OrdenCompra.objects.exclude(
            planta_normalizada="MACIMEX TENANGO"
        ).prefetch_related('lineas__historial'),
        pk=pk
    )

    lineas_con_historial = []
    for linea in orden.lineas.all():
        # Filtramos únicamente el historial con anulación lógica activa
        historial_activo = linea.historial.filter(activo=True).order_by('-fecha_registro')
        lineas_con_historial.append({
            'objeto': linea,
            'historial': historial_activo,
        })

    return render(request, "seguimiento_oc/detalle.html", {
        "page_title": f"Detalle OC #{orden.numero_oc}",
        "orden": orden,
        "lineas": lineas_con_historial,
    })

@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def eliminar_historial_view(request, pk: int):
    """Soft delete to preserve audit history without removing records."""
    historial = get_object_or_404(HistorialSeguimiento, pk=pk)
    orden_pk = historial.linea.orden.pk

    historial.activo = False
    historial.save()

    messages.success(request, "Entrada del historial anulada correctamente de la bitácora.")
    return redirect("supplyhub:seguimiento_oc_detalle", pk=orden_pk)

@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def eliminar_historial_view(request, pk: int):
    """Anulación lógica para auditar la bitácora sin pérdida de datos"""
    historial = get_object_or_404(HistorialSeguimiento, pk=pk)
    orden_pk = historial.linea.orden.pk

    historial.activo = False
    historial.save()

    messages.success(request, "Entrada del historial anulada correctamente de la bitácora.")
    return redirect("supplyhub:seguimiento_oc_detalle", pk=orden_pk)
PLANTILLAS_RESPUESTA_JACQUI = [
    "Material enviado por proveedor //",
    "Se re-confirma fecha de entrega //",
    "Se solicita estatus //",
    "CUENTA BLOQUEADA //",
    "*URGENTE* //",
    "Confirma fecha de entrega por correo //",
    "Se envía recordatorio de confirmación de recibido //",
    "Llamada con proveedor pdte fecha de entrega //",
    "Recolección programada //",
    "CAMBIO DE PRECIO //",
    "BPA EN AUTORIZACIÓN //",
    "ANTICIPO EN APROBACIÓN //",
    "Material en planta, pdte ingreso //",
]

def normalizar_planta(planta_original: str) -> OrdenCompra.PlantaNormalizada:
    if not planta_original:
        return OrdenCompra.PlantaNormalizada.DESCONOCIDA
        
    planta_limpia = planta_original.lower().strip()
    
    variantes_ramos = [
        "ira",
        "macimex ramos arize",
        "macimex ramos arispe",
        "macimex ramos",
        "questum mas y mex ramos arispe",
        "questum maquinados ramos",
        "mac ra",
        "maquinados ramos",
        "maq ra"
    ]
    if any(variante == planta_limpia or variante in planta_limpia for variante in variantes_ramos):
        return OrdenCompra.PlantaNormalizada.MAQ_RA
        
    variantes_tenango = [
        "questum mas y mex tenango",
        "tenango",
        "macimex tenango"
    ]
    if any(variante in planta_limpia for variante in variantes_tenango):
        return OrdenCompra.PlantaNormalizada.MACIMEX_TENANGO
        
    return OrdenCompra.PlantaNormalizada.DESCONOCIDA

def evaluar_estado_linea(linea: LineaOC) -> dict:
    """
    Evalúa el estado de entrega y vencimiento de una línea de compra.
    Retorna un diccionario con flags y clases CSS para el semáforo visual.
    """
    hoy = timezone.localdate()
    fecha_vigente = linea.fecha_revisada or linea.fecha_comprometida or linea.fecha_original
    
    esta_vencida = False
    if linea.estado_entrega not in [LineaOC.EstadoEntrega.ENTREGADA, LineaOC.EstadoEntrega.CANCELADA]:
        if fecha_vigente and fecha_vigente < hoy:
            esta_vencida = True

    return {
        "fecha_vigente": fecha_vigente,
        "vencida": esta_vencida,
        "badge_class": "badge-danger" if esta_vencida else "badge-success" if linea.estado_entrega == LineaOC.EstadoEntrega.ENTREGADA else "badge-info"
    }

def calcular_vencimiento_linea(linea: LineaOC) -> bool:
    """
    Determina si una línea está vencida basándose en la fecha comprometida vigente.
    Retorna True si está vencida, False en caso contrario.
    """
    if linea.estado_entrega in [LineaOC.EstadoEntrega.ENTREGADA, LineaOC.EstadoEntrega.CANCELADA]:
        return False
        
    # La fecha_revisada tiene prioridad si existe, de lo contrario usamos fecha_comprometida
    fecha_vigente = linea.fecha_revisada if linea.fecha_revisada else linea.fecha_comprometida
    
    if not fecha_vigente:
        return False # No hay fecha definida para comparar
        
    hoy = timezone.localdate()
    return fecha_vigente < hoy


def registrar_interaccion_linea(
    linea,
    respuesta,
    fecha_revisada=None,
    usuario="Sistema",
    fuente=None,
    nueva_fecha=None,
):
    """
    Registra una entrada en la bitácora de seguimiento de la línea de OC
    y sincroniza el comentario y la fecha prometida en la línea.
    """
    fecha_final = fecha_revisada or nueva_fecha

    if fuente is None:
        fuente = HistorialSeguimiento.Fuente.MANUAL

    historial = HistorialSeguimiento.objects.create(
        linea=linea,
        respuesta_proveedor=respuesta,
        fecha_revisada_propuesta=fecha_final,
        usuario_responsable=usuario,
        fuente=fuente,
        activo=True,
    )

    # Actualizar la línea de OC
    linea.comentarios = respuesta
    if hasattr(linea, "comentario_actual"):
        linea.comentario_actual = respuesta

    if fecha_final:
        linea.fecha_revisada = fecha_final

    linea.save()
    linea.refresh_from_db()  # Garantiza que las propiedades calculadas se actualicen

    return historial