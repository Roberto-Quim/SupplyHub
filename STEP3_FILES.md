# SupplyHub — Fix identidad + Paso 3

Este overlay parte de `feat/supplyhub-auth`.

Incluye:
- Nómina como `User.username` corporativo.
- Unificación Google -> DataAnalytics -> nómina.
- Google OAuth configurable totalmente por `.env`.
- Login con correo Google y nómina como métodos principales.
- HUB y Administración con menú dinámico.
- Guards backend por ruta/submódulo.
- Rutas placeholder para validar navegación/permisos antes de implementar CRUD.
- Tests de identidad, menú y guards.

No incluye secretos ni nombres inventados de SP de nómina.
