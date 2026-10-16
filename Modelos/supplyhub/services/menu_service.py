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
            {"label": "Log de Errores", "url_name": "supplyhub:admin_error_logs", "route": "/administracion/error-logs/"},
        ],
    },
]


def build_menu(id_perfil: int) -> list[dict]:
    allowed = get_allowed_routes(id_perfil)
    if allowed is None:
        from supplyhub.models import DevModulo
        from django.conf import settings
        from django.urls import resolve, Resolver404
        base = deepcopy(MENU_CATALOG)
        if not (settings.DEBUG and settings.SUPPLYHUB_LOCAL_AUTH_ENABLED):
            return base
        try:
            overrides = list(DevModulo.objects.all())
        except Exception:
            return base
        for module in overrides:
            for parent in base:
                parent['children'] = [c for c in parent['children'] if c['route'] != module.ruta]
            if not module.activo:
                continue
            try:
                match = resolve(module.ruta)
            except Resolver404:
                continue
            if match.app_name != 'supplyhub':
                continue
            parent = next((p for p in base if p['label'] == module.grupo), None)
            if parent is None:
                parent = {'key':module.grupo,'label':module.grupo,'children':[]}
                base.append(parent)
            parent['children'].append({'label':module.nombre,'route':module.ruta,'order':module.orden})
        for parent in base:
            parent['children'].sort(key=lambda c:c.get('order',0))
        return [p for p in base if p['children']]

    from .da_admin import dataanalytics_modulos_service as modules
    from django.urls import resolve, Resolver404
    try:
        parents = {m['id_modulo']:m for m in modules.list_modulos(solo_activos=True)}
        children = modules.list_submodulos(solo_activos=True)
    except Exception:
        return []
    grouped = {}
    for child in children:
        route = normalize_route(child['ruta'])
        parent = parents.get(child['id_modulo'])
        if not parent or route not in allowed:
            continue
        try:
            match = resolve(route)
        except Resolver404:
            continue
        # Menú propio: no publicar rutas de otro sistema que comparte DataAnalytics.
        if match.app_name != 'supplyhub':
            continue
        entry = grouped.setdefault(parent['id_modulo'], {'key':str(parent['id_modulo']), 'label':parent['modulo'], 'order':parent['orden'], 'children':[]})
        entry['children'].append({'label':child['submodulo'], 'route':route, 'order':child['orden']})
    result = sorted(grouped.values(), key=lambda p:(p['order'],p['label']))
    for parent in result:
        parent['children'].sort(key=lambda c:(c['order'],c['label']))
    return result
