# Ramas revisadas — 16 de octubre de 2026

Estado remoto consultado antes de implementar esta entrega. Base local: feat/step8-operations, f1cee3da901d9c12dc4f0cc08832f3cf383bdb86.

| Rama | SHA | Relación con main |
|---|---|---|
| feat/step7-gmail | 23cd141c07eaa72b9c889ad1d40f87d8f23ee05a | ahead; +2/-0 |
| feat/step8-operations | f1cee3da901d9c12dc4f0cc08832f3cf383bdb86 | ahead; +3/-0 |
| feat/supplyhub-auth | a1340ed825735809e3fda963c8094025b1b382fa | behind; +0/-7 |
| feat/supplyhub-foundation | 8fb4f5cfff76d83b160abaef0d0015d830343624 | behind; +0/-8 |
| feat/supplyhub-step3 | 49c81a4b9631c7bf2f37f8f9135dc669dd341342 | behind; +0/-6 |
| feat/supplyhub-step4-rfq-ui | 481b7fb2e6442e6fbfe9da7d9f5162ae88193ec1 | behind; +0/-5 |
| feat/supplyhub-step5-seguimiento-oc | ef486273f9d1fc0bb4e76dc8a0b77c016d35a785 | diverged; +1/-5 |
| fix/step5-step6-integration | de93bffcf0ef4c4be371e7c4ecc0c63fd2e0f6c9 | ahead; +1/-0 |
| fix/step7-step8-audit-repairs | 5235387f854d8c7fe5dce3b18764fe38fd589aa8 | ahead; +2/-0 |
| main | 878ef3f019e675b070868c0649b0c98818dcf2c4 | base |

La rama de auditoría 5235387 agrega documentación que afirma cinco submódulos funcionales, pero no incorpora sus controladores/plantillas. Su intención de anulación se implementó sobre la línea Gmail mediante una migración aditiva 0009, conservando fuente y fecha_interaccion. No se fusionaron sus migraciones destructivas 0007/0008.

La rama step5 antigua agrega únicamente un archivo anómalo tration\" y no es la base del módulo. Los pasos 5–6 reales llegaron a main mediante d9c873d, 35865ba y 7bb05af.

La entrega se publica en la rama nueva feat/8.5, derivada de feat/step8-operations. No se modifica main ni se borran ramas o datos.
