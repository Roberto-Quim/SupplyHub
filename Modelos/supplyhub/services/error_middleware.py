from django.conf import settings
from django.shortcuts import render


class ErrorLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code in [403,404] and not request.path.startswith('/static/') and request.path != '/favicon.ico':
            from .administracion_service import record_error
            record_error('Acceso denegado' if response.status_code == 403 else 'Ruta no encontrada', request)
        return response

    def process_exception(self, request, exception):
        from django.core.exceptions import PermissionDenied
        from django.http import Http404
        if isinstance(exception, (PermissionDenied, Http404)):
            return None
        from .administracion_service import record_error
        record = record_error('Solicitud HTTP', request)
        if not settings.DEBUG:
            return render(request, 'shared/error.html', {'reference': record.referencia if record else ''}, status=500)
        return None
