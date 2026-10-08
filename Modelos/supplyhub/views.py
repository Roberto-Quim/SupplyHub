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
from Controladores.modules_controller import seguimiento_oc_index
from Controladores.rfq_capex_controller import (
    rfq_capex_create,
    rfq_capex_decision,
    rfq_capex_detail,
    rfq_capex_edit,
    rfq_capex_index,
    rfq_capex_status,
)

__all__ = [
    "main_login_view",
    "active_directory_login_view",
    "payroll_login_view",
    "logout_view",
    "hub_index",
    "rfq_capex_index",
    "rfq_capex_create",
    "rfq_capex_edit",
    "rfq_capex_detail",
    "rfq_capex_status",
    "rfq_capex_decision",
    "seguimiento_oc_index",
    "usuarios_index",
    "perfiles_index",
    "modulos_index",
    "supplier_sites_index",
    "catalogos_index",
]
