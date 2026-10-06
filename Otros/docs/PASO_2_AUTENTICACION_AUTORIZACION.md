# Paso 2 — Autenticación y autorización

Objetivo: separar **identidad** (Django local en desarrollo, AD, nómina o Google)
de **autorización** (DataAnalytics), siguiendo el patrón del Sistema Data Analytics.

## Comportamiento seguro

- El login local se permite únicamente cuando `DEBUG=True` y `SUPPLYHUB_LOCAL_AUTH_ENABLED=True`.
- AD, nómina y Google están desactivados por defecto.
- DataAnalytics está desactivado por defecto para permitir desarrollo local sin red corporativa.
- Cuando DataAnalytics está activo, un usuario corporativo autenticado debe obtener `IdUsuario > 0` e `IdPerfil > 0` o se rechaza el acceso.
- Las contraseñas de AD/nómina nunca se persisten en Django.
- Los secretos se leen desde `.env` y pueden usar `fernet:`.
- SQL de valores de usuario usa parámetros. Los nombres de procedimientos provienen de configuración controlada.

## Validación local del Paso 2

```bash
python Otros/manage.py check
python Otros/manage.py migrate
python Otros/manage.py test tests
python Otros/manage.py createsuperuser
python Otros/manage.py runserver
```

Abrir `http://127.0.0.1:8000/`. Debe redirigir a `/login/`.
Entrar con el superusuario local y confirmar que se muestra el HUB.

## Aún NO activar

No activar AD, nómina, Google ni DataAnalytics hasta cargar la configuración
corporativa real y validar conectividad en el ambiente autorizado.

El Paso 3 conectará `IdPerfil` con el menú dinámico `HUB` / `Administración` y
los guards por submódulo.
