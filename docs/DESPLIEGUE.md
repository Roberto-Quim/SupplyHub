# Despliegue y operación

No se desplegó ni se conectaron servicios corporativos durante esta entrega.

## Antes de migrar una base existente

1. Respaldar SQLite/base operativa y la clave Fernet. Trabajar primero sobre una copia y detener escritores.
2. Revisar `showmigrations supplyhub`. No aplicar las migraciones destructivas de la rama de auditoría sobre esta línea.
3. Ejecutar `python Otros/manage.py migrate --plan` y `python Otros/manage.py migrate` sobre la copia.
4. La 0009 está probada con esquema canónico y un esquema que ya tenía activo y había perdido fecha_interaccion/estado_validacion. Conserva registros inactivos y fuente existente. Fuentes o fechas que ya se borraron requieren el respaldo original.
5. Validar el historial, relaciones Gmail y fechas antes de migrar el ambiente definitivo.

## DataAnalytics

Usar el esquema jerárquico existente: Usuarios, Perfiles, Modulos, Submodulo, PerfilModulos y Acceso. Revisar las dependencias del sistema original; no ejecutar scripts a ciegas. Los scripts 015–020 y 028 incluidos son copias de la referencia local; las altas por método requieren 028 y EXECUTE sobre sus SP.

Configurar DATAANALYTICS_DB_* y habilitar DATAANALYTICS_ENABLED. Dar a la cuenta únicamente los permisos que requieren los SP/conectores. Revisar las rutas SupplyHub con un perfil TI:

```powershell
python Otros/manage.py seed_supplyhub_administration --actor-profile ID_TI
python Otros/manage.py seed_supplyhub_administration --actor-profile ID_TI --apply
```

La primera llamada inspecciona; la segunda agrega registros faltantes. El mecanismo original asigna las nuevas rutas a TI. No concede automáticamente permisos a Compras: hacerlo desde Perfiles con un administrador autorizado. ErrorLog permanece exclusivo de TI.

Probar alta, edición y estado de una asignación de prueba por cada método; comprobar que Administrador no puede modificar TI. Probar revocación de una sesión existente y que una caída de DataAnalytics deniega acceso. Validar la nómina real en el login Google.

## Gmail y recordatorios

Configurar OAuth, callback y Fernet conforme a STEP7_FILES.md. Probar con un buzón autorizado y una OC de prueba. Gmail solo lee; los recordatorios usan un transporte SMTP independiente.

La tarea `python Otros/manage.py process_supplyhub_jobs` realiza una pasada y termina. Programarla cada 15 minutos con el programador del servidor, usando rutas absolutas, el entorno correcto y evitando ejecuciones solapadas. No se instala automáticamente una tarea del sistema.

- GMAIL_BACKGROUND_SYNC_ENABLED=True habilita las consultas periódicas; GMAIL_SYNC_INTERVAL_MINUTES controla el intervalo por buzón.
- Sin habilitar Gmail, la tarea aún genera la cola de recordatorios cada 24 horas.
- Revisar la cola en Seguimiento OC → Recordatorios y aprobar cada destinatario.
- Configurar EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD y DEFAULT_FROM_EMAIL. REMINDERS_SEND_ENABLED=True permite al ejecutor enviar únicamente aprobados.
- FALLIDO requiere revisión antes de aprobar un reintento. EN_PROCESO puede indicar una interrupción: revisar el buzón enviado y resolver operativamente antes de volver a encolar; no se reintenta automáticamente.
- No aprobar envíos a datos de demostración. Los ejemplos usan dominios .invalid.

## Producción

Configurar DJANGO_DEBUG=False, clave secreta propia, hosts, HTTPS/cookies seguras y autenticación corporativa; no habilitar login local. Ejecutar collectstatic y servir WSGI/ASGI con la plataforma corporativa elegida. Revisar `check --deploy`, copias de seguridad, logs, retención de correos y restauración de Fernet.

El almacenamiento actual es SQLite. Antes de operar múltiples escritores o procesos, validar bloqueo real y el motor elegido en un ambiente de prueba. Las pruebas automatizadas verifican estados/atomicidad, no simulan carga productiva paralela.

## Validación

```powershell
python Otros/manage.py check
python Otros/manage.py makemigrations --check --dry-run
python Otros/manage.py test tests --noinput
```

El workflow de GitHub Actions ejecuta estos controles tras publicar la rama. No se afirmó haber pasado un CI remoto que aún no ha ejecutado esta entrega.

La comprobación visual por navegador quedó pendiente: el único navegador automatizable disponible no pudo acceder al servidor localhost; no había navegador Chrome conectado. Los formularios y plantillas sí se verifican mediante solicitudes Django con CSRF y permisos.
