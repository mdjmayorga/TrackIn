# Novedades para el próximo informe

Material posterior al corte del Informe 2 (16/10/2026), para el informe final o
para una adenda. Cada entrada trae un texto listo para adaptar y la evidencia que
lo respalda.

---

## Mapa en vivo de ShipsGo en la especificación del pedido — 21/10/2026

**Texto propuesto**

> Una actualización reciente de ShipsGo, el proveedor comercial de rastreo
> contratado para las vías marítima y aérea, habilitó con la compra de créditos un
> mapa en vivo embebible en aplicaciones propias (ShipsGo Embed). TrackIn lo
> incorporó en la especificación del pedido: cuando el pedido tiene una referencia
> de embarque que ShipsGo rastrea —BL, contenedor, booking o guía aérea madre— y el
> envío está dado de alta en la cuenta, el detalle muestra el mapa en vivo del
> envío, con el buque o el vuelo, los puertos de carga y descarga, la ETA y el
> trayecto recorrido y por recorrer. Para los pedidos que ShipsGo no rastrea, el
> detalle conserva el mapa propio del sistema.
>
> La integración no agrega costo —el crédito de cada envío ya incluye el mapa—, no
> pasa por el backend ni por la base de datos, y usa un token propio del mapa,
> distinto del de la API, restringido a los dominios autorizados en la cuenta. Se
> verificó el 21/10/2026 con un pedido real (OC 4500016185-10, BL de COSCO con
> descarga en Puerto Caldera).
>
> El aporte al cronograma es directo: dos historias del Sprint 7, el mapa de
> seguimiento del pedido (`US-44`) y el trayecto del envío (`US-29`), se
> reestimaron de 18 a 9 horas, lo que deja el Sprint 7 en 67 horas frente a 65 de
> capacidad. Los mapas del panel principal siguen siendo propios, porque deben
> colorear cada pedido con el semáforo de TrackIn, responder a los filtros del
> panel y mostrar pedidos y no embarques.

**Puntos que conviene mencionar como limitaciones o pendientes**

- El mapa solo aparece para envíos dados de alta en ShipsGo. Al 21/10, una de las
  92 líneas activas tenía referencia: su alcance real depende de que el Z-tracking
  traiga el BL o la guía madre, como se acordó con Compras.
- Para producción falta autorizar el dominio definitivo de TrackIn en la cuenta de
  ShipsGo y verificar que la red de Gutis permite `embed.shipsgo.com`.
- Queda por confirmar cuánto tiempo conserva ShipsGo los envíos terminados.

**Evidencia en el repositorio**

| Qué | Dónde |
|---|---|
| Descripción técnica y fuentes | `docs/api-references.md` §ShipsGo Embed |
| Decisión de arquitectura | `docs/architecture.md` §1.6 |
| Reestimación del Sprint 7 | `docs/backlog/backlog_trackin.md` §Sprint 7 y `US-44` |
| Checklist de producción | `docs/deployment.md` §Checklist previo a producción |
| Código | `frontend/src/components/MapaShipsGo.tsx`, `frontend/src/utils/mapaShipsGo.ts` |
| Pruebas | `frontend/tests/MapaShipsGo.test.tsx`, `frontend/tests/DetallePedido.test.tsx` |

**Figura sugerida:** una captura del detalle de la OC 4500016185-10 con el mapa de
ShipsGo. Si el diagrama de arquitectura del informe se actualiza
(`docs/informes/diagramas/diagramas.py`), agregar la flecha del navegador a
`embed.shipsgo.com`, que es la única conexión del navegador fuera de la API de
TrackIn.
