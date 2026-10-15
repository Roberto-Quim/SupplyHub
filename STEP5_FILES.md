# STEP 5: Módulo de Seguimiento de Órdenes de Compra (OC) & Control CAPEX

## Resumen del Paso
Implementación del módulo de seguimiento operativo de Órdenes de Compra importadas desde Oracle QES, junto con la extensión de auditoría y captura masiva para el módulo RFQ CAPEX.

---

## Archivos Creados y Modificados

### 1. Modelos & Capa de Dominio
* `Modelos/supplyhub/domain/rfq_capex.py`: Definición del modelo `RFQCapex` con campos de control (`comparativa`, `proveedor_seleccionado`, `numero_oc`, `fecha_oc`, `fecha_tentativa_entrega`, `fecha_entrega`, `en_tiempo`, `tiempo_total`).
* `Modelos/supplyhub/models.py`: Exportación unificada de modelos (`OrdenCompra`, `LineaOC`, `HistorialSeguimiento`, `RFQCapex`).

### 2. Servicios de Importación y Negocio
* `Modelos/supplyhub/services/importacion_oc_service.py`: Servicio de carga idempotente desde reportes Oracle QES Open PO.
* `Modelos/supplyhub/services/importacion_rfq_service.py`: Servicio de carga de RFQs desde Excel (Form Approvals / Seguimiento).
* `Modelos/supplyhub/services/seguimiento_oc_service.py`: Normalización de plantas (`IRA`, `MACIMEX RAMOS ARIZPE` -> `MAQ_RA`), evaluación de vencimientos e historial de seguimiento.

### 3. Controladores y Formularios
* `Controladores/seguimiento_oc_controller.py`: Controladores de listado con filtro múltiple de plantas y vista de detalle de partidas.
* `Modelos/supplyhub/forms/rfq_capex.py`: Formularios `RFQCapexForm`, `RFQEstadoForm` y `RFQDecisionForm`.

### 4. Vistas y Plantillas (UI)
* `Vistas/seguimiento_oc/index.html`: Listado dinámico con selector múltiple desplegable por planta estilo Excel/PowerBI.
* `Vistas/seguimiento_oc/detalle.html`: Detalle de partidas QES con banderas de estatus (`✓ AL DÍA` / `⚠️ VENCIDO`) y formulario de interacción.
* `Vistas/rfq_capex/nuevo.html`: Formulario de captura manual con sección de control para Edith y acceso a carga masiva.

### 5. Suite de Pruebas
* `tests/test_seguimiento_oc.py`: Pruebas unitarias automatizadas para normalización, semaforización e importación masiva.

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
