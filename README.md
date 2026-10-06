# SupplyHub

SupplyHub será la plataforma interna para unificar dos dominios de Compras:

- **RFQ / CAPEX**: recepción, revisión, decisión de seguimiento e historial de solicitudes de cotización.
- **Seguimiento de órdenes de compra**: proveedores, supplier sites, ítems, comunicaciones, respuestas y recordatorios.

La base arquitectónica replica el patrón validado de Sistema Data Analytics:

`URL -> función pública Django -> Controlador -> Servicio -> datos -> Template`

La autenticación corporativa y la autorización por perfiles/módulos se integrarán con DataAnalytics en la Fase 2. Los datos de negocio de SupplyHub permanecen separados de las tablas administrativas de DataAnalytics.

## Arranque local de la fundación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python Otros/manage.py check
python Otros/manage.py migrate
python Otros/manage.py runserver
```

Abrir `http://127.0.0.1:8000/`.

## Seguridad

- `.env`, llaves, tokens y credenciales reales no se versionan.
- Secretos de configuración pueden almacenarse como `fernet:<token>`.
- `APP_CONFIG_ENCRYPTION_KEY` vive fuera del repositorio.
- No se deben subir reportes corporativos reales al repositorio de código final; usar fixtures anonimizados.

Ver `Otros/docs/ARQUITECTURA_SUPPLYHUB.md`.
