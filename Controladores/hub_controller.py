from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def hub_index(request):
    """Pantalla raíz autenticada de SupplyHub.

    Los permisos por submódulo se incorporan en el Paso 3. En este Paso 2 se
    exige sesión válida y se muestra la identidad de autorización disponible.
    """
    return render(
        request,
        "hub/index.html",
        {
            "page_title": "SupplyHub",
            "foundation_ready": True,
            "auth_ready": True,
        },
    )
