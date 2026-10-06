from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def hub_index(request):
    """Inicio autenticado con HUB y Administración filtrados por perfil."""
    return render(
        request,
        "hub/index.html",
        {
            "page_title": "SupplyHub",
            "foundation_ready": True,
            "auth_ready": True,
            "step3_ready": True,
        },
    )
