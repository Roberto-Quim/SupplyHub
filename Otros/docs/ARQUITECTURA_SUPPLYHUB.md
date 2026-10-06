# Arquitectura SupplyHub — Fundación

## Objetivo

SupplyHub unifica dos procesos de Compras sin mezclar sus reglas de negocio:

1. **RFQ / CAPEX**.
2. **Seguimiento de órdenes de compra y proveedores**.

La identidad, perfiles y permisos se integrarán con **DataAnalytics**; los datos operativos de Compras pertenecen a SupplyHub.

## Patrón MVC adaptado

Flujo objetivo:

```text
Navegador
  -> URL Django
  -> función pública en Modelos/supplyhub/views.py
  -> Controlador en Controladores/
  -> servicio en Modelos/servicios/ o Modelos/supplyhub/services/
  -> ORM / conector / procedimiento autorizado
  -> contexto
  -> template en Vistas/
```

Reglas:

- No colocar SQL en templates.
- No poner lógica de negocio extensa en `urls.py` ni en la fachada `views.py`.
- Los controladores coordinan HTTP, sesión y permisos.
- Los servicios concentran reglas, transacciones, normalización e infraestructura.
- Todo filtro enviado a SQL será parametrizado.

## Referencia capturada de DataAnalytics

La fundación se diseñó después de revisar la memoria técnica y el código real del Sistema Data Analytics. Los comportamientos que deben preservarse en SupplyHub son:

### Configuración y cifrado

- `.env` local no versionado.
- Variables sensibles con prefijo `fernet:` o `enc:`.
- `APP_CONFIG_ENCRYPTION_KEY` fuera del repositorio para secretos de configuración.
- `APP_ENCRYPTION_KEY` independiente para datos persistentes sensibles de aplicación.
- Contraseñas de usuarios **no** se cifran con Fernet.

### Autenticación y autorización — Fase 2

```text
Usuario
  -> Nómina / Google OAuth / AD-LDAPS
  -> identidad autenticada
  -> DataAnalytics
  -> usuario activo + método permitido + perfil activo
  -> IdUsuario / IdPerfil en sesión
  -> PerfilModulos
  -> menú dinámico + guards backend
```

Principios que se conservarán:

- autenticación y autorización son capas distintas;
- el menú oculto no sustituye un guard de servidor;
- accesos autorizados/denegados se auditan;
- errores de permiso deben tender a **fail-closed**;
- la conexión de SupplyHub hacia administración/autorización debe tender a centralizarse en DataAnalytics.

### Módulos objetivo

```text
HUB
  RFQ / CAPEX
  Seguimiento de Órdenes de Compra

Administración
  Usuarios
  Perfiles
  Módulos
  Supplier Sites
  Catálogos
```

## Separación de bases

```text
DataAnalytics
  usuarios
  perfiles
  módulos/submódulos
  permisos
  auditoría de acceso

SupplyHub
  RFQ/CAPEX
  historial RFQ
  proveedores y supplier sites
  órdenes/ítems
  comunicaciones
  respuestas
  recordatorios
  importaciones
  auditoría operativa
```

## Plan de implementación

1. Fundación MVC/configuración/cifrado — **este paquete**.
2. Autenticación corporativa + autorización DataAnalytics + menú dinámico.
3. Módulos padre HUB/Administración y seed de permisos.
4. Dominio RFQ/CAPEX.
5. Dominio Seguimiento de OC.
6. Recordatorios cada 24 h e idempotencia.
7. Integraciones reales (Forms/Oracle/Gmail según aprobación).
8. Hardening, pruebas, documentación y despliegue.

## Regla sobre información corporativa

Los archivos reales hoy usados para levantamiento no deben convertirse en fixtures de prueba del repositorio final. Se crearán copias anonimizadas/sintéticas y los originales deben quedar fuera del versionado de código.
