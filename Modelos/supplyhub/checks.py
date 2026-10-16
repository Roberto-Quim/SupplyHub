from django.conf import settings
from django.core.checks import Error, register


@register(deploy=True)
def deployment_integrations(app_configs, **kwargs):
    errors = []
    if not settings.DEBUG and not settings.DATAANALYTICS_ENABLED:
        errors.append(Error('Producción requiere autorización central DataAnalytics.', id='supplyhub.E001'))
    if settings.GMAIL_BACKGROUND_SYNC_ENABLED and not settings.GMAIL_ENABLED:
        errors.append(Error('La consulta programada requiere Gmail habilitado y configurado.', id='supplyhub.E002'))
    if settings.REMINDERS_SEND_ENABLED and (not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL):
        errors.append(Error('Los envíos requieren EMAIL_HOST y DEFAULT_FROM_EMAIL.', id='supplyhub.E003'))
    return errors
