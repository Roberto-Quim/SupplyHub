# Compras Indirectas — plan y flujo vigente

Referencia: levantamiento de Jacqueline, reportes Open PO y MIN–MAX disponibles en esta carpeta. Los originales se mantienen como referencia; no se usan como fixtures de prueba.

1. Importar el reporte Oracle Open PO desde Seguimiento OC. La clave de partida es OC + Release + Línea; repetir el mismo reporte actualiza sin duplicar.
2. Filtrar por comprador (incluida Tannia), proveedor y plantas. Tenango queda fuera del flujo de seguimiento.
3. Administrar Supplier Sites por proveedor, código y planta. Asociar el sitio a una OC; proveedor y planta deben coincidir. Completar correo solo donde no exista uno registrado.
4. Importar el reporte MIN–MAX (hoja Data). Se cruza por planta y artículo: suma On Hand de ubicaciones y exige mínimos/máximos coherentes. Si hay rangos distintos, pide revisión y conserva la partida anterior.
5. Registrar respuesta del proveedor, fecha revisada, embarque, entrega a planta, stock y MIN–MAX. Conservar historial por usuario y fecha.
6. Si una nota es incorrecta, anular con motivo; permanece visible como anulada. Se recalculan comentario y fecha derivados del historial activo sin borrar la entrada original.
7. Consultar Gmail manualmente o mediante la tarea configurada. Elegir partida/release y confirmar comentario/fecha; las coincidencias no se aplican automáticamente.
8. Revisar recordatorios diarios y aprobar destinatarios. El proceso programable envía solo aprobados con SMTP habilitado, registra estados y evita reintentos automáticos de envíos inciertos.

## Pendiente de validación de negocio/ambiente

Revisar con Jacqueline correos y catálogo reales, semáforos, rangos MIN–MAX y destinatarios. Oracle sigue siendo importación de archivos; no existe un contrato aprobado ni una conexión directa a Oracle en esta entrega. Gmail real, SMTP y despliegue no se probaron con cuentas corporativas.
