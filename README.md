# SupplyHub

SupplyHub es la plataforma interna de gestión y control para unificar dos dominios operativos de Compras:

- **RFQ / CAPEX (Flujo Edith)**: Recepción, revisión, decisión de seguimiento, estados (solicitada, en cotización, concluida, cancelada), autocompletado inteligente desde correos de *Form Approvals* (Regex) e importación de solicitudes.
- **Seguimiento de Órdenes de Compra (Flujo Jacqueline)**: Control de compras QES Oracle, proveedores, supplier sites, partidas, columna de Release ($R$), bitácora interactiva de respuestas predeterminadas por fecha y semaforización de vencimientos (excluyendo Macimex Tenango).

La base arquitectónica replica el patrón validado de Sistema Data Analytics:

`URL -> función pública Django -> Controlador -> Servicio -> datos -> Template`

La autenticación corporativa (Active Directory / Nómina) y la autorización por perfiles/módulos se integran con DataAnalytics. Los datos de negocio de SupplyHub permanecen separados de las tablas administrativas.

---

## Estructura del Proyecto

```text
SupplyHub/
├── Controladores/           # Controladores HTTP y orquestación de vistas
├── Modelos/                 # Aplicación Django principal (models, services, forms)
│   └── supplyhub/
│       ├── domain/          # Modelos de dominio ORM (OrdenCompra, LineaOC, RFQCapex, etc.)
│       ├── services/        # Servicios de negocio, importación Excel y parsers
│       └── forms/           # Formularios Django
├── Vistas/                  # Plantillas HTML y componentes UI (templates)
├── tests/                   # Suite automatizada de pruebas unitarias e integración
└── Otros/                   # Archivos de configuración (manage.py, settings, urls, static)

##Arranque Local de la Fundación
##Bash
# 1. Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
copy .env.example .env

# 4. Verificar integridad y migraciones
python Otros/manage.py check
python Otros/manage.py migrate

# 5. Ejecutar la suite de pruebas
python Otros/manage.py test tests

# 6. Levantar servidor de desarrollo
python Otros/manage.py runserver

## Gmail y pruebas de operación
- [Step 7: conexión Gmail y revisión de respuestas](STEP7_FILES.md)
- [Step 8: panel de operación, reintentos y demostración local](STEP8_FILES.md)

Las conexiones reales requieren configurar OAuth de Google y autorización individual. La demostración de Step 8 permite probar la revisión sin Gmail.
