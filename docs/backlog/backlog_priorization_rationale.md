# Justificación de la priorización del Product Backlog

**Proyecto:** TrackIn — Práctica Profesional, TEC · **Tarea:** TG-18
**Fecha:** 20 de agosto de 2026
**Insumos:** SRS v0.2 (14/08/2026), spikes técnicos TG-10 (AISStream) y TG-11 (OpenSky)

Este documento explica *por qué* el backlog quedó como quedó. La lista de
historias vive en [`backlog_trackin.md`](backlog_trackin.md); acá está el
razonamiento, los riesgos y lo que se asumió.

---

## 1. Cómo se derivó el backlog

Se recorrieron los **27 requerimientos funcionales** del SRS v0.2 y se
convirtieron en 44 elementos: 33 historias de usuario y 11 tareas técnicas.

Tres criterios gobernaron la conversión:

1. **Un RF puede generar más de una historia** cuando su implementación excede
   los tres días. RF-07 (consumo de OpenSky) se partió en US-05 —autenticación
   y consulta— y US-06 —resolución del `icao24` por tramo—, porque el spike
   TG-11 demostró que el vínculo aeronave↔vuelo es un problema propio y no un
   detalle del cliente HTTP.
2. **El trabajo sin cara de usuario es `Task`, no `Story`.** El esquema de base
   de datos, la habilitación de PostGIS, el andamiaje del frontend y los
   manuales no se redactan como «Como usuario, quiero…» porque nadie los pide
   como funcionalidad: son condición para que las demás existan.
3. **Nada que no esté en el SRS o en los spikes entró al backlog.** Durante la
   derivación aparecieron dos candidatos tentadores —exportación de la grilla a
   Excel y notificaciones por correo ante cambio de estado— que **se
   descartaron**: el propio `docs/srs/README.md` los lista como preguntas
   abiertas de las entrevistas con usuarios clave, no como requerimientos. Si
   se confirman, entran como RF nuevos con su cambio de alcance.

---

## 2. Peso de cada épica y por qué

| Épica | Items | Horas | % del esfuerzo |
|---|---|---|---|
| **OE2-Backend** | 21 | 192 h | **56%** |
| **OE3-Frontend** | 13 | 106 h | 31% |
| **OE4-Persistencia** | 9 | 68 h | 20% |
| **OE1-Análisis** | 1 | 6 h | 2% |

*(Los porcentajes suman más de 100 porque se calculan sobre las 340 h
calendarizadas, sin contar las 32 h bloqueadas.)*

**OE2 se lleva más de la mitad y es correcto.** El valor de TrackIn no está en
la interfaz: está en cruzar dos fuentes externas y derivar un estado que hoy no
existe. Ese cruce es backend. Además los spikes demostraron que las dos
integraciones son sustancialmente más complejas de lo que el SRS sugería —
reconexión con backoff, watchdog por ping/pong, resolución de identificadores
por tramo, normalización de `states: null`— y esa complejidad se pagó en
estimación, no se escondió.

**OE1 aparece con un solo elemento** porque el grueso del análisis se consumió
en los Sprints 1 y 2. Lo único que queda vivo es TASK-11, la actualización del
SRS con los hallazgos de los spikes, que es entregable de esta misma tarea.

**OE4 parece pequeño en horas pero es el que va primero.** TASK-01 y TASK-02
abren el Sprint 3 porque sin esquema y sin PostGIS no hay dónde escribir una
posición ni cómo calcular una distancia.

---

## 3. Criterio Must / Should / Could

### La regla que se aplicó

**Must** es lo que está en la cadena crítica que produce el producto mínimo
demostrable: *un pedido entra al sistema, se le asocia un identificador, una
API externa devuelve su posición, el motor calcula su estado, y el usuario lo
ve en una grilla y en un mapa con su color*. Si se corta cualquier eslabón de
esa cadena, no hay producto que enseñar.

**Should** es lo que el sistema necesita para operar de verdad en la empresa,
pero cuya ausencia **no impide demostrar** que la cadena funciona: confirmación
manual de desembarco, recepción en planta, auditoría, transbordo, próximos
arribos.

**Could** es lo que el propio SRS marcó como prioridad Media y que además puede
posponerse sin dejar un hueco funcional visible.

### Dónde el backlog se aparta del SRS, y por qué

El SRS marca **23 de 27 RF como prioridad Alta**. Traducir Alta→Must
mecánicamente habría dado un backlog con 85% de Must, lo que vacía de sentido
el ejercicio: si todo es prioritario, nada lo es. MoSCoW pregunta algo distinto
que la prioridad del SRS — pregunta *qué se cae si esto no está*.

Cinco requerimientos de prioridad **Alta** en el SRS quedaron como **Should**:

| RF | Título | Por qué baja a Should |
|---|---|---|
| RF-13 | Confirmación manual de desembarco | El sistema calcula estados sin ella; corrige al automatismo, no lo habilita. Además la geocerca de RN-05 revisada cubre ahora el caso principal. |
| RF-25 | Recepción en planta | Cierra el ciclo de vida, pero un pedido sin cerrar sigue siendo visible y correcto en el dashboard. |
| RF-26 | Actualización de nave por transbordo | Frecuente en la operación real, pero es mantenimiento de dato: sin ella el pedido simplemente deja de recibir lecturas. |
| RF-27 | Vista de próximos arribos | Es una consulta ordenada sobre datos que la grilla ya muestra. Valor alto, criticidad baja. |
| RF-14 | Auditoría de intervenciones manuales | Depende de que existan intervenciones manuales, que son todas Should. |

Y uno de prioridad **Media** subió de facto a **Must**: **RF-19 (filtros)**. El
SRS lo marca Alta en realidad, pero conviene explicitarlo: con 200 pedidos
activos —el volumen de referencia de RNF-01— una grilla sin filtros es
inutilizable. No es una comodidad, es la condición para que la grilla sirva.

### Distribución resultante frente a la esperada

| | Objetivo | Real | Desvío |
|---|---|---|---|
| Must | 50–60% | **68,2%** | +8 pts |
| Should | 25–30% | 22,7% | −2 pts |
| Could | 10–15% | 9,1% | −1 pt |

**El backlog quedó más cargado de Must de lo previsto, y no se forzó a
cuadrar.** La causa es estructural: el SRS v0.2 es un documento ya depurado —el
levantamiento con Greivin, Logística, Compras y Control de Calidad cerró once
notas pendientes y eliminó lo accesorio— así que casi todo lo que sobrevivió
es núcleo. Bajar más requerimientos a Should para alcanzar el 60% habría
significado degradar arbitrariamente cosas que sí son condición del producto.
Se prefirió reportar el desvío y explicarlo.

---

## 4. Dependencias entre historias

La cadena crítica, en orden estricto. Cada eslabón necesita el anterior:

```
TASK-01 (esquema) ─┬─> TASK-02 (PostGIS) ─> US-08 (ETA derivada) ─> US-09 (fecha proyectada)
                   │                                                      │
                   ├─> TASK-03 (ingesta semilla) ─> US-01 (identificador)  │
                   │                                     │                 v
                   │                                     ├─> US-02 (AIS) ──┴─> US-10 (estado)
                   │                                     └─> US-05 (OpenSky) ──> US-11 (geocerca)
                   │                                              │                    │
                   └─> US-04 (historial) <────────────────────────┘                    v
                                                                                  US-12 (recálculo)
                                                                                       │
US-13 (maestro destinos) ──────────────────────────────────────────────────────────────┤
                                                                                       v
                                                                            US-16 (API REST)
                                                                                       │
                                              TASK-05 (andamiaje) ──> US-19..US-26 (frontend)
```

Dependencias que conviene tener presentes porque no son obvias:

- **US-09 depende de US-13**, no solo de US-08. Sin lead time en el maestro de
  destinos no hay fecha proyectada, y US-13 está en el Sprint 5 mientras US-09
  está en el 4. **Mitigación:** el Sprint 4 usa lead times de los datos semilla
  de TASK-03; el CRUD de US-13 solo cambia quién los edita, no la fórmula.
- **US-11 (geocerca) depende de TASK-02**, porque el cálculo de distancia se
  apoya en `ST_Distance` sobre geografía. Si PostGIS se retrasa, la geocerca se
  retrasa.
- **US-24 (semáforo) depende de US-10**, no al revés: el color es consecuencia
  del estado calculado y no puede especificarse antes.
- **Todo el frontend depende de US-16 (API REST)**, que cierra el Sprint 5. Por
  eso el Sprint 6 arranca con TASK-05, que no depende de nada del backend.

---

## 5. Riesgos identificados

Ordenados por impacto sobre el cronograma.

### R1 — La cuenta de AISStream no está entregando datos 🔴

Desde el 19/08/2026 la clave de API es aceptada por el servidor —no la rechaza,
no cierra la conexión— pero no llega un solo mensaje. Se descartó que sea la red
corporativa: no hay inspección TLS, el handshake WebSocket funciona y un echo
público responde. La hipótesis es un tope del plan gratuito.

**Impacto:** bloquea la verificación de **US-02**, que es 16 h del Sprint 3.
**Mitigación:** el módulo se desarrolla y prueba contra el dataset crudo ya
capturado (`02_caribbean_raw_personal.jsonl`, 161 mensajes reales). La
integración en vivo se valida cuando la cuenta se restablezca.
**Acción pendiente:** revisar el consumo en aisstream.io y probar desde otra red.

### R2 — La especificación del servicio de SAP no tiene fecha 🔴

El SRS §2.5 la daba por recibida «antes del inicio del Sprint 3». Hoy está «en
veremos». v0.2 eliminó la carga por Excel, así que **RF-01 es la única vía de
entrada de pedidos que contempla el SRS**.

**Impacto:** 26 h bloqueadas (US-31, US-32), y algo más grave: sin SAP no hay
ninguna función de usuario que meta pedidos al sistema.
**Mitigación:** TASK-03 introduce un adaptador de ingesta con datos semilla, que
resuelve desarrollo y demostración sin ser una función de usuario.
**Decisión pendiente de Greivin:** si SAP no llega para el Sprint 5, hace falta
un RF de carga manual. **Es un cambio de alcance y no se asume acá.**

### R3 — La geocerca de 50 km puede producir falsos positivos 🟠

Regla definida por Greivin: buque a menos de 50 km del puerto ⇒ arribado. Moín
está a unos 296 km de la entrada caribe del Canal de Panamá, y por esa zona
pasa tráfico en tránsito que puede entrar en el radio sin dirigirse a Costa Rica.

**Mitigación implementada en US-11:** el arribo exige además velocidad por
debajo de un umbral configurable, y ambos parámetros viven en la tabla de
parámetros para poder ajustarlos sin desplegar código. El arribo así inferido
se marca como **inferido**, distinguible de uno confirmado por la fuente.

### R4 — La ETA derivada es una aproximación, no una medición 🟠

Regla definida por Greivin: estimar la ETA desde la posición y la velocidad.
Para el tramo Caribe→Moín es defendible porque es mar abierto, pero la fórmula
ingenua falla en dos casos: velocidad cero —buque fondeado, ETA infinita— y
rutas con tierra de por medio, donde la línea recta subestima la distancia real.

**Mitigación en US-08:** velocidad mínima configurable, por debajo de la cual no
se estima y el pedido se marca «ETA no estimable»; y el cálculo expone
distancia, velocidad y hora usadas, para poder auditarlo.

### R5 — Sin cobertura ADS-B en Liberia (MRLB) 🟡

Tres muestras independientes en franjas horarias distintas dieron cero
aeronaves en el radio de Liberia. **Mitigación:** el diseño no depende de MRLB;
la detección de aterrizaje se validó contra MROC (Juan Santamaría), donde sí
hay cobertura de superficie y aproximación.

### R6 — Riesgo de una sola persona 🟡

Todo el backlog lo ejecuta una persona. No hay paralelización posible: si un
sprint se desborda, arrastra a los siguientes. **Mitigación:** las 4 historias
`Could` (30 h) son la válvula de escape, y las semanas 17–18 quedan como buffer.

---

## 6. Asunciones hechas

Se listan porque, si alguna es falsa, el backlog cambia.

1. **Capacidad de 65 h por sprint de dos semanas.** Es el punto medio del rango
   60–70 indicado. Con 66 h, el Sprint 3 excede en 1 h, lo que está dentro del
   ruido de la estimación.
2. **El umbral de 48 h de RN-11 y la eliminación del lead time crítico de RN-12
   están cerrados.** El SRS v0.2 lo afirma explícitamente. Ninguna historia
   queda bloqueada esperando esa definición.
3. **Los datos semilla de TASK-03 son representativos.** Se asume que pueden
   construirse con casos marítimo, aéreo y sin identificador, conforme a la
   estructura tentativa del Anexo B. Si el contrato real de SAP difiere, US-31
   y US-32 absorben el retrabajo, no el resto del sistema.
4. **La demostración del 25 de septiembre se hace sobre datos semilla.** El
   Informe de Avance 1 cubre hasta el cierre del Sprint 3, que ya no incluye
   SAP.
5. **Las historias del frontend asumen que la API REST de US-16 está estable.**
   Si el Sprint 5 se corre, el Sprint 6 arranca con TASK-05 igual, que no
   depende del backend.
6. **La cobertura del 70% de RNF-18 se mide sobre las reglas de cálculo**, que
   es lo que el SRS exige, no sobre la totalidad del código.

---

## 7. Requerimientos no funcionales: cómo se trataron

Los 23 RNF **no generaron historias propias**, salvo tres excepciones. La razón
es que un RNF describe *cómo* debe comportarse el sistema, no *qué* hace, así
que su lugar natural es el criterio de aceptación de la historia que lo ejerce.

| RNF | Dónde se verifica |
|---|---|
| RNF-01, RNF-02 (rendimiento) | Criterios de US-19 y US-21 |
| RNF-06 (auditoría) | US-15 |
| RNF-07, RNF-15 (config fuera del código) | US-17 |
| RNF-08 (semáforo) | US-24, con historia propia por ser transversal |
| RNF-12, RNF-14 (degradación, aislamiento de fallos) | US-03 y US-12 |
| RNF-13 (historial íntegro) | US-04 |
| RNF-17 (OpenAPI) | TASK-04, con tarea propia |
| RNF-18 (pruebas de reglas) | TASK-06 y la DoD de todo el backlog |
| RNF-11 (pantalla permanente) | US-33, `Could` y bloqueada |
| RNF-22 (crecimiento del historial) | TASK-10, `Could` |
| RNF-04, RNF-05 (autenticación y perfiles) | **Sin historia — ver gap abajo** |

### ⚠️ Un hueco que no se rellenó

**RNF-04 y RNF-05 exigen autenticación y perfiles diferenciados, y ningún RF
los implementa.** El SRS pide que el acceso requiera autenticación y que los
permisos distingan perfiles, pero la sección 4 no tiene un requerimiento
funcional de gestión de usuarios, login o asignación de roles. La entidad
`usuarios` existe en el modelo de datos (§8.1) justificada por la auditoría de
RF-14, no por el control de acceso.

No se inventó la historia. **Es una decisión de Greivin** si la autenticación
entra al alcance —y en ese caso hacen falta RF nuevos, más unas 20–25 h que hoy
no están presupuestadas— o si se declara explícitamente fuera, como ya se hizo
con SSO en §1.2.2.

---

## 8. Resumen de decisiones que quedan abiertas

| # | Decisión | Quién | Bloquea |
|---|---|---|---|
| 1 | Si SAP no llega para el Sprint 5, ¿se agrega un RF de carga manual? | Greivin | US-31, US-32 y la entrada de datos del sistema |
| 2 | ¿La autenticación (RNF-04/05) entra al alcance con RF propios? | Greivin | 20–25 h no presupuestadas |
| 3 | ¿Se aprueba la compra de una fuente AIS con cobertura de Moín? | Compras / Greivin | Precisión de US-11; hoy la geocerca depende de una fuente que no ve Moín |
| 4 | Resolución de la pantalla de visualización permanente | Usuarios clave | US-33 |
| 5 | ¿Exportación a Excel y notificaciones son requerimientos? | Usuarios clave | RF nuevos, hoy fuera del backlog |
