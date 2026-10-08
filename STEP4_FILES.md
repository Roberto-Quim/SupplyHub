# SupplyHub — Fix visual + Paso 4 RFQ/CAPEX

Este overlay parte de `feat/supplyhub-step3`.

## Fix visual
- Shell visual inspirado en DataAnalytics / paleta corporativa Questum.
- Header oscuro + acento magenta.
- Navegación superior tipo DataAnalytics.
- Solo un menú desplegable puede permanecer abierto a la vez.
- Clic fuera del menú o `Esc` cierra el desplegable.
- Login y pantallas reutilizan el mismo sistema visual.

## Paso 4 — RFQ/CAPEX
- Modelo persistente `RFQCapex`.
- RFQ = número de Pedido/Request.
- Plantas canónicas iniciales:
  - `MACIMEX_TENANGO` → Macimex Tenango
  - `MAQ_RA` → MAQ RA
- Estados:
  - Solicitada
  - Cotización
  - Aprobación
  - Ordenada
  - Concluida
- Decisión de seguimiento:
  - Pendiente de revisión
  - Cotizar
  - No cotizar
- Historial append-only para cambios de estado y decisión.
- Alta, edición, detalle, filtros y cambios de estado/decisión.
- Usuario auditor = nómina (`sh_usuario`) cuando existe.
- La integración automática con Forms/Sheets/correo sigue reservada para la fase de integraciones; este paso deja el dominio y UI funcionales.

## Validación después de copiar
```bash
python Otros/manage.py check
python Otros/manage.py migrate
python Otros/manage.py test tests
python Otros/manage.py runserver
```
