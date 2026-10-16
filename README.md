# SupplyHub

Plataforma interna de Compras: RFQ/CAPEX (Edith), seguimiento de OC (Jacqueline) y Administración.

- **Usuarios:** asignaciones independientes de persona, método de ingreso y perfil; altas, edición, activación e inactivación.
- **Perfiles:** nombre, estado y selección de submódulos; jerarquía TI/Administrador de DataAnalytics.
- **Módulos:** padres, submódulos, rutas y orden; el menú lee el catálogo central y los permisos reales.
- **Supplier Sites:** catálogo de proveedor/sitio/planta, contacto y correo, asociado a OC.
- **ErrorLog:** consulta por fechas y búsqueda, exclusivamente TI; sin edición ni borrado.

Los tres catálogos de identidad/permisos usan DataAnalytics. Los datos operativos, Supplier Sites y errores de SupplyHub se guardan en su propia base. La demostración local es independiente y no crea permisos corporativos.

## Arranque

Python 3.14; ejecutar desde la raíz del repositorio:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python Otros/manage.py check
python Otros/manage.py migrate
python Otros/manage.py test tests --noinput
python Otros/manage.py createsuperuser
python Otros/manage.py seed_supplyhub_administration --demo --username TU_USUARIO_LOCAL
python Otros/manage.py seed_supplyhub_demo --username TU_USUARIO_LOCAL
python Otros/manage.py runserver 127.0.0.1:8000
```

En desarrollo, solo un superusuario local puede administrar. Las cuentas locales ordinarias conservan los flujos de Compras. No se crean contraseñas ni cuentas mediante las siembras.

## Documentación vigente

- [Plan original y correspondencia de entregas](docs/PLAN.md)
- [Estado, pruebas y límites](docs/ESTADO.md)
- [Arquitectura y referencia DataAnalytics](docs/ARQUITECTURA.md)
- [Despliegue y operación programada](docs/DESPLIEGUE.md)
- [Ramas y commits revisados](docs/RAMAS_REVISADAS.md)
- [Flujo de Compras Indirectas](Compras%20Indirectas/PLAN.md)

Los STEP*_FILES.md describen entregas históricas. Sus números no sustituyen el plan original. Las conexiones corporativas y envíos están apagados por defecto; consultar DESPLIEGUE antes de activarlos.
