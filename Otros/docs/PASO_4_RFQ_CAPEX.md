# Paso 4 — RFQ / CAPEX (Compras Directas)

## Objetivo

Convertir el flujo de Edith en un módulo persistente de SupplyHub sin depender
del Excel como fuente de verdad.

## Reglas confirmadas

1. **RFQ = número de Pedido/Request**.
2. `Clave del proyecto / No. CAPEX` es un dato independiente.
3. Alcance inicial de plantas:
   - **Macimex Tenango**
   - **MAQ RA**
4. Estados operativos:
   - Solicitada
   - Cotización
   - Aprobación
   - Ordenada
   - Concluida
5. No existe todavía un criterio automático confiable para decidir qué RFQ debe
   cotizarse. La decisión se conserva explícita:
   - Pendiente de revisión
   - Cotizar
   - No cotizar

## Modelo

`RFQCapex` guarda el estado actual. Los cambios relevantes no destruyen historia:

- `HistorialEstadoRFQ`
- `HistorialDecisionRFQ`

El usuario que ejecuta una acción se registra como la identidad corporativa de
SupplyHub. Cuando existe sesión corporativa, esa identidad es la **nómina**.

## Plantas

SupplyHub conserva un valor canónico y un valor de origen.

| Código | Nombre |
| --- | --- |
| `MACIMEX_TENANGO` | Macimex Tenango |
| `MAQ_RA` | MAQ RA |

En futuras importaciones, aliases como `Tenango`, `Questum Macimex Tenango`,
`Maquinados Ramos` o `MAQ RA` podrán normalizarse sin perder el texto original.

## Integraciones

Este paso no conecta todavía Google Sheets/Form Approvals/correo. Esa conexión
se hará sobre el dominio ya estable, de modo que las fuentes externas sean
adaptadores y no la base de datos de SupplyHub.
