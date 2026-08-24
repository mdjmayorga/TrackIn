# Plan semanal — Sprint 2, Semana 1 (24–28 agosto 2026)

**Proyecto:** TrackIn — Práctica Profesional, TEC
**Sprint 2:** 24 ago – 4 sep 2026 · **Ejecutor:** 1 persona
**Capacidad de la semana:** 32,5 h (6,5 h/día × 5 días, mitad de las 65 h del sprint)

> Este plan corresponde al backlog **ya revisado** el 24/08. Los cambios y su
> justificación están en `backlog_trackin.md` §«Revision del 24/08».

---

## 1. Objetivo de la semana

**Cerrar el modelo de datos definitivo.** Al viernes 28 debe existir un diagrama
ER consolidado, revisado con Greivin, con las **siete** entidades del SRS v0.3
§8.1, y el diccionario de las dos primeras tablas.

Se eligió este bloque y no los prototipos porque es el único con consumidores
aguas abajo con fecha: `TASK-01` (esquema y migraciones Alembic, Sprint 3, 7–18
sep) no puede arrancar sin él, y `TASK-02` (PostGIS) depende de que el tipo
geoespacial quede decidido. Los wireframes no bloquean a nadie hasta el Sprint 6.

---

## 2. Qué cambió en el backlog antes de empezar

El backlog original se derivó del **SRS v0.2**; el repositorio ya tiene **v0.3**
(commit `11e9edd`). Al contrastarlos aparecieron tres correcciones, todas ya
aplicadas a `backlog_trackin.md`:

### 2.1 Faltaban tres entidades — `TASK-15` pasó de 4 h a 10 h, y nace `TASK-24`

`TASK-12` a `TASK-15` nombraban **cuatro** entidades. El SRS v0.3 §8.1 identifica
**siete**. Las tres ausentes:

| Entidad | Por qué existe (SRS v0.3 §8.1) |
|---|---|
| `elementos_rastreados` | Varias líneas de OC viajan en un mismo buque, y una línea puede cambiar de nave por transbordo. Desacopla el identificador de rastreo del pedido. |
| `proveedores` | Normaliza el proveedor, hoy texto libre en el pedido. |
| `materiales` | Normaliza el material, hoy código y descripción concatenados. |

`elementos_rastreados` no es un detalle: sostiene `US-30` (transbordo) y ya
aparece nombrada en el criterio de aceptación de `TASK-02`
(`elementos_rastreados.posicion_actual`). Sin ella, `TASK-01` falla su propio
criterio, que exige *«las siete entidades de la sección 8.1 del SRS»*.

- **`TASK-15`** se amplió: ahora modela `usuarios`, `elementos_rastreados`, `proveedores` y `materiales`, y consolida el ER. **4 h → 10 h.**
- **`TASK-24`** (nueva, 4 h): diccionario de esas tres entidades.

### 2.2 `historial_tracking` colgaba de la entidad equivocada — `TASK-14` corregida

El criterio decía 1:N con `pedidos_transito`; el SRS v0.3 dice «por elemento
rastreado». Con la versión vieja, cinco líneas de OC en un mismo buque duplican
cinco veces cada posición recibida y un transbordo parte el trayecto.
**Ahora el historial cuelga de `elementos_rastreados`.**

### 2.3 `GEOGRAPHY`, no `geometry` — `TASK-14` corregida

`TASK-14` pedía `geometry`, `TASK-02` pedía `geometry(Point,4326)` y
`docs/data-model.md` documenta `GEOGRAPHY`. Manda la convención ya implementada
en `backend/app/db/base.py`, que además es la que necesita la geocerca de
`US-11`: **`GEOGRAPHY(Point,4326)`**, para que `ST_Distance` devuelva metros.

---

## 3. Plan día por día

### Lunes 24 — Arranque y `pedidos_transito`

| h | Actividad |
|---|---|
| 1,0 | **Arranque de sprint.** Tablero al día con el backlog revisado. **Agendar hoy mismo**: la sesión de validación de `US-39` con Compras y Logística para la semana del 1–4 sep, y la revisión del ER consolidado con Greivin para el viernes 28. |
| 5,5 | **TASK-12** — `pedidos_transito`: atributos, PK, FK a `maestro_destinos` y a `elementos_rastreados`, e índices para las consultas del dashboard. |

> La sesión de `US-39` se agenda el día 1, no cuando el prototipo esté listo: es
> la única actividad del sprint que depende de la agenda de terceros y es además
> el criterio de aceptación de OE1. Si no se reserva ahora, se cae.

### Martes 25 — `maestro_destinos` y primer diccionario

| h | Actividad |
|---|---|
| 0,5 | Cierre de **TASK-12** ✅ |
| 4,0 | **TASK-13** — `maestro_destinos`: puerto/aeropuerto, país, coordenadas, vía y lead time (tipado en días, no nulo). Las coordenadas alimentan la geocerca de `US-11`; el lead time, la fecha proyectada de `US-09`. ✅ |
| 2,0 | **TASK-16** — diccionario de `pedidos_transito` ✅ |

### Miércoles 26 — `historial_tracking`, el día geoespacial

| h | Actividad |
|---|---|
| 2,0 | **TASK-17** — diccionario de `maestro_destinos` ✅ |
| 4,5 | **TASK-14** — `historial_tracking` con los criterios ya corregidos: FK a `elementos_rastreados`, `GEOGRAPHY(Point,4326)` y payload en `JSONB`. |

### Jueves 27 — Las tres entidades nuevas

| h | Actividad |
|---|---|
| 1,5 | Cierre de **TASK-14** ✅ |
| 5,0 | **TASK-15** — `elementos_rastreados` primero (es la de mayor impacto estructural: identificador externo MMSI/icao24, `posicion_actual`, soporte de transbordo), luego `proveedores` y `materiales`. |

### Viernes 28 — Consolidación y revisión con Greivin

| h | Actividad |
|---|---|
| 4,0 | **TASK-15** — `usuarios` (rol Compras/Logística/Planificación, sin AD ni SSO) y consolidación del ER de las siete entidades con sus cardinalidades. |
| 1,0 | **Revisión con Greivin** del ER consolidado (parte de la DoD). Llevar preparada la decisión abierta sobre autenticación, y la de `US-38` (ver §5). |
| 1,5 | Ajustes del feedback y reemplazo de `docs/data-model.md`, que hoy contiene el modelo *tentativo del anteproyecto* con siete entidades que **no son** las del SRS v0.3. **TASK-15** ✅ |

---

## 4. Qué queda entregado el viernes

**30 h de las 75 h del sprint**, en seis items cerrados:

| Item | h |
|---|---|
| `TASK-12` `pedidos_transito` | 6 |
| `TASK-13` `maestro_destinos` | 4 |
| `TASK-14` `historial_tracking` | 6 |
| `TASK-15` 4 entidades + ER consolidado | 10 |
| `TASK-16` diccionario `pedidos_transito` | 2 |
| `TASK-17` diccionario `maestro_destinos` | 2 |

Más: `docs/data-model.md` actualizado al modelo real, la decisión geoespacial
cerrada —que desbloquea `TASK-02`— y la sesión de `US-39` reservada en agenda.

**Pasa a la semana 2:** `TASK-18` (dicc. `historial_tracking`, 3 h) ·
`TASK-24` (dicc. de las 3 entidades nuevas, 4 h) · arquitectura `TASK-20/21/22`
(12 h) · wireframes `US-34/35/36` (14 h) · prototipo `US-38` (8 h) ·
validación `US-39` (4 h).

---

## 5. Decisiones y riesgos vivos esta semana

**El viernes se modela `usuarios`, y ahí aterriza la decisión abierta #2 del
backlog.** RNF-04 y RNF-05 exigen autenticación y perfiles diferenciados, pero
ningún RF los implementa; el SRS v0.3 justifica la entidad por *«la autenticación
y, sobre todo, la auditoría»*. La revisión con Greivin es el momento de cerrarlo:
o entra al alcance con RF propios y 20–25 h no presupuestadas, o se declara
fuera explícitamente. **No se asume ninguna de las dos por cuenta propia.**

**Segunda decisión para el viernes: la fidelidad de `US-38`.** Es la única
palanca que cierra parte del sobrecosto del sprint sin degradar un `Must` (ver
§6). Conviene resolverla el 28, no el 4 de septiembre.

**Plan B si el modelado se bloquea.** Si `TASK-12` o `TASK-13` quedan esperando
una definición de Greivin, el trabajo de reemplazo es `US-34` (wireframe del
dashboard, 6 h): es el único item del sprint que no depende del ER.

**Riesgo R6 (una sola persona) vigente.** No hay paralelización posible; lo que
se desborde esta semana arrastra a la semana 2, que ya está sobrecargada.

---

## 6. La semana 2 sigue sin caber

Tras la revisión, el Sprint 2 quedó en **75 h** (era 81 h) contra 65 h de
capacidad. La semana 1 absorbe 32,5 h y deja **45 h para la semana 2**, contra
32,5 h de capacidad: **12,5 h de exceso**.

Palancas disponibles, en orden de preferencia:

| Palanca | Ahorro | Costo |
|---|---|---|
| `US-38` con navegación mínima sobre wireframes estáticos en vez de prototipo Figma completo | 4 h | `US-39` se valida igual; se pierde fidelidad de interacción. **Decisión de Greivin.** |
| Mover `TASK-22` (vista de secuencia) al Sprint 3 | 4 h | Es `Must`, pero su consumidor natural es la implementación del Sprint 3, no OE1. |
| Correr `US-39` en la primera semana del Sprint 3 | 4 h | Retrasa el cierre formal de OE1; hay que avisar a los usuarios clave al agendar. |

Las tres juntas cierran las 12,5 h. **La decisión es de Greivin y el momento es
la revisión del viernes 28.**

Efecto ya absorbido en el Sprint 3: recibió `TASK-19` y `TASK-23` (+10 h), pero
`TASK-11` se verificó cumplida —el SRS v0.3 del repositorio satisface sus dos
criterios de aceptación— y sus 6 h no se cuentan. Sprint 3 queda en **70 h**.

---

## 7. Pendiente de mantenimiento

`backlog_trackin.csv` tiene 44 filas y **no contiene ningún item del Sprint 2**:
se generó antes del commit `60d4184`, que añadió el sprint solo al `.md`. Los
cambios de esta revisión no lo afectan, pero hoy el CSV no sirve para importar
el Sprint 2 a Jira. Regenerarlo es trabajo aparte, no incluido en esta semana.
