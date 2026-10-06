"""Fachada de funciones públicas Django."""
from Controladores.auth_controller import (
    active_directory_login_view,
    logout_view,
    main_login_view,
    payroll_login_view,
)
from Controladores.hub_controller import hub_index

__all__ = [
    "main_login_view",
    "active_directory_login_view",
    "payroll_login_view",
    "logout_view",
    "hub_index",
]
