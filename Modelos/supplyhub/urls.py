from django.urls import path
from . import views
from Controladores.seguimiento_oc_controller import (
    seguimiento_oc_index,
    seguimiento_oc_detalle,
    importar_oc_view
)

from Controladores.rfq_capex_controller import (
    rfq_capex_index,
    rfq_capex_create,
    rfq_capex_edit,
    rfq_capex_detail,
    rfq_capex_status,
    rfq_capex_decision,
    rfq_capex_import,
)

app_name = "supplyhub"

urlpatterns = [
    path("", views.hub_index, name="hub_index"),
    path("ad-login/", views.active_directory_login_view, name="ad_login"),
    path("nomina-login/", views.payroll_login_view, name="payroll_login"),

    # Rutas RFQ / CAPEX (Se declaran ambos alias para compatibilidad con menú y vistas)
    path("hub/rfq-capex/", rfq_capex_index, name="rfq_capex"),
    path("hub/rfq-capex/", rfq_capex_index, name="rfq_capex_index"),
    path("hub/rfq-capex/nuevo/", rfq_capex_create, name="rfq_capex_create"),
    path("hub/rfq-capex/importar/", rfq_capex_import, name="importar_rfq_capex"),
    path("hub/rfq-capex/<int:pk>/", rfq_capex_detail, name="rfq_capex_detail"),
    path("hub/rfq-capex/<int:pk>/editar/", rfq_capex_edit, name="rfq_capex_edit"),
    path("hub/rfq-capex/<int:pk>/estado/", rfq_capex_status, name="rfq_capex_status"),
    path("hub/rfq-capex/<int:pk>/decision/", rfq_capex_decision, name="rfq_capex_decision"),

    # Rutas Seguimiento de OC
    path("hub/seguimiento-oc/", seguimiento_oc_index, name="seguimiento_oc"),
    path("hub/seguimiento-oc/<int:pk>/", seguimiento_oc_detalle, name="seguimiento_oc_detalle"),
    path("hub/seguimiento-oc/importar/", importar_oc_view, name="importar_oc"),

    # Rutas Administración
    path("administracion/usuarios/", views.usuarios_index, name="admin_usuarios"),
    path("administracion/perfiles/", views.perfiles_index, name="admin_perfiles"),
    path("administracion/modulos/", views.modulos_index, name="admin_modulos"),
    path("administracion/supplier-sites/", views.supplier_sites_index, name="admin_supplier_sites"),
    path("administracion/catalogos/", views.catalogos_index, name="admin_catalogos"),
]