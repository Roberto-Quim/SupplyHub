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
    from .rfq_capex_service import _plain
    value = _plain(planta_original).replace('_',' ')
    if 'tenango' in value:
        return OrdenCompra.PlantaNormalizada.MACIMEX_TENANGO
    if value in {'ira','mcm','maqra','maq ra','mac ra'} or any(alias in value for alias in [
        'macimex ramos','maquinados ramos','ramos arizpe','ramos arispe','ramos arize',
    ]):
        return OrdenCompra.PlantaNormalizada.MAQ_RA
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
def registrar_interaccion_linea(linea, respuesta, usuario, nueva_fecha=None, *, fecha_revisada=None, fuente=None, fecha_interaccion=None):
    from django.core.exceptions import ValidationError
    from django.utils.dateparse import parse_date
    from datetime import date, datetime, timedelta
    response = str(respuesta or '').strip()
    if not response:
        raise ValidationError('La respuesta es obligatoria.')
    revised = fecha_revisada or nueva_fecha
    if isinstance(revised, str):
        try:
            revised = parse_date(revised)
        except ValueError:
            revised = None
        if revised is None:
            raise ValidationError('La fecha revisada no es válida.')
    if revised is not None and (not isinstance(revised, date) or isinstance(revised, datetime)):
        raise ValidationError('La fecha revisada no es válida.')
    locked = LineaOC.objects.select_for_update().get(pk=linea.pk)
    history = HistorialSeguimiento.objects.create(
        linea=locked, respuesta_proveedor=response, usuario_responsable=str(usuario),
        fuente=fuente or HistorialSeguimiento.Fuente.MANUAL,
        fecha_revisada_propuesta=revised, fecha_revisada_anterior=locked.fecha_revisada,
        fecha_interaccion=fecha_interaccion or timezone.now(),
    )
    if revised:
        locked.fecha_revisada = revised
    locked.comentarios = locked.comentario_actual = response
    locked.ultima_interaccion = history.fecha_registro
    locked.proximo_recordatorio = history.fecha_registro + timedelta(hours=24)
    locked.save()
    linea.refresh_from_db()
    return history


@transaction.atomic
def anular_historial(linea_id, history_id, actor, reason):
    from django.core.exceptions import ValidationError
    if not str(reason or '').strip():
        raise ValidationError('Indica el motivo de anulación.')
    line = LineaOC.objects.select_for_update().get(pk=linea_id)
    history = HistorialSeguimiento.objects.select_for_update().get(pk=history_id, linea=line)
    if not history.activo:
        return history
    history.activo = False
    history.anulado_por = str(actor)
    history.anulado_en = timezone.now()
    history.motivo_anulacion = reason.strip()[:500]
    history.save(update_fields=['activo','anulado_por','anulado_en','motivo_anulacion'])
    latest = line.historial.filter(activo=True).order_by('-fecha_registro','-pk').first()
    line.comentarios = line.comentario_actual = latest.respuesta_proveedor if latest else ''
    line.ultima_interaccion = latest.fecha_registro if latest else None
    from datetime import timedelta
    line.proximo_recordatorio = latest.fecha_registro + timedelta(hours=24) if latest else None
    # Recalcular solo si la fecha actual procede del registro anulado.
    if history.fecha_revisada_propuesta and line.fecha_revisada == history.fecha_revisada_propuesta:
        revision = line.historial.filter(activo=True, fecha_revisada_propuesta__isnull=False).order_by('-fecha_registro','-pk').first()
        first = line.historial.order_by('fecha_registro','pk').first()
        line.fecha_revisada = revision.fecha_revisada_propuesta if revision else first.fecha_revisada_anterior
    line.save()
    return history


@transaction.atomic
def corregir_historial(linea_id, history_id, actor, respuesta, fecha, motivo):
    from django.core.exceptions import ValidationError
    line = LineaOC.objects.select_for_update().get(pk=linea_id)
    old = HistorialSeguimiento.objects.select_for_update().get(pk=history_id, linea=line)
    if not old.activo:
        raise ValidationError('Esta entrada ya fue anulada o corregida. Actualiza la pantalla.')
    if not str(motivo or '').strip():
        raise ValidationError('Indica el motivo de la corrección.')
    anular_historial(line.pk, old.pk, actor, 'Corrección: ' + motivo.strip())
    line.refresh_from_db()
    corrected = registrar_interaccion_linea(line, respuesta, actor, fecha)
    old.refresh_from_db()
    old.motivo_anulacion = f'Corregido con registro #{corrected.pk}: {motivo.strip()}'[:500]
    old.save(update_fields=['motivo_anulacion'])
    return corrected
