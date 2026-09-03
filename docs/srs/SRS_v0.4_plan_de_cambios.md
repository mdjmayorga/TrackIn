# SRS v0.4 — Plan de cambios

**Base:** `SRS_TrackIn_v0.3.docx` (20/08/2026) · **Motivo:** reunión con Logística
del **03/09/2026** — entrega del **Z-tracking** (`docs/analisis/2026-Agosto-WK36.xlsx`),
confirmación de **autenticación con dos vistas**, **detalle con país de origen y mapa**,
y **luz verde a APIs de pago**.

> Este redline se aplica **directamente sobre el `.docx`** (el generador `srs.js`
> está desfasado; regenerar perdería todo lo posterior a v0.1). Corresponde a la
> tarea `TASK-25` («Emitir el SRS v0.4»), cuyo alcance se amplía con esta reunión.
> Tras editar, actualizar la tabla de contenidos con **F9** y registrar v0.4 en el
> historial de revisiones.

Decisiones que respaldan estos cambios (tomadas el 03/09):

1. **Alcance de rastreo:** solo **PRODUCCION + IDA** (importaciones internacionales).
2. **País de origen:** **maestro de países + normalización, obligatorio**.
3. **Roles:** **3 roles + Administrador**; el rol determina la vista.
4. **APIs de pago:** arquitectura de dos proveedores — `Vizion` (marítimo) y `Portcast` o
   `ShipsGo Air` (aéreo), más APM Terminals Moín para el arribo. Sujeta a `TASK-28`.
5. **SAP:** sigue sin fecha. Se **formaliza la carga manual como `RF-31`** y el archivo
   Z-tracking pasa a ser la vía oficial de entrada. La sincronización con SAP queda como
   evolución futura, fuera del alcance. **Resuelve el riesgo R2.**

---

## 1. Historial de revisiones

Añadir fila:

> **v0.4 · 03/09/2026 · Mariano Mayorga** — Incorpora la muestra real de datos
> (Z-tracking, semana 36). Autenticación con login y dos vistas por rol entran al
> alcance. El detalle de pedido añade país de origen y mapa del envío. Se reabre la
> compra de fuentes de datos de pago (container tracking). Se puebla el Anexo B con
> el inventario real de campos y se ajusta el modelo de datos (§8).

---

## 2. §1.2 Alcance

- **Dentro del alcance** — añadir:
  - «Autenticación propia con inicio de sesión, gestión de usuarios y **dos vistas
    diferenciadas por rol** (simple y completa).»
  - «Evaluación e integración de **una fuente de rastreo comercial** (container
    tracking) para cubrir el tramo final y el punto ciego de AIS en Moín.»
- **Fuera del alcance** — quitar la exclusión de la compra de fuentes de datos
  (revierte la decisión del anteproyecto y B1). Mantener fuera **SSO/Active Directory**.

## 3. §2.2 / §2.3 / §3 Actores y usuarios

- Reescribir la frase «No se implementará autenticación corporativa. El control de
  acceso… será el mínimo necesario» → **«El sistema implementa autenticación propia
  (usuario y contraseña); la integración con SSO/Active Directory queda fuera del
  alcance.»**
- §2.3: confirmar los perfiles y **añadir el rol Administrador** con capacidad de
  **gestión de cuentas** (crea/edita usuarios y asigna rol). Mapear rol → vista:

  | Rol | Vista |
  |---|---|
  | Planificación · pantalla de planta | **Simple** (Material · Etapa · Cumplimiento) |
  | Compras · Logística | **Completa** (grilla actual + deliveries, departures, ETD, ATD) |
  | Administrador | Completa + gestión de usuarios |

## 4. §5.2 Seguridad — RNF-05 y nuevo RNF

- **RNF-05:** ampliar — los perfiles se distinguen **mediante autenticación**; las
  operaciones de mantenimiento de maestros, confirmación manual y gestión de usuarios
  quedan restringidas por rol.
- **RNF-24 (nuevo):** «Las contraseñas se almacenan con *hash* de un algoritmo
  adaptativo (p. ej. bcrypt/argon2); nunca en claro. La sesión expira por inactividad.»
- **B5 (autoría):** con login, `auditoria_intervenciones.id_usuario` se toma de la
  **sesión autenticada**; se retira el selector de usuario manual de RF-14.

## 5. §4 Requerimientos funcionales — nuevos RF

- **RF-28 — Autenticación y sesión.** El sistema autentica por usuario y contraseña,
  crea sesión, aplica cierre por inactividad y limita intentos fallidos.
- **RF-29 — Vista por rol.** El sistema presenta la grilla **simple** o **completa**
  según el rol del usuario autenticado.
- **RF-30 — Detalle con origen y mapa.** El detalle de pedido muestra el **país de
  origen** y un **mapa de seguimiento del envío individual**.
- **RF-31 — Carga manual de pedidos.** El sistema carga los pedidos desde el archivo de
  seguimiento de Logística, con validación, normalización, informe de rechazos y
  actualización por OC y posición. **Es la vía oficial de entrada**; SAP queda como
  evolución futura. *(Decisión 5 — resuelve R2.)*
- *(Renumerar y actualizar la cuenta «27 RF» en README y §1.5: ahora son **31**.)*

## 6. §7 Reglas de negocio

- **RN-17 (nueva) — Normalización de dominio.** País, vía de transporte, incoterm y
  temperatura entran como texto libre y se normalizan contra catálogo; los valores no
  resolubles (`PENDIENTE`, `N/A`, fuera de catálogo) se marcan para revisión sin
  abortar el lote.
- **RN-05 / RN-16:** nota de que, si el spike de container tracking (`TASK-28`) da
  cobertura en Moín, el **tramo final podría detectarse automáticamente**; revisar
  entonces si la confirmación manual de desembarco (RF-13/US-14) deja de ser la única
  vía (decisión B2).

## 7. §8 Modelo de datos

- **`pedidos_transito.oc_numero`:** `VARCHAR(20)` → **`CHAR(10)`** (las 2.045 líneas
  del Z-tracking tienen exactamente 10 dígitos). `posicion_oc` **`INTEGER`** confirmado
  (múltiplos de 10, rango 10–650). *(Cierra D2.)*
- **Nueva entidad `maestro_paises`** (código ISO + nombre); FK `pais_origen_id` desde
  `pedidos_transito`. *(Decisión 2.)*
- **Reorientar `maestro_destinos`:** el destino es **único** — **Moín (`CRMOB`)** por vía
  marítima y **SJO** por vía aérea. *(Ojo: `CRLIO` es Puerto Limón, un puerto distinto a 6 km;
  el terminal de contenedores es Moín.)* Lo que varía es el **origen**, y el **país** ya viene
  en el Z-tracking. El UN/LOCODE de los puertos de origen solo hace falta **si el lead time
  resulta estar definido por puerto** (ver C1). *(Cierra C2, replantea C3.)*
- **Nuevos campos en `pedidos_transito`** (presentes en el Z-tracking):
  `incoterm`, `temperatura` (cadena de frío), `tipo_proveedor` (local/internacional),
  `fabricante` (distinto de proveedor), `eta_cr`, `arribo_cr`.
- **`usuarios`:** añadir `hash_contrasena`, `rol` (Compras/Logística/Planificación/
  Administrador), `activo`; base de la autenticación real. *(Decisión 3.)*
- Actualizar el diccionario de datos (`docs/data-dictionary.md`) y el ER en consecuencia.

## 7 bis. §2.5 Suposiciones — el supuesto de SAP se cae

El SRS asumía que el Centro de Competencias entregaría la especificación del servicio API de
SAP **antes del Sprint 3**. El 03/09 se confirmó que **sigue sin fecha**. Se sustituye por:

> La vía oficial de entrada de datos es la **carga del archivo de seguimiento de Logística**
> (`RF-31`). La sincronización con SAP queda como evolución futura, fuera del alcance. El
> archivo de muestra recibido el 03/09 sustenta el contrato del Anexo B y **elimina el riesgo
> de que el sistema quede sin vía de entrada**.

**Anexo B se reorienta:** deja de titularse «Contrato de datos del servicio API de SAP» y pasa
a **«Contrato de datos de entrada»**, válido tanto para la carga manual como para el servicio
de SAP cuando exista.

## 8. §D3 SAP — confirmado por el Z-tracking

- SAP entrega **código + texto** para proveedor (`1007052` + nombre) y material
  (`11000371` + descripción) → **no hace falta coincidencia difusa** para esos. *(Cierra D3.)*
- Campos de logística (país, vía, incoterm, temperatura) llegan como **texto libre
  sucio** (`USA` vs `ESTADOS UNIDOS`, `Exw`/`EXW`, typo `PEDIENTE`, columnas desplazadas)
  → sí requieren catálogo y normalización (RN-17 / RF-02).

## 9. Anexo B — Contrato de datos (poblar con la muestra real)

Reemplazar el placeholder por el inventario real del Z-tracking. **22 columnas base**
(todas las hojas) + **17 de logística** (solo PRODUCCION e IDA):

| # | Campo | Tipo | Obligatorio | Observación (del Z-tracking) |
|---|---|---|---|---|
| 1 | Documento Compra (OC) | Texto(10) | Sí | 10 dígitos exactos |
| 2 | Posición | Entero | Sí | Múltiplo de 10 |
| 3 | Centro | Texto | Sí | Siempre `CR10` (destino único) |
| 4–5 | Proveedor (código + nombre) | Texto | Sí | Código y texto disponibles |
| 6–7 | Material (código + texto breve) | Texto | Sí | Código y texto disponibles |
| 8–9 | Solicitud de pedido + posición | Texto/Entero | No | |
| 10–12 | Fecha Solped / Entrega Solped / Pedido | Fecha | Sí | **Serial de Excel**; convertir a ISO |
| 13–14 | Cantidad reparto + UMP | Número + Texto | Sí | UMP: G, ML, MG, UN, CS… |
| 15–17 | Ctd. entregada / Fecha entrega / Ctd. pendiente | Núm/Fecha | Sí | |
| 18 | Fecha estadística | Fecha | No | |
| 19–20 | Usuario + Grupo compra | Texto | Sí | Grupos A00–A07 |
| 21–22 | Estatus + Diferencia Días | Texto/Entero | Sí | «Atrasado»/«A Tiempo»; días con signo |
| 24–25 | Fecha llegada a Gutis / según Lead Time SAP | Fecha | No | Solo PRODUCCION/IDA |
| 26 | Fabricante | Texto | No | Distinto del proveedor |
| 28 | **Incoterm** | Texto | No | EXW, CIF, CIF LIMON, CIP, FOB, FCA, CPT, LOCAL |
| 34 | Tipo de proveedor | Texto | No | LOCAL / INTERNACIONAL |
| 35 | **Temperatura** | Texto | No | Ambiente / 2–8 °C / 15–25 °C (cadena de frío) |
| 36 | **País de Origen** | Texto | No→**normalizar** | India, China, Brasil, España… (texto libre) |
| 37 | **Tipo de transporte** | Texto | No→**normalizar** | Aéreo / Marítimo / Terrestre |
| 38 | ETA CR | Fecha/Texto | No | A veces «PENDIENTE» |
| 39 | Carga arribó a CR | Texto | No | SI / No / PENDIENTE |

> **Nota:** el contenido lo expondrá el **API de SAP**; el Z-tracking es la **muestra
> que desbloquea este anexo** y sirve de plantilla para la carga manual (D1) mientras
> SAP siga varado.
>
> **No hay ninguna columna de identificador de rastreo** (MMSI, IMO, buque, vuelo,
> AWB, contenedor, booking, BL): solo «Tipo de transporte». Confirma el Anexo C.2 y
> justifica RF-03 (asociación manual) y las APIs de pago (Anexo C.5).

## 10. Anexo C.5 — APIs de rastreo de pago (nuevo)

Registrar las fuentes comerciales evaluadas y la recomendación:

- **Marítimo — `Vizion`:** hitos normalizados, más **IMO/MMSI, lat/lon, velocidad y rumbo**
  y traza horaria. Es el único que alimenta `elementos_rastreados`, `historial_tracking`
  y RN-16 tal como están especificados. **Solo marítimo.**
- **Marítimo, complementos:** `Terminal49` (holds, *last free day*, *pickup* del tramo de
  terminal; llave gratis de 10 contenedores para prototipar) y `ShipsGo` (alternativa
  económica que además cubre aéreo).
- **Aéreo — por AWB:** `Portcast` (350+ aerolíneas, 16+ hitos, ETD/ETA predictivos),
  `ShipsGo Air` (160+, económica) o `TrackingMore` (116, tier gratis).
  **Advertencia:** las APIs rastrean el **MAWB** (guía madre de la aerolínea); si el
  forwarder entrega un **HAWB** (guía hija), no resuelve. Hay que exigir el MAWB o el mapeo.
- **No confundir:** `FlightAware AeroAPI`, `Cirium` y `Aviationstack` rastrean **aeronaves**,
  no carga. Sirven para el punto en el mapa aéreo, no para el estado del envío.
- **Arribo en destino:** API de **APM Terminals Moín** (`CRMOB`) — *Container Event History*
  e *Import Availability*, con entorno de pruebas.
- **Posición de buque (opcional):** Spire Maritime, Datalastic, MarineTraffic. Redundante
  si se usa Vizion, que ya integra AIS terrestre y satelital.
- **Recomendación:** `Vizion` (marítimo) + `Portcast` o `ShipsGo Air` (aéreo) + APM Terminals
  Moín (arribo). Validar con `TASK-28` usando referencias reales antes de comprometer
  presupuesto, como en TG-10 y TG-11. Costo por uso; pedir cotización.
- **Prerrequisito:** sin la referencia de embarque (BL/booking/contenedor o MAWB) **ninguna
  de estas fuentes devuelve nada** — ver RF-03.

---

## Pendiente de Logística / SAP (bloquea partes del v0.4)

Estos valores **no** están en el Z-tracking y siguen abiertos:

- **C1** — lead time **por puerto de origen** (SAP da uno por línea, no por origen).
- **C4** — umbral de velocidad de arribo (RN-05).
- **C5** — velocidad mínima para ETA (RN-16).
- **C6** — intervalo mínimo entre lecturas (RNF-13).
- **ETD/ATD** — fuente (¿container tracking / rastreo? no vienen del Z-tracking).
- **Login** — duración de sesión, inactividad y bloqueo tras N intentos.

Mientras no lleguen, dejar estos umbrales como **parámetros de sistema** (RF-24/RNF-15)
con valor provisional documentado como supuesto.
