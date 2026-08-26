# Wireframes — especificación de contenido

Especificación de las vistas que se maquetan en Figma para `US-34` a `US-37` y
se ensamblan en `US-38`. **El entregable es el archivo de Figma**; este
documento es la fuente de contenido y la trazabilidad a requerimientos, y es lo
que `TASK-23` consolida para el Informe 1.

Metodología acordada el 25/08: baja fidelidad, escala de grises salvo el
semáforo, datos de ejemplo reales, casos extremos incluidos y anotaciones de
trazabilidad al margen.

## Estado

| Vista | Historia | Especificación | Frame de Figma |
|---|---|---|---|
| Dashboard | `US-34` | ✅ 25/08/2026 | ✅ 26/08/2026 |
| Mapa marítimo | `US-35` | ⏳ | ⏳ |
| Mapa aéreo | `US-36` | ⏳ | ⏳ |
| Detalle de pedido | `US-37` | ⏳ | ⏳ |

## Convenciones

- Frames: `01-dashboard`, `02-mapa-maritimo`, `03-mapa-aereo`, `04-detalle-pedido`. Ancho 1440.
- Sin logo, sin sombras, sin esquinas redondeadas, sin tipografía corporativa.
- Cada frame lleva anotaciones numeradas al margen con los RF que satisface.
- Datos de ejemplo tomados del maestro de destinos real (Moín, MROC, MRLB).

---

## 1. `US-34` — Dashboard de pedidos en tránsito

**Borrador visual:** <https://claude.ai/code/artifact/4d736814-d5d9-4d50-ac28-e50942919fea>

**Trazabilidad:** RF-04 (grilla) · RF-15 (KPIs) · RF-19 (filtros) · RF-20
(frescura) · **RF-27 (próximos arribos)** · RNF-01 (200 pedidos, 3 s) · RNF-02
(filtro en 1 s) · RNF-08 (semáforo)

### 1.1 Encabezado — RF-20

Fecha y hora de la última actualización, más el estado de sincronización **de
cada fuente por separado**: AIS y ADS-B se caen de forma independiente, así que
un indicador único ocultaría la mitad del problema. Cuando una fuente lleva
tiempo sin responder se muestra su antigüedad («ADS-B 6 min»).

### 1.2 Cinta de KPIs — RF-15

Los cinco que exige el requisito, y **responden a los filtros activos**:

| Indicador | Origen |
|---|---|
| Pedidos activos | Conteo de pedidos con `motivo_cierre IS NULL` |
| % a tiempo | `estado_cumplimiento = 'A_TIEMPO'` |
| % en riesgo | `estado_cumplimiento = 'EN_RIESGO'` |
| % retrasados | `estado_cumplimiento = 'RETRASADO'` |
| Lead time medio | Promedio de `lead_time_destino_dias` |

### 1.3 Próximos arribos — RF-27

**Decisión del 25/08: va dentro del dashboard, no en vista aparte.** RNF-01 ya
lo situaba ahí al enumerar la vista inicial como «cinta de KPIs, vista de
próximos arribos, grilla y ambos mapas». `US-28` se reformuló y pasó del
Sprint 7 al Sprint 6, con las demás historias del dashboard.

Cinco tarjetas entre los KPIs y los filtros. Cada una: OC y posición, material,
fecha proyectada con días restantes, destino y vía, y el distintivo de
cumplimiento.

**La regla de RF-27 tiene dos niveles, y ahí está la trampa:**

1. Los cinco pedidos con `fecha_proyectada_disponible` más cercana **dentro de
   los 7 días** siguientes.
2. Si no hay cinco en ese horizonte, se completa hasta cinco con los de **peor
   cumplimiento dentro de 30 días**.

Son dos poblaciones distintas en la misma fila de tarjetas. Un pedido que entra
por el segundo criterio **no arriba pronto** —está en mala situación—, y
mostrarlo igual que los demás hace que el bloque mienta. En el borrador se
distinguen con borde punteado y la etiqueta «relleno»; el criterio de
aceptación de `US-28` lo exige explícitamente.

El bloque responde a los filtros activos, igual que los KPIs y la grilla.

### 1.4 Filtros — RF-19

Orden de compra · Proveedor · Material · Vía · Estado · Destino.

Se aplican de forma transversal a los KPIs, la grilla y **ambos mapas**, no solo
a la grilla. RNF-02 fija un segundo para que todos los componentes reflejen el
cambio, sin recarga completa.

### 1.5 Grilla — RF-04

Once columnas: las nueve del requisito, más `Pos.` y el desdoble del estado.

| # | Columna | Campo | Nota |
|---|---|---|---|
| 1 | OC | `oc_numero` | Ordenable |
| 2 | Pos. | `posicion_oc` | **No está en RF-04**, pero la fila es la *línea* de OC, no la orden |
| 3 | Material | `materiales.codigo` + `descripcion` | |
| 4 | Proveedor | `proveedores.nombre` | |
| 5 | Vía | `via_transporte` | |
| 6 | Destino | `maestro_destinos.nombre` | |
| 7 | ETA | `eta_utilizada` | «no estimable» cuando RN-16 no proyecta |
| 8 | F. proyectada | `fecha_proyectada_disponible` | Nula si no hay ETA |
| 9 | F. comprometida | `fecha_entrega_pedido` | Referencia de RN-07 a RN-09 |
| 10 | Etapa | `etapa_viaje` | Dónde está la carga |
| 11 | Cumplimiento | `estado_cumplimiento` | Si llega a tiempo. Vacío si no hay proyección |

Con ordenamiento por columna y paginación, sobre el volumen de referencia de
200 pedidos activos de RNF-01.

### 1.6 Semáforo — RNF-08

| Estado | Color | Regla |
|---|---|---|
| `SIN_TRACKING` | Gris | RN-02 |
| `EN_ORIGEN` | Azul claro | RN-03 |
| `EN_TRANSITO` | Azul | RN-04 |
| `EN_DESTINO` | Morado | RN-05 |
| `EN_PROCESO_ADUANAL` | Amarillo | RN-06 |
| `A_TIEMPO` | Verde | RN-07 |
| `EN_RIESGO` | Naranja | RN-08 |
| `RETRASADO` | Rojo | RN-09 |
| `CERRADO` | **Neutro con contorno** | RN-10 — *sin color en el SRS* |
| `CANCELADO` | Gris oscuro | RN-15 |

**`CERRADO` es el único color que no venía dado.** El SRS asigna color a nueve
de los diez estados. Se resolvió el 25/08 como neutro con contorno, y no como
color pleno, porque `CERRADO` sale del dashboard activo y deja de contar en los
KPIs (RF-25): es justamente el estado que **no** debe pedir atención. Se
descartaron dos alternativas: un rojo oscuro competiría con `RETRASADO` y leería
como problema siendo el final exitoso del ciclo; un azul oscuro obligaría a
mover RN-03 y RN-04, que ya ocupan la familia azul.

**El color nunca va solo.** Cada estado se lee también como texto. Hay dos
grises y tres azules en la paleta, y el daltonismo rojo-verde afecta a cerca del
8 % de los hombres.

### 1.7 Casos extremos incluidos a propósito

No solo el caso feliz. Las nueve filas de ejemplo cubren:

| Caso | Por qué |
|---|---|
| Dos líneas de la misma OC en el mismo buque | El caso que el SRS §8.6 llama habitual |
| ETA no estimable, fecha proyectada nula | RN-16, nave fondeada o bajo la velocidad mínima |
| `SIN_TRACKING` | RN-02, pedido sin identificador de rastreo |
| `RETRASADO` y `EN_RIESGO` | Los estados que justifican el producto |
| `CANCELADO` | RN-15, estado terminal |
| Destino MRLB sin lectura | Riesgo R5: no hay cobertura ADS-B en Liberia |

### 1.8 Qué debe validarse el 4 de septiembre

| # | Pregunta | Qué cambia según la respuesta |
|---|---|---|
| 1 | ¿Se leen bien dos columnas de estado, o conviene una con el estado derivado? | `US-19`, `US-21`, `US-24` |
| 2 | ¿El guion en «Cumplimiento» se entiende, o hace falta etiqueta explícita? | `US-19` |
| 3 | ¿Agrupar visualmente las líneas de una misma OC, o repetir la OC está bien? | `US-19` |
| 4 | ¿Se aprueba el neutro para `CERRADO`? | `US-24` y `TASK-25` (el SRS debe fijarlo) |
| 5 | ¿La búsqueda por OC es exacta o por fragmento? | Índice de `pedidos_transito`, §1.8 del modelo |
| 6 | ¿Se entiende que las tarjetas punteadas de próximos arribos son relleno y no arribos cercanos? | `US-28` |
| 7 | Al filtrar por estado terminal, ¿la grilla cambia `ETA` y `F. proyectada` por `F. recepción` y `Cantidad recibida`? | `US-19` |

### 1.9 La discrepancia con RNF-01, resuelta

RNF-01 incluía la vista de próximos arribos en la vista inicial del dashboard,
pero los criterios de `US-34` no la mencionaban y `US-28` vivía en el Sprint 7
como vista aparte. **Se resolvió el 25/08 a favor de RNF-01**: el bloque se
integra al dashboard (§1.3) y `US-28` se movió al Sprint 6.

Efecto en el cronograma: Sprint 6 pasa de 56 h a 64 h y Sprint 7 baja de 62 h a
54 h. Ambos quedan dentro de las 65 h de capacidad, y de paso el reparto entre
los dos sprints de frontend queda más parejo.

### 1.10 Tres solapamientos entre reglas, detectados al armar los datos de ejemplo

Al construir las nueve filas aparecieron colisiones que el SRS no resuelve. No
son de diseño: son de especificación, y las necesita `US-10` para implementar el
motor de estados.

**RN-07 contra RN-08.** RN-07 define `A_TIEMPO` como fecha proyectada «anterior o
igual» a la comprometida, sin calificar. RN-11 dice que las 48 h son «el umbral
que separa el estado A tiempo del estado En riesgo». Entonces cualquier fecha
dentro de las 48 h previas cumple las dos reglas a la vez. La lectura correcta
es que RN-08 prevalece por ser más específica —y así está el ejemplo de BASF,
con un día de margen y `EN_RIESGO`— pero **eso hoy no está escrito**.

**RN-05 contra RN-06.** `EN_DESTINO` es haber llegado; `EN_PROCESO_ADUANAL` es
haber llegado y estar corriendo el lead time. Como el lead time arranca al
llegar, `EN_DESTINO` dura un instante. O se define su duración, o se acepta que
es un estado de transición que casi nunca se ve en la grilla.

**Las 48 h contra el tipo `DATE`.** El umbral está en horas, pero
`fecha_proyectada_disponible` y `fecha_entrega_pedido` son fechas sin hora.
Entre dos `DATE`, 48 h solo puede significar 2 días. Hay que fijarlo o el borde
queda indefinido.

**Los tres quedaron resueltos el 26/08:**

| Solapamiento | Decisión |
|---|---|
| RN-07 contra RN-08 | RN-08 prevalece por ser más específica |
| Unidad del umbral | 2 días |
| RN-05 contra RN-06 | `EN_DESTINO` dura 30 min; `EN_PROCESO_ADUANAL` arranca 30 min tras la notificación del arribo |

Se incorporaron como criterios de aceptación de `TASK-25` y como nota de implementación de `US-10`. La fila de BASF del borrador —`EN DESTINO` con `EN RIESGO` y un día de margen— es correcta bajo estas reglas.

### 1.11 Un pedido cerrado, y por qué no aparece en la grilla por omisión

RF-25 saca los cerrados de los pedidos activos y RN-10 los archiva, así que la
grilla por defecto —que filtra `motivo_cierre IS NULL`— no los muestra. Se ven
**al filtrar por estado `CERRADO`**, que es un valor válido del filtro de RF-19.

En una fila terminal, la columna **Etapa muestra el estado terminal**, no la
etapa: el dominio de `etapa_viaje` (RN-02 a RN-06) no tiene valor terminal, así
que queda congelado en su último valor real —`EN_PROCESO_ADUANAL` para un
pedido recibido— y mostrarlo sería engañoso. El dato crudo se conserva para
auditoría. La fila `CANCELADO` del borrador ya aplica esta regla.

**`estado_cumplimiento` congelado sobre un cerrado no es estado, es veredicto:**
dice si el proveedor cumplió. Es el dato que hace útil normalizar `proveedores`,
que el SRS §8.1 justifica por «el análisis de desempeño por proveedor». En
`CANCELADO` va vacío, porque una orden anulada nunca llegó.

---

## 2. `US-35` — Mapa marítimo

**Trazabilidad:** RF-16 (mapa marítimo) · RF-18 (información emergente) ·
RF-19 (filtros transversales) · RF-20 (frescura) · RNF-08 (semáforo) ·
RNF-12 (degradación) · CU-07

### 2.1 El marcador es la nave, no el pedido

Es la decisión que gobierna toda la vista, y el SRS se contradice en ella.

CU-07 dice que el sistema «representa cada **nave** como un marcador coloreado
según el estado **del pedido**» —en singular—, pero §8.6 establece que varias
líneas de una misma orden viajan en el mismo buque y que el usuario las percibe
como *«un único elemento en el mapa»*.

**Prevalece §8.6: un marcador es un `elemento_rastreado`.** Dibujar un marcador
por pedido apilaría cinco iconos idénticos en la misma coordenada.

De ahí sale el problema real: **si cinco pedidos comparten barco y tienen
estados distintos, ¿de qué color es el marcador?**

### 2.2 Cómo se colorea un marcador que lleva varios pedidos

La respuesta cae de la decisión del 25/08 de separar el estado en dos
dimensiones:

| Dimensión | ¿Varía entre pedidos del mismo buque? |
|---|---|
| `etapa_viaje` | **No.** Deriva de la posición, que es la del buque |
| `estado_cumplimiento` | **Sí.** Cada línea tiene su propia fecha comprometida |

**Propuesta:** el marcador se colorea por `etapa_viaje`, que es inequívoca, y la
peor situación de cumplimiento a bordo se señala con un **anillo** alrededor del
marcador. Un marcador azul con anillo rojo es «en tránsito, y lleva carga
retrasada».

Así el mapa conserva las dos preguntas sin inventar un color mezclado, y sigue
la misma lógica que la grilla. La alternativa —colorear por el peor
cumplimiento— haría que el mapa nunca mostrara dónde está la carga, que es
justamente lo que un usuario de Logística mira.

### 2.3 Contenido emergente — RF-18

RF-18 pide orden de compra, material, proveedor, ETA, fecha proyectada y estado.
Con varios pedidos por marcador, **el emergente es una tabla, no una línea**:
encabezado con la nave, su última lectura y su antigüedad, y luego una fila por
pedido a bordo.

> `US-35` pide en sus criterios un tooltip con «OC, nave y estado», que asume un
> pedido por marcador. Se maqueta con el contenido completo de RF-18 porque el
> prototipo se valida una sola vez, y porque es lo que `US-27` construirá.

### 2.4 Elementos de la vista

| Elemento | Origen | Nota |
|---|---|---|
| Encabezado con frescura | RF-20 | El mismo del dashboard |
| Barra de filtros | RF-19 | Los seis filtros aplican también al mapa |
| Lienzo del mapa | RF-16 | Leaflet; centrado en el Caribe con Moín visible |
| Marcadores de nave | RF-16 | Uno por `elemento_rastreado` con posición conocida |
| Geocerca del destino | RN-05 | Círculo de `radio_geocerca_km` alrededor de Moín |
| Emergente | RF-18 | Tabla de pedidos a bordo |
| Leyenda | RNF-08 | Solo los estados que aparecen en lo marítimo |
| Contador de pedidos sin posición | **§2.6** | No es de ningún RF |

### 2.5 La antigüedad de la lectura tiene que verse — RNF-12

RNF-12 exige degradar mostrando el último dato válido **junto con su
antigüedad**. En una grilla eso es una columna; en un mapa, un marcador miente
por omisión: un buque dibujado en una posición de hace seis horas se ve igual
que uno reportado hace un minuto.

En el borrador, los marcadores con lectura vieja van **atenuados y con la
antigüedad rotulada**. El umbral a partir del cual se considera vieja sale de
`parametros_sistema`, no del código.

El spike TG-10 midió una mediana de 62 s entre mensajes AIS de un mismo buque,
pero en alta mar las posiciones pueden espaciarse horas. Un buque sin reportar
no está perdido: está lejos.

### 2.6 Un hueco que el mapa deja y ningún RF cubre

**Un pedido marítimo `SIN_TRACKING` no tiene marcador**, porque no tiene nave
asociada y por tanto no tiene posición. Tampoco lo tiene uno cuya nave nunca ha
reportado.

Esos pedidos **desaparecen del mapa en silencio**. Si el usuario filtra por
Moín y ve tres barcos, no hay nada que le diga que hay otros cuatro pedidos
marítimos que el sistema no puede ubicar. Se propone un contador explícito —«4
pedidos marítimos sin posición»— junto al mapa, con enlace a la grilla filtrada.

No sale de ningún requerimiento; sale de que RN-02 existe y el mapa no puede
representarlo.

### 2.7 Qué debe validarse el 4 de septiembre

| # | Pregunta | Qué cambia |
|---|---|---|
| 1 | ¿Color por etapa con anillo de cumplimiento, o color por peor cumplimiento? | `US-25`, `US-27` |
| 2 | ¿El emergente como tabla de pedidos a bordo se lee bien? | `US-27` |
| 3 | ¿Sirve ver la geocerca dibujada, o distrae? | `US-25` |
| 4 | ¿Hace falta el contador de pedidos sin posición? | `US-25` |
| 5 | ¿Desde qué antigüedad una posición debe verse atenuada? | `parametros_sistema` |

### 2.8 Mosaicos del mapa — verificado

Leaflet carga los mosaicos desde un servidor externo, y si la red corporativa
los bloqueara, `US-25` y `US-26` quedarían sin fondo cartográfico.

**Verificado el 26/08: la red de Gutis no bloquea OpenStreetMap.** El riesgo
queda descartado y el Sprint 7 puede planificarse contando con el mapa.

Queda una nota para `TASK-09`: el servidor público de mosaicos de OSM tiene una
política de uso que exige atribución visible y desaconseja el consumo intensivo.
Con el volumen de este sistema —200 pedidos y pocos usuarios simultáneos— se
está dentro de lo aceptable, pero la guía de despliegue debe decirlo por si
el uso crece.
