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
| Dashboard | `US-34` | ✅ 25/08/2026 | ⏳ Pendiente |
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

### 1.9 La discrepancia con RNF-01, resuelta

RNF-01 incluía la vista de próximos arribos en la vista inicial del dashboard,
pero los criterios de `US-34` no la mencionaban y `US-28` vivía en el Sprint 7
como vista aparte. **Se resolvió el 25/08 a favor de RNF-01**: el bloque se
integra al dashboard (§1.3) y `US-28` se movió al Sprint 6.

Efecto en el cronograma: Sprint 6 pasa de 56 h a 64 h y Sprint 7 baja de 62 h a
54 h. Ambos quedan dentro de las 65 h de capacidad, y de paso el reparto entre
los dos sprints de frontend queda más parejo.
