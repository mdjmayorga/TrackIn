# Spike Parcels API — `TASK-32` (29/09/2026)

**Por qué.** En la reunión del 29/09/2026 los usuarios clave pidieron una alternativa a
ShipsGo con licencia —cuota fija mensual— en vez de pago por embarque. Parcels vende planes
mensuales con cuota: 300 envíos por US$19, 500 por US$29.

**Qué se probó.** Tres pedidos reales del Z-tracking WK38 contra lo que ya se sabía por
ShipsGo y TICA, con los tres envíos gratuitos de la cuenta. Script: `01_rastrear.py`.
Respuestas crudas en `output/raw/` (ignorado por git).

## Resultado

| | Aéreo (arribado) | Marítimo en tránsito | Marítimo arribado |
|---|---|---|---|
| Pedido | OC 4500018062 | OC 4500016185-10 | OC 4500016171-90 |
| Referencia | MAWB `020-25244995` | BL COSCO `COSU6508789000` | Contenedor Maersk `MRSU8132490` |
| Verdad conocida | TICA: llegó el 10/09 desde FRA | ShipsGo: SAILING, ETA 05/10, **CRCAL** | ShipsGo: DISCHARGED el 18/09, **CRPMN** |
| ¿Lo resuelve? | ✅ solo, sin pista | ✅ solo, sin pista | ❌ `NO_DATA`; ✅ con `carrier_hint=maersk-line` |
| Transportista | Lufthansa Cargo | COSCO Bill of Lading | Maersk Line |
| Hitos | 12, con código IATA (BKD, RCS, MAN, DEP, ARR, RCF, NFD, DLV) | 8 | 15 |
| Llegada real | ✅ ARR en SJO el 10/09 17:33 — **coincide con TICA** | — | ✅ Discharge en Moín el 18/09 — **coincide con ShipsGo** |
| Transbordos / naves | 2 vuelos: LH-757 BOM→FRA, LH-518 FRA→SJO | ✅ YANTIAN 133E → MEDKON ZOE 206N en Chancay | ✅ 3 naves, vía Cartagena y Manzanillo |
| **ETA** | Llegada programada por tramo (`flight_legs`) | ❌ **ninguna** (ShipsGo: 05/10) | ❌ ninguna |
| **Puerto de descarga** | «SJO» solo en el texto y en `station` | ❌ **«San José, Costa Rica»**: el destino final, no Caldera | Solo como texto: «TERMINAL DE CONTENEDORES DE MOIN» |
| Estado | `delivered` | `transit` | `transit`, aunque ya se descargó |
| Posición de la nave | — | ❌ | ❌ |

## Veredicto

**Aéreo: Parcels sirve, y quizá mejor que ShipsGo Air.** Trae los hitos con código IATA, cada
vuelo con hora programada y real, y la llegada real a SJO al minuto. La ETA de un envío en
tránsito sale de la `scheduled_arrival` del último tramo. Es el 83 % de los pedidos.

**Marítimo: no reemplaza a ShipsGo.** Faltan justo las tres cosas que TrackIn usa:

1. **La ETA** — la regla RN-14 la toma de la fuente (`ETA_FUENTE`). Sin ella, un pedido
   marítimo en tránsito cae a la ETA declarada del archivo, que casi nunca viene.
2. **El puerto de descarga en UN/LOCODE** — `US-54` lo usa para ubicar el pedido. En el BL de
   COSCO, Parcels da el destino final («San José»); con eso no se distingue Caldera de Moín.
3. **La posición** — el mapa marítimo (`US-25`) la necesita.

Además: el estado dice `transit` en un contenedor ya descargado, y Maersk solo resuelve si se
le indica el transportista (habría que deducirlo del prefijo del contenedor).

**Lo que eso sugiere: una combinación.** Parcels para el aéreo, con cuota fija, y ShipsGo solo
para el marítimo, que son pocos BL al mes y por lo tanto pocos créditos. La decisión es de
los usuarios clave; ver el backlog, `TASK-32`.

## Detalles para una integración

- **El contrato OpenAPI no coincide con la respuesta real.** Los eventos traen el texto en
  `status`, no en `state`. `toPort`, `fromPort`, `toAirport` y `transportMode` están
  documentados y **no vinieron en ninguna de las tres**. El lugar llega en `attributes`
  (`from`, `to`) como texto libre.
- **Cuota.** Se cuenta por número de rastreo único **por ciclo de facturación**: reenviar el
  mismo número en el ciclo es gratis (así se reintentó Maersk con la pista). Pero no es una
  suscripción: cada mes que un embarque sigue activo cuenta de nuevo. Un marítimo de 45 días
  cuenta en dos ciclos. La cuota mide **embarques activos por mes**, no altas.
- **Asíncrono.** `POST /trackings` devuelve un `request_id` que vive unos 30 minutos; se lee
  con `GET /trackings/{id}`. Las tres consultas terminaron en la primera lectura.
- **Cuenta.** El primer intento dio `403 UNCONFIRMED_ACCOUNT` sin consumir cuota: hay que
  confirmar el correo antes de usar el token.
- **Guías hijas (HAWB).** No se probaron: Parcels rastrea guías de aerolínea. `ZIVHYD017` lo
  sigue resolviendo TICA (`US-49`).

## Lo que no se pudo probar

- **Un aéreo en tránsito.** Las dos guías aéreas con referencia en WK38 ya habían llegado.
  Que la ETA aérea salga de `flight_legs` está visto en un envío llegado, no en uno en vuelo.
- **Más transportistas.** Tres referencias son una muestra mínima: faltan las otras navieras
  y los 22 prefijos de aerolínea que usa Gutis.
