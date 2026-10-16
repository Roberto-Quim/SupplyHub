# Arquitectura vigente

Patrón: URL → función pública/controlador Django → servicio → ORM/conector parametrizado → plantilla. El código de interfaz no ejecuta SQL.

## Fuente DataAnalytics revisada

Referencia local leída sin modificar: `C:/x/proyectos/SistemaDataAnalytics`, rama `feat-admin-perfiles-modulos-jerarquicos`, HEAD `23b1004d204e7f6b54585400d264a309edee3b97` (también se revisaron archivos actuales del checkout).

Se adaptaron los servicios reales de Usuarios, asignaciones por método, Perfiles, Módulos y plantas a `services/da_admin/`. Se sustituyeron imports del conector y configuración del proyecto, se ocultaron errores SQL en formularios y se reforzó el cierre de permisos ante errores. Los scripts SQL existentes 015–020 y 028 se incluyen como referencia de instalación, sin ejecutarlos.

Usuarios se guarda en dbo.Usuarios: cada fila es persona + IdAcceso + IdPerfil. Alta/edición usa `GuardarUsuarioMetodoAdminDAsp` del script 028. Las credenciales se autentican en AD/nómina/Google; ninguna pantalla administrativa guarda una contraseña corporativa. Google obtiene NoNomina de la fila autorizada; IdUsuario sigue siendo el ID de asignación. La sesión se revalida en cada solicitud corporativa y se cierra si la asignación cambia o se desactiva.

Perfiles y sus permisos usan dbo.Perfiles y dbo.PerfilModulos. Sus cambios son transaccionales en DataAnalytics. Módulos usa dbo.Modulos y dbo.Submodulo, con el mismo patrón SP-first y fallback solo por objetos faltantes reconocido por el sistema de referencia. Una caída real no provoca un cambio a almacenamiento local.

El menú lee nombres, grupos, orden y rutas del catálogo central, filtra permisos y solo enlaza endpoints existentes de SupplyHub. Los guards del backend siguen siendo obligatorios. Administración requiere TI/Administrador; ErrorLog además requiere TI. Se protegen rutas administrativas base y el acceso propio para evitar un bloqueo accidental.

## Datos operativos

SupplyHub conserva RFQ, OC, partidas, historial, SupplierSite, respuestas Gmail, consultas y recordatorios. SupplierSite tiene identidad única proveedor/sitio/planta, contacto y correo. Asociarlo a una OC comprueba proveedor y planta; solo completa correos de partidas que no tenían uno.

ErrorLog es la bitácora de errores de SupplyHub, no la de otros sistemas. Guarda folio, fecha y metadatos controlados; no guarda contraseñas, tokens, cuerpos de correo, query strings ni excepciones SQL. La auditoría administrativa registra actor/entidad/ID/acción. Si falla su persistencia después de una confirmación central, se registra la incidencia en el log del servidor; no se repite una escritura central ya confirmada. No hay transacción distribuida entre ambas bases.

## Desarrollo

DevPerfil/DevModulo/DevAsignacion son catálogos de demostración, disponibles solo con DEBUG, login local habilitado y DataAnalytics deshabilitado. Requieren superusuario; no alimentan autenticación corporativa y no se usan como fallback ante fallos centrales.

## Migraciones y auditoría

Se conserva la línea Gmail 0007/0008. La migración 0009 agrega activo, anulación con actor/motivo y fecha anterior sin retirar fuente ni fecha_interaccion. Reconoce un activo existente de la rama de auditoría y repone columnas históricas ausentes. Cuando fecha_interaccion fue eliminada por la rama anterior, se reconstruye a partir de fecha_registro; no se inventa la fecha original perdida. Las fuentes que ya hubieran sido borradas por otra migración requieren respaldo para recuperarse.

## Operación

Gmail usa gmail.readonly; sincronización manual o por el ejecutor programable, con deduplicación por buzón/mensaje. Conserva el límite de 30 días/250 mensajes y revisión humana de asociaciones/fechas. No implementa Gmail historyId ni adjuntos.

Los recordatorios se encolan como máximo una vez por partida y día, con intervalo de 24 horas. Solo los aprobados se envían por SMTP si está habilitado. Se marca EN_PROCESO antes de enviar; ante una respuesta incierta de SMTP no se reintenta automáticamente, pues el servidor podría haber aceptado el correo. Se requiere revisar antes de aprobar otro intento. No se promete exactamente una entrega SMTP ante fallos de red.
