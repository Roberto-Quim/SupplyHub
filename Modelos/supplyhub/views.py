"""Fachada de funciones públicas Django."""
from Controladores.administracion_controller import (
    catalogos_index,
    modulos_index,
    perfiles_index,
    supplier_sites_index,
    usuarios_index,
)
from Controladores.auth_controller import (
    active_directory_login_view,
    logout_view,
    main_login_view,
    payroll_login_view,
)
from Controladores.hub_controller import hub_index
from Controladores.modules_controller import rfq_capex_index, seguimiento_oc_index

__all__ = [
    "main_login_view",
    "active_directory_login_view",
    "payroll_login_view",
    "logout_view",
    "hub_index",
    "rfq_capex_index",
    "seguimiento_oc_index",
    "usuarios_index",
    "perfiles_index",
    "modulos_index",
    "supplier_sites_index",
    "catalogos_index",
]
