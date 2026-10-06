from django.conf import settings

from .menu_service import build_menu


def supplyhub_context(request):
    user = getattr(request, "user", None)
    session = getattr(request, "session", {})
    authenticated = bool(getattr(user, "is_authenticated", False))
    id_perfil = int(session.get("sh_id_perfil", 0) or 0)

    return {
        "supplyhub_name": "SupplyHub",
        "supplyhub_authenticated": authenticated,
        "supplyhub_identity": {
            "usuario": session.get("sh_usuario", ""),
            "id_usuario": session.get("sh_id_usuario", 0),
            "id_perfil": id_perfil,
            "metodo_acceso": session.get("sh_metodo_acceso", 0),
            "no_nomina": session.get("sh_no_nomina", ""),
            "correo": session.get("sh_correo", ""),
            "display_name": session.get("sh_display_name", ""),
            "source": session.get("sh_identity_source", ""),
        },
        "supplyhub_auth": {
            "local": settings.SUPPLYHUB_LOCAL_AUTH_ENABLED,
            "google": settings.GOOGLE_OAUTH_ENABLED,
            "ad": settings.AD_LDAP_ENABLED,
            "payroll": settings.PAYROLL_AUTH_ENABLED,
            "dataanalytics": settings.DATAANALYTICS_ENABLED,
        },
        "supplyhub_menu": build_menu(id_perfil) if authenticated else [],
    }
