---
status: accepted
---

# El estado del pedido son dos dimensiones, y el Estado se deriva

El SRS (§8.2) pide un solo estado por pedido, pero un pedido puede estar en tránsito **y** retrasado a la vez: Logística pregunta dónde está la carga y Compras si llega a tiempo. Por eso cada pedido guarda por separado su **etapa de viaje** y su **estado de cumplimiento**, y el **Estado** único que se muestra se deriva de ellos con esta precedencia: cerrado o cancelado gana a todo; si no tiene tracking, sin tracking; si está en riesgo o retrasado, manda el cumplimiento; si no, la etapa de viaje. Que el riesgo mande sobre la etapa es deliberado: es la información por la que existe TrackIn. Aprobado en la revisión del 25/08/2026.

## Considered Options

- **Una sola columna, como dice el SRS.** Rechazada: cualquier valor que se elija para un pedido en tránsito y retrasado pierde la mitad de lo que un usuario necesita, y el filtro por etapa de viaje dejaría de funcionar.
- **Derivar el Estado al consultar, sin guardarlo.** Rechazada: la grilla filtra e indexa por Estado y RNF-02 fija 1 s para aplicar un filtro.

## Consequences

- El Estado se guarda y debe recalcularse cada vez que cambia cualquiera de las dos dimensiones o el pedido se cierra; si no, diverge. La precedencia vive en un solo lugar, `derivar_estado_calculado` en `backend/app/services/estado.py`.
- El estado de cumplimiento puede no existir (sin fecha disponible proyectada no se puede afirmar nada), y entonces el Estado cae en la etapa de viaje.
- Un pedido en riesgo o retrasado no muestra su etapa en el Estado; quien la necesite la tiene aparte, con su propio filtro.

Detalle completo en [`docs/data-model.md` §1.4](../data-model.md).
