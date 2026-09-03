# Product Backlog - TrackIn (TG-18)

Derivado del SRS v0.3 y de los spikes tecnicos TG-10 (AISStream) y TG-11 (OpenSky). Priorizado con MoSCoW.

**Generado:** 20 de agosto de 2026 · **Revisado:** 24 de agosto de 2026 (arranque del Sprint 2) · **Congelado:** 3 de septiembre de 2026 (cierre del Sprint 2) · **Ejecutor:** 1 persona a tiempo completo

> **Backlog congelado.** Incorpora los hallazgos de la reunión con Logística del 03/09 y la
> entrega del Z-tracking. A partir de aquí solo debería cambiar por la resolución de
> `TASK-28`, que está explícitamente planteada como bifurcación (Plan A / Plan B).

> Este archivo se genera desde un script. La justificacion de la priorizacion vive en `backlog_priorization_rationale.md`.

## Definition of Done (aplica a todo el backlog)

- Codigo con pruebas unitarias (cobertura minima 70%)
- Documentacion tecnica actualizada
- Revision con supervisor (Greivin) cuando aplique
- Merge a rama principal sin errores de CI

---

## Tabla resumen

| ID | Titulo | Tipo | OE | MoSCoW | Sprint | Horas | Origen |
|---|---|---|---|---|---|---|---|
| `TASK-12` | Modelar la entidad pedidos_transito en el diagrama ER ✅ | Task | OE1 | **Must** | Sprint 2 | 6h | Diseño OE1 / modelo de datos |
| `TASK-13` | Modelar la entidad maestro_destinos ✅ | Task | OE1 | **Must** | Sprint 2 | 4h | Diseño OE1 / modelo de datos |
| `TASK-14` | Modelar la entidad historial_tracking (geoespacial) ✅ | Task | OE1 | **Must** | Sprint 2 | 6h | Diseño OE1 / modelo de datos |
| `TASK-15` | Modelar usuarios, elementos_rastreados, proveedores y materiales, y consolidar el ER ✅ | Task | OE1 | **Must** | Sprint 2 | 10h | Diseño OE1 / modelo de datos (SRS v0.3 §8.1) |
| `TASK-16` | Diccionario de datos: pedidos_transito ✅ | Task | OE1 | **Must** | Sprint 2 | 2h | Diseño OE1 / diccionario de datos |
| `TASK-17` | Diccionario de datos: maestro_destinos ✅ | Task | OE1 | **Must** | Sprint 2 | 2h | Diseño OE1 / diccionario de datos |
| `TASK-18` | Diccionario de datos: historial_tracking ✅ | Task | OE1 | **Must** | Sprint 2 | 3h | Diseño OE1 / diccionario de datos |
| `TASK-24` | Diccionario de datos: elementos_rastreados, proveedores y materiales ✅ | Task | OE1 | **Must** | Sprint 2 | 4h | Diseño OE1 / diccionario de datos (SRS v0.3 §8.1) |
| `TASK-26` | Diccionario de datos: auditoria_intervenciones, parametros_sistema y pedido_elemento_rastreado ✅ | Task | OE1 | **Must** | Sprint 2 | 3h | Revision con el supervisor, 25/08/2026 |
| `TASK-25` | Emitir el SRS v0.4 con las decisiones de la revision del 25/08 y de la reunion del 03/09 ✅ | Task | OE1 | **Must** | Sprint 2 | 8h | Revision con el supervisor, 25/08/2026 |
| `TASK-20` | Arquitectura: vista de componentes ✅ | Task | OE1 | **Must** | Sprint 2 | 6h | Diseño OE1 / arquitectura |
| `TASK-21` | Arquitectura: vista de despliegue (instalacion nativa) ✅ | Task | OE1 | **Must** | Sprint 2 | 2h | Diseño OE1 / arquitectura (decision: sin Docker) |
| `TASK-22` | Arquitectura: vista de secuencia (flujo de tracking) ✅ | Task | OE1 | **Must** | Sprint 2 | 4h | Diseño OE1 / arquitectura |
| `US-34` | Wireframe del dashboard principal (grilla, filtros y KPIs) ✅ | Story | OE1 | **Must** | Sprint 2 | 6h | Diseño OE1 / prototipo |
| `US-35` | Wireframe del mapa marítimo ✅ | Story | OE1 | **Must** | Sprint 2 | 4h | Diseño OE1 / prototipo |
| `US-36` | Wireframe del mapa aéreo ✅ | Story | OE1 | **Must** | Sprint 2 | 4h | Diseño OE1 / prototipo |
| `US-37` | Wireframe del detalle de pedido ✅ | Story | OE1 | **Should** | Sprint 2 | 4h | Diseño OE1 / prototipo |
| `US-41` | Wireframe del login ✅ | Story | OE1 | **Must** | Sprint 2 | 3h | Reunión con Logística, 03/09/2026 (autenticación entra al alcance) |
| `US-38` | Prototipo interactivo navegable en Figma ✅ | Story | OE1 | **Must** | Sprint 2 | 8h | Diseño OE1 / prototipo |
| `US-39` | Validación de prototipos con usuarios clave ✅ | Story | OE1 | **Must** | Sprint 2 | 4h | Diseño OE1 / criterio de aceptación de OE1 |
| `TASK-01` | Esquema de base de datos y migraciones Alembic | Task | OE4 | **Must** | Sprint 3 | 14h | SRS 8.1-8.5 |
| `TASK-02` | Habilitar PostGIS y columna geometrica WGS 84 | Task | OE4 | **Must** | Sprint 3 | 4h | SRS 8.6 / RNF-20 |
| `TASK-03` | Adaptador de ingesta de pedidos con datos semilla | Task | OE2 | **Must** | Sprint 3 | 8h | Habilitador de RF-01 |
| `TASK-27` | Spike: suscripcion por MMSI y limite del plan gratuito de AISStream 🔀 | Task | OE2 | **Must** | Sprint 3 | 4h | Riesgo R1 |
| `TASK-28` | Spike: cobertura de container tracking de pago (Vizion/Terminal49/ShipsGo) en Moín y aéreo en SJO | Task | OE2 | **Must** | Sprint 3 | 6h | Reunión Logística 03/09 (revierte decisión abierta #3 / B1) / Riesgo R1 |
| `TASK-29` | Modelar maestro_paises y normalizar país, vía, incoterm y temperatura en la ingesta | Task | OE1 | **Must** | Sprint 3 | 6h | Muestra Z-tracking 03/09 (texto libre sucio) / RF-02 |
| `TASK-30` | Contrato de captura de la referencia de embarque (contenedor, BL, booking, MAWB) | Task | OE1 | **Must** | Sprint 3 | 3h | Reunión Logística 03/09 (prerrequisito de todo rastreo) |
| `US-01` | Asociar un identificador de rastreo externo a un pedido | Story | OE2 | **Must** | Sprint 3 | 6h | RF-03 |
| `US-02` | Consumir posiciones AIS desde AISStream por WebSocket 🔀 | Story | OE2 | **Must** | Sprint 3 | 16h | RF-06 |
| `US-03` | Tolerar la caida de una API externa sin degradar el dashboard | Story | OE2 | **Must** | Sprint 3 | 8h | RF-09 / RNF-12 |
| `US-04` | Registrar el historial de posiciones con el payload original | Story | OE4 | **Must** | Sprint 3 | 8h | RF-21 / RNF-13 |
| `TASK-19` | Diccionario de datos: usuarios | Task | OE1 | **Should** | Sprint 3 | 2h | Diseño OE1 / diccionario de datos |
| `TASK-23` | Consolidar el material de OE1 para el Informe 1 | Task | OE1 | **Must** | Sprint 3 | 8h | Hito Informe 1 (25/09/2026) |
| `US-05` | Consumir posiciones ADS-B desde OpenSky con OAuth2 | Story | OE2 | **Must** | Sprint 4 | 10h | RF-07 |
| `US-06` | Resolver el icao24 de un vuelo como vinculo temporal del tramo | Story | OE2 | **Must** | Sprint 4 | 8h | RF-07 / spike TG-11 |
| `US-07` | Planificar las consultas periodicas con frecuencia parametrizable | Story | OE2 | **Must** | Sprint 4 | 8h | RF-08 (reformulado) |
| `US-08` | Estimar la ETA a partir de la posicion y la velocidad del buque 🔀 | Story | OE2 | **Must** | Sprint 4 | 12h | RN-16 (nueva, Greivin) |
| `US-09` | Calcular la fecha proyectada de disponibilidad | Story | OE2 | **Must** | Sprint 4 | 6h | RF-10 / RN-01 |
| `US-10` | Determinar el estado logistico bajo el esquema de semaforo | Story | OE2 | **Must** | Sprint 4 | 12h | RF-11 / RN-02 a RN-11 |
| `US-11` | Inferir el arribo a destino por geocerca de proximidad 🔀 | Story | OE2 | **Must** | Sprint 4 | 8h | RN-05 (revisada, Greivin) |
| `US-31` | Cargar los pedidos en transito desde el archivo Z-tracking | Story | OE2 | **Must** | Sprint 4 | 14h | RF-31 carga manual (03/09) / RF-01 / CU-01 |
| `US-32` | Validar y normalizar los datos del Z-tracking antes de persistirlos | Story | OE2 | **Must** | Sprint 4 | 10h | RF-02 / RN-17 |
| `US-45` | Integrar la fuente comercial de rastreo marítimo por contenedor o BL 🔀 | Story | OE2 | **Must** | Sprint 4 | 12h | Plan A de `TASK-28` (03/09) |
| `US-46` | Integrar el rastreo aéreo por guía aérea (MAWB) 🔀 | Story | OE2 | **Must** | Sprint 4 | 10h | Plan A de `TASK-28` (03/09) |
| `US-12` | Recalcular fecha y estado ante cualquier cambio de insumo | Story | OE2 | **Must** | Sprint 5 | 8h | RF-12 |
| `US-13` | Mantener el maestro de destinos y sus lead times | Story | OE2 | **Must** | Sprint 5 | 10h | RF-23 / CU-06 |
| `US-14` | Confirmar manualmente el desembarco de un pedido | Story | OE2 | **Must** | Sprint 5 | 8h | RF-13 / CU-05 |
| `US-15` | Auditar toda intervencion manual sobre un pedido | Story | OE4 | **Should** | Sprint 5 | 8h | RF-14 / RNF-06 |
| `US-16` | Exponer los pedidos y su detalle por API REST | Story | OE2 | **Must** | Sprint 5 | 10h | RF-04 / RF-05 (backend) |
| `US-17` | Mantener credenciales, umbrales y frecuencias fuera del codigo | Story | OE2 | **Should** | Sprint 5 | 6h | RF-24 / RNF-07 / RNF-15 |
| `US-18` | Registrar la recepcion en planta y cerrar el pedido | Story | OE2 | **Should** | Sprint 5 | 8h | RF-25 / RN-10 |
| `US-40` | Ajustar manualmente la fecha proyectada de un pedido | Story | OE2 | **Should** | Sprint 5 | 4h | RN-01 (ajuste manual) |
| `US-42` | Autenticar usuarios con login, sesión y tres roles más Administrador | Story | OE3 | **Must** | Sprint 5 | 12h | Reunión Logística 03/09 / RNF-05 (ampliado) |
| `TASK-04` | Publicar la documentacion OpenAPI del backend | Task | OE2 | **Should** | Sprint 5 | 4h | RNF-17 |
| `TASK-05` | Andamiaje del frontend React con TypeScript, Vite y Tailwind | Task | OE3 | **Must** | Sprint 6 | 6h | RNF (stack 5.8) |
| `US-19` | Listar los pedidos en transito en una grilla ordenable | Story | OE3 | **Must** | Sprint 6 | 12h | RF-04 / RNF-01 |
| `US-20` | Consultar el detalle completo de un pedido | Story | OE3 | **Must** | Sprint 6 | 10h | RF-05 / CU-03 |
| `US-21` | Filtrar el dashboard de forma transversal y coherente | Story | OE3 | **Must** | Sprint 6 | 12h | RF-19 / CU-04 / RNF-02 |
| `US-22` | Mostrar la cinta de indicadores KPI | Story | OE3 | **Must** | Sprint 6 | 8h | RF-15 |
| `US-23` | Indicar la frescura de los datos en el encabezado | Story | OE3 | **Should** | Sprint 6 | 4h | RF-20 / RNF-12 |
| `US-24` | Aplicar el semaforo de estados de forma consistente | Story | OE3 | **Must** | Sprint 6 | 4h | RNF-08 / RN-02 a RN-15 |
| `US-43` | Ofrecer dos vistas de la grilla según el rol: simple y completa | Story | OE3 | **Must** | Sprint 6 | 10h | Reunión Logística 03/09 |
| `US-25` | Presentar el mapa interactivo marítimo con posiciones actuales | Story | OE3 | **Must** | Sprint 7 | 12h | RF-16 / CU-07 |
| `US-26` | Presentar el mapa interactivo aéreo separado del marítimo | Story | OE3 | **Must** | Sprint 7 | 8h | RF-17 / CU-08 |
| `US-27` | Mostrar informacion emergente en los marcadores del mapa | Story | OE3 | **Could** | Sprint 7 | 6h | RF-18 (Media en SRS) |
| `US-28` | Presentar los proximos arribos dentro del dashboard | Story | OE3 | **Should** | Sprint 6 | 8h | RF-27 / RNF-01 |
| `US-29` | Consultar el historial de tracking y dibujar el trayecto | Story | OE3 | **Could** | Sprint 7 | 10h | RF-22 (Media en SRS) / CU-09 |
| `US-30` | Actualizar la nave asignada ante un transbordo | Story | OE2 | **Should** | Sprint 7 | 10h | RF-26 / CU-10 |
| `US-44` | Mostrar en el detalle el país de origen y el mapa de seguimiento del pedido | Story | OE3 | **Should** | Sprint 7 | 8h | Reunión Logística 03/09 / RF-05 (ampliado) |
| `US-33` | Habilitar el modo de visualizacion permanente en pantalla grande | Story | OE3 | **Could** | Sprint 7 | 6h | RNF-11 / vista simple de `US-43` |
| `TASK-06` | Pruebas de integracion extremo a extremo | Task | OE4 | **Must** | Cierre | 12h | RNF-18 / Criterios seccion 10 |
| `TASK-07` | Manual de instalacion local | Task | OE4 | **Must** | Cierre | 6h | Criterios seccion 10 |
| `TASK-08` | Manual de usuario del dashboard | Task | OE4 | **Must** | Cierre | 6h | RNF-10 / Criterios seccion 10 |
| `TASK-09` | Guia de despliegue para produccion | Task | OE4 | **Must** | Cierre | 6h | Criterios seccion 10 |
| `TASK-10` | Politica de retencion y submuestreo del historial de posiciones | Task | OE4 | **Could** | Sprint 7 | 8h | RNF-22 / spike TG-10 |
| `TASK-11` | Actualizar el SRS con los hallazgos de los spikes tecnicos ✅ | Task | OE1 | **Must** | Sprint 3 | ~~6h~~ 0h | Fase 6 de TG-18 (cumplida por el SRS v0.3) |

🔀 = alcance sujeto a la decisión de `TASK-28` (compra de la fuente comercial de rastreo). Ver «La bifurcación de `TASK-28`» al final.

**Ya no queda ninguna historia bloqueada por insumo externo:** el riesgo R2 se resolvió el 03/09 formalizando la carga manual (`RF-31`).

---

## Detalle por sprint

### Sprint 2 (24 ago - 4 sep 2026)

**19 items · 90 h estimadas · capacidad 65 h nominal** (13 Task, 6 Story). Corresponde a OE1 (analisis y diseño); produce el modelo de datos de las **siete** entidades del SRS v0.3 §8.1, el diccionario, la arquitectura y los prototipos sobre los que se construyen los Sprints 3-7.

> Revisado el 24/08 — ver «Revision del 24/08» al final de esta seccion y el [plan de la semana 1](plan_semanal_s2_sem1.md).

#### TASK-12 — Modelar la entidad pedidos_transito en el diagrama ER ✅ HECHA

Como desarrollador, quiero modelar la entidad pedidos_transito con sus atributos, clave e indices, para dar base a la persistencia de los pedidos en transito.

**Criterios de aceptación**

- Dado el diagrama ER, cuando modelo pedidos_transito, entonces incluye OC, proveedor, material, via, destino, fecha comprometida, identificador de rastreo y estado, con clave primaria definida
- Dada la relacion con maestro_destinos, cuando la defino, entonces queda con su cardinalidad y clave foranea
- Dadas las consultas frecuentes del dashboard, cuando reviso el modelo, entonces propongo los indices necesarios

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen | Diseño OE1 / modelo de datos |
| Etiquetas | `diseno,bd,modelo` |

> **Completada el 24/08** en `docs/data-model.md` §1 (rama `Modelos_Datos`). Los tres criterios de aceptacion se satisfacen: atributos y PK en §1.2-§1.3, relacion con `maestro_destinos` con cardinalidad 1:N y FK `NOT NULL` en §1.7, e indices propuestos en §1.8.
>
> **DoD completa:** revisada y aprobada por el supervisor el 25/08. La separacion del estado en dos dimensiones (§1.4) quedo aprobada, y la implementan US-10 y US-24. Ver el acta en `agenda_revision_supervisor.md`.

#### TASK-13 — Modelar la entidad maestro_destinos ✅ HECHA

Como desarrollador, quiero modelar maestro_destinos con lead time y coordenadas, para soportar el calculo de disponibilidad y la geocerca de arribo.

**Criterios de aceptación**

- Dado el ER, cuando modelo maestro_destinos, entonces incluye puerto/aeropuerto, pais, coordenadas, via y lead time con clave primaria
- Dado el lead time, cuando lo defino, entonces queda tipado en dias y no nulo
- Dadas las coordenadas del destino, cuando las modelo, entonces quedan disponibles para la geocerca de proximidad

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 4 h |
| Origen | Diseño OE1 / modelo de datos |
| Etiquetas | `diseno,bd,modelo` |

> **Completada el 25/08** en `docs/data-model.md` §2. Los tres criterios se satisfacen: puerto/aeropuerto, pais, coordenadas, via y lead time con PK en §2.2-§2.3; `lead_time_dias INTEGER NOT NULL` con `CHECK >= 0` en §2.4; coordenadas en `GEOGRAPHY(Point,4326)` disponibles para la geocerca en §2.5.
>
> Dos propuestas que van a la revision del viernes: el **FK compuesto** `(id_destino, via_transporte)` que impide que un pedido maritimo apunte a un aeropuerto (§2.7, enmienda §1.7 de TASK-12), y el **radio de geocerca por destino** (§2.5). §2.9 deja los valores de referencia para los datos semilla de TASK-03, con los lead times pendientes de Logistica.

#### TASK-14 — Modelar la entidad historial_tracking (geoespacial) ✅ HECHA

Como desarrollador, quiero modelar historial_tracking con posicion geoespacial y payload, para poder auditar y reconstruir el trayecto de cada pedido.

**Criterios de aceptación**

- Dado el ER, cuando modelo historial_tracking, entonces la posicion usa `GEOGRAPHY(Point,4326)` —no `geometry`— para que ST_Distance devuelva metros y no grados
- Dada la relacion con elementos_rastreados, cuando la defino, entonces es 1:N: el historial cuelga del elemento rastreado y no del pedido, conforme al SRS v0.3 §8.1
- Dadas varias lineas de OC que viajan en un mismo buque, cuando reviso el modelo, entonces cada posicion recibida se persiste una sola vez y un transbordo no parte el trayecto
- Dado el requisito de auditoria, cuando modelo el payload, entonces almacena la respuesta completa de la API en JSONB

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen | Diseño OE1 / modelo de datos |
| Etiquetas | `diseno,bd,postgis,geoespacial` |

> **Completada el 25/08** en `docs/data-model.md` §3. Los criterios se satisfacen: `GEOGRAPHY(Point,4326)` y payload `JSONB` en §3.2, relacion 1:N con `elementos_rastreados` en §3.5.
>
> Destapa un problema que necesita decision: **el transbordo rompe el trayecto** (§3.8). RF-26 exige conservar el historial de la nave anterior y RF-22 consultar el trayecto del pedido, pero el FK unico del pedido apunta solo a la nave vigente. A lo largo del tiempo la relacion pedido-elemento es N:M, no N:1. La recomendacion es una entidad asociativa, lo que llevaria el ER a **ocho** entidades y cambiaria el criterio de TASK-01.
>
> Dimensionamiento de §3.6 con datos de los spikes: ~25 millones de filas y ~20 GB al año. Sostiene que **TASK-10 (submuestreo) deberia dejar de ser `Could`**.

> **Correccion (24/08):** el criterio original relacionaba el historial con `pedidos_transito` y pedia `geometry`. Prevalecen el SRS v0.3 §8.1 (historial por elemento rastreado) y la convencion ya implementada en `backend/app/db/base.py` (`GEOGRAPHY`, SRID 4326).

#### TASK-15 — Modelar usuarios, elementos_rastreados, proveedores y materiales, y consolidar el ER ✅ HECHA

Como desarrollador, quiero modelar las cuatro entidades restantes del SRS v0.3 §8.1 y consolidar el ER completo, para que el modelo cubra las siete entidades que TASK-01 debe crear en el Sprint 3.

**Criterios de aceptación**

- Dado el ER, cuando modelo elementos_rastreados, entonces desacopla el identificador de rastreo del pedido, admite N lineas de OC sobre una misma nave y soporta el cambio de nave por transbordo (US-30)
- Dado elementos_rastreados, cuando modelo posicion_actual, entonces su tipo es `GEOGRAPHY(Point,4326)`, consistente con el criterio de aceptacion de TASK-02
- Dado el ER, cuando modelo proveedores y materiales, entonces normalizan los campos hoy embebidos como texto libre en el pedido y habilitan el filtrado de US-21
- Dado el ER, cuando modelo usuarios, entonces incluye rol (Compras, Logística, Planificacion) sin depender de SSO/AD, y soporta la auditoria de RF-14
- Dado el conjunto de entidades, cuando consolido el ER, entonces las **siete** entidades del SRS v0.3 §8.1 quedan con sus relaciones y cardinalidades
- Dado el SRS v0.3, cuando reviso el ER consolidado, entonces es consistente con los requerimientos aprobados

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 10 h |
| Origen | Diseño OE1 / modelo de datos (SRS v0.3 §8.1) |
| Etiquetas | `diseno,bd,modelo,transbordo` |

> **Ampliacion (24/08):** la version original modelaba solo `usuarios` en 4 h. El SRS v0.3 §8.1 identifica **siete** entidades y ninguna tarea del Sprint 2 nombraba `elementos_rastreados`, `proveedores` ni `materiales`. Sin ellas, TASK-01 falla su propio criterio de aceptacion.

> **Completada el 25/08** en `docs/data-model.md` §4 a §9, con el **ER consolidado** al inicio del archivo. Las siete entidades del SRS v0.3 §8.1 quedan modeladas con relaciones y cardinalidades.
>
> **Aparecen tres entidades mas.** Dos las exige el articulado del SRS aunque §8.1 no las enumere: `auditoria_intervenciones` (RF-14 pide usuario, fecha, valor anterior, valor nuevo y motivo) y `parametros_sistema` (RN-05 y RN-11 citan textualmente «la tabla de mantenimiento de parametros»). La tercera es `pedido_elemento_rastreado`, la asociativa de §3.8. **El esquema real tiene diez tablas, no siete.**
>
> Consecuencia directa: el criterio de aceptacion de **TASK-01 debe pasar de siete a diez entidades** y reestimarse (hoy 10 h; se sugieren ~4 h mas). Ver §8.4.
>
> Ademas **RNF-04 declara la autenticacion dentro del alcance** con mecanismo propio, y ninguna historia del backlog la construye. Ver §7.2: la pregunta para Greivin no es si se hace, sino de donde salen las 20-25 h o si se modifica el SRS.

#### TASK-16 — Diccionario de datos: pedidos_transito ✅ HECHA

Como desarrollador, quiero documentar el diccionario de datos de pedidos_transito, para garantizar consistencia en la implementacion de la tabla.

**Criterios de aceptación**

- Dada la tabla pedidos_transito, cuando documento el diccionario, entonces cada campo tiene nombre, tipo, nulabilidad, PK/FK, dominio y descripcion
- Dado el diagrama ER, cuando comparo, entonces el diccionario es consistente con el modelo

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 2 h |
| Origen | Diseño OE1 / diccionario de datos |
| Etiquetas | `diseno,diccionario` |

> **Completada el 25/08** en `docs/data-dictionary.md` §1. Los 26 campos con nombre, tipo, nulabilidad, PK/FK, dominio y descripcion en §1.1; restricciones de tabla en §1.2.
>
> La consistencia con el ER **se verifica de forma automatica**, no por inspeccion: `scripts/check_docs_model.py` compara el diccionario contra el bloque mermaid de `data-model.md` y falla si divergen campos, orden o tipos. Sirve para las tres tareas de diccionario restantes.

#### TASK-17 — Diccionario de datos: maestro_destinos ✅ HECHA

Como desarrollador, quiero documentar el diccionario de datos de maestro_destinos, para garantizar consistencia en la implementacion de la tabla.

**Criterios de aceptación**

- Dada la tabla maestro_destinos, cuando documento el diccionario, entonces cada campo (incluido lead time) tiene tipo, restricciones y descripcion
- Dado el diagrama ER, cuando comparo, entonces el diccionario es consistente con el modelo

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 2 h |
| Origen | Diseño OE1 / diccionario de datos |
| Etiquetas | `diseno,diccionario` |

> **Completada el 25/08** en `docs/data-dictionary.md` §2. Los 12 campos con tipo, restricciones y descripcion; `lead_time_dias` documentado como unico por destino (RN-12) y aclarando que **no incluye** el circuito de Control de Calidad que el SRS §7.1 deja fuera de RN-01.

#### TASK-18 — Diccionario de datos: historial_tracking ✅ HECHA

Como desarrollador, quiero documentar el diccionario de datos de historial_tracking, para dejar clara la estructura geoespacial y del payload almacenado.

**Criterios de aceptación**

- Dada la tabla historial_tracking, cuando documento el diccionario, entonces cada campo esta descrito, incluido el geoespacial con su SRID
- Dado el payload almacenado, cuando lo documento, entonces se especifica su estructura (JSONB)

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 3 h |
| Origen | Diseño OE1 / diccionario de datos |
| Etiquetas | `diseno,diccionario,geoespacial` |

> **Completada el 25/08** en `docs/data-dictionary.md` §3. Los 8 campos con su SRID explicito y la estructura del `JSONB`; §3.3 documenta el caracter append-only y §3.4 el dimensionamiento medido (~25 M filas y ~20 GB al año).

#### TASK-24 — Diccionario de datos: elementos_rastreados, proveedores y materiales ✅ HECHA

Como desarrollador, quiero documentar el diccionario de datos de las tres entidades incorporadas, para que TASK-01 pueda implementarlas sin ambiguedad.

**Criterios de aceptación**

- Dada la tabla elementos_rastreados, cuando documento el diccionario, entonces incluye el identificador externo (MMSI para buques, icao24 para aeronaves), la via, la posicion actual con su SRID y la fecha de ultima lectura
- Dadas las tablas proveedores y materiales, cuando documento el diccionario, entonces cada campo tiene nombre, tipo, nulabilidad, PK/FK y descripcion
- Dado el diagrama ER consolidado en TASK-15, cuando comparo, entonces el diccionario es consistente con el modelo

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 4 h |
| Origen | Diseño OE1 / diccionario de datos (SRS v0.3 §8.1) |
| Etiquetas | `diseno,diccionario` |

> **Completada el 25/08** en `docs/data-dictionary.md` §4 a §6. `elementos_rastreados` incluye identificador externo (MMSI e icao24), via, `posicion_actual` con SRID y `ultima_actualizacion_api`; §4.3 explica por que el unico es parcial y §4.4 por que `tramo` no esta.

#### TASK-20 — Arquitectura: vista de componentes ✅ HECHA

Como desarrollador, quiero elaborar el diagrama de arquitectura de componentes, para guiar la construccion del backend, el frontend y las integraciones.

**Criterios de aceptación**

- Dado el diagrama, cuando lo elaboro, entonces representa backend FastAPI, frontend React, PostgreSQL/PostGIS, integraciones AISStream/OpenSky y los jobs de ingesta y calculo
- Dadas las integraciones externas, cuando las modelo, entonces quedan como componentes con su responsabilidad definida
- Dadas las decisiones clave, cuando las documento, entonces registro geocerca mas confirmacion manual y carga por semilla

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen | Diseño OE1 / arquitectura |
| Etiquetas | `arquitectura,diseno` |

> **Completada el 25/08** en `docs/architecture.md` §1. Los tres criterios se satisfacen: el diagrama representa FastAPI, React, PostgreSQL/PostGIS, ambas integraciones y los procesos de ingesta y calculo (§1.1); cada componente tiene su responsabilidad y lo que **no** hace (§1.2); y §1.6 registra las decisiones clave —geocerca mas confirmacion manual, `on_ground` para lo aereo, carga por semilla, sin autenticacion en la practica y parametros fuera del codigo—.
>
> **Resuelve la pregunta abierta del anteproyecto:** el rastreo corre en un **worker aparte**, no dentro del proceso de la API (§1.4). El argumento decisivo es local: el entorno arranca con `uvicorn --reload`, asi que cada guardado reiniciaria el proceso y tumbaria la suscripcion WebSocket de AIS —justo lo que no conviene con el riesgo R1 sospechando un tope del plan gratuito—. Sin broker de mensajes: la base es el unico estado compartido.
>
> **RNF-21 obligo a una abstraccion que el stub no contemplaba** (§1.3): AIS es *push* y OpenSky es *pull*, asi que no se pueden unificar por la entrada. Se unifican por la salida, con ambos adaptadores produciendo el mismo tipo `LecturaPosicion`.

#### TASK-21 — Arquitectura: vista de despliegue (instalacion nativa) ✅ HECHA

Como desarrollador, quiero elaborar el diagrama de despliegue con los componentes instalados de forma nativa (sin Docker), para reflejar que el equipo de trabajo no ejecuta contenedores y usa PostGIS nativo.

**Criterios de aceptación**

- Dado el entorno de desarrollo, cuando elaboro el despliegue, entonces muestra API FastAPI, PostgreSQL con PostGIS y frontend instalados de forma nativa, sin contenedores
- Dados los servicios locales, cuando los documento, entonces indico puertos y dependencias del equipo
- Dado el alcance, cuando lo reviso, entonces queda limitado a desarrollo (produccion fuera de alcance)
- Dado `docs/deployment.md`, cuando elaboro la vista, entonces reutilizo la seccion «Entorno de desarrollo sin Docker» ya redactada en lugar de rehacerla

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 2 h |
| Origen | Diseño OE1 / arquitectura (decision: sin Docker) |
| Etiquetas | `arquitectura,diseno,nativo` |

> **Completada el 25/08** en `docs/architecture.md` §2. Muestra API, worker, PostgreSQL con PostGIS y frontend nativos, sin contenedores; §2.2 lista puertos (5432, 8000, 5173, 5050) y §2.4 las dependencias del equipo; el alcance queda acotado a desarrollo.
>
> **Detecto una contradiccion y la corrigio.** `deployment.md` describia tres procesos; con la decision de TASK-20 son **cuatro**. Se agrego el worker a esa tabla para que los dos documentos no digan cosas distintas.



#### TASK-22 — Arquitectura: vista de secuencia (flujo de tracking) ✅ HECHA

Como desarrollador, quiero elaborar el diagrama de secuencia del flujo principal de tracking, para clarificar la interaccion entre los componentes del sistema.

**Criterios de aceptación**

- Dado el flujo principal, cuando lo modelo, entonces recorre ingesta AIS/ADS-B, persistencia en historial_tracking, calculo de estado, API REST y visualizacion en el dashboard
- Dadas las interacciones, cuando las represento, entonces son consistentes con la vista de componentes

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 4 h |
| Origen | Diseño OE1 / arquitectura |
| Etiquetas | `arquitectura,diseno` |

> **Completada el 25/08** en `docs/architecture.md` §3. El diagrama recorre ingesta AIS/ADS-B, normalizacion, persistencia idempotente, calculo de estado, API REST y pintado del dashboard, y es consistente con la vista de componentes (§3.3).
>
> **Lo que el diagrama hace visible:** las dos mitades no se tocan. El worker corre sin usuario presente y la API responde sin esperar a nadie; lo unico que comparten es la base. Ahi se ve por que RNF-03 y RNF-12 se pueden cumplir. Tambien se ve donde la secuencia deja de ser simetrica entre vias: geometria para lo maritimo, `on_ground` para lo aereo.

#### US-34 — Wireframe del dashboard principal (grilla, filtros y KPIs) ✅ HECHA

Como usuario de Compras, quiero revisar un wireframe del dashboard con grilla, filtros y KPIs, para validar la vista principal antes de que se construya.

**Criterios de aceptación**

- Dado el wireframe del dashboard, cuando lo reviso, entonces muestra la grilla con OC, proveedor, material, via, estado, destino y ETA
- Dado el wireframe, cuando reviso los filtros, entonces incluye OC, proveedor, material, via, estado y destino, mas la cinta de KPIs y el semaforo
- Dado el wireframe, cuando reviso su composicion, entonces incluye el bloque de proximos arribos entre los KPIs y la grilla, conforme a RNF-01 y a US-28 (decision del 25/08)

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen | Diseño OE1 / prototipo |
| Etiquetas | `frontend,ux,wireframe` |

> **Completada el 26/08.** Frame `01-dashboard` montado en Figma. Especificacion de contenido en `docs/design/wireframes.md` §1, con trazabilidad a RF-04, RF-15, RF-19, RF-20, RF-27 y RNF-08.
>
> Incluye el bloque de proximos arribos (decision del 25/08) y siete preguntas para la sesion del 4/09. Al armar los datos de ejemplo aparecieron los tres solapamientos de reglas que se resolvieron el 26/08.

#### US-35 — Wireframe del mapa marítimo ✅ HECHA

Como usuario de Logística, quiero revisar un wireframe del mapa marítimo con marcadores y tooltips, para validar la visualizacion de las cargas maritimas antes de construirla.

**Criterios de aceptación**

- Dado el wireframe, cuando lo reviso, entonces muestra marcadores geolocalizados coloreados por estado
- Dado un marcador, cuando lo reviso, entonces contempla un tooltip con OC, nave y estado

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 4 h |
| Origen | Diseño OE1 / prototipo |
| Etiquetas | `frontend,ux,wireframe` |

> **Completada el 27/08** en `docs/design/wireframes.md` §2 y en el borrador visual (frame `02-mapa-maritimo`). Los dos criterios de aceptacion se satisfacen: marcadores geolocalizados coloreados por estado en §2.2, y emergente en §2.3.
>
> El criterio pedia un tooltip con «OC, nave y estado», que asume un pedido por marcador. Se entrego el contenido completo de RF-18 en formato de tabla, porque §8.6 del SRS establece que varias lineas de OC viajan en el mismo buque: el criterio se cumple **por exceso**, no por desviacion. La decision de colorear por `etapa_viaje` con anillo de peor cumplimiento (§2.2) queda a validar en `US-39`.
>
> Deja dos aportes fuera de su alcance: el contador de pedidos sin posicion (§2.6), que ningun RF cubre, y la verificacion de que la red de Gutis no bloquea los mosaicos de OpenStreetMap (§2.8), que descarta el riesgo del Sprint 7.

#### US-36 — Wireframe del mapa aéreo ✅ HECHA

Como usuario de Logística, quiero revisar un wireframe del mapa aéreo con rutas y estados, para validar la visualizacion de las cargas aereas antes de construirla.

**Criterios de aceptación**

- Dado el wireframe, cuando lo reviso, entonces muestra la posicion y ruta del vuelo con su estado
- Dado un vuelo seleccionado, cuando lo reviso, entonces contempla mostrar la carga asociada y su ETA

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 4 h |
| Origen | Diseño OE1 / prototipo |
| Etiquetas | `frontend,ux,wireframe` |

> **Completada el 27/08** en `docs/design/wireframes.md` §3 y en el borrador visual (frame `03-mapa-aereo`). Los dos criterios de aceptacion se satisfacen: posicion y ruta del vuelo con su estado en §3.4, y carga asociada con su ETA en el emergente de §3.8.
>
> **La vista no reutiliza el mapa maritimo tal cual**, y §3.1 lista las cinco diferencias con su origen medido. Las tres de fondo: no se dibuja geocerca porque el arribo aereo se decide por `on_ground` (decision del 25/08) y el circulo sugeriria una regla que no aplica (§3.2); el marcador solo vale dentro de la ventana del tramo, porque un `icao24` vuela otra ruta a las pocas horas (§3.3, evidencia TG-11); y un marcador atenuado en descenso significa «probablemente aterrizo», no «esta lejos» (§3.5, caso `LRS1018`).
>
> **Deja tres puntos abiertos que no son de diseño:**
>
> 1. La ruta **recorrida** depende de `US-29`, hoy `Could` del Sprint 7. Si cae, `US-26` entrega solo la ruta prevista. Conviene decidirlo antes del Sprint 7 (§3.4).
> 2. Si el sondeo ADS-B es por ventanas activas —la recomendacion del spike TG-11—, los horarios de la ventana son un parametro de `US-17`, y el indicador de frescura necesita **tres** estados, no dos (§3.7).
> 3. MRLB no tiene cobertura ADS-B (riesgo R5, tres muestras en cero). Sus pedidos no esperan su primera lectura: no la van a tener. El wireframe los cuenta aparte de los `SIN_TRACKING` (§3.6).

#### US-37 — Wireframe del detalle de pedido ✅ HECHA

Como usuario de Compras, quiero revisar un wireframe de la vista de detalle de un pedido, para validar que muestre toda la informacion e historial necesarios.

**Criterios de aceptación**

- Dado un pedido seleccionado, cuando reviso el wireframe de detalle, entonces contempla datos maestros, estado, ETA proyectada y trazabilidad
- Dado el historial, cuando lo reviso, entonces contempla una linea de tiempo de posiciones y estados

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE1 |
| MoSCoW | **Should** |
| Estimacion | 4 h |
| Origen | Diseño OE1 / prototipo |
| Etiquetas | `frontend,ux,wireframe` |

> **Completada el 28/08** en `docs/design/wireframes.md` §4 y en el borrador visual (frame `04-detalle-pedido`). Los dos criterios de aceptacion se satisfacen: datos maestros, estado, ETA proyectada y trazabilidad en §4.1 a §4.3, y linea de tiempo de posiciones y estados en §4.5.
>
> **La linea de tiempo se aparta de la lectura literal del criterio, y conviene que conste.** Pedia «posiciones y estados» en una sola secuencia; un viaje de tres semanas produce decenas de miles de posiciones y menos de diez eventos, de modo que fundirlas entierra lo que importa. La vista muestra los eventos y **pliega las posiciones entre ellos** con su conteo y un enlace. La secuencia cronologica existe y es legible, y la posicion individual sigue a un clic.
>
> **Deja tres puntos abiertos, dos de ellos fuera de diseño:**
>
> 1. **Falta un valor en el dominio de `tipo_intervencion`.** Asociar un identificador de rastreo es una intervencion manual sobre un pedido —la exige `US-20` en su tercer criterio— y cae de lleno en RF-14, pero los cinco valores modelados no la cubren. Propuesto `ASOCIACION_TRACKING`. Va a `TASK-25` y lo consume `US-15` (§4.7).
> 2. **`velocidad_minima_eta` sigue como *a definir*.** Cuando RN-16 no proyecta, la vista muestra distancia, velocidad e instante —los tres insumos que la regla exige exponer— y el umbral contra el que fallo. La vista se puede construir sin el valor; **validarla el 4 de septiembre, no** (§4.4).
> 3. **El lead time usado no es el vigente.** El snapshot de `lead_time_destino_dias` puede diferir del maestro hasta que `US-12` recalcule, y ninguno de los dos esta mal. Esta es la unica vista donde la diferencia es visible, y se muestra al margen para evitar que se lea como un error (§4.1).
>
> Nota de interfaz para `US-14`, `US-18` y `US-12`: RF-14 exige el **motivo declarado** en cada intervencion, de modo que **ninguna accion puede ser un boton que ejecuta al pulsarlo**. Todas abren confirmacion con campo de motivo obligatorio (§4.8).

> **Devuelta al Sprint 2 el 25/08.** Se había movido al Sprint 6 el 24/08 para aliviar carga, pero `US-38` exige navegar «entre dashboard, mapas **y detalle de pedido**»: sin este wireframe, el prototipo no puede cumplir su criterio y la sesion de validacion del 4 de septiembre se quedaria sin la vista donde vive el desglose del calculo de la ETA (RF-05), que es lo mas novedoso del producto.

#### US-38 — Prototipo interactivo navegable en Figma

Como usuario clave, quiero navegar un prototipo interactivo del dashboard en Figma, para experimentar el flujo de la aplicacion antes de construirla.

**Criterios de aceptación**

- Dados los wireframes de todas las vistas, cuando se ensamblan en Figma, entonces el prototipo permite navegar entre dashboard, mapas y detalle de pedido
- Dado el flujo principal, cuando lo recorro, entonces las transiciones entre vistas funcionan y son coherentes

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen | Diseño OE1 / prototipo |
| Etiquetas | `frontend,ux,figma` |

#### US-39 — Validación de prototipos con usuarios clave

Como usuario clave de Compras/Logística, quiero revisar y aprobar los prototipos de interfaz, para asegurar que el diseño refleja las necesidades levantadas antes de desarrollar.

**Criterios de aceptación**

- Dado el prototipo listo, cuando se realiza la sesion de validación, entonces se registra el feedback de los usuarios clave
- Dado el feedback, cuando termina la sesion, entonces los prototipos quedan aprobados o con cambios documentados

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 4 h |
| Origen | Diseño OE1 / criterio de aceptación de OE1 |
| Etiquetas | `ux,validación` |

> **Sesion agendada para el viernes 4 de septiembre**, ultimo dia del sprint. El prototipo de US-38 debe estar terminado antes. Si los usuarios piden cambios, el criterio se cumple documentandolos: aplicarlos no cabe en el Sprint 2 y caeria en el Sprint 3 o en las historias de frontend del Sprint 6.

#### Revision del 24/08 — que cambio en este sprint y por que

Al arrancar el Sprint 2 se contrasto el backlog contra el **SRS v0.3** (el backlog original se derivo de v0.2) y contra el codigo ya existente. Resultado:

| Cambio | Efecto | Motivo |
|---|---|---|
| `TASK-15` ampliada de 4 h a **10 h** | +6 h | El SRS v0.3 §8.1 identifica **siete** entidades. Ninguna tarea del sprint nombraba `elementos_rastreados`, `proveedores` ni `materiales`. `elementos_rastreados` sostiene US-30 y ya aparece nombrada en el criterio de aceptacion de TASK-02. |
| `TASK-24` incorporada | +4 h | Diccionario de esas tres entidades, que tampoco existia. |
| `TASK-14` corregida | 0 h | El historial cuelga de `elementos_rastreados`, no de `pedidos_transito` (SRS v0.3 §8.1), y el tipo es `GEOGRAPHY(Point,4326)`, no `geometry`. |
| `TASK-21` reducida de 4 h a **2 h** | −2 h | `docs/deployment.md` §«Entorno de desarrollo sin Docker» ya documenta el grueso de la vista de despliegue. |
| `TASK-23` movida al **Sprint 3** | −8 h | Su propio criterio dice que el Informe 1 abarca los Sprints 1, 2 y 3 y se presenta el 25/09. El Sprint 3 cierra el 18/09. |
| `US-37` movida al **Sprint 6** | −4 h | Es `Should`. La validacion de US-39 corre sobre dashboard y mapas; el wireframe del detalle se hace junto a US-20, que construye esa misma vista. |
| `TASK-19` movida al **Sprint 3** | −2 h | Es `Should` y es la tabla de menor riesgo de implementacion. Va junto a TASK-01. |

**Neto: 81 h → 75 h.** El sprint sigue 10 h por encima de la capacidad de 65 h.

##### Resuelto el 25/08: no se recorta

La palanca disponible era bajar la fidelidad del prototipo de `US-38` de un navegable en Figma (8 h) a wireframes con navegacion minima (~4 h). **El supervisor decidio dejar el sprint como esta**: ocho tareas estimadas en 37 h se cerraron en dos dias, de modo que la sobrecarga aparente proviene de la estimacion y no del alcance. Se revisa con datos reales al cierre del Sprint 2, no antes.

##### Efecto sobre el Sprint 3

Las 10 h movidas caen sobre un sprint que ya estaba en 66 h. Lo compensa parcialmente que **`TASK-11` se verifico cumplida**: el SRS v0.3 ya en el repositorio satisface sus dos criterios de aceptacion. Sprint 3 queda en **70 h** contra 65 h de capacidad.

##### Desincronizacion pendiente

`backlog_trackin.csv` tiene 44 filas y **no contiene ningun item del Sprint 2** (se genero antes del commit `60d4184`). Los cambios de esta revision no lo afectan, pero el CSV no sirve hoy para importar el Sprint 2 a Jira.

#### TASK-26 — Diccionario de datos: auditoria_intervenciones, parametros_sistema y pedido_elemento_rastreado ✅ HECHA

Como desarrollador, quiero documentar el diccionario de las tres tablas aprobadas en la revision del 25/08, para que TASK-01 pueda implementarlas sin ambiguedad y su criterio de las diez entidades sea alcanzable.

**Criterios de aceptación**

- Dada `auditoria_intervenciones`, cuando documento el diccionario, entonces cada campo tiene nombre, tipo, nulabilidad, PK/FK, dominio y descripcion, y el dominio de `tipo_intervencion` queda enumerado de forma explicita
- Dada `parametros_sistema`, cuando documento el diccionario, entonces registra `clave` como PK natural, el dominio de `tipo_dato`, y la lista de parametros que exigen RN-05, RN-10, RN-11 y RN-16
- Dada `pedido_elemento_rastreado`, cuando documento el diccionario, entonces incluye `tramo`, `fecha_desde` y `fecha_hasta`, con la semantica de que `fecha_hasta` nula identifica el tramo vigente
- Dado el ER consolidado, cuando ejecuto `scripts/check_docs_model.py`, entonces no reporta divergencias en ninguna de las tres tablas

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 3 h |
| Origen | Revision con el supervisor, 25/08/2026 |
| Etiquetas | `diseno,diccionario` |

> **Por que existe esta tarea.** Las tres tablas se aprobaron el 25/08 pero ninguna tarea de diccionario las cubria: `TASK-16` a `TASK-19` y `TASK-24` se escribieron cuando el modelo tenia siete entidades. Sin ellas documentadas, `TASK-01` no puede cumplir su criterio nuevo de crear las diez.

> **Completada el 25/08** en `docs/data-dictionary.md` §7 a §9. Los cuatro criterios se satisfacen; `scripts/check_docs_model.py` confirma que las tres tablas concuerdan con el ER.
>
> **Afinada la asociativa al documentarla.** RF-26 pide «el puerto en que se produjo y la fecha de la notificacion», y el modelo aprobado los guardaba como texto libre dentro de `motivo`. Se separaron en `puerto_transbordo` y `fecha_notificacion`. Se agrego ademas un unico parcial `UNIQUE (id_pedido) WHERE fecha_hasta IS NULL`, que impide que un pedido tenga dos tramos vigentes a la vez.

#### TASK-25 — Emitir el SRS v0.4 con las decisiones de la revision del 25/08

Como estudiante practicante, quiero el SRS actualizado a v0.4 con las decisiones aprobadas y las correcciones que produjo el modelado, para que la especificacion vigente no comprometa requisitos que el proyecto no va a entregar ni describa un modelo de datos que ya no es el aprobado.

**Criterios de aceptación**

- Dados RNF-04 y RNF-05, cuando emito v0.4, entonces la autenticacion queda descrita como trabajo previo al despliegue a cargo del Centro de Competencias, y se suma a las exclusiones explicitas de la seccion 1.2.2
- Dada la seccion 8.1, cuando la actualizo, entonces enumera las **diez** entidades del modelo aprobado, incluidas `auditoria_intervenciones`, `parametros_sistema` y `pedido_elemento_rastreado`
- Dadas las secciones 8.2 a 8.5, cuando las corrijo, entonces reflejan los campos incorporados, el tipo `GEOGRAPHY` en lugar de `GEOMETRY`, `id_elemento_rastreado` como `BIGINT` y no `VARCHAR`, y la salida de `tramo` de `elementos_rastreados`
- Dada RN-05, cuando la actualizo, entonces distingue el criterio de arribo aereo (`on_ground`) del maritimo (geocerca), y contempla el radio por destino
- Dada RN-07, cuando la reescribo, entonces exige margen **mayor** que el umbral y no solo «anterior o igual», dejando escrito que **RN-08 prevalece por ser mas especifica** (decision del 26/08)
- Dado el umbral de RN-11, cuando lo reescribo, entonces queda fijado en **2 dias** al aplicarse entre dos valores `DATE` sin hora (decision del 26/08)
- Dadas RN-05 y RN-06, cuando las reescribo, entonces `En destino` **dura 30 minutos** y `En proceso aduanal` arranca 30 minutos despues de la notificacion del arribo, con la duracion en la tabla de parametros (decision del 26/08)
- Dada RN-05, cuando la reviso, entonces el modelo distingue los **tres origenes de arribo** que la regla exige: `ata_api` de la fuente, `ata_inferida` del sistema y `ata_confirmada` manual
- Dada RN-05, cuando la actualizo, entonces registra que **no se adquieren fuentes de datos de pago** (decision B1 del 01/09) y que, por tanto, el arribo al puerto de destino **no se detecta automaticamente**: depende de la confirmacion manual de RF-13
- Dado RF-14, cuando lo reviso, entonces el dominio de tipos de intervencion incluye **`ASOCIACION_TRACKING`**, que hoy falta pese a que asociar un identificador es una intervencion manual sobre un pedido (decision B6)
- Dados RNF-04 y RNF-05, cuando los reescribo, entonces queda constancia de que **la autoria de las intervenciones no esta autenticada**: el usuario se elige de una lista en cada dialogo y el sistema no verifica su identidad (decision B5)
- Dado RF-27, cuando lo reescribo, entonces la vista de proximos arribos muestra **los cinco pedidos con fecha proyectada mas cercana**, sin el segundo nivel que rellenaba con los de peor cumplimiento a 30 dias (validacion con usuarios del 01/09)
- Dado RNF-05, cuando lo reviso, entonces los perfiles quedan fijados en **tres** —Compras, Logistica y Planificacion— sin rol administrador (decision B9)
- Dado el supuesto de la seccion 9.4 sobre la entrega de la especificacion de SAP, cuando lo reviso, entonces queda registrado como **incumplido** y remite al riesgo R2
- Dado el historial de revisiones, cuando lo consulto, entonces registra v0.4 con su fecha y la descripcion de los cambios

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen | Revision con el supervisor, 25/08/2026 |
| Etiquetas | `documentacion,srs,hito` |

> **Por que es Must y no se puede omitir.** La decision del 25/08 fue sacar la autenticacion del alcance de la practica. Esa decision **se ejecuta modificando el SRS**: mientras el documento vigente diga que «se implementara un mecanismo propio», RNF-04 y RNF-05 siguen siendo requisitos comprometidos y no entregados, y el Informe 1 se presentaria contra una especificacion que el producto no cumple.
>
> **Trampa de ejecucion:** `docs/srs/README.md` advierte que `generador/srs.js` quedo desfasado en v0.1 y que **regenerar el documento destruiria todo lo posterior**. La v0.4 se edita directamente sobre el `.docx`, no se regenera. Tras editar, actualizar la tabla de contenidos con F9.
>
> **Calibracion:** `TASK-11` costo 6 h para incorporar los hallazgos de los spikes. Esta toca mas secciones —dos RNF, cinco subsecciones del modelo de datos, una regla de negocio y un supuesto— de ahi las 8 h.

---

### Revision con el supervisor — 25/08/2026

Cubre la DoD «Revision con supervisor (Greivin) cuando aplique» para `TASK-12` a `TASK-18` y `TASK-24`. Acta completa en [`agenda_revision_supervisor.md`](agenda_revision_supervisor.md); el modelo aprobado esta en `docs/data-model.md`.

| Punto | Decision | Efecto en el backlog |
|---|---|---|
| Transbordo y trayecto | Se conserva el trayecto completo: entra `pedido_elemento_rastreado` | El ER pasa a diez entidades |
| Entidades de `TASK-01` | Criterio actualizado a diez entidades | `TASK-01` reestimada de 10 h a **14 h**; Sprint 3 de 70 h a 74 h |
| Autenticacion RNF-04 | **Fuera del alcance de la practica** | No entra ninguna historia. **Requiere emitir el SRS v0.4** |
| Estado del pedido | Dos columnas mas una derivada | Sin cambio de horas; lo implementan `US-10` y `US-24` |
| Arribo aereo | `on_ground` para aereo, geocerca para maritimo | Criterio nuevo en `US-11` |
| Volumen del historial | Intervalo minimo configurable en `US-04` | Criterio nuevo en `US-04`. `TASK-10` se queda en Sprint 7 con `Could` |
| `tracking_interno` | Lo genera TrackIn | Consumo de `TASK-03` |
| Sobrecarga del Sprint 2 y 3 | No se recorta alcance | Se revisa al cierre del Sprint 2 |
| Especificacion de SAP | **Sin fecha, proceso varado** | Ver abajo |

#### Consecuencias que quedan abiertas

**1. Hay que emitir el SRS v0.4** — incorporado como **`TASK-25`** (8 h) al cierre del Sprint 2. Mientras el documento vigente diga que «se implementara un mecanismo propio» de autenticacion, RNF-04 y RNF-05 siguen siendo requisitos comprometidos y no entregados. La decision fue sacarlos del alcance de la practica, pero eso **se ejecuta modificando el SRS**, no omitiendolo.

**2. Tres tablas aprobadas no tienen tarea de diccionario.** `auditoria_intervenciones`, `parametros_sistema` y `pedido_elemento_rastreado` quedaron aprobadas y modeladas, pero `TASK-16` a `TASK-19` y `TASK-24` no las cubren. Son ~3 h que hoy no estan en ningun sprint, y `TASK-01` las necesita documentadas.

**3. El riesgo R2 empeoro.** Ver la seccion «Sin asignar».

---

### Sprint 3 (7-18 sep 2026)

**11 items · 78 h estimadas · capacidad 65 h — SOBRECARGADO en 13 h.** TASK-19 y TASK-23 llegan desde el Sprint 2 (+10 h); TASK-11 se verifico cumplida y sus 6 h no se cuentan; TASK-01 se reestimo de 10 h a 14 h el 25/08.

> **No se recorta alcance por ahora** (decision del 25/08). Ocho tareas estimadas en 37 h se cerraron en dos dias, lo que sugiere que la holgura esta en la estimacion y no en el alcance. Se revisa con datos reales al cierre del Sprint 2.

#### TASK-01 — Esquema de base de datos y migraciones Alembic

Como desarrollador, quiero el esquema relacional de las diez entidades versionado en Alembic, para que el resto del backend tenga sobre que construir.

**Criterios de aceptación**

- Dado el repositorio limpio, cuando ejecuto 'alembic upgrade head', entonces se crean las **diez** entidades del modelo sin error: las siete del SRS v0.3 seccion 8.1 mas `auditoria_intervenciones` (RF-14), `parametros_sistema` (RN-05, RN-11) y `pedido_elemento_rastreado` (RF-26)
- Dado el esquema aplicado, cuando inspecciono pedidos_transito, entonces existen los campos de la seccion 8.2 con sus tipos
- Dado el esquema aplicado, cuando ejecuto 'alembic downgrade base', entonces la base queda vacia sin error

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 14 h |
| Origen en el SRS | SRS 8.1-8.5 + articulado (RF-14, RN-05, RN-11, RF-26) |
| Etiquetas | `backend,persistencia,fundacional` |

> **Reestimada el 25/08** de 10 h a 14 h. El esquema tiene diez tablas, no siete: dos las exige el articulado del SRS aunque su seccion 8.1 no las enumere, y la tercera se aprobo en la revision con el supervisor. Modelo en `docs/data-model.md`, diccionario en `docs/data-dictionary.md`.

#### TASK-02 — Habilitar PostGIS y columna geometrica WGS 84

Como desarrollador, quiero PostGIS habilitado y la posicion almacenada como geometry(Point,4326), para poder calcular distancias con operadores nativos.

**Criterios de aceptación**

- Dado PostgreSQL 16, cuando ejecuto la migracion, entonces la extension postgis queda instalada
- Dado elementos_rastreados, cuando consulto posicion_actual, entonces su tipo es geometry(Point,4326)
- Dadas dos posiciones conocidas, cuando aplico ST_Distance sobre geography, entonces la distancia en metros coincide con el valor esperado con margen del 1%

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 4 h |
| Origen en el SRS | SRS 8.6 / RNF-20 |
| Etiquetas | `backend,persistencia,postgis` |

#### TASK-03 — Adaptador de ingesta de pedidos con datos semilla

Como desarrollador, quiero una interfaz de ingesta con una implementación de datos semilla, para desarrollar y demostrar el sistema sin depender del servicio de SAP.

**Criterios de aceptación**

- Dado que no existe el servicio de SAP, cuando arranco el sistema con el perfil de desarrollo, entonces se cargan pedidos semilla que cubren via maritima, via aerea y un caso sin identificador de rastreo
- Dada la interfaz de ingesta, cuando se implemente el adaptador de SAP, entonces no requiere cambios en el motor de calculo ni en la API REST
- Dado el perfil de produccion, cuando no hay adaptador configurado, entonces el sistema arranca y lo reporta en el healthcheck

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | Habilitador de RF-01 |
| Etiquetas | `backend,ingesta,riesgo-sap` |

#### TASK-27 — Spike: suscripcion por MMSI y limite del plan gratuito de AISStream

Como desarrollador, quiero medir si la suscripcion por MMSI funciona con la clave actual y cuanta cuota consume cada modalidad, para saber si el rastreo maritimo puede seguir a un buque fuera del Caribe sin topar el limite del plan.

**Criterios de aceptación**

- Dada la clave vigente, cuando me suscribo con `FiltersShipMMSI` sobre un MMSI conocido, entonces registro si llegan mensajes o el servidor rechaza la suscripcion
- Dadas las dos modalidades —bounding box amplio contra filtro por MMSI—, cuando las comparo, entonces mido mensajes por minuto y volumen de datos de cada una
- Dado el riesgo R1, cuando termino el spike, entonces queda documentado **cual es el limite real del plan gratuito** o por que no se pudo determinar
- Dado el resultado, cuando lo documento, entonces `docs/api-references.md` recoge la estrategia de suscripcion que usara `US-02`

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 4 h |
| Origen en el SRS | Riesgo R1 / RF-06 |
| Etiquetas | `spike,aisstream,riesgo` |

> **Creada el 01/09 (decision B8).** El riesgo R1 esta abierto desde el 19/08: la clave es valida pero no llegan datos, y la hipotesis es un tope del plan gratuito que **nadie ha medido**. Ninguno de los seis spikes de TG-10 probo el filtro por MMSI; los seis usaron `BoundingBoxes`.
>
> Importa mas de lo que parece: con suscripcion por area, un buque **deja de reportarse al salir del recuadro**, asi que el seguimiento se cortaria en medio del viaje. Va **antes de `US-02`**, que son 16 h construidas sobre esta decision.

#### US-01 — Asociar un identificador de rastreo externo a un pedido

Como usuario de Logística, quiero asociar a cada pedido su identificador de rastreo, para que el sistema pueda seguirlo automáticamente.

**Criterios de aceptación**

- Dado un pedido sin identificador, cuando registro un MMSI valido de nueve digitos, entonces el pedido queda habilitado para rastreo automatico
- Dado un pedido sin identificador, cuando consulto su estado, entonces es 'Sin tracking' conforme a RN-02
- Dado un tipo de identificador no soportado por ninguna API, cuando lo registro, entonces el sistema lo acepta y advierte que el pedido no sera rastreable automaticamente

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | RF-03 |
| Etiquetas | `backend,tracking` |

#### US-02 — Consumir posiciones AIS desde AISStream por WebSocket

Como sistema, quiero mantener una suscripción WebSocket a AISStream, para recibir las posiciones de los buques asociados a pedidos activos.

**Criterios de aceptación**

- Dada una clave de API valida, cuando abro la conexion y envio la suscripcion, entonces recibo mensajes PositionReport y los persisto
- Dado un mensaje ShipStaticData, cuando lo proceso, entonces persisto IMO, nombre y destino por separado de la posicion
- Dada una conexion establecida, cuando el socket se cae, entonces reconecto con backoff exponencial de 1s con techo de 60s
- Dado el cierre de la conexion, cuando termino la suscripcion, entonces aborto el transporte sin esperar el close negociado

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 16 h |
| Origen en el SRS | RF-06 |
| Etiquetas | `backend,aisstream,riesgo-externo` |

#### US-03 — Tolerar la caída de una API externa sin degradar el dashboard

Como sistema, quiero una politica de reintentos y un watchdog de conexion, para que la indisponibilidad de una fuente externa no afecte la consulta del usuario.

**Criterios de aceptación**

- Dada una API que no responde, cuando falla la consulta, entonces registro el error y conservo la ultima posicion valida con su antiguedad
- Dada una suscripcion AIS a una zona sin trafico, cuando pasan minutos sin mensajes, entonces el watchdog NO reconecta, porque se apoya en el ping/pong del protocolo y no en la ausencia de datos
- Dado un cierre inmediato tras conectar, cuando ocurre, entonces lo clasifico como problema de credencial y no reintento en bucle cerrado
- Dada una API caida, cuando consulto el dashboard, entonces responde con los ultimos datos conocidos

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-09 / RNF-12 |
| Etiquetas | `backend,resiliencia` |

#### US-04 — Registrar el historial de posiciones con el payload original

Como usuario de Logística, quiero que cada lectura de API quede registrada con su respuesta completa, para poder auditar y reconstruir el trayecto.

**Criterios de aceptación**

- Dada una lectura valida, cuando la proceso, entonces inserto un registro en historial_tracking con fecha, coordenadas, velocidad, rumbo, estado crudo y payload en JSONB
- Dado un registro del historial, cuando intento modificarlo, entonces la operacion se rechaza por ser inmutable
- Dado un volumen alto de mensajes, cuando aplico el submuestreo configurado, entonces persisto como maximo una posicion por elemento rastreado por intervalo
- Dado el parametro `intervalo_minimo_persistencia_s`, cuando lo modifico, entonces el intervalo cambia sin desplegar codigo (decision del 25/08: el crecimiento del historial se ataca con un parametro desde el Sprint 3, no subiendo TASK-10 de prioridad)

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-21 / RNF-13 |
| Etiquetas | `backend,persistencia,auditoria` |

#### TASK-11 — Actualizar el SRS con los hallazgos de los spikes tecnicos ✅ HECHA

Como estudiante practicante, quiero el SRS actualizado con lo aprendido en los spikes, para que la especificacion refleje la realidad tecnica verificada.

**Criterios de aceptación**

- Dado el SRS v0.3, cuando lo reviso, entonces incorpora las reglas RN-05 revisada y RN-16, y la limitacion de cobertura AIS
- Dado el historial de revisiones, cuando lo consulto, entonces registra la version v0.3 con su fecha y descripcion

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 6 h — **0 h pendientes** |
| Origen en el SRS | Fase 6 de TG-18 |
| Etiquetas | `documentacion,srs` |

> **Verificada como cumplida (24/08).** `docs/srs/SRS_TrackIn_v0.3.docx` (commit `11e9edd`) ya define RN-16, incorpora RN-05 revisada y registra la entrada v0.3 en el historial de revisiones con la limitacion de cobertura AIS. Ambos criterios de aceptacion se satisfacen; sus 6 h no se cuentan contra el Sprint 3.

#### TASK-19 — Diccionario de datos: usuarios

Como desarrollador, quiero documentar el diccionario de datos de usuarios/roles, para garantizar consistencia en la implementacion de la tabla.

**Criterios de aceptación**

- Dada la tabla usuarios, cuando documento el diccionario, entonces cada campo tiene tipo, restricciones y descripcion
- Dado el dominio de roles, cuando lo documento, entonces queda enumerado de forma explicita

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Should** |
| Estimacion | 2 h |
| Origen | Diseño OE1 / diccionario de datos (movida desde Sprint 2) |
| Etiquetas | `diseno,diccionario` |

#### TASK-23 — Consolidar el material de OE1 para el Informe 1

Como estudiante practicante, quiero consolidar los entregables de OE1 (SRS, modelo, diccionario, arquitectura y prototipos), para integrarlos al Primer Informe de Avance.

**Criterios de aceptación**

- Dados los entregables de OE1 (Sprints 1-2), cuando los consolido, entonces quedan con evidencias e integrados al borrador del Informe 1
- Dado el calendario academico, cuando lo reviso, entonces el Informe 1 se presenta el 25/09/2026 y abarca los Sprints 1, 2 y 3

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen | Hito Informe 1 (25/09/2026) — movida desde Sprint 2 |
| Etiquetas | `documentacion,informe1,hito` |

---

### Sprint 4 (21 sep - 2 oct 2026)

**7 items · 64 h estimadas · capacidad 65 h — dentro de capacidad**

#### US-05 — Consumir posiciones ADS-B desde OpenSky con OAuth2

Como sistema, quiero autenticarme con OAuth2 y consultar OpenSky, para obtener la posición de las aeronaves de los pedidos aéreos.

**Criterios de aceptación**

- Dadas credenciales validas, cuando solicito el token, entonces lo obtengo y lo renuevo proactivamente al 80% de su TTL de 1800 s
- Dado un bounding box, cuando consulto /states/all, entonces extraigo latitud, longitud, altitud, velocidad y rumbo de cada aeronave
- Dada una respuesta sin aeronaves, cuando la deserializo, entonces normalizo 'states: null' a lista vacia sin lanzar excepcion
- Dada cualquier respuesta, cuando la recibo, entonces registro el valor de x-rate-limit-remaining

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 10 h |
| Origen en el SRS | RF-07 |
| Etiquetas | `backend,opensky` |

#### US-06 — Resolver el icao24 de un vuelo como vínculo temporal del tramo

Como sistema, quiero resolver el icao24 a partir del callsign y la fecha en cada tramo, para no seguir una aeronave que ya vuela hacia otro destino con otra carga.

**Criterios de aceptación**

- Dado un pedido aéreo, cuando resuelvo su aeronave, entonces guardo el icao24 asociado al tramo y no como atributo fijo del pedido
- Dada una aeronave que cambio de vuelo, cuando finaliza el tramo, entonces el vinculo queda cerrado y no se sigue consultando
- Dado un callsign nulo en la lectura, cuando lo proceso, entonces uso el icao24 como identificador estable y reintento el callsign en la siguiente lectura

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-07 / spike TG-11 |
| Etiquetas | `backend,opensky` |

#### US-07 — Planificar las consultas periódicas con frecuencia parametrizable

Como administrador, quiero configurar la frecuencia de consulta por vía de transporte, para ajustar el consumo de cuota sin tocar el código.

**Criterios de aceptación**

- Dado el parámetro de frecuencia aerea, cuando lo modifico, entonces el planificador aplica el nuevo intervalo sin reiniciar el servicio
- Dado el rastreo aéreo por ventana activa, cuando estoy dentro de la ventana, entonces consulto al intervalo configurado y fuera de ella suspendo el sondeo
- Dado el rastreo marítimo, cuando lo configuro, entonces se gestiona como suscripcion persistente y no como sondeo periodico
- Dada la cuota diaria, cuando el consumo proyectado la excederia, entonces el planificador lo advierte en el log

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-08 (reformulado) |
| Etiquetas | `backend,scheduler` |

#### US-08 — Estimar la ETA a partir de la posición y la velocidad del buque

Como usuario de Compras, quiero que el sistema estime la ETA desde la posición actual, para no depender del campo de texto libre que declara la tripulación.

**Criterios de aceptación**

- Dada una posicion y una velocidad sobre tierra, cuando calculo la ETA, entonces uso la distancia PostGIS al destino dividida por la velocidad
- Dada una velocidad menor al minimo configurado, cuando calculo la ETA, entonces no la estimo y marco el pedido como 'ETA no estimable'
- Dada una ETA declarada por la fuente, cuando existe y es coherente, entonces registro ambas y la calculada es la que alimenta RN-01
- Dado el calculo, cuando lo consulto, entonces expone la distancia, la velocidad y la hora usadas para poder auditarlo

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RN-16 (nueva, Greivin) |
| Etiquetas | `backend,calculo,regla-nueva` |

#### US-09 — Calcular la fecha proyectada de disponibilidad

Como usuario de Planificacin, quiero la fecha proyectada de disponibilidad de cada pedido, para usarla como insumo del calculo de necesidades de materiales.

**Criterios de aceptación**

- Dado un pedido con ETA y destino con lead time, cuando ejecuto el calculo, entonces obtengo ETA mas lead time mas ajuste manual conforme a RN-01
- Dado un pedido con ATA confirmada, cuando calculo, entonces la ATA tiene precedencia sobre la ETA conforme a RN-14
- Dado un destino sin lead time definido, cuando calculo, entonces no produzco fecha proyectada y lo senalo

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | RF-10 / RN-01 |
| Etiquetas | `backend,calculo` |

#### US-10 — Determinar el estado logistico bajo el esquema de semaforo

Como usuario de Compras, quiero que cada pedido tenga su estado calculado automaticamente, para detectar de un vistazo cuales exigen atencion.

**Criterios de aceptación**

- Dado un pedido sin identificador, cuando evaluo su estado, entonces es 'Sin tracking' en gris
- Dada una fecha proyectada anterior o igual a la comprometida, cuando evaluo, entonces el estado es 'A tiempo' en verde
- Dada una fecha proyectada dentro del umbral de 48 h, cuando evaluo, entonces el estado es 'En riesgo' en naranja
- Dada una fecha proyectada posterior a la comprometida, cuando evaluo, entonces el estado es 'Retrasado' en rojo
- Dado el umbral de 48 h, cuando lo modifico en la tabla de parámetros, entonces el recalculo lo aplica sin desplegar codigo

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RF-11 / RN-02 a RN-11 |

> **Reglas desambiguadas el 26/08**, necesarias para implementar el motor:
> 1. **RN-08 prevalece sobre RN-07.** `A_TIEMPO` exige margen mayor que el umbral; dentro del umbral es `EN_RIESGO`.
> 2. **El umbral son 2 dias**, no 48 h, porque ambas fechas son `DATE` sin hora.
> 3. **`EN_DESTINO` dura `duracion_en_destino_minutos` (30 por defecto)** y luego pasa a `EN_PROCESO_ADUANAL`. Es la **unica transicion que dispara el tiempo** y no un dato nuevo: la barre el tic periodico del planificador de US-07, no US-12.
| Etiquetas | `backend,calculo,nucleo` |

#### US-11 — Inferir el arribo a destino por geocerca de proximidad

Como usuario de Logística, quiero que el sistema asuma el arribo cuando el buque entra en el radio del puerto, para no depender de que la fuente externa reporte la llegada.

**Criterios de aceptación**

- Dado un buque a menos del radio configurado (50 km por defecto) del destino, cuando evaluo su estado, entonces lo clasifico como 'En destino' conforme a RN-05
- Dado un buque dentro del radio pero con velocidad superior al umbral configurado, cuando evaluo, entonces NO lo doy por arribado, para descartar el trafico en transito hacia el Canal de Panama
- Dado el radio y el umbral de velocidad, cuando los modifico en la tabla de parámetros, entonces se aplican sin desplegar codigo
- Dado un elemento **aereo**, cuando evaluo su arribo, entonces uso el indicador `on_ground` de la fuente y no la geocerca, porque 50 km alrededor de un aeropuerto capturan trafico en sobrevuelo (decision del 25/08)
- Dado un destino con `radio_geocerca_km` propio, cuando evaluo la proximidad, entonces ese valor tiene precedencia sobre el parametro global
- Dado un arribo inferido, cuando lo registro, entonces queda marcado como inferido y no como confirmado por la fuente
- Dado un elemento rastreado cuyos pedidos han arribado todos, cuando cierro el arribo, entonces lo marco `activo = false` y el planificador deja de consultarlo (decision B7 del 01/09): la nave zarpa hacia otro puerto y su posicion deja de representar la carga, ademas de gastar cuota del plan gratuito

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RN-05 (revisada, Greivin) |
| Etiquetas | `backend,calculo,regla-nueva` |

---

### Sprint 5 (5-16 oct 2026)

**9 items · 66 h estimadas · capacidad 65 h — al limite.** US-40 entro el 01/09 (decision B4).

#### US-12 — Recalcular fecha y estado ante cualquier cambio de insumo

Como sistema, quiero recalcular automáticamente cuando cambie un insumo, para que el dashboard nunca muestre un estado obsoleto.

**Criterios de aceptación**

- Dada una nueva lectura de ETA, cuando la persisto, entonces se recalculan fecha proyectada y estado del pedido
- Dado un cambio de lead time en el maestro de destinos, cuando lo guardo, entonces se recalculan todos los pedidos activos de ese destino
- Dado un fallo al recalcular un pedido, cuando ocurre, entonces los demas pedidos se recalculan igual conforme a RNF-14

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-12 |
| Etiquetas | `backend,calculo` |

#### US-13 — Mantener el maestro de destinos y sus lead times

Como usuario de Logística, quiero administrar los destinos y su lead time en días, para que la fecha proyectada refleje la realidad de cada puerto.

**Criterios de aceptación**

- Dado un destino nuevo, cuando lo creo con via y lead time, entonces queda disponible para asociarse a pedidos
- Dado un lead time negativo o no numerico, cuando intento guardarlo, entonces el sistema lo rechaza e informa el formato esperado
- Dado un destino con pedidos activos, cuando intento desactivarlo, entonces el sistema advierte del impacto y pide confirmacion
- Dado un destino duplicado en nombre y via, cuando intento crearlo, entonces el sistema impide la duplicacion

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 10 h |
| Origen en el SRS | RF-23 / CU-06 |
| Etiquetas | `backend,maestros` |

#### US-14 — Confirmar manualmente el desembarco de un pedido

Como usuario de Logística, quiero registrar la llegada real de la carga, para corregir al sistema cuando la fuente automática no la reporta

**Criterios de aceptación**

- Dado un pedido no terminal, cuando registro la ATA con motivo, entonces la ATA prevalece sobre la ETA de la API conforme a RN-14
- Dada una fecha futura, cuando intento confirmarla, entonces el sistema la rechaza
- Dado un pedido con ATA ya confirmada, cuando la sobrescribo, entonces el sistema advierte y exige confirmacion explicita
- Dada la confirmacion, cuando se registra, entonces se recalculan fecha y estado y queda auditada

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 8 h |
| Origen en el SRS | RF-13 / CU-05 |

> **Sube de `Should` a `Must` el 01/09.** Confirmado que no se compran fuentes de datos de pago (B1), y el spike TG-10 probo que **no hay cobertura AIS gratuita en Moin**. Sin fuente satelital, el arribo al puerto de destino no se puede detectar automaticamente: esta historia deja de ser un respaldo del automatismo y pasa a ser el **unico mecanismo** que cierra ese paso del ciclo.
| Etiquetas | `backend,manual` |

#### US-15 — Auditar toda intervención manual sobre un pedido

Como supervisor, quiero la traza de cada cambio manual, para saber quien alteró un dato calculado y por que.

**Criterios de aceptación**

- Dada una intervencion manual, cuando se ejecuta, entonces se registra usuario, fecha, valor anterior, valor nuevo y motivo
- Dado un registro de auditoria, cuando intento alterarlo, entonces la operacion se rechaza
- Dado un pedido, cuando consulto su bitacora, entonces veo sus intervenciones en orden cronologico

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE4 |
| MoSCoW | **Should** |
| Estimacion | 8 h |
| Origen en el SRS | RF-14 / RNF-06 |
| Etiquetas | `backend,auditoria` |

#### US-16 — Exponer los pedidos y su detalle por API REST

Como frontend, quiero endpoints REST de listado y detalle de pedidos, para construir la grilla y la vista de detalle.

**Criterios de aceptación**

- Dado el endpoint de listado, cuando lo consulto con filtros y paginacion, entonces devuelve los pedidos con su estado calculado
- Dado el endpoint de detalle, cuando consulto un pedido, entonces devuelve datos maestros, rastreo, ultima posicion y desglose del calculo
- Dado un identificador inexistente, cuando lo consulto, entonces responde 404 con cuerpo de error descriptivo

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 10 h |
| Origen en el SRS | RF-04 / RF-05 (backend) |
| Etiquetas | `backend,api-rest` |

#### US-17 — Mantener credenciales, umbrales y frecuencias fuera del código

Como administrador, quiero configurar credenciales y umbrales sin tocar el codigo, para ajustar el sistema sin un nuevo despliegue.

**Criterios de aceptación**

- Dadas las credenciales de API, cuando reviso el repositorio, entonces no aparecen en el codigo fuente ni en el control de versiones
- Dado el umbral de 48 h, cuando lo modifico en la tabla de parámetros, entonces el proximo recalculo lo aplica
- Dado un parámetro ausente, cuando arranca el sistema, entonces falla de forma explicita indicando cual falta

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 6 h |
| Origen en el SRS | RF-24 / RNF-07 / RNF-15 |
| Etiquetas | `backend,configuracion` |

#### US-18 — Registrar la recepcion en planta y cerrar el pedido

Como usuario de Logística, quiero registrar la recepción efectiva en planta, para que el pedido pase a Cerrado y deje de consumir cuota de API.

**Criterios de aceptación**

- Dada una cantidad recibida dentro del margen del 10%, cuando la registro, entonces el pedido transita a 'Cerrado' conforme a RN-10
- Dada una cantidad por debajo del margen, cuando la registro, entonces el pedido NO se cierra y se ofrece el cierre forzado
- Dado un pedido cerrado, cuando corre el planificador, entonces no se consulta contra las APIs externas
- Dado un pedido cerrado, cuando calculo los KPIs, entonces no computa entre los pedidos activos

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 8 h |
| Origen en el SRS | RF-25 / RN-10 |
| Etiquetas | `backend,manual,ciclo-vida` |

#### US-40 — Ajustar manualmente la fecha proyectada de un pedido

Como usuario de Logistica, quiero sumar o restar dias a la fecha proyectada de un pedido, para reflejar informacion que el sistema no puede conocer por si solo.

**Criterios de aceptación**

- Dado el detalle de un pedido, cuando aplico un ajuste, entonces se guarda en `ajuste_manual_dias` y entra en la formula de RN-01 en el siguiente recalculo
- Dado un ajuste, cuando lo confirmo, entonces el dialogo exige un **motivo declarado** y la intervencion queda registrada en `auditoria_intervenciones` con tipo `AJUSTE_MANUAL`, conforme a RF-14
- Dado un ajuste ya aplicado, cuando lo modifico, entonces la auditoria conserva el valor anterior y el nuevo
- Dado el desglose del calculo, cuando reviso el pedido ajustado, entonces el ajuste aparece como sumando propio y no mezclado con el lead time (RF-05)

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 4 h |
| Origen en el SRS | RN-01 (ajuste manual) / RF-14 |
| Etiquetas | `backend,intervencion,auditoria` |

> **Creada el 01/09 (decision B4).** RN-01 define la fecha proyectada como «ETA o ATA, mas el lead time, mas un **ajuste manual opcional**». `US-09` lo usaba en la formula y `US-20` lo mostraba en el desglose, pero **ninguna historia permitia introducirlo**: el campo existia en el modelo y hasta habia un valor `AJUSTE_MANUAL` en la auditoria, sin pantalla que lo escribiera. El hueco aparecio al dibujar la barra de acciones de US-37.

#### TASK-04 — Publicar la documentación OpenAPI del backend

Como desarrollador, quiero la documentación OpenAPI generada automáticamente, para cumplir RNF-17 y facilitar el trabajo del frontend.

**Criterios de aceptación**

- Dado el backend en ejecucion, cuando accedo a /docs, entonces veo Swagger UI con todos los endpoints
- Dado un endpoint nuevo, cuando lo agrego, entonces aparece documentado sin escribir el esquema a mano

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 4 h |
| Origen en el SRS | RNF-17 |
| Etiquetas | `backend,documentacion` |

---

### Sprint 6 (19-30 oct 2026)

**8 items · 64 h estimadas · capacidad 65 h — dentro de capacidad.** US-37 volvio al Sprint 2 el 25/08 (US-38 la necesita) y US-28 llego desde el Sprint 7, al integrarse al dashboard en vez de ser una vista aparte.

#### TASK-05 — Andamiaje del frontend React con TypeScript, Vite y Tailwind

Como desarrollador, quiero el proyecto de frontend configurado, para empezar a construir vistas sobre una base estable.

**Criterios de aceptación**

- Dado el repositorio, cuando ejecuto el arranque de desarrollo, entonces la aplicacion carga sin errores de compilacion
- Dado el proyecto, cuando ejecuto las pruebas, entonces Vitest corre y reporta cobertura
- Dada la configuracion, cuando construyo para produccion, entonces genera el bundle sin advertencias bloqueantes

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | RNF (stack 5.8) |
| Etiquetas | `frontend,fundacional` |

#### US-19 — Listar los pedidos en transito en una grilla ordenable

Como usuario de Compras, quiero ver todos los pedidos en una grilla, para revisar el estado de mi cartera de un vistazo.

**Criterios de aceptación**

- Dado un conjunto de pedidos, cuando abro el dashboard, entonces veo OC, material, proveedor, via, destino, ETA, fecha proyectada, fecha comprometida y estado
- Dada la grilla, cuando ordeno por una columna, entonces los datos se reordenan sin recargar la pagina
- Dado un volumen de 200 pedidos, cuando cargo la vista, entonces se pagina y responde en menos de 3 segundos

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RF-04 / RNF-01 |

> **Validado el 01/09.** Confirmado por los usuarios: dos columnas de estado —etapa y cumplimiento—, la OC repetida en cada linea sin agrupar, y el guion como marca de «cumplimiento no evaluable» sin etiqueta adicional.
>
> **Criterio nuevo:** al filtrar por un estado terminal, la grilla sustituye `ETA` y `F. proyectada` por `F. recepcion` y `Cantidad recibida`, que es lo que importa de un pedido cerrado.
| Etiquetas | `frontend,grilla` |

#### US-20 — Consultar el detalle completo de un pedido

Como usuario de Logística, quiero ver el detalle de un pedido con el desglose del calculo, para entender por que tiene el estado que tiene.

**Criterios de aceptación**

- Dado un pedido, cuando abro su detalle, entonces veo datos maestros, identificador de rastreo, ultima posicion y fecha de la ultima consulta exitosa
- Dado el detalle, cuando reviso el calculo, entonces veo ETA, lead time y ajuste manual que produjeron la fecha proyectada
- Dado un pedido sin identificador, cuando abro su detalle, entonces se indica que no es rastreable y se ofrece asociar uno

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 10 h |
| Origen en el SRS | RF-05 / CU-03 |
| Etiquetas | `frontend,detalle` |

#### US-21 — Filtrar el dashboard de forma transversal y coherente

Como usuario de Compras, quiero filtrar por OC, proveedor, material, vía, estado y destino, para concentrarme en el subconjunto que me interesa.

**Criterios de aceptación**

- Dado un filtro aplicado, cuando se procesa, entonces la cinta de KPIs, la grilla y ambos mapas reflejan el mismo subconjunto
- Dada una combinacion sin resultados, cuando se aplica, entonces se muestra la vista vacia con la opcion de limpiar filtros
- Dado un filtro, cuando lo aplico, entonces la vista se actualiza en menos de 1 segundo y sin recarga completa

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RF-19 / CU-04 / RNF-02 |
| Etiquetas | `frontend,filtros` |

#### US-22 — Mostrar la cinta de indicadores KPI

Como gerencia de operaciones, quiero una cinta de indicadores agregados, para evaluar el desempeño de la cartera sin entrar al detalle.

**Criterios de aceptación**

- Dado un conjunto de pedidos, cuando cargo el dashboard, entonces veo pedidos activos, porcentaje a tiempo, en riesgo y retrasados, y lead time promedio
- Dado un filtro activo, cuando cambia, entonces los indicadores se recalculan sobre el subconjunto filtrado
- Dado un pedido en estado terminal, cuando calculo los KPIs, entonces no computa entre los activos

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-15 |
| Etiquetas | `frontend,kpi` |

#### US-23 — Indicar la frescura de los datos en el encabezado

Como usuario, quiero saber de cuando son los datos que estoy viendo, para juzgar si puedo confiar en ellos para decidir.

**Criterios de aceptación**

- Dado un ciclo de consulta ejecutado, cuando abro el dashboard, entonces el encabezado muestra la fecha y hora de la ultima actualizacion
- Dada una sincronizacion fallida, cuando ocurre, entonces el encabezado senala la incidencia y la antiguedad del ultimo dato valido

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Should** |
| Estimacion | 4 h |
| Origen en el SRS | RF-20 / RNF-12 |
| Etiquetas | `frontend,ux` |

#### US-24 — Aplicar el semáforo de estados de forma consistente

Como usuario sin formación técnica, quiero que el color signifique lo mismo en toda la interfaz, para interpretar el estado sin aprender convenciones.

**Criterios de aceptación**

- Dado un pedido en un estado, cuando lo veo en la grilla y en el mapa, entonces el color es el mismo en ambos
- Dados los siete estados de la seccion 7.2, cuando los represento, entonces cada uno usa el color que fija su regla de negocio
- Dada la paleta, cuando la reviso, entonces los colores mantienen contraste suficiente para lectura a distancia

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 4 h |
| Origen en el SRS | RNF-08 / RN-02 a RN-15 |
| Etiquetas | `frontend,ux` |

#### US-28 — Presentar los proximos arribos dentro del dashboard

Como usuario de Planificacion, quiero ver los cinco arribos mas cercanos **en el propio dashboard**, para anticipar que llega esta semana sin cambiar de vista.

**Criterios de aceptación**

- Dado el dashboard, cuando lo abro, entonces el bloque de proximos arribos aparece entre la cinta de KPIs y la grilla, conforme al orden que enumera RNF-01
- Dados pedidos con fecha proyectada, cuando se arma el bloque, entonces muestra los cinco mas proximos dentro de los siguientes 7 dias
- Dado que hay menos de cinco pedidos con fecha proyectada, cuando armo el bloque, entonces muestro los que haya, **sin rellenar** con pedidos ajenos al horizonte (RF-27 revisado el 01/09)
- Dado un filtro activo, cuando cambia, entonces el bloque responde al subconjunto filtrado igual que los KPIs y la grilla

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Should** |
| Estimacion | 8 h |
| Origen en el SRS | RF-27 / RNF-01 |
| Etiquetas | `frontend,dashboard` |

> **Reformulada y movida al Sprint 6 el 25/08.** Era una vista aparte en el Sprint 7. RNF-01 enumera la vista inicial como «cinta de KPIs, **vista de proximos arribos**, grilla y ambos mapas», de modo que el requisito no funcional ya la situaba dentro del dashboard. Se integra ahi y se agrupa con las demas historias del dashboard, que viven en el Sprint 6.

> **RF-27 se simplifico el 01/09.** En la sesion de validacion los usuarios pidieron **los cinco arribos mas proximos y nada mas**: se elimina el segundo nivel de la regla —rellenar con los de peor cumplimiento a 30 dias— y con el la necesidad de distinguir dos poblaciones. La historia se simplifica; `TASK-25` lleva el cambio al SRS.

---

### Sprint 7 (2-13 nov 2026)

**6 items · 54 h estimadas · capacidad 65 h — dentro de capacidad.** US-28 paso al Sprint 6 el 25/08, integrada al dashboard.

#### US-25 — Presentar el mapa interactivo marítimo con posiciones actuales

Como usuario de Logística, quiero ver mis buques en un mapa, para ubicar geograficámente la carga y su estado.

**Criterios de aceptación**

- Dados pedidos marítimos con posicion, cuando abro el mapa, entonces cada buque aparece como marcador coloreado por estado
- Dado un filtro activo, cuando cambia, entonces el mapa muestra solo los buques del subconjunto
- Dada una nave sin lectura reciente, cuando la represento, entonces la diferencio visualmente e indico la antiguedad del dato
- Dadas varias naves proximas, cuando se solapan, entonces se agrupan y se despliegan al acercar la vista

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RF-16 / CU-07 |
| Etiquetas | `frontend,mapas,leaflet` |

#### US-26 — Presentar el mapa interactivo aéreo separado del marítimo

Como usuario de Compras, quiero un mapa aéreo independiente, para seguir los embarques por avión sin mezclarlos con los marítimos.

**Criterios de aceptación**

- Dados pedidos aéreos con posicion, cuando abro el mapa aéreo, entonces cada aeronave aparece con el mismo esquema de color por estado
- Dado un vuelo finalizado que ya no emite, cuando lo represento, entonces muestro la ultima posicion e indico que el vuelo concluyo
- Dada una aeronave fuera de cobertura ADS-B, cuando la represento, entonces conservo la ultima posicion valida y senalo su antiguedad

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-17 / CU-08 |
| Etiquetas | `frontend,mapas,leaflet` |

#### US-27 — Mostrar información emergente en los marcadores del mapa

Como usuario, quiero ver los datos del pedido al posarme sobre su marcador, para obtener contexto sin salir del mapa.

**Criterios de aceptación**

- Dado un marcador, cuando poso el cursor o lo selecciono, entonces veo OC, material, proveedor, ETA, fecha proyectada y estado
- Dado un marcador seleccionado, cuando lo activo, entonces puedo navegar al detalle del pedido

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Could** |
| Estimacion | 6 h |
| Origen en el SRS | RF-18 (Media en SRS) |
| Etiquetas | `frontend,mapas` |

#### US-29 — Consultar el historial de tracking y dibujar el trayecto

Como usuario de Logística, quiero ver el recorrido histórico de un pedido, para reconstruir su viaje y auditar lo ocurrido.

**Criterios de aceptación**

- Dado un pedido con dos o mas posiciones, cuando abro su historial, entonces veo la secuencia cronologica en tabla y el trayecto sobre el mapa
- Dado un pedido con una sola posicion, cuando abro su historial, entonces se muestra el punto sin trazar trayecto
- Dado un registro del historial, cuando pido su detalle tecnico, entonces se muestra el payload original de la API

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Could** |
| Estimacion | 10 h |
| Origen en el SRS | RF-22 (Media en SRS) / CU-09 |

> **Se mantiene en `Could` (decision B3 del 01/09).** Se evaluo subirla porque el detalle de pedido ofrecia un enlace «ver historial» que ninguna historia comprometida construye. **Se resolvio al reves: se quita el enlace del detalle** y esta historia sigue siendo la valvula de escape del Sprint 7.
>
> Consecuencia para `US-20` y `US-37`: el conteo de posiciones plegadas se muestra como dato informativo, **sin accion asociada**. Si RF-22 se considera incumplido por eso, hay que reabrir la decision.
| Etiquetas | `frontend,mapas,auditoria` |

#### US-30 — Actualizar la nave asignada ante un transbordo

Como usuario de Logística, quiero sustituir la nave de un pedido cuando hay transbordo, para seguir rastreándolo en el tramo vigente.

**Criterios de aceptación**

- Dado un pedido marítimo con nave, cuando registro la nueva nave, el puerto y la fecha, entonces el rastreo pasa a la nave nueva
- Dado el tramo anterior, cuando se cierra, entonces su historial de posiciones se conserva asociado a ese tramo
- Dadas varias lineas de OC que comparten la nave anterior, cuando aplico el transbordo, entonces puedo aplicarlo en bloque
- Dado un identificador desconocido por la fuente AIS, cuando lo registro, entonces se acepta y se advierte que no habra lectura hasta que la fuente lo reporte

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 10 h |
| Origen en el SRS | RF-26 / CU-10 |
| Etiquetas | `backend,manual,tracking` |

#### TASK-10 — Política de retención y submuestreo del historial de posiciones

Como desarrollador, quiero una política de retención del historial, para que su crecimiento no degrade la consulta de pedidos activos.

**Criterios de aceptación**

- Dado el historial creciendo, cuando aplico la politica, entonces la consulta de pedidos activos mantiene su tiempo de respuesta
- Dado el submuestreo configurado, cuando lo modifico, entonces cambia la granularidad persistida sin desplegar codigo

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE4 |
| MoSCoW | **Could** |
| Estimacion | 8 h |
| Origen en el SRS | RNF-22 / spike TG-10 |
| Etiquetas | `persistencia,rendimiento,opcional` |

---

### Cierre (16-21 nov 2026)

**4 items · 30 h estimadas · capacidad 32 h — dentro de capacidad**

#### TASK-06 — Pruebas de integración extremo a extremo

Como desarrollador, quiero pruebas que recorran el flujo completo, para demostrar que el sistema opera de punta a punta.

**Criterios de aceptación**

- Dado un pedido semilla, cuando corre el flujo completo de ingesta, tracking, calculo y consulta, entonces el estado final es el esperado
- Dadas las reglas de calculo, cuando ejecuto su suite, entonces la cobertura de la seccion 7 del SRS supera el 70% conforme a RNF-18

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RNF-18 / Criterios seccion 10 |
| Etiquetas | `pruebas,cierre` |

#### TASK-07 — Manual de instalación local

Como técnico del Centro de Competencias, quiero un manual de instalación reproducible, para levantar el sistema en otro equipo.

**Criterios de aceptación**

- Dado un equipo limpio, cuando sigo el manual, entonces el sistema queda operativo sin consultar al autor
- Dado el manual, cuando lo reviso, entonces documenta la ejecucion nativa sin contenedores conforme a la seccion 9.3

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | Criterios seccion 10 |
| Etiquetas | `documentacion,cierre` |

#### TASK-08 — Manual de usuario del dashboard

Como usuario de Compras, quiero un manual de uso, para operar el dashboard sin capacitación previa.

**Criterios de aceptación**

- Dado el manual, cuando lo sigo, entonces puedo filtrar, consultar detalle y confirmar un desembarco
- Dado el manual, cuando lo reviso, entonces esta integramente en espanol conforme a RNF-09

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | RNF-10 / Criterios seccion 10 |
| Etiquetas | `documentacion,cierre` |

#### TASK-09 — Guía de despliegue para producción

Como técnico del Centro de Competencias, quiero la guía de despliegue, para asumir la puesta en producción tras la practica.

**Criterios de aceptación**

- Dada la guia, cuando la reviso, entonces documenta variables de entorno, dependencias y los artefactos de contenedor conservados
- Dada la guia, cuando la sigo, entonces identifico que queda fuera del alcance de la practica conforme a la seccion 1.2.2

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | Criterios seccion 10 |
| Etiquetas | `documentacion,cierre` |

---

### Riesgo R2 — resuelto el 03/09: la carga manual entra al alcance

**Las tres historias que estaban «Sin asignar» ya tienen sprint.** El 25/08 se registró que
SAP no tenía fecha y que, sin él, *no existía ninguna función de usuario que metiera pedidos
al sistema*. El 03/09 se tomó la decisión pendiente: **se formaliza la carga manual como
requerimiento** (`RF-31`), el archivo **Z-tracking pasa a ser la vía oficial de entrada** y la
sincronización con el servicio de SAP queda como **evolución futura, fuera del alcance de la
práctica**.

Con eso, el riesgo R2 **sale del camino crítico** y el backlog deja de tener deuda sin fecha.

#### `US-31` — Cargar los pedidos en tránsito desde el archivo Z-tracking · Sprint 4

Como usuario de Compras, quiero cargar el archivo Z-tracking en el sistema, para que los
pedidos entren sin mantenerlos a mano y sin depender de que SAP exponga un servicio.

**Criterios de aceptación**

- Dado un archivo Z-tracking, cuando lo cargo, entonces los pedidos nuevos se insertan y los existentes se actualizan **por OC y posición**
- Dado un pedido que ya no figura en el archivo, cuando cargo, entonces lo señalo para revisión manual y **NO** lo elimino
- Dada una carga, cuando termina, entonces informo recibidos, insertados, actualizados y rechazados
- Dadas las hojas del archivo, cuando lo proceso, entonces solo tomo **PRODUCCION e IDA** (alcance del 03/09)
- Dadas las fechas en formato serial de Excel, cuando las leo, entonces las convierto a fecha ISO

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 14 h |
| Origen en el SRS | `RF-31` carga manual (03/09) · RF-01 · CU-01 |
| Etiquetas | `backend,ingesta,carga-manual` |

> Reemplaza a la sincronización con el API de SAP, que pasa a evolución futura. La muestra
> real anonimizada (`docs/analisis/2026-Agosto-WK36_anonimizado.csv`) sirve de caso de prueba.

#### `US-32` — Validar y normalizar los datos del Z-tracking antes de persistirlos · Sprint 4

Como sistema, quiero validar y normalizar cada registro, para que un dato malo no contamine
la base ni aborte la carga completa.

**Criterios de aceptación**

- Dado un registro sin OC, posición o material, cuando lo valido, entonces lo rechazo con su motivo y sigo con el resto del lote
- Dado `USA` y `ESTADOS UNIDOS`, cuando normalizo, entonces ambos resuelven al mismo país del maestro (`TASK-29`)
- Dado un valor no resoluble (`PENDIENTE`, `N/A`, fuera de catálogo), cuando lo proceso, entonces marco la línea para revisión **sin abortar el lote** (RN-17)
- Dada la vía de transporte con ruido (`INDIA`, `AEREO/MARITIMO`), cuando la normalizo, entonces resuelve a {Aéreo, Marítimo, Terrestre} o a revisión
- Dada una referencia de embarque presente, cuando la valido, entonces verifico su formato según `TASK-30`
- Dada la carga, cuando termina, entonces queda un informe de validación con cada rechazo y su clave de origen

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 10 h |
| Origen en el SRS | RF-02 · RN-17 (nueva, 03/09) |
| Etiquetas | `backend,ingesta,validacion,normalizacion` |

#### `US-33` — Habilitar el modo de visualización permanente en pantalla grande · Sprint 7

Como usuario de planta, quiero una vista permanente en pantalla grande, para seguir el estado
de los pedidos sin interactuar con el sistema.

**Criterios de aceptación**

- Dada la pantalla de planta, cuando se abre, entonces muestra la **vista simple** de `US-43` (material, etapa y cumplimiento)
- Dada la vista, cuando pasa el tiempo, entonces se refresca sola sin recargar la página (RNF-02)
- Dada la sesión, cuando la pantalla queda desatendida, entonces se aplica la política de inactividad de `US-42`

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE3 |
| MoSCoW | **Could** |
| Estimacion | 6 h |
| Origen en el SRS | RNF-11 · vista simple de `US-43` |
| Etiquetas | `frontend,ux,pantalla-planta` |

> **Desbloqueada el 03/09.** Ya no depende de definir qué mostrar: la vista simple lo resuelve.
> Solo queda pendiente la resolución física de la pantalla, que es un detalle de maquetación.

---

## Cambios de la reunión con Logística (03/09/2026)

Entrega del **Z-tracking** (`docs/analisis/2026-Agosto-WK36.xlsx`) y cierre de dudas.
Las decisiones que reabre están anotadas en
[`dudas_sesion_validacion.md`](dudas_sesion_validacion.md) (addendum 03/09).

### `US-41` — Wireframe del login ✅ HECHA

Como equipo, queremos un wireframe del login para maquetar la autenticación que
Logística pidió, para validar la entrada y el enrutado por rol antes de construirla.

**Criterios de aceptación**

- Dado el wireframe, cuando lo reviso, entonces muestra usuario, contraseña, «recordar sesión», enlace de olvido y botón Entrar, en baja fidelidad y escala de grises
- Dado el wireframe, cuando reviso el post-login, entonces documenta el enrutado **rol → vista** (simple vs completa) y las decisiones abiertas (bloqueo, sesión, olvido)

> **Completada el 03/09.** Sección `00 · Autenticación` en `docs/design/wireframes.html` y §0 en `docs/design/wireframes.md`. Falta el frame de Figma.

### `TASK-28` — Spike: container tracking de pago

Como equipo, queremos medir la cobertura de **container tracking** de pago
(`Vizion`, con `Terminal49` / `ShipsGo` como alternativas) en **Moín (`CRMOB`)** y de una
fuente **aérea por AWB** (`Portcast` / `ShipsGo Air` / `TrackingMore`) en **SJO**, para
decidir si resuelven el tramo final y el punto ciego de AIS antes de comprometer la
arquitectura de rastreo.

**Criterios de aceptación**

- Dado un BL/booking/contenedor real, cuando consulto el API, entonces obtengo eventos de milestone hasta el arribo a Moín, o se documenta la ausencia de cobertura
- Dado un **MAWB** real de India o China a SJO, cuando consulto el API aéreo, entonces obtengo los hitos de carga (no la posición de la aeronave)
- Dado que el forwarder puede entregar un **HAWB**, cuando lo consulto, entonces documento si resuelve o si hace falta exigir el MAWB
- Dado el resultado, cuando lo registro, entonces queda un `output/` con evidencia y una recomendación go/no-go y de costo, al estilo de TG-10 y TG-11

> **Revierte la decisión abierta #3 / B1.** Se dio luz verde a fuentes de datos de pago (03/09).

### `TASK-29` — Maestro de países y normalización de la ingesta

Como desarrollador, quiero un **maestro de países** y una capa de normalización de
`país`, `vía`, `incoterm` y `temperatura`, para que la carga (RF-02) convierta el
texto libre sucio del Z-tracking en valores de dominio fiables.

**Criterios de aceptación**

- Dado el Z-tracking con `USA` y `ESTADOS UNIDOS`, cuando lo cargo, entonces ambos resuelven al mismo país del maestro (ISO)
- Dado un valor no reconocido (`PENDIENTE`, `N/A`, país fuera del maestro), cuando lo cargo, entonces la línea se marca para revisión sin abortar el lote
- Dado el campo `vía` con ruido (`INDIA`, `AEREO/MARITIMO`), cuando lo normalizo, entonces resuelve a {Aéreo, Marítimo, Terrestre} o a revisión

### `US-42` — Autenticación con login, sesión y roles

Como usuario, quiero iniciar sesión con usuario y contraseña, para que el sistema me
identifique, restrinja las operaciones según mi rol y registre la autoría de mis
intervenciones.

**Criterios de aceptación**

- Dadas credenciales válidas, cuando entro, entonces se crea una sesión y `auditoria_intervenciones.id_usuario` se llena **de la sesión**, no de un selector manual (revisa B5)
- Dado mi rol (Compras, Logística, Planificación o **Administrador**), cuando opero, entonces solo el Administrador mantiene cuentas y solo los autorizados confirman/mantienen maestros (RNF-05)
- Dadas credenciales inválidas, cuando fallo, entonces el mensaje es genérico y se cuenta el intento
- Dada la pantalla de planta, cuando pasa el tiempo de inactividad, entonces la sesión cierra

> Sin SSO/Active Directory: mecanismo propio (RNF-05 ampliado). **Revierte B9:** el rol Administrador entra porque, con login, el rol sí restringe.

### `US-43` — Dos vistas de la grilla según el rol

Como usuario, quiero que la grilla se ajuste a mi rol, para ver solo lo que me compete:
una **vista simple** (Material · Etapa · Cumplimiento) o la **vista completa**.

**Criterios de aceptación**

- Dado un rol de Planificación / pantalla de planta, cuando abro el dashboard, entonces la grilla muestra solo Material, Etapa y Cumplimiento
- Dado un rol de Compras o Logística, cuando abro el dashboard, entonces la grilla muestra la actual **más deliveries, departures, ETD y ATD**
- Dado que ETD/ATD no vienen del Z-tracking, cuando los muestro, entonces provienen del rastreo (US-08/US-11) o de la fuente de container tracking (TASK-28) — **fuente por confirmar**

### `US-44` — País de origen y mapa del pedido en el detalle

Como usuario, quiero ver en el detalle el **país de origen** del pedido y un **mapa de
seguimiento** de ese envío en particular, para saber de dónde viene y por dónde va.

**Criterios de aceptación**

- Dado un pedido, cuando abro su detalle, entonces muestra el país de origen normalizado (maestro de TASK-29)
- Dado un pedido con posición, cuando abro su detalle, entonces muestra un mapa centrado en ese envío con su última posición y, si existe, su trayecto (depende de US-29/RF-22)

### `TASK-30` — Contrato de captura de la referencia de embarque

Como equipo, queremos definir por escrito qué referencia se captura por envío, en qué formato
y quién la provee, para que Logística la registre de forma utilizable y la carga pueda
validarla. **Es el prerrequisito de todo el rastreo: sin referencia, ninguna API devuelve nada.**

**Criterios de aceptación**

- Dado el documento, cuando lo reviso, entonces define los tipos admitidos: **contenedor** (ISO 6346, 4 letras + 7 dígitos), **BL máster**, **booking** y **MAWB** (11 dígitos con prefijo de aerolínea)
- Dado el caso aéreo, cuando lo documento, entonces deja explícito que **el HAWB del agente de carga no resuelve** y que hay que exigir el MAWB o su correspondencia
- Dado el incoterm, cuando lo documento, entonces indica quién posee la referencia: el agente de Gutis en `EXW`/`FOB`/`FCA` (56 OC) y el proveedor en `CIF`/`CIP`/`CPT` (71 OC)
- Dado el contrato, cuando se entrega, entonces Logística puede añadir las columnas al Z-tracking y `US-32` puede validar el formato

| | |
|---|---|
| Tipo | Task |
| Objetivo específico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 3 h |
| Origen | Reunión con Logística, 03/09/2026 |
| Etiquetas | `analisis,ingesta,referencia,prerrequisito` |

> El Z-tracking no contiene **ninguna** referencia legible por máquina en sus 429 líneas, pero
> los comentarios del comprador dicen «BL recibido»: el dato existe en el proceso y se pierde
> por falta de un campo. Esta tarea cierra ese hueco.

### `US-45` — Integrar la fuente comercial de rastreo marítimo 🔀

Como sistema, quiero consultar la fuente comercial por contenedor o BL, para obtener los hitos
y la posición del envío sin depender del AIS gratuito.

**Criterios de aceptación**

- Dada una referencia marítima válida, cuando consulto la fuente, entonces obtengo los hitos normalizados y los mapeo a las etapas de RN-02 a RN-06
- Dada la respuesta, cuando la persisto, entonces guardo el **payload original** en `historial_tracking` (RF-21 / RNF-13)
- Dada una respuesta con buque, cuando la proceso, entonces relleno `elementos_rastreados` con nombre, IMO y MMSI
- Dado un envío con posición, cuando la registro, entonces alimenta el mapa marítimo con su antigüedad (RF-20)
- Dada la fuente caída, cuando falla, entonces conservo la última lectura y señalo la antigüedad, sin degradar el dashboard (RF-09)

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** (solo en Plan A) |
| Estimacion | 12 h |
| Origen | Plan A de `TASK-28`, reunión 03/09 |
| Etiquetas | `backend,tracking,api-pago,plan-a` |

### `US-46` — Integrar el rastreo aéreo por guía aérea (MAWB) 🔀

Como sistema, quiero consultar los hitos de carga aérea por MAWB, para conocer el estado real
del envío y no solo la posición de la aeronave.

**Criterios de aceptación**

- Dado un MAWB válido, cuando consulto la fuente, entonces obtengo los hitos de carga y los mapeo a las etapas del semáforo
- Dados los hitos, cuando los proceso, entonces extraigo **ETD y ATD** para la vista completa de `US-43`
- Dado un envío partido en varias entregas, cuando lo rastreo, entonces la etapa refleja el estado de cada parte y no solo de la primera
- Dado un HAWB en vez de un MAWB, cuando la consulta no resuelve, entonces lo señalo para revisión con un motivo claro
- Dada la vía aérea, cuando la presento, entonces uso una **línea de tiempo de hitos**; la posición de la aeronave es opcional y no bloquea

| | |
|---|---|
| Tipo | Story |
| Objetivo específico | OE2 |
| MoSCoW | **Must** (solo en Plan A) |
| Estimacion | 10 h |
| Origen | Plan A de `TASK-28`, reunión 03/09 |
| Etiquetas | `backend,tracking,aereo,awb,plan-a` |

---

## La bifurcación de `TASK-28`

`TASK-28`, en el Sprint 3, decide si se compra la fuente comercial de rastreo. **Es el único
punto donde este backlog debería volver a cambiar.** Las historias marcadas 🔀 dependen de su
resultado.

### Plan A — se compra

| Historia | Efecto |
|---|---|
| `US-45` Rastreo marítimo comercial | **Entra** (12 h) |
| `US-46` Rastreo aéreo por MAWB | **Entra** (10 h) |
| `US-02` Consumir AIS por WebSocket | Se **reduce**: el AIS deja de ser fuente primaria y queda de respaldo del mapa (16 h → ~6 h) |
| `US-08` Estimar la ETA desde posición y velocidad | Pasa a **`Could`**: la fuente ya entrega ETA; RN-16 queda como respaldo |
| `US-11` Inferir el arribo por geocerca | Se **simplifica**: el hito de descarga lo da la fuente (8 h → ~4 h) |
| `TASK-27` Spike de cuota de AISStream | Se **cancela** |
| `US-14` Confirmar el desembarco a mano | Baja de `Must` a `Should` si la fuente confirma el arribo (revisa la decisión B2) |

**Balance: +22 h de integración contra −34 h de cálculo propio.** Cuadra sin sobrecargar el plan.

### Plan B — no se compra

Todo queda como está: AIS gratuito y OpenSky como fuentes primarias, `US-08` y `US-11` se
construyen completas, `US-14` sigue `Must` como única vía de confirmar el arribo, y `US-45` y
`US-46` **no entran**. El riesgo **R1** (sin cobertura AIS en Moín) sigue abierto y el tramo
final se confirma a mano indefinidamente.

### Criterio de decisión

El spike debe responder tres cosas antes de que cierre el Sprint 3:

1. ¿La fuente devuelve hitos hasta la **descarga en Moín** con un BL real?
2. ¿Cubre las **aerolíneas** del tramo India/China → SJO con un MAWB real?
3. ¿En qué **porcentaje** de los embarques se consigue la referencia, y con **cuántos días de antelación** al arribo?

**La tercera es la que manda.** Si la referencia llega tres días antes de que la carga atraque,
ninguna API vale lo que cuesta, y el Plan B deja de ser el peor escenario para ser el correcto.

---

## Cierre del Sprint 2 — 4 de septiembre de 2026

**20 de 20 items completados · 93 h.** Cierra el Objetivo Específico 1 (análisis y diseño):

- **Modelo de datos:** diez entidades modeladas y su diccionario completo (`TASK-12` a `TASK-18`, `TASK-24`, `TASK-26`).
- **Arquitectura:** vistas de componentes, despliegue nativo y secuencia (`TASK-20` a `TASK-22`).
- **Prototipos:** wireframes de dashboard, ambos mapas, detalle y **login** (`US-34` a `US-37`, `US-41`), prototipo navegable en Figma (`US-38`) y validación con usuarios clave (`US-39`).
- **SRS v0.4** emitido con las decisiones del 25/08 y del 03/09 (`TASK-25`).

Entra al Sprint 3 con el backlog congelado y sin historias bloqueadas por insumo externo.

