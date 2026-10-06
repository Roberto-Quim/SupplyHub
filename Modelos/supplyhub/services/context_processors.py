from django.conf import settings


def supplyhub_context(request):
    user = getattr(request, "user", None)
    session = getattr(request, "session", {})
    return {
        "supplyhub_name": "SupplyHub",
        "supplyhub_authenticated": bool(getattr(user, "is_authenticated", False)),
        "supplyhub_identity": {
            "id_usuario": session.get("sh_id_usuario", 0),
            "id_perfil": session.get("sh_id_perfil", 0),
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
    }
