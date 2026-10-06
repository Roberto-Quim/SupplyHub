from django.urls import path

from . import views

app_name = "supplyhub"

urlpatterns = [
    path("", views.hub_index, name="hub_index"),
    path("ad-login/", views.active_directory_login_view, name="ad_login"),
    path("nomina-login/", views.payroll_login_view, name="payroll_login"),

    path("hub/rfq-capex/", views.rfq_capex_index, name="rfq_capex"),
    path("hub/seguimiento-oc/", views.seguimiento_oc_index, name="seguimiento_oc"),

    path("administracion/usuarios/", views.usuarios_index, name="admin_usuarios"),
    path("administracion/perfiles/", views.perfiles_index, name="admin_perfiles"),
    path("administracion/modulos/", views.modulos_index, name="admin_modulos"),
    path("administracion/supplier-sites/", views.supplier_sites_index, name="admin_supplier_sites"),
    path("administracion/catalogos/", views.catalogos_index, name="admin_catalogos"),
]
