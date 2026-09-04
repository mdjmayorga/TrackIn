# Dudas abiertas — sesión de validación de prototipos

**Fecha:** 01/09/2026 · **Cubre:** `US-39` (validación de prototipos con usuarios clave)
**Insumos:** borrador de wireframes · `docs/design/wireframes.md` · `docs/data-model.md` · SRS v0.3

> **Secciones A y B respondidas el 01/09/2026** — A en la sesión de validación con usuarios clave, B con Greivin — y ya aplicada al backlog, al modelo y al diccionario.
>
> Anotar la respuesta en la última columna. Las secciones están ordenadas por
> audiencia: **A** se resuelve con los usuarios en la sesión, **B** necesita a
> Greivin, **C** son datos de Logística y **D** depende de SAP.
>
> La columna «Recomiendo» es mi propuesta razonada desde el SRS y el
> anteproyecto. **No es una decisión tomada.**

---

## A · Con los usuarios clave — dashboard

| # | Pregunta | Por qué importa | Recomiendo | Respuesta |
|---|---|---|---|---|
| A1 | ¿Se leen bien **dos columnas de estado** —etapa y cumplimiento— o prefieren una sola? | El SRS §7.2 las separa: RN-02 a RN-06 dicen *dónde está*, RN-07 a RN-09 *si llega a tiempo*. Con una columna se pierde una de las dos respuestas | **Dos columnas + la derivada.** Un pedido «En destino» que llegará tarde es las dos cosas | ✅ **Dos columnas**, etapa y cumplimiento, como está |
| A2 | En «Cumplimiento», ¿el **guion** se entiende, o hace falta etiqueta explícita? | Es el caso «ETA no estimable» de RN-16: sin proyección no se puede afirmar nada | **Etiqueta explícita.** RN-16 le da nombre al caso; el guion no lo comunica | ⚠️ **El guion está bien.** No se agrega etiqueta |
| A3 | ¿**Agrupar** visualmente las líneas de una misma OC, o repetir la OC está bien? | El SRS §8.6 dice que cinco líneas en un mismo barco son el caso habitual | **Repetir la OC.** Agrupar rompe el ordenamiento por columna que exige RF-04 | ✅ **Repetir la OC** |
| A4 | ¿Se aprueba el **neutro con contorno** para `CERRADO`? | Es el único de los diez estados al que el SRS no asigna color | **Sí.** `CERRADO` sale del dashboard activo (RF-25): es el estado que no debe pedir atención | ✅ **Fondo blanco, letras negras** |
| A5 | La búsqueda por **orden de compra**, ¿es exacta o por fragmento? | Define el índice: btree sirve para exacta o prefijo; por fragmento hace falta `pg_trgm` | **Exacta o por prefijo.** Es un número de SAP, no texto libre | ✅ **Por prefijo.** Buscar «4500» devuelve las OC que inician con 4500; el btree basta |
| A6 | ¿Se entiende que las tarjetas **punteadas** de próximos arribos son relleno y no arribos cercanos? | RF-27 llena el bloque en dos niveles: 5 dentro de 7 días y, si faltan, los de peor cumplimiento a 30 días. Sin distinguirlos, el bloque miente | **Mantener la distinción.** Sin ella el título «Próximos arribos» es falso para dos de las cinco | ⚠️ **RF-27 cambia:** los 5 arribos más próximos, sin relleno. Se eliminan las tarjetas punteadas |
| A7 | Al filtrar por estado **terminal**, ¿la grilla cambia `ETA` y `F. proyectada` por `F. recepción` y `Cantidad recibida`? | De un pedido cerrado importa cuándo entró y cuánto se recibió; RF-04 no incluye esos campos | **Sí, intercambiarlas.** Mostrar ETA de algo ya recibido es ruido | ✅ **Sí, se intercambian** |

## A · Con los usuarios clave — mapas

| # | Pregunta | Por qué importa | Recomiendo | Respuesta |
|---|---|---|---|---|
| A8 | El marcador, ¿**color por etapa con anillo** de cumplimiento, o color por peor cumplimiento? | Un buque lleva varios pedidos: la etapa es común, el cumplimiento no | **Etapa + anillo.** Colorear por cumplimiento haría que el mapa no muestre dónde está la carga | ✅ **Etapa + anillo**, como está |
| A9 | ¿El **emergente como tabla** de pedidos a bordo se lee bien? ¿Hasta cuántas filas? | RF-18 pide OC, material, proveedor, ETA, fecha proyectada y estado. Con varios pedidos no cabe en una línea | **Tabla, con tope de 5 filas** y «ver los N restantes» | ✅ Se agregan **ETA y fecha proyectada** al emergente (ya aplicado en Figma) |
| A10 | ¿Sirve ver la **geocerca** dibujada, o distrae? | Es la regla de arribo de RN-05 hecha visible | **Mantenerla.** Es la única forma de que el usuario entienda por qué un buque «llegó» | ⚠️ **Se elimina la geocerca** del mapa |
| A11 | ¿Hace falta el **contador de pedidos sin posición**? | Un `SIN_TRACKING` no tiene marcador y desaparece del mapa en silencio | **Sí.** Sin él, el mapa oculta pedidos sin avisar | ✅ **Sí es necesario** |
| A12 | ¿Desde qué **antigüedad** una posición debe verse atenuada? | RNF-12 exige mostrar la antigüedad del último dato | **6 h para marítimo, 15 min para aéreo.** En alta mar las posiciones se espacian horas; ADS-B se consulta cada 31 s | ✅ Opción recomendada: 6 h marítimo, 15 min aéreo |
| A13 | Las tres vías de arribo —manual, fuente, inferido—, ¿se entienden como **orígenes** y no como estados? | RN-05 exige distinguirlas. En la revisión interna se leyeron mal | **Validar tal cual.** Si vuelve a leerse mal, separar la etiqueta del valor | ✅ Opción recomendada |
| A14 | Los **dos mapas**, ¿lado a lado debajo de la grilla? | RNF-01 exige que la vista inicial incluya «ambos mapas» y RNF-02 prohíbe recarga de página | **Lado a lado.** Evita el problema de Leaflet en pestaña oculta y sirve para la pantalla permanente de RNF-11 | ✅ **Sí**, ya montados en Figma |

---

## B · Decisiones de alcance — Greivin

| # | Pregunta | Por qué importa | Recomiendo | Respuesta |
|---|---|---|---|---|
| B1 | ¿Se confirma que **no se compran fuentes de datos de pago**? | Cierra la decisión abierta #3 del backlog. El spike TG-10 probó que **no hay cobertura AIS gratuita en Moín** | **Confirmar el no**, y asumir que el tramo final no se detecta automáticamente | ✅ **Confirmado el no.** El tramo final no se detecta automáticamente |
| B2 | ¿`US-14` **Confirmar desembarco** sube de `Should` a `Must`? | Si B1 es «no», es la **única vía** de saber que la carga llegó a Moín | **Sí, a `Must`.** Deja de ser un respaldo y pasa a ser el mecanismo principal | ✅ **Sube a `Must`** |
| B3 | ¿`US-29` **historial y trayecto** deja de ser `Could`, o se quita el enlace «ver historial»? | El detalle promete un enlace que hoy nadie construye. RF-22 lo exige | **Sacarla de `Could`.** RF-22 es un requerimiento, no una mejora | ⚠️ **Se quita el enlace «ver historial»**; `US-29` sigue en `Could` |
| B4 | Falta historia para **«Ajustar días»** — el ajuste manual de RN-01 | `US-09` lo usa en la fórmula y `US-20` lo muestra, pero **ninguna historia permite introducirlo** | **Crear la historia**, ~4 h, en el Sprint 5 con las demás intervenciones | ✅ **Se crea la historia** → `US-40`, 4 h, Sprint 5 |
| B5 | Sin login, ¿**quién es el usuario** que firma cada intervención auditada? | `auditoria_intervenciones.id_usuario` es `NOT NULL` y RF-14 exige «el usuario que la ejecutó». La autenticación se declaró fuera de alcance el 25/08 | **Selector de usuario obligatorio** en cada diálogo, y dejar registrado en el SRS que la autoría no está autenticada | ✅ Opción recomendada: selector de usuario, autoría no autenticada |
| B6 | Falta el valor **`ASOCIACION_TRACKING`** en `tipo_intervencion` | Asociar un identificador es una intervención manual (RF-14) y el dominio no la cubre | **Agregarlo**, dentro de `TASK-25` | ✅ **Agregado**, dentro de `TASK-25` |
| B7 | ¿`US-11` **apaga el rastreo** cuando la carga llega? | Sin eso, el worker sigue consultando naves que ya no llevan nada nuestro y gasta cuota del plan gratuito | **Sí, criterio nuevo** en `US-11`: al arribar, `elementos_rastreados.activo = false` | ✅ Opción recomendada: `activo = false` al arribar |
| B8 | ¿Entra un **spike de suscripción por MMSI y cuota** del plan gratuito? | El riesgo R1 sigue abierto desde el 19/08 y nadie ha medido el límite real. Determina si el rastreo funciona fuera del Caribe | **Sí, ~4 h en el Sprint 3**, antes de `US-02` | ✅ Opción recomendada → `TASK-27`, 4 h, Sprint 3 |
| B9 | ¿Hace falta un **cuarto rol** administrador? | RNF-05 pide perfiles diferenciados; hoy el dominio tiene Compras, Logística y Planificación | **No.** Sin autenticación, un cuarto rol no restringe nada | ✅ **No.** Solo los tres roles establecidos |

---

## C · Datos que solo Logística puede dar

| # | Dato | Para qué | Bloquea | Respuesta |
|---|---|---|---|---|
| C1 | **Lead time real** de cada destino, en días | Es el segundo sumando de RN-01; sin él no hay fecha proyectada | Sprint 4 · `US-09` | ⚠️ **Parcial (03/09).** El Z-tracking trae `Fecha según Lead Time de SAP` y `Fecha de llegada a Gutis` por línea (SAP ya calcula un lead time), pero **no por puerto de origen**. Falta el lead time por origen |
| C2 | **Lista definitiva de destinos** que opera Gutis | Hoy el maestro solo tiene lo que los spikes necesitaron probar | Sprint 3 · `TASK-03` | ✅ **Replanteada (03/09).** El destino es **único** (Gutis, `CR10`, puerto Limón/Moín). Lo que varía es el **origen**; `maestro_destinos` se reorienta a orígenes |
| C3 | **UN/LOCODE** oficial de los puertos | Clave natural del maestro de destinos | Sprint 3 | ⚠️ **Replanteada y corregida (03/09).** Destino único: **Moín (`CRMOB`)** por vía marítima y **SJO** por aérea — `CRLIO` es Puerto Limón, otro puerto a 6 km. Sobre los **orígenes**: el país ya viene en el Z-tracking, no hace falta pedirlo; el UN/LOCODE de puertos de origen solo se necesita **si el lead time resulta ser por puerto** (ver C1) |
| C4 | **Umbral de velocidad** bajo el cual se da por arribado un buque | RN-05 lo exige para descartar el tráfico que pasa de largo | Sprint 4 · `US-11` | ❌ **Pendiente.** No está en el Z-tracking; es parámetro de rastreo AIS |
| C5 | **Velocidad mínima** para estimar ETA | RN-16: por debajo, el pedido se marca «ETA no estimable» | Sprint 4 · `US-08` | ❌ **Pendiente.** No está en el Z-tracking |
| C6 | **Intervalo mínimo** entre lecturas guardadas | Decisión del 25/08 para frenar el crecimiento del historial | Sprint 3 · `US-04` | ❌ **Pendiente.** No está en el Z-tracking |
| C7 | **¿De dónde zarpan los embarques?** | Determina el alcance del mapa: si es Europa, es transatlántico; si es EE. UU., mucho más cerrado. **Nunca se preguntó** | Sprint 7 · `US-25` | ✅ **Cerrada (03/09).** Multi-continente: India + China ≈ 62 %, luego Europa (España, Alemania, Suiza, Bélgica, Italia…) y LatAm (Brasil, México, Guatemala). Columna `País de Origen` (texto libre) → maestro de países (`TASK-29`) |

---

## D · Bloqueado por SAP — riesgo R2

| # | Pregunta | Por qué importa | Recomiendo | Respuesta |
|---|---|---|---|---|
| D1 | ¿Hay **fecha** para la especificación del servicio de SAP? | El 25/08 se confirmó que el proceso está varado. Sin SAP **no existe ninguna función de usuario que meta pedidos al sistema** | Plantear formalmente un **RF de carga manual** si no hay fecha antes del cierre del Sprint 3 | |
| D2 | Longitud real de `oc_numero` y formato de `posicion_oc` | Hoy están como `VARCHAR(20)` e `INTEGER` provisionales | Mantener lo provisional y documentarlo como supuesto | |
| D3 | ¿SAP expone **códigos** de proveedor y material, o solo texto? | Si solo manda texto, la normalización necesita coincidencia difusa, que hoy no está estimada en ninguna historia | Si es texto, **estimar el retrabajo dentro de `US-31`** | |

---

## Resumen para abrir la sesión

- **14 preguntas de diseño** se resuelven mostrando el prototipo (sección A).
- **9 decisiones de alcance** necesitan a Greivin (sección B). Tres de ellas
  —B2, B3, B4— destapan trabajo comprometido que **hoy nadie construye**.
- **7 datos** dependen de Logística (sección C); los cinco primeros bloquean el
  Sprint 4, y C7 nunca se había preguntado.
- **SAP sigue varado** y es el riesgo más caro del proyecto (sección D).

**Lo más urgente si la sesión se acorta:** B1, B2 y D1. Las tres deciden si el
sistema puede saber que la carga llegó y si alguien puede meter pedidos.


---

## Nota sobre A5 — resuelto: es prefijo, no fragmento

La respuesta inicial decía «por fragmento», pero **el ejemplo citado describía
un prefijo**: buscar «4500» y obtener las OC que *inician* con 4500. Precisado
el 01/09: **es por prefijo**.

| Tipo | Consulta | Índice |
|---|---|---|
| **Prefijo** ✅ | `oc_numero LIKE '4500%'` | El btree ya propuesto **sirve** |
| Fragmento | `oc_numero LIKE '%4500%'` | Habría exigido la extensión `pg_trgm` |

**Consecuencia:** el índice de `pedidos_transito` §1.8 queda como estaba, no se
agrega ninguna extensión a la migración de `TASK-01`, y la persistencia sigue
dependiendo solo de PostgreSQL con PostGIS, como acota RNF-20.


---

## Addendum — reunión con Logística (03/09/2026)

Con la entrega del **Z-tracking** y las decisiones tomadas, cambian cuatro
respuestas previas. Las filas históricas se conservan; esto las reabre:

| Decisión previa | Estado 03/09 |
|---|---|
| **B1** — no se compran fuentes de datos de pago | 🔄 **Revertida.** Luz verde a APIs de pago (container tracking / aéreo). → `TASK-28` |
| **B2** — `US-14` desembarco sube a `Must` como única vía | ⚠️ **A revisar.** Si el container tracking (`TASK-28`) detecta el tramo final, deja de ser la *única* vía; se mantiene `Must` hasta el resultado del spike |
| **B5** — selector de usuario, autoría **no** autenticada | 🔄 **Revertida.** Con login (`US-42`) la autoría de RF-14 pasa a ser **autenticada**; el selector manual se retira |
| **B9** — no hace falta un cuarto rol Administrador | 🔄 **Revertida.** Con autenticación el rol **sí** restringe → entra el rol **Administrador** |

**Nuevo al alcance (03/09):** autenticación con login y **dos vistas por rol**
(simple: Material · Etapa · Cumplimiento / completa: la actual + deliveries,
departures, ETD y ATD), y el detalle con **país de origen + mapa del pedido**.

**Alcance de rastreo confirmado:** solo **PRODUCCION + IDA** (importaciones
internacionales); las demás categorías del Z-tracking son compras locales.

---

## Addendum 2 — respuestas de Logística (04/09/2026)

Tres consultas posteriores a la reunión del 03/09 cierran o replantean parte de la
sección C:

| # | Estado 04/09 |
|---|---|
| **C1** — lead time real | ✅ **Cerrada.** El lead time real **por origen vive en SAP**. El API está en desarrollo y la fecha es próxima. `maestro_destinos.lead_time_dias` deja de ser el dato maestro y queda como **respaldo** mientras el API no exista. Abre P2–P5 para Planeación: granularidad, si llega hasta puerto o hasta planta, y qué valor provisional se usa mientras tanto |
| **C3** — UN/LOCODE de puertos de origen | ✅ **Cerrada como innecesaria.** El **puerto de origen no se requiere**: basta el **país**, que ya viene en el Z-tracking. `maestro_destinos` se reduce a los dos destinos (`CRMOB` y SJO) y el origen se modela solo en `maestro_paises` (`TASK-29`) |
| **ETD/ATD** | ⚠️ **Nueva.** Hoy **no se registran**. Logística los entregará en **otro Excel**. Es una **segunda fuente de entrada** que `RF-31` no contempla y que ninguna historia ingesta. Ver sección R de `dudas_reunion_planeacion.md` |
| **C4, C5, C6** | 🔄 **Reclasificadas.** Con Vizion entregando hitos y ETA, dejan de ser datos del negocio y pasan a **parámetros de sistema** con valor por defecto (RF-24 / RNF-15) |

**Decisión de proveedores (04/09):** **Vizion** para rastreo marítimo, **Portcast**
para carga aérea y **OpenSky** (gratuito) únicamente para la posición de la aeronave en
el mapa. Resuelve `TASK-28` a favor del **Plan A**; el spike se reformula para
*validar* ambas fuentes con un BL y un MAWB reales, no para elegir proveedor.

**Las preguntas que quedan son para Planeación** → `dudas_reunion_planeacion.md`.
