from django.utils import timezone
from django.db import transaction
from supplyhub.models import OrdenCompra, LineaOC
from supplyhub.models import LineaOC, HistorialSeguimiento

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


@transaction.atomic
def registrar_interaccion_linea(linea: LineaOC, respuesta: str, usuario: str, nueva_fecha=None) -> HistorialSeguimiento:
    """
    Registra una entrada en el historial de seguimiento y actualiza la fecha revisada de la línea.
    """
    historial = HistorialSeguimiento.objects.create(
        linea=linea,
        respuesta_proveedor=respuesta,
        usuario_responsable=usuario,
        fuente=HistorialSeguimiento.Fuente.MANUAL,
        fecha_revisada_propuesta=nueva_fecha
    )

    # Actualizar campos denormalizados en la línea de compra
    if nueva_fecha:
        linea.fecha_revisada = nueva_fecha
    
    linea.comentarios = respuesta
    linea.comentario_actual = respuesta
    linea.ultima_interaccion = historial.fecha_registro
    linea.save()

    return historial