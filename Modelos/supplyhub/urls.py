from django.urls import path
from . import views
from Controladores import administracion_controller as administration
from Controladores import seguimiento_oc_controller as tracking
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

from Controladores import gmail_controller as gmail

app_name = "supplyhub"

urlpatterns = [
    path('hub/seguimiento-oc/<int:pk>/historial/<int:history_pk>/editar/', tracking.editar_historial_view, name='editar_historial'),
    path('hub/seguimiento-oc/inventario/', tracking.importar_min_max_view, name='importar_min_max'),
    path('hub/seguimiento-oc/recordatorios/', tracking.recordatorios_view, name='recordatorios'),
    path('hub/seguimiento-oc/<int:pk>/historial/<int:history_pk>/anular/', tracking.anular_historial_view, name='anular_historial'),
    path('hub/seguimiento-oc/<int:pk>/supplier-site/', tracking.asignar_supplier_site, name='asignar_supplier_site'),
    path('administracion/usuarios/<int:pk>/editar/', administration.usuarios_index, name='admin_usuarios_editar'),
    path('administracion/perfiles/<int:pk>/editar/', administration.perfiles_index, name='admin_perfiles_editar'),
    path('administracion/modulos/<int:pk>/editar/', administration.modulos_index, name='admin_modulos_editar'),
    path('administracion/modulos/padre/crear/', administration.modulo_padre, name='admin_modulo_padre_crear'),
    path('administracion/modulos/padre/<int:pk>/', administration.modulo_padre, name='admin_modulo_padre'),
    path('administracion/supplier-sites/<int:pk>/editar/', administration.supplier_sites_index, name='admin_supplier_sites_editar'),
    path('administracion/error-logs/', administration.error_logs_index, name='admin_error_logs'),
    path('hub/correos/partida/<int:pk>/proveedor/', gmail.supplier_email, name='gmail_supplier_email'),
    path('hub/correos/', gmail.index, name='gmail_index'),
    path('hub/correos/conectar/', gmail.start, name='gmail_start'),
    path('hub/correos/callback/', gmail.callback, name='gmail_callback'),
    path('hub/correos/<int:pk>/sincronizar/', gmail.sync, name='gmail_sync'),
    path('hub/correos/<int:pk>/desconectar/', gmail.disconnect, name='gmail_disconnect'),
    path('hub/correos/respuestas/<int:pk>/revisar/', gmail.review, name='gmail_review'),
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