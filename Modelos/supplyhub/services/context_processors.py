def supplyhub_context(request):
    """Contexto global mínimo; Fase 2 añadirá identidad, perfil y menú dinámico."""
    return {
        "supplyhub_name": "SupplyHub",
        "supplyhub_authenticated": bool(
            getattr(getattr(request, "user", None), "is_authenticated", False)
        ),
    }
