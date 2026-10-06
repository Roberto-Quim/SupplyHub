from copy import deepcopy

from .dataanalytics_permissions_service import get_allowed_routes, normalize_route

MENU_CATALOG = [
    {
        "key": "hub",
        "label": "HUB",
        "children": [
            {
                "label": "RFQ / CAPEX",
                "url_name": "supplyhub:rfq_capex",
                "route": "/hub/rfq-capex/",
                "description": "Solicitudes y seguimiento de cotización CAPEX.",
            },
            {
                "label": "Seguimiento de Órdenes de Compra",
                "url_name": "supplyhub:seguimiento_oc",
                "route": "/hub/seguimiento-oc/",
                "description": "Órdenes, proveedores, vencidos, respuestas y recordatorios.",
            },
        ],
    },
    {
        "key": "administracion",
        "label": "Administración",
        "children": [
            {"label": "Usuarios", "url_name": "supplyhub:admin_usuarios", "route": "/administracion/usuarios/"},
            {"label": "Perfiles", "url_name": "supplyhub:admin_perfiles", "route": "/administracion/perfiles/"},
            {"label": "Módulos", "url_name": "supplyhub:admin_modulos", "route": "/administracion/modulos/"},
            {"label": "Supplier Sites", "url_name": "supplyhub:admin_supplier_sites", "route": "/administracion/supplier-sites/"},
            {"label": "Catálogos", "url_name": "supplyhub:admin_catalogos", "route": "/administracion/catalogos/"},
        ],
    },
]


def build_menu(id_perfil: int) -> list[dict]:
    allowed = get_allowed_routes(id_perfil)
    if allowed is None:
        return deepcopy(MENU_CATALOG)

    result = []
    for parent in MENU_CATALOG:
        children = [
            deepcopy(child)
            for child in parent["children"]
            if normalize_route(child["route"]) in allowed
        ]
        if children:
            item = {"key": parent["key"], "label": parent["label"], "children": children}
            result.append(item)
    return result
