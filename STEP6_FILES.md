> Documento histórico de esta entrega. Estado y plan vigentes: [docs/ESTADO.md](docs/ESTADO.md) y [docs/PLAN.md](docs/PLAN.md).

# STEP 6: Consolidación de Requerimientos de Negocio (Edith & Jacqueline)

## Resumen del Paso
Implementación del parser de notificaciones por correo de Form Approvals para el módulo RFQ CAPEX, junto con la extensión operativa del módulo de Seguimiento de OC adaptada al flujo de Jacqueline (columna Release, bitácora de seguimiento y exclusión de Macimex Tenango).

---

## Archivos Creados y Modificados

### 1. Modelos & Capa de Dominio
- `Modelos/supplyhub/domain/rfq_capex.py`: Integración del estado `CANCELADO` en la enumeración de estatus de RFQ CAPEX.
- `Modelos/supplyhub/models.py`: Incorporación de campos extendidos en `LineaOC` (`comentarios`, `dias_tarde`, `stock`, `min_max`, `fecha_embarque_proveedor`, `fecha_entrega_planta`).
- `Modelos/supplyhub/migrations/0006_lineaoc_comentarios_lineaoc_dias_tarde_and_more.py`: Migración de base de datos para los nuevos campos de persistencia en `LineaOC`.

### 2. Servicios de Importación y Negocio
- `Modelos/supplyhub/services/parser_rfq_service.py`: Servicio de parseo automático mediante expresiones regulares para extraer datos clave desde correos de Form Approvals.
- `Modelos/supplyhub/services/seguimiento_oc_service.py`: Extensión de la lógica de negocio para gestionar el historial y evaluación de partidas de órdenes de compra.

### 3. Controladores y Formularios
- `Controladores/rfq_capex_controller.py`: Integración del servicio de importación Excel y gestión de formularios de captura/edición con estado `CANCELADO`.
- `Controladores/seguimiento_oc_controller.py`: Exclusión estricta de Macimex Tenango, procesamiento del formulario POST de seguimiento por línea e importación dinámica del servicio Excel.
- `Modelos/supplyhub/forms/seguimiento_linea.py`: Formulario con catálogo de respuestas predeterminadas frecuentes de seguimiento (`OPCIONES_RESPUESTA_PREDETERMINADA`).
- `Modelos/supplyhub/urls.py`: Declaración de alias de rutas `rfq_capex` y `rfq_capex_index` para compatibilidad completa entre el menú global y las vistas internas.

### 4. Vistas y Plantillas (UI)
- `Vistas/rfq_capex/form.html` & `Vistas/rfq_capex/nuevo.html`: Inclusión del acordeón interactivo con script JavaScript para autocompletar el formulario al pegar texto de correo.
- `Vistas/seguimiento_oc/index.html`: Estructura limpia de tabla general con la nueva columna **Release ($R$)** y filtro ajustado para omitir Macimex Tenango.
- `Vistas/seguimiento_oc/detalle.html`: Vista detallada por partida con autoinserción de fecha corta en plantillas rápidas de respuesta y renderizado del historial cronológico.

---

## Ejecución de Pruebas
```bash
python Otros/manage.py test tests
```

## Correcciones de integración (14 de octubre de 2026)
- Carga OC conectada a `importar_oracle_open_po`, con formulario de archivo y resumen real.
- Captura de seguimiento validada y atómica, con bitácora y campos actuales sincronizados.
- Pantalla de importación RFQ y manejo de errores de lectura/filas.
- Persistencia de campos de control CAPEX al crear y editar.
- Dependencias Excel declaradas y transacción por fila para aislar errores.
- Regresiones cubiertas en `tests/test_step56_integration.py`.

Step 7 queda pendiente de definición. No se incluye automatización de correos/recordatorios en esta corrección.

Validación ejecutada: 25 pruebas aprobadas; `manage.py check` sin errores; `makemigrations --check --dry-run` sin cambios pendientes. Pruebas locales con SQLite, sin servicios corporativos ni navegador.
