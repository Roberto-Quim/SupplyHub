"""Cola de recordatorios cada 24 h, aprobación humana y ejecución programable."""
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from supplyhub.models import LineaOC, RecordatorioOC, GmailMailbox
from .administracion_service import record_error


def generate_reminders(now=None):
    now = now or timezone.now()
    generated = 0
    candidates = LineaOC.objects.exclude(orden__planta_normalizada='MACIMEX_TENANGO').filter(
        orden__estado='ABIERTA', cantidad_pendiente__gt=0).exclude(estado_entrega__in=['ENTREGADA','CANCELADA'])
    for candidate in candidates.iterator():
        with transaction.atomic():
            line = LineaOC.objects.select_for_update().get(pk=candidate.pk)
            due = line.proximo_recordatorio or (line.ultima_interaccion + timedelta(hours=24) if line.ultima_interaccion else now)
            if due > now:
                continue
            # Una fila por partida y día; repetir la tarea no vuelve a encolarla.
            slot = now.astimezone(timezone.get_current_timezone()).date().isoformat()
            _, created = RecordatorioOC.objects.get_or_create(clave_idempotencia=f'{line.pk}:{slot}', defaults={'linea':line, 'fecha_programada':now})
            generated += created
            line.proximo_recordatorio = now + timedelta(hours=24)
            line.save(update_fields=['proximo_recordatorio'])
    return generated


@transaction.atomic
def approve_reminder(pk, actor):
    item = RecordatorioOC.objects.select_for_update().select_related('linea__orden').get(pk=pk)
    if item.estado not in ['PROGRAMADO','FALLIDO']:
        return False
    if item.linea.orden.planta_normalizada == 'MACIMEX_TENANGO':
        return False
    validate_email(item.linea.correo_proveedor)
    item.aprobado_por = str(actor)
    item.aprobado_en = timezone.now()
    item.destinatario_aprobado = item.linea.correo_proveedor.strip().lower()
    item.estado = 'GENERADO'
    item.save(update_fields=['aprobado_por','aprobado_en','destinatario_aprobado','estado'])
    return True


def send_approved(now=None):
    if not settings.REMINDERS_SEND_ENABLED:
        return 0
    now = now or timezone.now()
    sent = 0
    for pk in RecordatorioOC.objects.filter(estado='GENERADO', aprobado_en__isnull=False, fecha_programada__lte=now).values_list('pk',flat=True).iterator():
        with transaction.atomic():
            item = RecordatorioOC.objects.select_for_update().select_related('linea__orden').get(pk=pk)
            if item.estado != 'GENERADO':
                continue
            line = item.linea
            if not item.destinatario_aprobado or item.destinatario_aprobado != line.correo_proveedor.strip().lower() or line.orden.planta_normalizada == 'MACIMEX_TENANGO' or line.orden.estado != 'ABIERTA' or line.cantidad_pendiente <= 0 or line.estado_entrega in ['ENTREGADA','CANCELADA'] or (line.ultima_interaccion and line.ultima_interaccion > item.aprobado_en):
                item.estado = 'OMITIDO'
                item.save(update_fields=['estado'])
                continue
            try:
                validate_email(line.correo_proveedor)
            except Exception:
                item.estado = 'FALLIDO'
                item.ultimo_error = 'El correo del proveedor no es válido.'
                item.save(update_fields=['estado','ultimo_error'])
                continue
            item.estado = 'EN_PROCESO'
            item.intentos += 1
            item.save(update_fields=['estado','intentos'])
        try:
            count = send_mail(
                f'Seguimiento OC {line.orden.numero_oc} / Release {line.release} / Línea {line.numero_linea}',
                f'Buen día. Solicitamos confirmar el estado y la fecha de entrega de {line.descripcion}.\nOC {line.orden.numero_oc}, release {line.release}, línea {line.numero_linea}.',
                settings.DEFAULT_FROM_EMAIL, [item.destinatario_aprobado], fail_silently=False,
            )
            if count != 1:
                raise RuntimeError('No confirmado')
        except Exception:
            RecordatorioOC.objects.filter(pk=pk,estado='EN_PROCESO').update(estado='FALLIDO',ultimo_error='Envío no confirmado. Revisar el correo enviado antes de aprobar otro intento.')
            record_error('Recordatorios SMTP')
        else:
            RecordatorioOC.objects.filter(pk=pk,estado='EN_PROCESO').update(estado='ENVIADO',fecha_ejecucion=timezone.now(),ultimo_error='')
            sent += 1
    return sent


def sync_mailboxes():
    if not settings.GMAIL_BACKGROUND_SYNC_ENABLED:
        return 0
    from .gmail_service import sync, GmailError
    count = 0
    for mailbox in GmailMailbox.objects.filter(is_demo=False).exclude(encrypted_tokens='').iterator():
        if mailbox.last_sync and mailbox.last_sync > timezone.now()-timedelta(minutes=settings.GMAIL_SYNC_INTERVAL_MINUTES):
            continue
        try:
            count += sync(mailbox)
        except GmailError:
            continue
    return count
