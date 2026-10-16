"""Revalida la asignación exacta; una baja o cambio de perfil revoca la sesión existente."""
from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect


class CorporateSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DATAANALYTICS_ENABLED and settings.SUPPLYHUB_REVALIDATE_SESSION and request.user.is_authenticated:
            from .dataanalytics_access_service import validate_user, clear_session_identity, TIPO_NOMINA, TIPO_CORREO
            session = request.session
            method = session.get('sh_metodo_acceso', 0)
            payroll, email = session.get('sh_no_nomina', ''), session.get('sh_correo', '')
            pair = validate_user(TIPO_NOMINA if payroll else TIPO_CORREO, no_nomina=payroll or None, correo=email or None, metodo_acceso=method) if method in [1,2,3] else (0,0)
            if not pair[0] or not pair[1] or pair != (session.get('sh_id_usuario'), session.get('sh_id_perfil')):
                clear_session_identity(session)
                logout(request)
                return redirect(settings.LOGIN_URL)
        return self.get_response(request)
