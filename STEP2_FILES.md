# SupplyHub — Paso 2

Overlay para aplicar sobre `feat/supplyhub-foundation`.

Incluye:
- login local seguro para desarrollo;
- controlador de autenticación;
- backend AD/LDAPS opcional;
- backend nómina opcional;
- adaptador Google OAuth opcional;
- conexión DataAnalytics;
- validación/auditoría de acceso DataAnalytics;
- servicio inicial de rutas por perfil;
- sesión de identidad `sh_*`;
- HUB protegido por `login_required`;
- templates de login/logout;
- tests de autenticación y passthrough local.

No contiene credenciales reales ni activa integraciones corporativas por defecto.
