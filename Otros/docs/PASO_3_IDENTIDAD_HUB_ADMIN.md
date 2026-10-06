# Paso 3 — Identidad corporativa, HUB y Administración

## Regla de identidad

En SupplyHub el **usuario corporativo es el número de nómina**. Django conserva
su `pk` técnico, pero `User.username` debe ser la nómina para accesos corporativos.

- Login por nómina: el backend crea/busca `User.username = nómina`.
- Login por Google: Google valida el correo; DataAnalytics resuelve ese correo a
  `IdUsuario/IdPerfil`; `IdUsuario` se interpreta como nómina para unificar la
  misma cuenta corporativa.
- Login local: solo desarrollo, no representa identidad corporativa.

## Google OAuth

El flujo queda montado y apagado por defecto. Para activarlo:

1. `pip install -r requirements-auth-google.txt`
2. Crear cliente OAuth Web en Google Cloud Console.
3. Registrar callback local:
   `http://127.0.0.1:8000/accounts/google/login/callback/`
4. Definir `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (idealmente fernet) y
   `GOOGLE_ALLOWED_DOMAIN`.
5. Poner `GOOGLE_OAUTH_ENABLED=True`.

SupplyHub no guarda tokens (`SOCIALACCOUNT_STORE_TOKENS=False`).

## Nómina

La pantalla y backend están listos. Para una prueba real deben configurarse en
`.env` los `PAYROLL_DB_*`, `PAYROLL_SP_VALIDATE` y `PAYROLL_SP_WORKER_DATA`
reales. No se inventan nombres de SP.

## Paso 3 funcional

Módulos padre visibles:

- HUB
  - RFQ / CAPEX
  - Seguimiento de Órdenes de Compra
- Administración
  - Usuarios
  - Perfiles
  - Módulos
  - Supplier Sites
  - Catálogos

Con `DATAANALYTICS_ENABLED=False`, el modo local muestra todo para desarrollo.
Con DataAnalytics activo, el menú se filtra por rutas y los controladores vuelven
a verificar permiso (fail-closed).
