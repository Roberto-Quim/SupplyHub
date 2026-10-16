> Documento histórico de esta entrega. Estado y plan vigentes: [docs/ESTADO.md](docs/ESTADO.md) y [docs/PLAN.md](docs/PLAN.md).

# STEP 7 — Gmail y revisión de respuestas de proveedores

Implementación sobre `fix/step5-step6-integration`. Incluye correcciones de Step 5/6, aún independientes de main.

## Alcance
- Buzones corporativos @questum.com autorizados individualmente por OAuth de Google.
- Permiso exclusivo `https://www.googleapis.com/auth/gmail.readonly`; no envía ni modifica correos.
- Credencial de actualización cifrada con Fernet. Access token solo en memoria durante la operación.
- State OAuth ligado a sesión/usuario, válido 10 minutos y consumido una sola vez.
- Cada usuario ve y opera únicamente sus buzones y respuestas. Usa el guard de Seguimiento OC.
- Consulta manual de INBOX de los últimos 30 días, máximo 250 resultados por consulta (5 páginas). No es sincronización histórica completa ni programada.
- Excluye por mensaje remitentes @questum.com y subdominios, remitentes múltiples, enviados, borradores, spam y papelera.
- Solo captura cuerpo text/plain; omite HTML sin alternativa de texto y adjuntos. Corta citas comunes y limita a 20 000 caracteres. No garantiza retirar todos los formatos de firma/cita.
- Requiere referencia explícita OC/PO/orden de compra y coincidencia con correo del proveedor registrado en la partida. No procesa cualquier correo externo.
- Omite OC Tenango. Candidatas pueden incluir varias partidas/releases; la persona elige la definitiva.
- No infiere fechas automáticamente: la fecha revisada se confirma manualmente.
- Respuestas pendientes, aplicadas o descartadas; ID Gmail único por buzón. Aplicación atómica una sola vez, con historial de fuente CORREO.
- Desconectar elimina la credencial local y conserva respuestas para trazabilidad. Para revocar autorización Google, entrar a las conexiones de terceros de la cuenta Google.

## Configuración local
1. Instalar `python -m pip install -r requirements.txt`.
2. En Google Cloud crear/seleccionar proyecto y habilitar Gmail API.
3. Configurar Google Auth Platform, audiencia interna si la organización lo permite; de otro modo usuarios de prueba. Añadir a las practicantes según la configuración de Google.
4. Crear cliente OAuth de tipo aplicación Web. Registrar exactamente `http://127.0.0.1:8000/hub/correos/callback/` como URI de redirección.
5. Copiar `.env.example` a `.env` si aún no existe. Configurar GMAIL_ENABLED=True, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET y GMAIL_REDIRECT_URI. No publicar secretos.
6. Ejecutar `python Otros/manage.py generate_encryption_key` y guardar la clave en APP_ENCRYPTION_KEY; activar APP_ENCRYPTION_ENABLED=True. Mantener la clave estable para poder descifrar credenciales existentes.
7. Ejecutar `python Otros/manage.py migrate` y `python Otros/manage.py runserver 127.0.0.1:8000`.
8. Iniciar sesión en SupplyHub. Seguimiento OC > Correos de proveedores > Conectar Gmail. La titular elige y autoriza su cuenta.
9. En detalle OC registrar el correo externo del proveedor por partida. Consultar correos, revisar candidatas y confirmar comentario/fecha antes de incorporar a la bitácora.

Google puede requerir aprobación del administrador corporativo. Eso no se evita desde SupplyHub. En producción usar HTTPS y registrar el callback de producción; configurar los permisos/verificación que Google requiera.

## Archivos
- Modelos GmailMailbox/GmailResponse y migración 0007.
- Servicios gmail_service, controlador gmail_controller, rutas y pantalla Vistas/gmail/index.html.
- Acceso desde Seguimiento OC y captura del correo del proveedor en detalle de partida.
- El importador OC conserva un correo registrado cuando el Excel no trae ese campo.
- Pruebas en tests/test_gmail.py, sin llamadas reales a Google.

## Validación y límites
Pruebas locales con SQLite y Google simulado. No se conectaron buzones reales ni se verificaron credenciales o políticas de la organización. La coincidencia de remitente no autentica al proveedor; toda aplicación sigue requiriendo revisión humana. No hay envíos, extracción automática de fechas, procesamiento de adjuntos o acceso global de administradores a buzones ajenos.

Step 8 pendiente: sincronización programada/incremental y operación de recordatorios con aprobación, reintentos, pruebas reales autorizadas y despliegue.

Referencias:
- https://developers.google.com/workspace/gmail/api/auth/web-server
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/workspace/gmail/api/guides/list-messages

Validación ejecutada: 38 pruebas aprobadas (13 de Gmail), check sin errores, migración 0007 generada y verificada sin cambios adicionales pendientes, diff sin errores de espacios.
