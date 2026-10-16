# Plan original de SupplyHub

Actualización: 16 de octubre de 2026. Se conserva el orden de la arquitectura fundacional; la numeración histórica STEP6/7/8 cambió de alcance y no demuestra por sí sola el cierre de cada fase.

| Fase original | Implementación en esta entrega | Validación externa restante |
|---|---|---|
| 1. Fundación MVC, configuración y cifrado | Django, servicios, plantillas, Fernet | Configuración de secretos del ambiente |
| 2. Autenticación corporativa y autorización central | AD, nómina y Google; asignación exacta por método; nómina real y revocación de sesión | Probar proveedores y SP con cuentas autorizadas |
| 3. HUB, Administración y seed de permisos | Menú central; comando idempotente de siembra; guards en servidor | Ejecutar siembra central con TI y revisar perfiles |
| 4. Dominio RFQ/CAPEX | Captura, edición, estados, decisión, historial e importación auditada | Validar ejemplos reales y criterios de negocio |
| 5. Seguimiento OC | Open PO, releases, partidas, Supplier Sites, MIN–MAX, filtros, bitácora y anulación lógica | Validación operativa con Jacqueline |
| 6. Recordatorios cada 24 h e idempotencia | Cola diaria, revisión, aprobación, SMTP opt-in y tarea ejecutable | SMTP real, tarea del sistema y aprobación de destinatarios |
| 7. Integraciones Forms/Oracle/Gmail según aprobación | Parser Form Approvals al pegar texto; importación Excel de Oracle y MIN–MAX; Gmail readonly y consulta programable | OAuth real; Oracle directo y captura automática de Forms no implementados sin un contrato de origen aprobado |
| 8. Hardening, pruebas, documentación y despliegue | Tests, migración compatible con auditoría, CI, manual de despliegue, errores seguros | Navegador accesible, concurrencia con base productiva y despliegue real |

## Cinco submódulos finales

Usuarios, Perfil, Módulo, SupplierSite y ErrorLog. Catálogos queda como alias compatible de Supplier Sites; el menú muestra los cinco requeridos. ErrorLog respeta el modelo DataAnalytics de consulta exclusiva de TI, sin CRUD de errores.

## Criterios

No sustituir DataAnalytics por una copia SQLite en producción; no convertir IdUsuario en nómina. Conservar historiales y fuente, sin borrados físicos desde las pantallas. No confundir código terminado con conexiones reales validadas o un despliegue ya realizado.
