from django.shortcuts import render

from supplyhub.services.permission_guard import supplyhub_route_required


def _page(request, title, description):
    return render(request, "shared/module_placeholder.html", {
        "module_group": "Administración",
        "module_title": title,
        "module_description": description,
        "module_status": "Ruta y guard de permisos listos; CRUD se implementará por fases.",
    })


@supplyhub_route_required("/administracion/usuarios/")
def usuarios_index(request):
    return _page(request, "Usuarios", "Usuarios corporativos autorizados para SupplyHub.")


@supplyhub_route_required("/administracion/perfiles/")
def perfiles_index(request):
    return _page(request, "Perfiles", "Perfiles y permisos por submódulo.")


@supplyhub_route_required("/administracion/modulos/")
def modulos_index(request):
    return _page(request, "Módulos", "HUB, Administración y sus submódulos.")


@supplyhub_route_required("/administracion/supplier-sites/")
def supplier_sites_index(request):
    return _page(request, "Supplier Sites", "Catálogo de sitios de proveedor para seguimiento.")


@supplyhub_route_required("/administracion/catalogos/")
def catalogos_index(request):
    return _page(request, "Catálogos", "Catálogos compartidos de SupplyHub.")
