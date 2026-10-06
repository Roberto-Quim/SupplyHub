from django.shortcuts import render

from supplyhub.services.permission_guard import supplyhub_route_required


@supplyhub_route_required("/hub/rfq-capex/")
def rfq_capex_index(request):
    return render(request, "shared/module_placeholder.html", {
        "module_group": "HUB",
        "module_title": "RFQ / CAPEX",
        "module_description": "Aplicación de Compras Directas / flujo de Edith.",
        "module_status": "Estructura habilitada. La lógica de negocio entra en el Paso 4.",
    })


@supplyhub_route_required("/hub/seguimiento-oc/")
def seguimiento_oc_index(request):
    return render(request, "shared/module_placeholder.html", {
        "module_group": "HUB",
        "module_title": "Seguimiento de Órdenes de Compra",
        "module_description": "Aplicación de Compras Indirectas / flujo de Jacky.",
        "module_status": "Estructura habilitada. La migración del dominio entra en el Paso 5.",
    })
