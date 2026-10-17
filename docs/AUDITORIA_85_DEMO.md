# Auditoría SupplyHub 8.5 — 17 de octubre de 2026

## Base y aislamiento

Repositorio Roberto-Quim/SupplyHub. Se consultaron las ramas remotas y se tomó origin/feat/8.5, commit 2679a17d01f8cadb011897f81a0ad9c21e3e61d6. Rama de trabajo: fix/audit-85-demo. La copia SupplyHub original contenía cambios anteriores y no se modificó. No se trabajó en main ni se restauró el archivo de entorno cifrado.

Commits revisados: 1d3ba1a consolida administración/OC y migración 0009; a7f318e cambia el ejemplo de entorno; 2679a17 añade transferencia cifrada. Los dos últimos no cambian controladores. Se inspeccionaron rutas supplyhub/config, fachada views, controladores de seguimiento/Gmail/administración, templates de detalle/catálogos/Gmail, modelos y migración 0009, servicios de autorización/sesión/administración/seguimiento y configuración/adaptador Google OAuth.

## Hallazgos comprobados

1. Controladores/gmail_controller.py, callback: con sesión OAuth válida y GET state=ñ, secrets.compare_digest recibe texto no ASCII y genera HTTP 500. Traceback reproducido por Django test client:

```text
Controladores/gmail_controller.py, callback
secrets.compare_digest(pending.get('state',''), request.GET.get('state',''))
TypeError: comparing strings with non-ASCII characters is not supported
```

Corrección: comprobar ASCII antes de comparar. Se conserva comparación de tiempo constante, caducidad, propietario y consumo único del estado. La prueba confirma redirección de rechazo y que connect no se llama. Es un defecto del callback de conexión Gmail, no prueba de que el login Google corporativo fallara en la demo.

2. Controladores/seguimiento_oc_controller.py, seguimiento_oc_detalle: DELETE devuelve 200 y renderiza el detalle. La prueba previa falla con AssertionError: 200 != 405. Se limita a GET, POST y HEAD y se devuelve 405 para otros métodos. No se observó modificación de datos por DELETE antes del arreglo.

## Recorridos que funcionan en esta revisión

- GET detalle con historial y stock nulo: 200 y template renderizado.
- POST correo externo de proveedor siguiendo la redirección al detalle: 200, correo persistido.
- Correo inválido: mensaje de validación sin 500.
- Usuarios/perfiles/módulos con fallo simulado de catalog: pantalla informa indisponibilidad; no sustituye la fuente con datos locales.
- Suite previa: 85 pruebas aprobadas. Suite final: 91 aprobadas, incluyendo seis pruebas nuevas en tests/test_demo_regressions.py.
- La suite existente cubre autorización, CSRF, Gmail simulado, administración local/central simulada, importadores y migración desde 0008 con esquema alternativo e historial inactivo.

## Hipótesis y límites

No se reprodujeron los errores específicos de detalle OC, guardado de correo o administración descritos por el usuario bajo el esquema migrado de tests. No se les atribuyen los dos defectos anteriores. La conversación recuperada contiene una transcripción truncada y no proporciona sus tracebacks completos. Faltan los tracebacks del servidor de la demo, el commit efectivamente desplegado y el estado de migraciones de esa base para una atribución concluyente.

Una base sin 0009 podría fallar al consultar SupplierSite/AuditoriaAdministracion o columnas de historial; es hipótesis de despliegue, no causa comprobada en la demo. La migración ya implementa compatibilidad para determinadas variantes del historial. No se aplicaron migraciones a la base operativa ni se alteraron credenciales.

Google OAuth de login y OAuth de Gmail son configuraciones independientes. check pasa con GOOGLE_OAUTH_ENABLED=True y allauth instalado. Esto valida carga de configuración/rutas, no consentimiento, redirect URI, credenciales, nómina o SP de DataAnalytics reales. No se inició sesión externa, consultó correo real ni conectó SQL corporativo. CI remoto no verificado. No se realizó comprobación visual de navegador.

## Validación reproducible

Desde la raíz de la rama, con Python 3.14.0 y Django 6.0.5 instalados:

```powershell
$env:GOOGLE_OAUTH_ENABLED='False'
$env:GMAIL_ENABLED='False'
$env:DATAANALYTICS_ENABLED='False'
$env:AD_LDAP_ENABLED='False'
$env:PAYROLL_AUTH_ENABLED='False'
python Otros/manage.py check
python Otros/manage.py makemigrations --check --dry-run
python Otros/manage.py test tests --noinput
```

Resultados: check sin incidencias; sin migraciones pendientes de generar; 91 tests OK. Avisos de staticfiles ausente en checkout y tracebacks sintéticos de mocks de fallo no son fallos de suite. No se cambió requirements, templates, modelos ni migraciones.

Para verificar una copia del entorno de demo: ejecutar showmigrations supplyhub y migrate --plan sobre una copia respaldada, y comparar el commit desplegado con esta base. No ejecutar restore_local_env.py ni imprimir .env para esta investigación.
