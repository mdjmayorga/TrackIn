# Revisión con el supervisor — modelo de datos y diccionario

**Fecha:** 25/08/2026 · **Participantes:** M. Mayorga, Greivin (supervisor de empresa)
**Insumos:** `docs/data-model.md`, `docs/data-dictionary.md`, `docs/backlog/backlog_trackin.md`
**Cubre la DoD:** «Revisión con supervisor (Greivin) cuando aplique» para `TASK-12` a `TASK-18` y `TASK-24`

> **Reunión celebrada el 25/08/2026. Las nueve decisiones quedaron tomadas** y
> están aplicadas a `data-model.md`, `data-dictionary.md` y `backlog_trackin.md`.
> Este archivo es el acta.

---

## Estado que conviene reportar de entrada

- Cerradas ocho tareas del Sprint 2: modelo de datos completo (`TASK-12` a
  `TASK-15`) y diccionario de seis tablas (`TASK-16`, `17`, `18`, `24`).
- Suman **37 h estimadas** y se ejecutaron en dos días. Las estimaciones del
  backlog parecen holgadas; conviene decirlo antes de discutir sobrecargas.
- Falta la arquitectura (`TASK-20`, `21`, `22`) y los prototipos.
- ~~Nada está aprobado todavía.~~ **Aprobado el 25/08**: con esta reunión, las ocho tareas cumplen la DoD.

---

# A. Decisiones que cambian alcance

## A1 · Transbordo: ¿se conserva el trayecto completo del pedido?

**Preguntar:** «Cuando un pedido cambia de barco por transbordo, ¿necesitás ver
el trayecto completo —el tramo del barco viejo y el del nuevo— o alcanza con ver
dónde está ahora?»

**Contexto:** RF-26 ya promete conservarlo. Pero el modelo actual apunta el
pedido a una sola nave: al reapuntarlo, el tramo anterior se pierde.

| Opción | Qué implica |
|---|---|
| **A — entidad asociativa** | Tabla que guarda pedido × nave × tramo con fechas. ~3 h. El ER pasa a 10 entidades |
| B — reconstruir desde la auditoría | Cero entidades nuevas, pero si alguien depura la auditoría el trayecto desaparece |
| C — aceptar la pérdida | El trayecto empieza en la nave actual |

**Recomiendo A.** RF-26 ya está aprobado y dice textualmente que el historial de
la nave anterior debe conservarse; B cumple de casualidad y se rompe solo. El
modelado ya está escrito, así que el costo real es menor a 3 h.

**Decisión:** El historial de la nave anterior debe conservarse. **Opción A**: entra la entidad asociativa.

## A2 · El esquema tiene diez tablas, no siete

**Preguntar:** «El SRS enumera siete entidades, pero su propio articulado exige
dos más que no están en esa lista. ¿Actualizamos el criterio de `TASK-01`?»

**Contexto:** no son invenciones del análisis:

- `auditoria_intervenciones` — RF-14 exige registrar usuario, fecha, valor
  anterior, valor nuevo y motivo de cada intervención. No hay dónde escribirlo.
- `parametros_sistema` — RN-05 y RN-11 citan literalmente «la tabla de
  mantenimiento de parámetros».
- `pedido_elemento_rastreado` — depende de A1.

**Recomiendo actualizar el criterio a diez entidades y reestimar `TASK-01` de
10 h a ~14 h.** Sin esas tablas, RF-14, RN-05 y RN-11 no se pueden cumplir; no
es una preferencia de diseño. Y `TASK-01` hoy fallaría su propio criterio de
aceptación.

**Ojo con el efecto:** el Sprint 3 pasa de 70 h a ~74 h contra 65 h de
capacidad. Ver C1.

**Decisión:** **Se actualiza el criterio de `TASK-01`** para incluir las diez entidades. Reestimada a 14 h.

## A3 · Autenticación: está comprometida y nadie la va a construir

**Preguntar:** «RNF-04 dice que el sistema tendrá autenticación con mecanismo
propio. No hay ningún RF que la especifique ni ninguna historia en el backlog
que la construya. Son 20–25 h. ¿De dónde salen, o la sacamos del SRS?»

**Contexto:** el SRS §9.1 dice que el sistema **no se despliega en producción
dentro de la práctica**, así que durante la práctica no hay exposición real.

| Opción | Qué implica |
|---|---|
| **Declararla fuera de la práctica** | Cambio documentado en el SRS (v0.4): la autenticación queda como trabajo previo al despliegue, a cargo del Centro de Competencias |
| Construirla ahora | 20–25 h que hoy no existen. Saldrían de las cuatro historias `Could` (30 h), que el propio backlog llama «la válvula de escape» |
| Dejarlo como está | Un requisito comprometido y no entregado. Es la peor de las tres |

**Recomiendo declararla fuera de la práctica y documentarlo.** La entidad
`usuarios` se construye igual porque RF-14 la necesita para la auditoría, así
que la puerta queda abierta sin gastar las horas. Lo que no se puede es dejar
RNF-04 escrito y no hacerlo.

**Decisión:** **Fuera del alcance de la práctica**, documentado en el SRS. La entidad `usuarios` se construye igual.

---

# B. Decisiones de diseño

## B1 · ¿El estado del pedido es una cosa o dos?

**Preguntar:** «En el dashboard, ¿querés ver a la vez *dónde está* la carga —en
tránsito, en aduana— y *si va a llegar tarde*? Con una sola columna hay que
elegir uno de los dos.»

**Contexto:** el SRS §7.2 ya los separa: RN-02 a RN-06 describen dónde está,
RN-07 a RN-09 si llega a tiempo. Un pedido en tránsito que llegará tarde es las
dos cosas.

**Recomiendo dos columnas** más una tercera derivada para el semáforo. Logística
pregunta una cosa y Compras la otra; con una sola columna, uno de los dos pierde
su respuesta. No cuesta horas extra: es el mismo trabajo en `US-10` y `US-24`.

**Decisión:** **Dos columnas más una tercera derivada.**

## B2 · Arribo aéreo: ¿geocerca o «en tierra»?

**Preguntar:** «Para barcos detectamos la llegada por cercanía al puerto. Para
aviones, 50 km alrededor del aeropuerto agarra cualquier avión que sobrevuele
Costa Rica. ¿Usamos para aire la señal de "en tierra" que ya da la fuente?»

**Contexto:** los spikes ya usaron radios distintos —50 km para Moín, 27 km para
los aeropuertos— precisamente para no capturar tráfico ajeno.

**Recomiendo `on_ground` para aéreo y geocerca para marítimo.** Es más preciso y
más simple: `US-11` deja de forzar la misma regla sobre dos vías que no se
parecen.

**Decisión:** **`on_ground` para aéreo, geocerca para marítimo.**

## B3 · Volumen del historial: ~20 GB al año

**Preguntar:** «Guardar cada lectura son unos 25 millones de registros y 20 GB
al año, para un sistema que muestra 200 pedidos. ¿Ponemos desde el Sprint 3 un
intervalo mínimo entre lecturas guardadas?»

**Contexto:** medido con los spikes — AIS reporta cada 62 s por buque, ADS-B se
consulta cada 31 s.

**Recomiendo el intervalo mínimo configurable en `US-04`, y dejar `TASK-10`
donde está.** Es un parámetro, no una historia: resuelve el 90 % del problema
sin agregar horas a un sprint sobrecargado. La política de purga puede esperar
al Sprint 7.

**Decisión:** **Intervalo mínimo configurable en `US-04`**; `TASK-10` se queda en el Sprint 7.

## B4 · `tracking_interno`: ¿lo define Gutis o lo genera TrackIn?

**Preguntar:** «¿Ya existe en Gutis un formato de código interno de seguimiento,
o lo genera TrackIn?»

**Recomiendo que lo genere TrackIn**, salvo que ya exista uno en uso. Es
consumo de `TASK-03` en el Sprint 3.

**Decisión:** **Lo genera TrackIn.**

---

# C. Lo que hay que resolver aunque no sea de modelo

## C1 · El Sprint 3 no cabe

Con A2 queda en ~74 h contra 65 h de capacidad. Y el Sprint 2, en 75 h con la
segunda semana en 45 h contra 32,5 h.

**Preguntar:** «¿Bajamos la fidelidad del prototipo de `US-38`, o corremos la
validación con usuarios a la primera semana del Sprint 3?»

**Recomiendo esperar dos días antes de recortar.** Ocho tareas estimadas en 37 h
se cerraron en dos; si el resto del sprint mantiene ese ritmo, la sobrecarga es
de la estimación y no del alcance. Conviene decidirlo el lunes 31 con datos, no
hoy con proyecciones.

**Decisión:** **Se deja el sprint como está.** El ritmo actual demuestra que la estimación es mayor que la realidad.

## C2 · Fecha de la especificación de SAP (riesgo R2)

**Preguntar:** «¿Hay fecha para la especificación del servicio de SAP?»

Es el riesgo más caro del proyecto: bloquea 26 h y, sobre todo, **no hay ninguna
otra forma de que entren pedidos al sistema**. El SRS lo daba por recibido antes
del Sprint 3, que arranca el 7 de septiembre.

Si no hay fecha, hay que decidir si se agrega un RF de carga manual — y eso es
un cambio de alcance que no se puede asumir en silencio.

**Decisión:** 🔴 **No hay fecha presupuestada. El proceso está varado.**

---

# D. Datos que hay que pedir (no son decisiones)

| Dato | Quién | Para cuándo |
|---|---|---|
| Lead time real de cada destino | Logística | Antes del Sprint 4 |
| Lista definitiva de destinos que opera Gutis | Logística | Antes del Sprint 3 |
| Código UN/LOCODE oficial de los puertos | Logística | Antes del Sprint 3 |
| Umbral de velocidad para dar por arribado un buque | Logística | Antes del Sprint 4 |
| Velocidad mínima para estimar ETA | Logística | Antes del Sprint 4 |
| ¿Hay un cuarto perfil de administrador, o alcanza con Compras/Logística/Planificación? | Greivin | Antes del Sprint 5 |
| Agendar la sesión de validación de prototipos (`US-39`) | Compras y Logística | Semana del 1–4 sep |

---

# E. Para informar, no para preguntar

Decisiones técnicas ya tomadas. Mencionar por transparencia; no requieren su tiempo.

- **Clave foránea compuesta destino↔vía**: la base impide que un pedido marítimo
  apunte a un aeropuerto. Costo despreciable.
- **Claves primarias sustitutas** en todas las tablas, con la clave natural como
  `UNIQUE`. Protege ante el formato desconocido de SAP.
- **`GEOGRAPHY` y no `GEOMETRY`** para las coordenadas: las distancias salen en
  metros, que es lo que necesita la regla de los 50 km.
- **El historial cuelga de la nave, no del pedido.** Evita multiplicar por cinco
  cada lectura cuando cinco líneas viajan en el mismo barco.
- **Se corrigieron tres errores del SRS §8**: un tipo de dato incompatible entre
  tablas, latitud y longitud sueltas donde el propio §8.6 pide geometría, y
  `tramo` en una tabla donde no puede tener valor correcto.


---

# F. Pendientes que deja la reunión

| # | Pendiente | Quien | Para cuando |
|---|---|---|---|
| 1 | ~~**Emitir el SRS v0.4**~~ ✅ **`TASK-25`, 8 h, Sprint 2** | M. Mayorga | Cierre del Sprint 2 |
| 2 | ~~Crear la tarea de diccionario de las tres tablas nuevas~~ ✅ **`TASK-26`, 3 h, Sprint 2** | M. Mayorga | Hecho el 25/08 |
| 3 | Plantear formalmente el RF de carga manual si SAP no llega | Greivin | Antes del cierre del Sprint 3 |
| 4 | Lead times, lista de destinos y UN/LOCODE | Logística | Antes del Sprint 3 |
| 5 | Umbral de velocidad de arribo y velocidad mínima para ETA | Logística | Antes del Sprint 4 |
| 6 | ¿Hace falta un cuarto perfil de administrador? | Greivin | Antes del Sprint 5 |
| 7 | ~~Agendar la sesión de validación de prototipos (`US-39`)~~ ✅ **Agendada para el vie 4 de septiembre** | Compras y Logística | Hecho |

> Los puntos 4 a 7 **no se registraron como resueltos en esta reunión**. Si se
> trataron y hay respuesta, conviene anotarla aquí; si no, siguen abiertos.
