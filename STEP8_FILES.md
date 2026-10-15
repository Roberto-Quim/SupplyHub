# STEP 8 — Operación local y preparación de pruebas

Implementado sobre `feat/step7-gmail`. Esta rama incluye Step 7 y las correcciones de Step 5/6. No implica que main haya sido actualizado ni que Gmail real esté validado.

## Funcionalidad
- Panel de Correos con configuración habilitada/pendiente, credencial presente/desconectada, última consulta exitosa y número de respuestas pendientes del usuario.
- Bitácora de las últimas 30 consultas propias, con inicio, fin, estado y nuevas respuestas de consultas completas.
- Exclusión de consultas simultáneas por buzón mediante transacción y bloqueo de fila. Una consulta interrumpida puede recuperarse pasados 30 minutos; el intento previo se marca fallido.
- Tras un fallo, espera mínima de 60 segundos. El usuario vuelve a consultar manualmente; no hay bucles automáticos ni envíos.
- Fallos parciales conservan respuestas ya guardadas. El siguiente intento no las duplica. La bitácora indica que el recuento del intento fallido no representa una consulta completa.
- Errores persistidos con texto controlado, sin tokens, cuerpos de correo ni excepciones de red.
- Demostración local para un usuario existente: OC ficticia, partida y dos respuestas, sin Google ni credenciales.
- Repetir la creación de demostración no duplica datos ni reinicia respuestas revisadas. Solo se permite con DEBUG=True. Datos marcados DEMOSTRACIÓN y direcciones .invalid.

## Probar en tu equipo (Git Bash)
```bash
git fetch origin &&
git switch feat/step8-operations &&
python -m pip install -r requirements.txt &&
python Otros/manage.py migrate &&
python Otros/manage.py test tests --noinput
```

Para la demostración, usa el nombre de un usuario local existente. No es una dirección Gmail ni crea una cuenta nueva:
```bash
python Otros/manage.py seed_supplyhub_demo --username TU_USUARIO_LOCAL
python Otros/manage.py runserver 127.0.0.1:8000
```
Si no tienes usuario local, crea uno mediante `python Otros/manage.py createsuperuser` y habilita el login local de desarrollo en `.env`. Entra con ese usuario, ve a Seguimiento OC > Correos de proveedores. Confirma la primera respuesta (fecha opcional) y descarta la segunda. Comprueba la bitácora en el detalle de la OC DEMO. Consultar Gmail no está disponible para buzones ficticios.

## Probar Gmail real después
Seguir STEP7_FILES.md para habilitar Gmail API, configurar cliente OAuth, callback y Fernet. Autoriza cada buzón con su titular. Registra correo del proveedor por partida. Comprueba primero con una OC conocida y una respuesta externa explícita, revisa la asociación y confirma manualmente. El filtro excluye @questum.com y subdominios, pero nunca convierte una coincidencia de remitente en autenticación del proveedor.

## Archivos
- GmailMailbox: is_demo, sync_started, retry_after.
- GmailSyncRun y migración 0008 para bitácora de operación.
- gmail_service.sync: operación protegida y registro del resultado.
- gmail_controller y Vistas/gmail/index.html: panel de estado e historial propio.
- seed_supplyhub_demo: datos locales idempotentes.
- tests/test_step8_operations.py: éxito, fallo, cooldown, bloqueo, recuperación, privacidad, demo y restricciones.

## Pendientes para producción
- Validar OAuth y políticas del dominio con buzones reales autorizados; hasta entonces las pruebas Google son simuladas.
- Definir hosting, HTTPS, callback definitivo, DEBUG=False, secretos y conservación de la clave Fernet.
- Verificar permisos DataAnalytics, acceso por usuario, copias de seguridad y política de retención/borrado de correos almacenados.
- Usar base de datos de producción y verificar bloqueos con concurrencia real. Las pruebas actuales usan SQLite y verifican estados de bloqueo, no carga paralela de producción.
- Evitar cargar la demostración en producción; si se promovió una base de desarrollo, retirar sus datos ficticios antes de usarla.
- Validar fechas y OC/releases con ejemplos reales de proveedores.
- La consulta sigue siendo manual: INBOX, últimos 30 días y hasta 250 mensajes por intento. Sincronización incremental/programada y cobertura histórica quedan fuera de este Step 8 temporal.
- No hay envíos, recordatorios automáticos, adjuntos ni lectura de mensajes exclusivamente HTML. Form Approvals sigue como captura/importación separada.
- Validación visual de navegador y despliegue productivo pendientes.

Este paso cierra el alcance de operación local acordado; no declara terminada la integración real ni el despliegue.

Validación ejecutada: 48 pruebas aprobadas (10 nuevas de operación), `manage.py check` sin errores y `makemigrations --check --dry-run` sin cambios pendientes después de generar 0008.
