from django.shortcuts import render


def hub_index(request):
    """Pantalla raíz del HUB. En Fase 2 quedará protegida por sesión y permisos."""
    return render(
        request,
        "hub/index.html",
        {
            "page_title": "SupplyHub",
            "foundation_ready": True,
        },
    )
