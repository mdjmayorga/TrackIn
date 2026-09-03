# Wireframes — especificación de contenido

Especificación de las vistas que se maquetan en Figma para `US-34` a `US-37` y
se ensamblan en `US-38`. **El entregable es el archivo de Figma**; este
documento es la fuente de contenido y la trazabilidad a requerimientos, y es lo
que `TASK-23` consolida para el Informe 1.

Metodología acordada el 25/08: baja fidelidad, escala de grises salvo el
semáforo, datos de ejemplo reales, casos extremos incluidos y anotaciones de
trazabilidad al margen.

## Estado

| Vista | Historia | Especificación | Frame de Figma | Validado con usuarios |
|---|---|---|---|---|
| Login | `US-41` | ✅ 03/09/2026 | ⏳ pendiente | ⏳ pendiente |
| Dashboard | `US-34` | ✅ 25/08/2026 | ✅ 26/08/2026 | ✅ 01/09/2026 |
| Mapa marítimo | `US-35` | ✅ 26/08/2026 | ✅ 27/08/2026 | ✅ 01/09/2026 |
| Mapa aéreo | `US-36` | ✅ 27/08/2026 | ✅ 27/08/2026 | ✅ 01/09/2026 |
| Detalle de pedido | `US-37` | ✅ 28/08/2026 | ✅ 28/08/2026 | ✅ 01/09/2026 |

Las 14 respuestas de la sesión están en
[`../backlog/dudas_sesion_validacion.md`](../backlog/dudas_sesion_validacion.md)
§A, y ya aplicadas a este documento, al backlog y al borrador
[`wireframes.html`](wireframes.html).

## Convenciones

- Frames: `01-dashboard`, `02-mapa-maritimo`, `03-mapa-aereo`, `04-detalle-pedido`. Ancho 1440.
- Sin logo, sin sombras, sin esquinas redondeadas, sin tipografía corporativa.
- Cada frame lleva anotaciones numeradas al margen con los RF que satisface.
- Datos de ejemplo tomados del maestro de destinos real (Moín, MROC, MRLB).

---

## 0. `US-41` — Login / autenticación

**Borrador visual:** [`wireframes.html`](wireframes.html) §00.

**Trazabilidad:** RNF-05 (perfiles diferenciados, ahora con autenticación) ·
RF-14 / RNF-06 (autoría de la intervención) · RNF-11 (pantalla permanente de
planta) · **nuevo RF de autenticación y de vista según rol** (pendiente de
numerar en el SRS v0.4).

> **Origen del cambio (reunión con Logística, 03/09/2026).** El SRS v0.3 excluía
> la autenticación. Logística confirmó que necesita **dos vistas** con distinto
> nivel de detalle, y distinguirlas obliga a saber quién entra. La autenticación
> pasa a estar **dentro del alcance**.

### 0.1 Formulario

Tarjeta centrada, sin logo, escala de grises. Campos: **Usuario** y
**Contraseña**, casilla «Recordar sesión», enlace «¿Olvidó su contraseña?» y
botón **Entrar**. Credenciales gestionadas por TrackIn (mecanismo propio); **no**
hay Active Directory ni SSO —eso sigue fuera del alcance—.

### 0.2 Estado de error

Mensaje **genérico** que no revela si falló el usuario o la contraseña, más un
contador de intentos restantes. El **bloqueo tras N intentos** es una decisión
abierta.

### 0.3 Enrutado por rol — la razón de ser del login

Tras autenticar, el sistema lleva al usuario a una de dos vistas:

| Vista | Roles | Grilla |
|---|---|---|
| **Simple** | Planificación · pantalla de planta | Solo **Material · Etapa · Cumplimiento** |
| **Completa** | Compras · Logística | La actual **+ deliveries, departures, ETD y ATD**, con mapas, detalle y auditoría |

### 0.4 Decisiones abiertas

- Bloqueo tras N intentos; duración de sesión y cierre por inactividad (relevante
  para la pantalla permanente de planta, RNF-11).
- Flujo de «olvidó su contraseña»: sin infraestructura de correo, lo más probable
  es **reinicio por administrador**.
- Si «Recordar sesión» aplica en la pantalla de planta.
- Confirmar el mapa **rol → vista** y si vuelve a hacer falta un **rol
  Administrador** que gestione cuentas (la decisión B9 lo descartó *sin*
  autenticación; con login el argumento cambia).

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

> 🔴 **RF-27 cambió el 01/09.** Los usuarios pidieron **los cinco arribos más próximos, sin más**: se elimina el segundo nivel de la regla y con él las tarjetas de relleno. Lo que sigue describe la regla anterior y queda **derogado**; `TASK-25` debe llevar el cambio al SRS y `US-28` ya no necesita distinguir dos poblaciones.
>
> Efecto lateral bueno: desaparece el riesgo de que el bloque afirme que cinco pedidos llegan pronto cuando dos no.

**~~La regla de RF-27 tiene dos niveles, y ahí está la trampa:~~** *(derogado)*

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
| `CERRADO` | **Blanco, letras negras** | RN-10 — *sin color en el SRS* |
| `CANCELADO` | Gris oscuro | RN-15 |

> **Validado el 01/09:** los usuarios aprobaron **fondo blanco con letras negras**. Se conserva el contorno gris, sin el cual el distintivo desaparece sobre la fila blanca de la grilla.

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
| 5 | ¿La búsqueda por OC es exacta o por fragmento? | ✅ **Por prefijo** — 01/09. El btree de `pedidos_transito` §1.8 basta |
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
| ~~Geocerca del destino~~ | RN-05 | **Retirada el 01/09.** No se mostró en Figma y los usuarios no la echaron de menos. El arribo inferido sigue explicándose en el detalle de pedido |
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

---

## 3. `US-36` — Mapa aéreo

**Trazabilidad:** RF-17 (mapa aéreo separado) · RF-18 (información emergente) ·
RF-19 (filtros transversales) · RF-20 (frescura) · RNF-08 (semáforo) ·
RNF-12 (degradación) · CU-08

RF-17 exige que el mapa aéreo esté **separado** del marítimo, y `US-26` lo
repite en su título. La vista reutiliza el andamiaje de `US-35` —encabezado,
filtros, lienzo, emergente y leyenda—: quien aprendió a leer un mapa no debería
tener que aprender el otro. Lo que cambia, cambia por razones medidas en los
spikes, no por preferencia.

### 3.1 Cinco diferencias con el mapa marítimo, y de dónde sale cada una

| # | Marítimo | Aéreo | Origen |
|---|---|---|---|
| 1 | El arribo se decide por geocerca | Se decide por `on_ground` | Decisión del 25/08, modelo §2.5 |
| 2 | El buque lleva la carga todo el viaje | El `icao24` cambia de vuelo en horas | TG-11 fase 4 |
| 3 | No se dibuja ruta | `US-36` pide **posición y ruta** | Criterio de aceptación |
| 4 | Sin lectura = está lejos | Sin lectura = **pudo haber aterrizado** | TG-11, caso `LRS1018` |
| 5 | Fuente continua por WebSocket | Sondeo con cuota diaria de 4000 créditos | TG-11 fases 1 y 3 |

### 3.2 Aquí la geocerca no aplica como regla, y tampoco se dibuja

> **Actualizado el 01/09.** Los usuarios pidieron **retirar el círculo también del
> mapa marítimo** (respuesta A10), así que ninguna de las dos vistas lo dibuja.
> Lo que sigue conserva su valor porque la diferencia de fondo no era gráfica
> sino **de regla**: en lo marítimo la proximidad decide el arribo, en lo aéreo no.

RN-05 decide el arribo marítimo por proximidad al puerto, y esa regla sigue
vigente aunque el círculo ya no se pinte. **En el aéreo el círculo sería además
una mentira gráfica:** el arribo lo decide `on_ground`, por decisión del 25/08
(`data-model.md` §2.5, punto 4 de §2.10). Dibujar un círculo alrededor de MROC
haría creer que entrar en él significa haber llegado, y no significa nada —
cincuenta kilómetros alrededor de Juan Santamaría cubren buena parte del Valle
Central, de modo que cualquier avión en ruta sobre Costa Rica caería dentro.

**Pero el radio sigue existiendo y sigue haciendo falta**, y conviene decirlo
porque es fácil concluir lo contrario: los 27 km de MROC y MRLB no deciden *si*
aterrizó, deciden **en qué aeropuerto** aterrizó. Una aeronave con
`on_ground = true` en medio del Pacífico no es un arribo; una con
`on_ground = true` a 8 km de MROC, sí. El radio pasó de criterio a
desambiguador.

En el borrador el aeropuerto se dibuja como un marcador con su código, sin
círculo, y el estado «en tierra» se lee en el marcador de la aeronave, no en la
geometría del lienzo.

### 3.3 El marcador es la aeronave, pero solo durante su tramo

Igual que en lo marítimo, un marcador es un `elemento_rastreado` y no un pedido:
un courier consolida varias líneas de OC en el mismo vuelo, y §8.6 vale para las
dos vías. El color por `etapa_viaje` y el anillo por peor `estado_cumplimiento`
a bordo se mantienen sin cambios, por coherencia con `US-35`.

**Lo que no se puede copiar es la permanencia.** El spike TG-11 documentó el
historial real de la aeronave `0ac9e1` en 48 horas: cinco vuelos distintos entre
Bogotá, Cancún, Chicago y Nueva York. Un buque lleva la carga de puerta a
puerta; un avión hace el tramo y a las tres horas está volando otra ruta para
otro cliente.

De ahí sale una regla que el mapa marítimo no necesita:

> **Un marcador aéreo solo es válido dentro de la ventana del tramo.** Fuera de
> ella, el `icao24` sigue reportando posiciones perfectamente válidas que **no
> son las de la carga**. Si el mapa las dibuja, señala un avión ajeno con el
> nombre de nuestro pedido.

El cierre de la ventana es el arribo por `on_ground` en el aeropuerto de
destino. Después de eso el pedido pasa a `EN_PROCESO_ADUANAL` y **su marcador
desaparece del mapa aéreo**: ya no está volando, está en tierra en MROC, y su
seguimiento vive en la grilla y en el detalle. Mantenerlo dibujado sobre el
aeropuerto sugeriría que la posición sigue siendo un dato vivo, cuando lo que
corre es el lead time.

### 3.4 La ruta: cuál se dibuja y cuál todavía no se puede dibujar

El criterio de aceptación de `US-36` pide «la posición **y ruta** del vuelo». Es
lo único que el mapa marítimo no tiene, y hay dos rutas posibles que no cuestan
lo mismo:

| Ruta | Fuente | Estado |
|---|---|---|
| **Prevista** — origen a destino, línea directa | Aeropuerto de origen del tramo + `maestro_destinos` | Disponible sin costo adicional |
| **Recorrida** — el trayecto realmente volado | `historial_tracking` acumulado, o `/tracks/all` | Depende de `US-29`, que es `Could` del Sprint 7 |

**El wireframe dibuja la prevista con trazo punteado y la recorrida con trazo
continuo hasta la posición actual**, que es lo que un usuario espera ver. Pero
la recorrida sale de `historial_tracking`, y quien la consulta y la dibuja es
`US-29` — una historia **`Could`** que puede no entrar. Si `US-29` cae, `US-26`
entrega solo la línea punteada de origen a destino, y el criterio de `US-36`
sigue cumpliéndose, porque «ruta» no obliga a que sea la volada.

Conviene que quede escrito antes de la validación, porque es exactamente el tipo
de detalle que un usuario aprueba en el prototipo y luego echa de menos en el
producto.

> Hay un tercer camino que se descartó: `/tracks/all` devuelve los 64 puntos de
> trayectoria de un vuelo en una sola llamada, y el spike la midió operativa.
> Pero es un endpoint **experimental** en la documentación de OpenSky, y su
> costo en créditos **no se midió**. Con 4000 créditos diarios y los
> `/flights/*` costando 30 cada uno, no se compromete la vista a un endpoint sin
> tarifa conocida.

### 3.5 Cuatro maneras en que un marcador aéreo miente, todas con evidencia

El spike TG-11 capturó los cuatro casos con datos reales. Ninguno es hipotético,
y los cuatro tienen consecuencia de diseño:

| Caso | Evidencia | Qué hace el wireframe |
|---|---|---|
| **Señal perdida en descenso** | `LRS1018`, 2256 m, `vertical_rate` −4,88 m/s, 207 s sin reportar | Marcador rotulado **«en aproximación · aterrizaje sin confirmar»**, no atenuado sin más |
| **Posición congelada** | `TIANI`, una sola posición en 30 muestras | El emergente muestra **antigüedad del dato y antigüedad del movimiento** por separado |
| **Callsign nulo o tardío** | `0ae105` reportó `null`, y `TIAGO` tres minutos después | La etiqueta cae a `icao24`, que es el identificador estable |
| **Altitud nula en tierra** | `baro_altitude` nulo en el **100 %** de los `on_ground` | El emergente escribe «en tierra», no un guion |

**El primero es el que obliga a apartarse de `US-35`.** En el mapa marítimo un
marcador atenuado significa «está lejos, el AIS no alcanza» —benigno—. En el
aéreo, el mismo marcador atenuado en descenso sobre el Valle Central significa
casi lo contrario: **probablemente ya aterrizó y el receptor perdió línea de
vista**, justo en el momento que interesa confirmar. Usar la misma opacidad para
las dos cosas diría lo incorrecto en la mitad de los casos.

Por eso la atenuación aérea se acompaña de la razón. Con `vertical_rate`
negativo, altitud baja y última posición dentro del radio del aeropuerto, el
marcador no dice «sin lectura»: dice «aterrizaje sin confirmar», que es una
invitación a `US-14` —la confirmación manual del desembarco— y no un fallo de la
fuente.

### 3.6 MRLB: un destino que nunca va a tener marcador

El contador de «pedidos sin posición» de §2.6 se hereda, pero en lo aéreo hay un
caso que no es el mismo y no puede contarse igual.

**MRLB (Liberia) dio cero aeronaves en tres muestras, en tres franjas horarias
distintas.** Es el riesgo R5 del backlog, y el modelo de datos ya lo advierte
(`data-model.md` §2.9): el destino es real y debe existir en el maestro, pero no
va a recibir lecturas automáticas, porque no parece haber receptores ADS-B en
Guanacaste.

Un pedido a MRLB sin marcador **no está esperando su primera lectura: no la va a
tener nunca**. Meterlo en el mismo contador que un `SIN_TRACKING` recién creado
promete una cobertura que no existe.

El wireframe los separa:

- MRLB se dibuja en el lienzo con la etiqueta explícita **«sin cobertura
  ADS-B»**, para que la ausencia se vea en el mapa y no solo en un contador.
- El contador lateral desglosa las dos razones: *sin identificador de rastreo*
  (RN-02, transitorio) y *destino sin cobertura* (R5, estructural).

No sale de ningún requerimiento. Sale de que el riesgo R5 está medido, y el mapa
es más honesto diciéndolo que callándolo.

### 3.7 «Fuera de ventana» no es «fuente caída»

El encabezado muestra la frescura de cada fuente por separado (§1.1), y en el
borrador ADS-B aparece en naranja con «6 min». En lo marítimo el AIS llega por
WebSocket y seis minutos de silencio son un síntoma. **En lo aéreo pueden ser el
funcionamiento normal.**

El spike midió la cuota en 4000 créditos diarios y calculó los intervalos
sostenibles: 31 s sondeando de forma continua, 10 s con ventanas de 8 h. La
recomendación para el Sprint 3 fue **sondear por ventanas activas**, porque un
embarque no está en vuelo las veinticuatro horas y sondear de madrugada sin
vuelos rastreados quema cuota sin obtener nada.

Si se adopta esa recomendación, el indicador de ADS-B pasará noches enteras
marcando una antigüedad alta **sin que nada esté roto**. Un indicador que no
distingue las dos situaciones entrena al usuario a ignorarlo.

El wireframe usa tres estados para la fuente aérea, no dos:

| Estado | Significado |
|---|---|
| Al día | Sondeo activo y última respuesta reciente |
| **Fuera de ventana** | No se está sondeando por diseño; se muestra la hora de reanudación |
| Sin respuesta | Se está sondeando y la fuente no contesta — esto sí es un fallo |

Queda como punto abierto para `TASK-25` y `US-17`: si el sondeo es por ventanas,
los horarios de esa ventana son un parámetro de `parametros_sistema`, junto al
`intervalo_consulta_adsb_s` que ya está fijado en 31 s.

### 3.8 Contenido emergente — RF-18

Mismo formato que en `US-35` —encabezado con el elemento rastreado y tabla de
pedidos a bordo— con tres campos que lo marítimo no tiene:

| Campo | Por qué |
|---|---|
| Altitud y tendencia vertical | Distingue crucero de aproximación, y es lo que sostiene §3.5 |
| Antigüedad del **movimiento** | Separada de la antigüedad del dato, por el caso `TIANI` |
| Vuelo e `icao24` | El callsign puede venir nulo; el `icao24` no |

La velocidad se expresa en nudos en lo marítimo y en km/h en lo aéreo, que es lo
que cada usuario espera leer.

**La altitud tiene un problema de unidad que conviene resolver antes de
`US-27`.** OpenSky devuelve `baro_altitude` **en metros**; la aviación la nombra
por nivel de vuelo (`FL330` = 33 000 pies de altitud de presión, ~10 060 m,
referida a la isobara estándar de 1013,25 hPa y no al nivel del mar). El
borrador escribe las dos —`FL330 · 10 060 m`— porque **el lector no es un
controlador aéreo, es Logística**: el nivel de vuelo es la convención del
dominio, pero los metros son lo que la persona que mira el tablero entiende sin
traducir. Si en la validación resulta que el nivel de vuelo no aporta, se
elimina y queda el dato crudo de la fuente, sin conversión ni posibilidad de
error de redondeo.

### 3.9 Elementos de la vista

| Elemento | Origen | Nota |
|---|---|---|
| Encabezado con frescura | RF-20 | Con los tres estados de §3.7 |
| Barra de filtros | RF-19 | Los seis filtros, igual que en las otras vistas |
| Lienzo del mapa | RF-17 | Leaflet; encuadre de la ruta activa, no de Costa Rica |
| Marcadores de aeronave | RF-17 | Uno por `elemento_rastreado` en vuelo |
| Rutas | `US-36` | Punteada la prevista, continua la recorrida (§3.4) |
| Aeropuertos de destino | `maestro_destinos` | MROC y MRLB, **sin círculo** — como el marítimo desde el 01/09 (§3.2) |
| Emergente | RF-18 | Tabla de pedidos a bordo, con altitud (§3.8) |
| Leyenda | RNF-08 | Las mismas tres codificaciones de `US-35` |
| Contador de pedidos sin posición | §3.6 | Desglosado por razón |

### 3.10 Qué debe validarse el 4 de septiembre

| # | Pregunta | Qué cambia según la respuesta |
|---|---|---|
| 1 | ¿Se entiende que un pedido aterrizado sale del mapa aéreo y pasa a la grilla? | `US-26`, `US-11` |
| 2 | ¿Basta la ruta prevista punteada, o la recorrida es indispensable? | Prioridad de `US-29`, hoy `Could` |
| 3 | ¿«Aterrizaje sin confirmar» se entiende, o se lee como error del sistema? | `US-26`, `US-14` |
| 4 | ¿Sirve marcar MRLB como sin cobertura, o alarma de más? | `US-26` |
| 5 | ¿El encuadre por ruta activa es mejor que un mapa fijo de la región? | `US-26` |
| 6 | ¿Hace falta la altitud en el emergente, o es ruido para Logística? | `US-27` |
| 7 | Si hace falta, ¿en metros, en nivel de vuelo, o ambos? (§3.8) | `US-27` |

---

## 4. `US-37` — Detalle de pedido

**Trazabilidad:** RF-05 (detalle y desglose del cálculo) · RF-14 (auditoría de
intervenciones) · RF-22 (historial de posiciones) · RF-26 (transbordo) ·
RN-01 (fecha proyectada) · RN-05 (los tres arribos) · RN-16 (ETA no estimable) ·
RNF-13 (reconstrucción a posteriori) · CU-03

Las otras tres vistas muestran **qué** dice el sistema. Esta muestra **por qué**,
y es la única que lo hace. El backlog ya lo decía al devolverla al Sprint 2 el
25/08: aquí vive el desglose del cálculo de la ETA, que es lo más novedoso del
producto.

### 4.1 La vista existe para hacer auditable un número

La grilla muestra `F. proyectada = 08/09`. De dónde sale ese número no cabe en
una celda, y RF-05 exige *«el desglose del cálculo que produjo la fecha
proyectada»*. RN-01 da la fórmula —ETA o ATA, más el lead time del destino, más
un ajuste manual opcional— y la vista la escribe como una operación legible:

| | Valor | De dónde sale |
|---|---|---|
| ETA utilizada | `05/09/2026 14:20` | *Snapshot* de `elementos_rastreados.eta_api` al recalcular |
| + Lead time del destino | `3 días` | *Snapshot* de `maestro_destinos.lead_time_dias` |
| + Ajuste manual | `0 días` | `ajuste_manual_dias`, con su motivo si no es cero |
| **= Fecha proyectada** | **`08/09/2026`** | `fecha_proyectada_disponible` |

Y debajo, la comparación que produce el cumplimiento:

| | Valor |
|---|---|
| Fecha comprometida | `09/09/2026` |
| Margen | `+1 día` |
| Cumplimiento | `EN RIESGO` — RN-08 prevalece sobre RN-07; el umbral son 2 días |

**Los dos *snapshots* son el motivo por el que esta vista funciona.**
`lead_time_destino_dias` y `eta_utilizada` están desnormalizados a propósito
(`data-model.md` §1.3): si el lead time se leyera por *join*, editar el maestro
reescribiría retroactivamente el desglose de todos los pedidos ya calculados, y
el número dejaría de ser auditable.

**De ahí sale algo que hay que dibujar y que ningún requerimiento pide.** Si
Logística cambia el lead time de Moín de 3 a 5 días, el maestro dice 5 y este
pedido sigue diciendo 3 hasta que `US-12` lo recalcule. **Ninguno de los dos
está mal, y la vista es el único lugar donde se puede ver la diferencia.** Sin
señalarla, un usuario que compare el detalle con el maestro concluirá que el
sistema tiene un error.

El borrador la muestra así: el valor usado en la operación, y al margen
—cuando difieren— el valor vigente del maestro con la fecha del último
recálculo. No es una alerta: es una nota al pie que evita una llamada.

### 4.2 El estado, explicado en las dos dimensiones que lo componen

La grilla trae dos columnas de estado, y §1.8 dejó como pregunta abierta si se
leen bien. **Esta vista es donde la separación deja de ser una convención de
tabla y se vuelve una explicación**, porque cada dimensión puede mostrar su
insumo:

| Dimensión | Valor | Por qué |
|---|---|---|
| `etapa_viaje` | `EN_TRANSITO` | Deriva de la posición — RN-04 |
| `estado_cumplimiento` | `EN_RIESGO` | Deriva de las fechas — RN-08 |
| `estado_calculado` | `EN_RIESGO` | Derivado: el riesgo manda sobre la etapa |

La tercera fila es la que conviene mostrar y no esconder. `estado_calculado` es
el valor que RF-11 exige y que el semáforo pinta, y sale de una precedencia de
cuatro pasos (`data-model.md` §1.4) donde **el paso 3 hace que el cumplimiento
tape la etapa**. Un usuario que ve el pedido pintado de naranja en el dashboard
y `EN_TRANSITO` en el detalle necesita que alguien le diga que las dos cosas son
ciertas a la vez.

### 4.3 Tres arribos distintos, y esta es la única vista que los distingue

RN-05 exige que el arribo inferido *«se registre como inferido y se distinga del
reportado por la fuente y del confirmado manualmente»*. El modelo guarda los
tres por separado —`ata_inferida`, `ata_api`, `ata_confirmada`— y **el origen no
tiene columna propia: se deriva por precedencia** (`data-model.md` §1.3).

En la grilla hay una sola columna de fecha, así que la distinción se pierde por
falta de espacio. Aquí caben las tres, cada una con su origen:

| Origen | Campo | En el borrador |
|---|---|---|
| `MANUAL` | `ata_confirmada` | *sin confirmar* |
| `FUENTE` | `elementos_rastreados.ata_api` | *sin reportar* |
| `INFERIDO` | `ata_inferida` | *fuera de la geocerca* |

> **Corregido el 01/09.** El ejemplo mostraba las tres vías con fechas del 7 de
> septiembre para un pedido que la grilla marca `EN TRÁNSITO` y cuyo «ahora» es el
> 25 de agosto: un arribo diez días en el futuro. Como el pedido de esta pantalla
> —`4500012847·10`— sigue navegando, **las tres vías van vacías**. La grilla ya
> tiene un pedido arribado, `4500012760·40`, si se quiere ilustrar el caso lleno.

**Cuando dos de los tres discrepan, la discrepancia es información.** Veintiséis
minutos entre lo que infirió la geocerca y lo que reportó la fuente no es un
error: es la diferencia entre cruzar el radio y atracar. Pero media jornada de
diferencia sí querría decir que la geocerca está mal dimensionada, y el usuario
que puede notarlo es el que mira esta pantalla. La vista los muestra los tres y
señala cuál está gobernando por precedencia.

### 4.4 «No estimable» no es un error, y aquí hay que decirlo con sus insumos

Cuando RN-16 no proyecta —nave fondeada, velocidad bajo el mínimo— la grilla
muestra un guion. Un guion no explica nada, y RN-16 exige exponer *«la
distancia, la velocidad y el instante empleados»*. **Esos tres datos no caben en
ninguna otra vista: viven aquí.**

El bloque de desglose, en ese caso, no muestra una operación sino su ausencia y
su causa:

| Insumo | Valor |
|---|---|
| Distancia al destino | `412 km` |
| Velocidad de la última lectura | `0,4 nudos` |
| Instante de la lectura | `26/08/2026 09:12` |
| Umbral de velocidad mínima | `velocidad_minima_eta` — **a definir** |

Y en lugar de fecha proyectada, la frase: «no estimable — la nave está por
debajo de la velocidad mínima desde hace 14 h».

> **Un punto abierto que esta vista vuelve urgente.** `velocidad_minima_eta`
> figura en `parametros_sistema` como *a definir* (`data-model.md` §8.3). Se
> puede construir la vista sin el valor, pero **no se puede validar el 4 de
> septiembre sin decidir qué se le muestra al usuario**: si el umbral aparece en
> pantalla, tiene que tener un número.

### 4.5 La línea de tiempo son dos secuencias, y mezclarlas la arruina

El criterio de `US-37` pide *«una línea de tiempo de posiciones y estados»*. Son
dos cosas con orígenes y densidades distintas:

| Secuencia | Fuente | Cuántas filas |
|---|---|---|
| Posiciones | `historial_tracking` | Mediana de 62 s entre mensajes AIS (TG-10); 7 s en ADS-B (TG-11) |
| Estados e intervenciones | Cambios de estado y `auditoria_intervenciones` | Unos pocos por viaje |

Un viaje de tres semanas produce **decenas de miles de posiciones y menos de
diez eventos**. Fundirlas en una sola lista cronológica —que es lo que el
criterio pide literalmente— entierra los eventos que importan bajo el ruido de
las posiciones.

**Propuesta: la línea de tiempo es de eventos, y las posiciones se pliegan entre
ellos.** Cada tramo entre dos eventos muestra su conteo —«1 284 posiciones»— con
enlace al historial completo. Así la secuencia cronológica existe y es legible,
y la posición individual sigue estando a un clic.

> **Resuelto el 01/09 (decisión B3).** `US-29` **se mantiene en `Could`** y el
> enlace «ver historial» **se retiró del detalle**: el conteo plegado queda como
> dato informativo sin acción, y es contenido de `US-20`. Si en algún momento se
> considera que RF-22 queda incumplido por eso, hay que reabrir la decisión.
>
> El conteo sigue diciendo lo que hubo.

### 4.6 El transbordo parte la línea de tiempo, y hay que verlo

La decisión del 25/08 fue la opción A: entra `pedido_elemento_rastreado` con
`tramo`, `fecha_desde` y `fecha_hasta`, para que el historial de la nave
anterior se conserve (RF-26).

**Esta es la vista donde esa decisión se cobra su valor.** Sin mostrar los
tramos, un trayecto con transbordo se lee como un salto inexplicable: la carga
aparece de golpe en otro buque, a cientos de kilómetros. Con los tramos, la
línea de tiempo dice «tramo 1 · MSC BRUNELLA · del 12/08 al 26/08» y «tramo 2 ·
MAERSK CAMPTON · desde el 26/08», y el salto se vuelve un hecho documentado.

El borrador incluye un pedido con transbordo justamente por eso: es el caso que
justifica una entidad entera del modelo, y conviene que el supervisor lo vea
dibujado.

### 4.7 Un pedido sin identificador de rastreo, y un hueco en la auditoría

`US-20` pide que un pedido sin identificador indique *«que no es rastreable»* y
ofrezca **asociar uno**. Es el estado vacío de esta vista, y corresponde a RN-02:
sin identificador no hay posición, no hay ETA y no hay cumplimiento.

Al maquetar esa acción aparece un hueco que no es de diseño:

> **Asociar un identificador de rastreo es una intervención manual sobre un
> pedido, y el dominio de `tipo_intervencion` no tiene un valor para ella.**

Los cinco valores modelados son `CONFIRMACION_DESEMBARCO`, `RECEPCION_PLANTA`,
`TRANSBORDO`, `AJUSTE_MANUAL` y `CIERRE_FORZADO` (`data-model.md` §8.2). RF-14
exige registrar *«por cada intervención manual sobre un pedido»* el usuario, la
fecha, el valor anterior, el valor nuevo y el motivo. Asociar un identificador
cumple esa definición —cambia el pedido, lo hace una persona, y es exactamente
el cambio que después explica por qué empezaron a llegar posiciones—, así que
**falta un valor en el dominio**, del tipo `ASOCIACION_TRACKING`.

No se resuelve aquí: es del modelo, lo consume `US-15` y hay que llevarlo a
`TASK-25` con las demás correcciones del SRS.

### 4.8 Las acciones, y por qué ninguna es de un solo clic

Cinco acciones viven en esta vista, y cada una construye una historia distinta:

| Acción | Historia | Escribe en |
|---|---|---|
| Confirmar desembarco | `US-14` | `ata_confirmada` + auditoría |
| Registrar recepción en planta | `US-18` | `fecha_recepcion_planta`, `cantidad_recibida`, `motivo_cierre` |
| Ajustar días manualmente | `US-12` | `ajuste_manual_dias` + auditoría |
| Actualizar nave por transbordo | `US-30` | `pedido_elemento_rastreado` + auditoría |
| Asociar identificador de rastreo | `US-20` | `elementos_rastreados` + auditoría (§4.7) |

RF-14 exige **el motivo declarado** en todas. Eso tiene una consecuencia de
interfaz que conviene fijar antes de construirla: **ninguna acción puede ser un
botón que ejecuta al pulsarlo.** Todas abren una confirmación con un campo de
motivo obligatorio. Un botón de un clic no puede satisfacer RF-14.

### 4.9 Elementos de la vista

| Elemento | Origen | Nota |
|---|---|---|
| Migas y encabezado del pedido | CU-03 | OC, posición, material, proveedor |
| Distintivos de estado | RNF-08 | Las dos dimensiones y el estado derivado (§4.2) |
| Desglose del cálculo | **RF-05** | La operación de RN-01, o su ausencia con causa (§4.1, §4.4) |
| Datos maestros | RF-05 | Destino, vía, fechas, cantidades |
| Elemento rastreado | RF-05 | Identificador, última posición y **última consulta exitosa** |
| Bloque de arribo | RN-05 | Los tres arribos con su origen (§4.3) |
| Línea de tiempo | RF-22 | Eventos, con posiciones plegadas (§4.5) y tramos (§4.6) |
| Barra de acciones | RF-14 | Cinco acciones, todas con motivo (§4.8) |
| Estado vacío sin identificador | RN-02 | Con la acción de asociar (§4.7) |

### 4.10 Qué debe validarse el 4 de septiembre

| # | Pregunta | Qué cambia según la respuesta |
|---|---|---|
| 1 | ¿El desglose como operación aritmética se entiende, o hace falta prosa? | `US-20` |
| 2 | ¿Ver el lead time vigente junto al usado aclara o confunde? (§4.1) | `US-20`, `US-12` |
| 3 | ¿Los tres arribos son útiles, o basta el que gobierna? (§4.3) | `US-20` |
| 4 | ¿La línea de tiempo con posiciones plegadas basta, o se piden todas? (§4.5) | Prioridad de `US-29` |
| 5 | ¿Cuál es el valor de `velocidad_minima_eta`? (§4.4) | `US-17`, `TASK-25` |
| 6 | ¿El motivo obligatorio en cada acción es aceptable operativamente? (§4.8) | `US-14`, `US-18`, `US-12` |
