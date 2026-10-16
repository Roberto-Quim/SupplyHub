# Estado de la entrega — 16 de octubre de 2026

Rama de entrega: feat/8.5, sobre f1cee3d (Feat 8). main permanece sin cambios.

## Implementado

- Cinco submódulos completos: Usuarios, Perfiles, Módulos, Supplier Sites y ErrorLog; búsquedas, formularios, estados, paginación y guards. ErrorLog es solo lectura y exclusivo TI.
- Servicios centrales derivados de la implementación real local de DataAnalytics, preservando asignaciones por método, jerarquía y transacciones. Catálogos Dev aislados de producción.
- Menú central por nombres/rutas/orden y permisos; siembra idempotente de rutas.
- NoNomina resuelta desde la asignación, no desde IdUsuario. Revocación de sesiones corporativas al cambiar la asignación.
- Correcciones heredadas de Feat 5–8, proveedor seleccionado CAPEX y auditoría de estado en importación; creador original preservado.
- OC con filtros por comprador/proveedor/plantas, asociación de Supplier Site e importación MIN–MAX por planta/artículo.
- Edición de seguimiento mediante una corrección que conserva el original; anulación lógica con motivo/actor/fecha; conservación de fuente y fecha_interaccion; recálculo desde entradas activas.
- Cola diaria de recordatorios, aprobación humana, SMTP opt-in y ejecutor programable; consulta Gmail periódica opt-in.
- Migración 0009 aditiva, prueba de compatibilidad con el esquema divergente de auditoría y workflow de CI.

## Validación

Suite final completa: **85/85 pruebas aprobadas** en SQLite, incluidas las regresiones de IDs inválidos. `check` sin errores, `makemigrations --check --dry-run` sin cambios pendientes y revisión de espacios sin errores.

Los tests usan SQLite y ejemplos sintéticos; Google/SMTP/DataAnalytics se simulan. Se verifican permisos, CSRF, aislamiento por dueño, importaciones, transacciones con rollback, historial, recordatorios e integridad de migración. La referencia corporativa y sources no se modificaron.

## Límites reales

- No se ejecutaron SP ni modificaciones en DataAnalytics corporativo. Se necesita validar conexión, esquema y privilegios reales.
- No se conectaron buzones Google ni se enviaron correos reales. La consulta Gmail sigue limitada a 30 días/250 mensajes y no usa historyId.
- Forms automático, integración directa Oracle y adjuntos no están implementados; quedan los adaptadores de texto/Excel y Gmail de proveedores documentados.
- La tarea del sistema, HTTPS, plataforma de hosting y despliegue no se instalaron. El ejecutor está listo para programarse tras validar el ambiente.
- Navegador: se intentó acceder al servidor temporal en localhost, pero el navegador automatizable no pudo alcanzarlo y no había Chrome conectado. Se verifican respuestas HTML de las pantallas mediante Django; no se afirma validación visual.
- Concurrencia real y un SMTP con respuesta incierta requieren pruebas operativas; no se promete entrega exactamente una vez ante interrupciones de red.

Ver PLAN.md, ARQUITECTURA.md, DESPLIEGUE.md y RAMAS_REVISADAS.md.
