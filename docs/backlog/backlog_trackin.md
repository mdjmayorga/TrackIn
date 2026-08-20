# Product Backlog - TrackIn (TG-18)

Derivado del SRS v0.2 y de los spikes tecnicos TG-10 (AISStream) y TG-11 (OpenSky). Priorizado con MoSCoW.

**Generado:** 20 de agosto de 2026 · **Ejecutor:** 1 persona a tiempo completo

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
| `TASK-01` | Esquema de base de datos y migraciones Alembic | Task | OE4 | **Must** | Sprint 3 | 10h | SRS 8.1-8.5 |
| `TASK-02` | Habilitar PostGIS y columna geometrica WGS 84 | Task | OE4 | **Must** | Sprint 3 | 4h | SRS 8.6 / RNF-20 |
| `TASK-03` | Adaptador de ingesta de pedidos con datos semilla | Task | OE2 | **Must** | Sprint 3 | 8h | Habilitador de RF-01 |
| `US-01` | Asociar un identificador de rastreo externo a un pedido | Story | OE2 | **Must** | Sprint 3 | 6h | RF-03 |
| `US-02` | Consumir posiciones AIS desde AISStream por WebSocket | Story | OE2 | **Must** | Sprint 3 | 16h | RF-06 |
| `US-03` | Tolerar la caida de una API externa sin degradar el dashboard | Story | OE2 | **Must** | Sprint 3 | 8h | RF-09 / RNF-12 |
| `US-04` | Registrar el historial de posiciones con el payload original | Story | OE4 | **Must** | Sprint 3 | 8h | RF-21 / RNF-13 |
| `US-05` | Consumir posiciones ADS-B desde OpenSky con OAuth2 | Story | OE2 | **Must** | Sprint 4 | 10h | RF-07 |
| `US-06` | Resolver el icao24 de un vuelo como vinculo temporal del tramo | Story | OE2 | **Must** | Sprint 4 | 8h | RF-07 / spike TG-11 |
| `US-07` | Planificar las consultas periodicas con frecuencia parametrizable | Story | OE2 | **Must** | Sprint 4 | 8h | RF-08 (reformulado) |
| `US-08` | Estimar la ETA a partir de la posicion y la velocidad del buque | Story | OE2 | **Must** | Sprint 4 | 12h | RN-16 (nueva, Greivin) |
| `US-09` | Calcular la fecha proyectada de disponibilidad | Story | OE2 | **Must** | Sprint 4 | 6h | RF-10 / RN-01 |
| `US-10` | Determinar el estado logistico bajo el esquema de semaforo | Story | OE2 | **Must** | Sprint 4 | 12h | RF-11 / RN-02 a RN-11 |
| `US-11` | Inferir el arribo a destino por geocerca de proximidad | Story | OE2 | **Must** | Sprint 4 | 8h | RN-05 (revisada, Greivin) |
| `US-12` | Recalcular fecha y estado ante cualquier cambio de insumo | Story | OE2 | **Must** | Sprint 5 | 8h | RF-12 |
| `US-13` | Mantener el maestro de destinos y sus lead times | Story | OE2 | **Must** | Sprint 5 | 10h | RF-23 / CU-06 |
| `US-14` | Confirmar manualmente el desembarco de un pedido | Story | OE2 | **Should** | Sprint 5 | 8h | RF-13 / CU-05 |
| `US-15` | Auditar toda intervencion manual sobre un pedido | Story | OE4 | **Should** | Sprint 5 | 8h | RF-14 / RNF-06 |
| `US-16` | Exponer los pedidos y su detalle por API REST | Story | OE2 | **Must** | Sprint 5 | 10h | RF-04 / RF-05 (backend) |
| `US-17` | Mantener credenciales, umbrales y frecuencias fuera del codigo | Story | OE2 | **Should** | Sprint 5 | 6h | RF-24 / RNF-07 / RNF-15 |
| `US-18` | Registrar la recepcion en planta y cerrar el pedido | Story | OE2 | **Should** | Sprint 5 | 8h | RF-25 / RN-10 |
| `TASK-04` | Publicar la documentacion OpenAPI del backend | Task | OE2 | **Should** | Sprint 5 | 4h | RNF-17 |
| `TASK-05` | Andamiaje del frontend React con TypeScript, Vite y Tailwind | Task | OE3 | **Must** | Sprint 6 | 6h | RNF (stack 5.8) |
| `US-19` | Listar los pedidos en transito en una grilla ordenable | Story | OE3 | **Must** | Sprint 6 | 12h | RF-04 / RNF-01 |
| `US-20` | Consultar el detalle completo de un pedido | Story | OE3 | **Must** | Sprint 6 | 10h | RF-05 / CU-03 |
| `US-21` | Filtrar el dashboard de forma transversal y coherente | Story | OE3 | **Must** | Sprint 6 | 12h | RF-19 / CU-04 / RNF-02 |
| `US-22` | Mostrar la cinta de indicadores KPI | Story | OE3 | **Must** | Sprint 6 | 8h | RF-15 |
| `US-23` | Indicar la frescura de los datos en el encabezado | Story | OE3 | **Should** | Sprint 6 | 4h | RF-20 / RNF-12 |
| `US-24` | Aplicar el semaforo de estados de forma consistente | Story | OE3 | **Must** | Sprint 6 | 4h | RNF-08 / RN-02 a RN-15 |
| `US-25` | Presentar el mapa interactivo maritimo con posiciones actuales | Story | OE3 | **Must** | Sprint 7 | 12h | RF-16 / CU-07 |
| `US-26` | Presentar el mapa interactivo aereo separado del maritimo | Story | OE3 | **Must** | Sprint 7 | 8h | RF-17 / CU-08 |
| `US-27` | Mostrar informacion emergente en los marcadores del mapa | Story | OE3 | **Could** | Sprint 7 | 6h | RF-18 (Media en SRS) |
| `US-28` | Presentar la vista de proximos arribos | Story | OE3 | **Should** | Sprint 7 | 8h | RF-27 |
| `US-29` | Consultar el historial de tracking y dibujar el trayecto | Story | OE3 | **Could** | Sprint 7 | 10h | RF-22 (Media en SRS) / CU-09 |
| `US-30` | Actualizar la nave asignada ante un transbordo | Story | OE2 | **Should** | Sprint 7 | 10h | RF-26 / CU-10 |
| `TASK-06` | Pruebas de integracion extremo a extremo | Task | OE4 | **Must** | Cierre | 12h | RNF-18 / Criterios seccion 10 |
| `TASK-07` | Manual de instalacion local | Task | OE4 | **Must** | Cierre | 6h | Criterios seccion 10 |
| `TASK-08` | Manual de usuario del dashboard | Task | OE4 | **Must** | Cierre | 6h | RNF-10 / Criterios seccion 10 |
| `TASK-09` | Guia de despliegue para produccion | Task | OE4 | **Must** | Cierre | 6h | Criterios seccion 10 |
| `US-31` | Sincronizar los pedidos en transito desde el servicio API de SAP 🔒 | Story | OE2 | **Should** | Sin asignar | 16h | RF-01 / CU-01 |
| `US-32` | Validar los datos recibidos de SAP antes de persistirlos 🔒 | Story | OE2 | **Should** | Sin asignar | 10h | RF-02 / CU-01 |
| `US-33` | Habilitar el modo de visualizacion permanente en pantalla grande 🔒 | Story | OE3 | **Could** | Sin asignar | 6h | RNF-11 |
| `TASK-10` | Politica de retencion y submuestreo del historial de posiciones | Task | OE4 | **Could** | Sprint 7 | 8h | RNF-22 / spike TG-10 |
| `TASK-11` | Actualizar el SRS con los hallazgos de los spikes tecnicos | Task | OE1 | **Must** | Sprint 3 | 6h | Fase 6 de TG-18 |

🔒 = bloqueada por insumo externo

---

## Detalle por sprint

### Sprint 3 (7-18 sep 2026)

**8 items · 66 h estimadas · capacidad 65 h — SOBRECARGADO**

#### TASK-01 — Esquema de base de datos y migraciones Alembic

Como desarrollador, quiero el esquema relacional de las siete entidades versionado en Alembic, para que el resto del backend tenga sobre que construir.

**Criterios de aceptacion**

- Dado el repositorio limpio, cuando ejecuto 'alembic upgrade head', entonces se crean las siete entidades de la seccion 8.1 del SRS sin error
- Dado el esquema aplicado, cuando inspecciono pedidos_transito, entonces existen los campos de la seccion 8.2 con sus tipos
- Dado el esquema aplicado, cuando ejecuto 'alembic downgrade base', entonces la base queda vacia sin error

| | |
|---|---|
| Tipo | Task |
| Objetivo especifico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 10 h |
| Origen en el SRS | SRS 8.1-8.5 |
| Etiquetas | `backend,persistencia,fundacional` |

#### TASK-02 — Habilitar PostGIS y columna geometrica WGS 84

Como desarrollador, quiero PostGIS habilitado y la posicion almacenada como geometry(Point,4326), para poder calcular distancias con operadores nativos.

**Criterios de aceptacion**

- Dado PostgreSQL 16, cuando ejecuto la migracion, entonces la extension postgis queda instalada
- Dado elementos_rastreados, cuando consulto posicion_actual, entonces su tipo es geometry(Point,4326)
- Dadas dos posiciones conocidas, cuando aplico ST_Distance sobre geography, entonces la distancia en metros coincide con el valor esperado con margen del 1%

| | |
|---|---|
| Tipo | Task |
| Objetivo especifico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 4 h |
| Origen en el SRS | SRS 8.6 / RNF-20 |
| Etiquetas | `backend,persistencia,postgis` |

#### TASK-03 — Adaptador de ingesta de pedidos con datos semilla

Como desarrollador, quiero una interfaz de ingesta con una implementacion de datos semilla, para desarrollar y demostrar el sistema sin depender del servicio de SAP.

**Criterios de aceptacion**

- Dado que no existe el servicio de SAP, cuando arranco el sistema con el perfil de desarrollo, entonces se cargan pedidos semilla que cubren via maritima, via aerea y un caso sin identificador de rastreo
- Dada la interfaz de ingesta, cuando se implemente el adaptador de SAP, entonces no requiere cambios en el motor de calculo ni en la API REST
- Dado el perfil de produccion, cuando no hay adaptador configurado, entonces el sistema arranca y lo reporta en el healthcheck

| | |
|---|---|
| Tipo | Task |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | Habilitador de RF-01 |
| Etiquetas | `backend,ingesta,riesgo-sap` |

#### US-01 — Asociar un identificador de rastreo externo a un pedido

Como usuario de Logistica, quiero asociar a cada pedido su identificador de rastreo, para que el sistema pueda seguirlo automaticamente.

**Criterios de aceptacion**

- Dado un pedido sin identificador, cuando registro un MMSI valido de nueve digitos, entonces el pedido queda habilitado para rastreo automatico
- Dado un pedido sin identificador, cuando consulto su estado, entonces es 'Sin tracking' conforme a RN-02
- Dado un tipo de identificador no soportado por ninguna API, cuando lo registro, entonces el sistema lo acepta y advierte que el pedido no sera rastreable automaticamente

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | RF-03 |
| Etiquetas | `backend,tracking` |

#### US-02 — Consumir posiciones AIS desde AISStream por WebSocket

Como sistema, quiero mantener una suscripcion WebSocket a AISStream, para recibir las posiciones de los buques asociados a pedidos activos.

**Criterios de aceptacion**

- Dada una clave de API valida, cuando abro la conexion y envio la suscripcion, entonces recibo mensajes PositionReport y los persisto
- Dado un mensaje ShipStaticData, cuando lo proceso, entonces persisto IMO, nombre y destino por separado de la posicion
- Dada una conexion establecida, cuando el socket se cae, entonces reconecto con backoff exponencial de 1s con techo de 60s
- Dado el cierre de la conexion, cuando termino la suscripcion, entonces aborto el transporte sin esperar el close negociado

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 16 h |
| Origen en el SRS | RF-06 |
| Etiquetas | `backend,aisstream,riesgo-externo` |

#### US-03 — Tolerar la caida de una API externa sin degradar el dashboard

Como sistema, quiero una politica de reintentos y un watchdog de conexion, para que la indisponibilidad de una fuente externa no afecte la consulta del usuario.

**Criterios de aceptacion**

- Dada una API que no responde, cuando falla la consulta, entonces registro el error y conservo la ultima posicion valida con su antiguedad
- Dada una suscripcion AIS a una zona sin trafico, cuando pasan minutos sin mensajes, entonces el watchdog NO reconecta, porque se apoya en el ping/pong del protocolo y no en la ausencia de datos
- Dado un cierre inmediato tras conectar, cuando ocurre, entonces lo clasifico como problema de credencial y no reintento en bucle cerrado
- Dada una API caida, cuando consulto el dashboard, entonces responde con los ultimos datos conocidos

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-09 / RNF-12 |
| Etiquetas | `backend,resiliencia` |

#### US-04 — Registrar el historial de posiciones con el payload original

Como usuario de Logistica, quiero que cada lectura de API quede registrada con su respuesta completa, para poder auditar y reconstruir el trayecto.

**Criterios de aceptacion**

- Dada una lectura valida, cuando la proceso, entonces inserto un registro en historial_tracking con fecha, coordenadas, velocidad, rumbo, estado crudo y payload en JSONB
- Dado un registro del historial, cuando intento modificarlo, entonces la operacion se rechaza por ser inmutable
- Dado un volumen alto de mensajes, cuando aplico el submuestreo configurado, entonces persisto como maximo una posicion por elemento rastreado por intervalo

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-21 / RNF-13 |
| Etiquetas | `backend,persistencia,auditoria` |

#### TASK-11 — Actualizar el SRS con los hallazgos de los spikes tecnicos

Como estudiante practicante, quiero el SRS actualizado con lo aprendido en los spikes, para que la especificacion refleje la realidad tecnica verificada.

**Criterios de aceptacion**

- Dado el SRS v0.3, cuando lo reviso, entonces incorpora las reglas RN-05 revisada y RN-16, y la limitacion de cobertura AIS
- Dado el historial de revisiones, cuando lo consulto, entonces registra la version v0.3 con su fecha y descripcion

| | |
|---|---|
| Tipo | Task |
| Objetivo especifico | OE1 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | Fase 6 de TG-18 |
| Etiquetas | `documentacion,srs` |

---

### Sprint 4 (21 sep - 2 oct 2026)

**7 items · 64 h estimadas · capacidad 65 h — dentro de capacidad**

#### US-05 — Consumir posiciones ADS-B desde OpenSky con OAuth2

Como sistema, quiero autenticarme con OAuth2 y consultar OpenSky, para obtener la posicion de las aeronaves de los pedidos aereos.

**Criterios de aceptacion**

- Dadas credenciales validas, cuando solicito el token, entonces lo obtengo y lo renuevo proactivamente al 80% de su TTL de 1800 s
- Dado un bounding box, cuando consulto /states/all, entonces extraigo latitud, longitud, altitud, velocidad y rumbo de cada aeronave
- Dada una respuesta sin aeronaves, cuando la deserializo, entonces normalizo 'states: null' a lista vacia sin lanzar excepcion
- Dada cualquier respuesta, cuando la recibo, entonces registro el valor de x-rate-limit-remaining

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 10 h |
| Origen en el SRS | RF-07 |
| Etiquetas | `backend,opensky` |

#### US-06 — Resolver el icao24 de un vuelo como vinculo temporal del tramo

Como sistema, quiero resolver el icao24 a partir del callsign y la fecha en cada tramo, para no seguir una aeronave que ya vuela hacia otro destino con otra carga.

**Criterios de aceptacion**

- Dado un pedido aereo, cuando resuelvo su aeronave, entonces guardo el icao24 asociado al tramo y no como atributo fijo del pedido
- Dada una aeronave que cambio de vuelo, cuando finaliza el tramo, entonces el vinculo queda cerrado y no se sigue consultando
- Dado un callsign nulo en la lectura, cuando lo proceso, entonces uso el icao24 como identificador estable y reintento el callsign en la siguiente lectura

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-07 / spike TG-11 |
| Etiquetas | `backend,opensky` |

#### US-07 — Planificar las consultas periodicas con frecuencia parametrizable

Como administrador, quiero configurar la frecuencia de consulta por via de transporte, para ajustar el consumo de cuota sin tocar el codigo.

**Criterios de aceptacion**

- Dado el parametro de frecuencia aerea, cuando lo modifico, entonces el planificador aplica el nuevo intervalo sin reiniciar el servicio
- Dado el rastreo aereo por ventana activa, cuando estoy dentro de la ventana, entonces consulto al intervalo configurado y fuera de ella suspendo el sondeo
- Dado el rastreo maritimo, cuando lo configuro, entonces se gestiona como suscripcion persistente y no como sondeo periodico
- Dada la cuota diaria, cuando el consumo proyectado la excederia, entonces el planificador lo advierte en el log

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-08 (reformulado) |
| Etiquetas | `backend,scheduler` |

#### US-08 — Estimar la ETA a partir de la posicion y la velocidad del buque

Como usuario de Compras, quiero que el sistema estime la ETA desde la posicion actual, para no depender del campo de texto libre que declara la tripulacion.

**Criterios de aceptacion**

- Dada una posicion y una velocidad sobre tierra, cuando calculo la ETA, entonces uso la distancia PostGIS al destino dividida por la velocidad
- Dada una velocidad menor al minimo configurado, cuando calculo la ETA, entonces no la estimo y marco el pedido como 'ETA no estimable'
- Dada una ETA declarada por la fuente, cuando existe y es coherente, entonces registro ambas y la calculada es la que alimenta RN-01
- Dado el calculo, cuando lo consulto, entonces expone la distancia, la velocidad y la hora usadas para poder auditarlo

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RN-16 (nueva, Greivin) |
| Etiquetas | `backend,calculo,regla-nueva` |

#### US-09 — Calcular la fecha proyectada de disponibilidad

Como usuario de Planificacion, quiero la fecha proyectada de disponibilidad de cada pedido, para usarla como insumo del calculo de necesidades de materiales.

**Criterios de aceptacion**

- Dado un pedido con ETA y destino con lead time, cuando ejecuto el calculo, entonces obtengo ETA mas lead time mas ajuste manual conforme a RN-01
- Dado un pedido con ATA confirmada, cuando calculo, entonces la ATA tiene precedencia sobre la ETA conforme a RN-14
- Dado un destino sin lead time definido, cuando calculo, entonces no produzco fecha proyectada y lo senalo

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | RF-10 / RN-01 |
| Etiquetas | `backend,calculo` |

#### US-10 — Determinar el estado logistico bajo el esquema de semaforo

Como usuario de Compras, quiero que cada pedido tenga su estado calculado automaticamente, para detectar de un vistazo cuales exigen atencion.

**Criterios de aceptacion**

- Dado un pedido sin identificador, cuando evaluo su estado, entonces es 'Sin tracking' en gris
- Dada una fecha proyectada anterior o igual a la comprometida, cuando evaluo, entonces el estado es 'A tiempo' en verde
- Dada una fecha proyectada dentro del umbral de 48 h, cuando evaluo, entonces el estado es 'En riesgo' en naranja
- Dada una fecha proyectada posterior a la comprometida, cuando evaluo, entonces el estado es 'Retrasado' en rojo
- Dado el umbral de 48 h, cuando lo modifico en la tabla de parametros, entonces el recalculo lo aplica sin desplegar codigo

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RF-11 / RN-02 a RN-11 |
| Etiquetas | `backend,calculo,nucleo` |

#### US-11 — Inferir el arribo a destino por geocerca de proximidad

Como usuario de Logistica, quiero que el sistema asuma el arribo cuando el buque entra en el radio del puerto, para no depender de que la fuente externa reporte la llegada.

**Criterios de aceptacion**

- Dado un buque a menos del radio configurado (50 km por defecto) del destino, cuando evaluo su estado, entonces lo clasifico como 'En destino' conforme a RN-05
- Dado un buque dentro del radio pero con velocidad superior al umbral configurado, cuando evaluo, entonces NO lo doy por arribado, para descartar el trafico en transito hacia el Canal de Panama
- Dado el radio y el umbral de velocidad, cuando los modifico en la tabla de parametros, entonces se aplican sin desplegar codigo
- Dado un arribo inferido, cuando lo registro, entonces queda marcado como inferido y no como confirmado por la fuente

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RN-05 (revisada, Greivin) |
| Etiquetas | `backend,calculo,regla-nueva` |

---

### Sprint 5 (5-16 oct 2026)

**8 items · 62 h estimadas · capacidad 65 h — dentro de capacidad**

#### US-12 — Recalcular fecha y estado ante cualquier cambio de insumo

Como sistema, quiero recalcular automaticamente cuando cambie un insumo, para que el dashboard nunca muestre un estado obsoleto.

**Criterios de aceptacion**

- Dada una nueva lectura de ETA, cuando la persisto, entonces se recalculan fecha proyectada y estado del pedido
- Dado un cambio de lead time en el maestro de destinos, cuando lo guardo, entonces se recalculan todos los pedidos activos de ese destino
- Dado un fallo al recalcular un pedido, cuando ocurre, entonces los demas pedidos se recalculan igual conforme a RNF-14

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-12 |
| Etiquetas | `backend,calculo` |

#### US-13 — Mantener el maestro de destinos y sus lead times

Como usuario de Logistica, quiero administrar los destinos y su lead time en dias, para que la fecha proyectada refleje la realidad de cada puerto.

**Criterios de aceptacion**

- Dado un destino nuevo, cuando lo creo con via y lead time, entonces queda disponible para asociarse a pedidos
- Dado un lead time negativo o no numerico, cuando intento guardarlo, entonces el sistema lo rechaza e informa el formato esperado
- Dado un destino con pedidos activos, cuando intento desactivarlo, entonces el sistema advierte del impacto y pide confirmacion
- Dado un destino duplicado en nombre y via, cuando intento crearlo, entonces el sistema impide la duplicacion

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 10 h |
| Origen en el SRS | RF-23 / CU-06 |
| Etiquetas | `backend,maestros` |

#### US-14 — Confirmar manualmente el desembarco de un pedido

Como usuario de Logistica, quiero registrar la llegada real de la carga, para corregir al sistema cuando la fuente automatica no la reporta.

**Criterios de aceptacion**

- Dado un pedido no terminal, cuando registro la ATA con motivo, entonces la ATA prevalece sobre la ETA de la API conforme a RN-14
- Dada una fecha futura, cuando intento confirmarla, entonces el sistema la rechaza
- Dado un pedido con ATA ya confirmada, cuando la sobrescribo, entonces el sistema advierte y exige confirmacion explicita
- Dada la confirmacion, cuando se registra, entonces se recalculan fecha y estado y queda auditada

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 8 h |
| Origen en el SRS | RF-13 / CU-05 |
| Etiquetas | `backend,manual` |

#### US-15 — Auditar toda intervencion manual sobre un pedido

Como supervisor, quiero la traza de cada cambio manual, para saber quien alteró un dato calculado y por que.

**Criterios de aceptacion**

- Dada una intervencion manual, cuando se ejecuta, entonces se registra usuario, fecha, valor anterior, valor nuevo y motivo
- Dado un registro de auditoria, cuando intento alterarlo, entonces la operacion se rechaza
- Dado un pedido, cuando consulto su bitacora, entonces veo sus intervenciones en orden cronologico

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE4 |
| MoSCoW | **Should** |
| Estimacion | 8 h |
| Origen en el SRS | RF-14 / RNF-06 |
| Etiquetas | `backend,auditoria` |

#### US-16 — Exponer los pedidos y su detalle por API REST

Como frontend, quiero endpoints REST de listado y detalle de pedidos, para construir la grilla y la vista de detalle.

**Criterios de aceptacion**

- Dado el endpoint de listado, cuando lo consulto con filtros y paginacion, entonces devuelve los pedidos con su estado calculado
- Dado el endpoint de detalle, cuando consulto un pedido, entonces devuelve datos maestros, rastreo, ultima posicion y desglose del calculo
- Dado un identificador inexistente, cuando lo consulto, entonces responde 404 con cuerpo de error descriptivo

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Must** |
| Estimacion | 10 h |
| Origen en el SRS | RF-04 / RF-05 (backend) |
| Etiquetas | `backend,api-rest` |

#### US-17 — Mantener credenciales, umbrales y frecuencias fuera del codigo

Como administrador, quiero configurar credenciales y umbrales sin tocar el codigo, para ajustar el sistema sin un nuevo despliegue.

**Criterios de aceptacion**

- Dadas las credenciales de API, cuando reviso el repositorio, entonces no aparecen en el codigo fuente ni en el control de versiones
- Dado el umbral de 48 h, cuando lo modifico en la tabla de parametros, entonces el proximo recalculo lo aplica
- Dado un parametro ausente, cuando arranca el sistema, entonces falla de forma explicita indicando cual falta

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 6 h |
| Origen en el SRS | RF-24 / RNF-07 / RNF-15 |
| Etiquetas | `backend,configuracion` |

#### US-18 — Registrar la recepcion en planta y cerrar el pedido

Como usuario de Logistica, quiero registrar la recepcion efectiva en planta, para que el pedido pase a Cerrado y deje de consumir cuota de API.

**Criterios de aceptacion**

- Dada una cantidad recibida dentro del margen del 10%, cuando la registro, entonces el pedido transita a 'Cerrado' conforme a RN-10
- Dada una cantidad por debajo del margen, cuando la registro, entonces el pedido NO se cierra y se ofrece el cierre forzado
- Dado un pedido cerrado, cuando corre el planificador, entonces no se consulta contra las APIs externas
- Dado un pedido cerrado, cuando calculo los KPIs, entonces no computa entre los pedidos activos

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 8 h |
| Origen en el SRS | RF-25 / RN-10 |
| Etiquetas | `backend,manual,ciclo-vida` |

#### TASK-04 — Publicar la documentacion OpenAPI del backend

Como desarrollador, quiero la documentacion OpenAPI generada automaticamente, para cumplir RNF-17 y facilitar el trabajo del frontend.

**Criterios de aceptacion**

- Dado el backend en ejecucion, cuando accedo a /docs, entonces veo Swagger UI con todos los endpoints
- Dado un endpoint nuevo, cuando lo agrego, entonces aparece documentado sin escribir el esquema a mano

| | |
|---|---|
| Tipo | Task |
| Objetivo especifico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 4 h |
| Origen en el SRS | RNF-17 |
| Etiquetas | `backend,documentacion` |

---

### Sprint 6 (19-30 oct 2026)

**7 items · 56 h estimadas · capacidad 65 h — dentro de capacidad**

#### TASK-05 — Andamiaje del frontend React con TypeScript, Vite y Tailwind

Como desarrollador, quiero el proyecto de frontend configurado, para empezar a construir vistas sobre una base estable.

**Criterios de aceptacion**

- Dado el repositorio, cuando ejecuto el arranque de desarrollo, entonces la aplicacion carga sin errores de compilacion
- Dado el proyecto, cuando ejecuto las pruebas, entonces Vitest corre y reporta cobertura
- Dada la configuracion, cuando construyo para produccion, entonces genera el bundle sin advertencias bloqueantes

| | |
|---|---|
| Tipo | Task |
| Objetivo especifico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | RNF (stack 5.8) |
| Etiquetas | `frontend,fundacional` |

#### US-19 — Listar los pedidos en transito en una grilla ordenable

Como usuario de Compras, quiero ver todos los pedidos en una grilla, para revisar el estado de mi cartera de un vistazo.

**Criterios de aceptacion**

- Dado un conjunto de pedidos, cuando abro el dashboard, entonces veo OC, material, proveedor, via, destino, ETA, fecha proyectada, fecha comprometida y estado
- Dada la grilla, cuando ordeno por una columna, entonces los datos se reordenan sin recargar la pagina
- Dado un volumen de 200 pedidos, cuando cargo la vista, entonces se pagina y responde en menos de 3 segundos

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RF-04 / RNF-01 |
| Etiquetas | `frontend,grilla` |

#### US-20 — Consultar el detalle completo de un pedido

Como usuario de Logistica, quiero ver el detalle de un pedido con el desglose del calculo, para entender por que tiene el estado que tiene.

**Criterios de aceptacion**

- Dado un pedido, cuando abro su detalle, entonces veo datos maestros, identificador de rastreo, ultima posicion y fecha de la ultima consulta exitosa
- Dado el detalle, cuando reviso el calculo, entonces veo ETA, lead time y ajuste manual que produjeron la fecha proyectada
- Dado un pedido sin identificador, cuando abro su detalle, entonces se indica que no es rastreable y se ofrece asociar uno

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 10 h |
| Origen en el SRS | RF-05 / CU-03 |
| Etiquetas | `frontend,detalle` |

#### US-21 — Filtrar el dashboard de forma transversal y coherente

Como usuario de Compras, quiero filtrar por OC, proveedor, material, via, estado y destino, para concentrarme en el subconjunto que me interesa.

**Criterios de aceptacion**

- Dado un filtro aplicado, cuando se procesa, entonces la cinta de KPIs, la grilla y ambos mapas reflejan el mismo subconjunto
- Dada una combinacion sin resultados, cuando se aplica, entonces se muestra la vista vacia con la opcion de limpiar filtros
- Dado un filtro, cuando lo aplico, entonces la vista se actualiza en menos de 1 segundo y sin recarga completa

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RF-19 / CU-04 / RNF-02 |
| Etiquetas | `frontend,filtros` |

#### US-22 — Mostrar la cinta de indicadores KPI

Como gerencia de operaciones, quiero una cinta de indicadores agregados, para evaluar el desempeno de la cartera sin entrar al detalle.

**Criterios de aceptacion**

- Dado un conjunto de pedidos, cuando cargo el dashboard, entonces veo pedidos activos, porcentaje a tiempo, en riesgo y retrasados, y lead time promedio
- Dado un filtro activo, cuando cambia, entonces los indicadores se recalculan sobre el subconjunto filtrado
- Dado un pedido en estado terminal, cuando calculo los KPIs, entonces no computa entre los activos

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-15 |
| Etiquetas | `frontend,kpi` |

#### US-23 — Indicar la frescura de los datos en el encabezado

Como usuario, quiero saber de cuando son los datos que estoy viendo, para juzgar si puedo confiar en ellos para decidir.

**Criterios de aceptacion**

- Dado un ciclo de consulta ejecutado, cuando abro el dashboard, entonces el encabezado muestra la fecha y hora de la ultima actualizacion
- Dada una sincronizacion fallida, cuando ocurre, entonces el encabezado senala la incidencia y la antiguedad del ultimo dato valido

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Should** |
| Estimacion | 4 h |
| Origen en el SRS | RF-20 / RNF-12 |
| Etiquetas | `frontend,ux` |

#### US-24 — Aplicar el semaforo de estados de forma consistente

Como usuario sin formacion tecnica, quiero que el color signifique lo mismo en toda la interfaz, para interpretar el estado sin aprender convenciones.

**Criterios de aceptacion**

- Dado un pedido en un estado, cuando lo veo en la grilla y en el mapa, entonces el color es el mismo en ambos
- Dados los siete estados de la seccion 7.2, cuando los represento, entonces cada uno usa el color que fija su regla de negocio
- Dada la paleta, cuando la reviso, entonces los colores mantienen contraste suficiente para lectura a distancia

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 4 h |
| Origen en el SRS | RNF-08 / RN-02 a RN-15 |
| Etiquetas | `frontend,ux` |

---

### Sprint 7 (2-13 nov 2026)

**7 items · 62 h estimadas · capacidad 65 h — dentro de capacidad**

#### US-25 — Presentar el mapa interactivo maritimo con posiciones actuales

Como usuario de Logistica, quiero ver mis buques en un mapa, para ubicar geograficamente la carga y su estado.

**Criterios de aceptacion**

- Dados pedidos maritimos con posicion, cuando abro el mapa, entonces cada buque aparece como marcador coloreado por estado
- Dado un filtro activo, cuando cambia, entonces el mapa muestra solo los buques del subconjunto
- Dada una nave sin lectura reciente, cuando la represento, entonces la diferencio visualmente e indico la antiguedad del dato
- Dadas varias naves proximas, cuando se solapan, entonces se agrupan y se despliegan al acercar la vista

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RF-16 / CU-07 |
| Etiquetas | `frontend,mapas,leaflet` |

#### US-26 — Presentar el mapa interactivo aereo separado del maritimo

Como usuario de Compras, quiero un mapa aereo independiente, para seguir los embarques por avion sin mezclarlos con los maritimos.

**Criterios de aceptacion**

- Dados pedidos aereos con posicion, cuando abro el mapa aereo, entonces cada aeronave aparece con el mismo esquema de color por estado
- Dado un vuelo finalizado que ya no emite, cuando lo represento, entonces muestro la ultima posicion e indico que el vuelo concluyo
- Dada una aeronave fuera de cobertura ADS-B, cuando la represento, entonces conservo la ultima posicion valida y senalo su antiguedad

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Must** |
| Estimacion | 8 h |
| Origen en el SRS | RF-17 / CU-08 |
| Etiquetas | `frontend,mapas,leaflet` |

#### US-27 — Mostrar informacion emergente en los marcadores del mapa

Como usuario, quiero ver los datos del pedido al posarme sobre su marcador, para obtener contexto sin salir del mapa.

**Criterios de aceptacion**

- Dado un marcador, cuando poso el cursor o lo selecciono, entonces veo OC, material, proveedor, ETA, fecha proyectada y estado
- Dado un marcador seleccionado, cuando lo activo, entonces puedo navegar al detalle del pedido

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Could** |
| Estimacion | 6 h |
| Origen en el SRS | RF-18 (Media en SRS) |
| Etiquetas | `frontend,mapas` |

#### US-28 — Presentar la vista de proximos arribos

Como usuario de Planificacion, quiero ver los cinco arribos mas cercanos, para anticipar que llega esta semana.

**Criterios de aceptacion**

- Dados pedidos con fecha proyectada, cuando abro la vista, entonces veo los cinco mas proximos dentro de los siguientes 7 dias
- Dado que hay menos de cinco en ese horizonte, cuando se completa la vista, entonces se rellena con los de peor cumplimiento dentro de 30 dias
- Dado un filtro activo, cuando cambia, entonces la vista responde al subconjunto filtrado

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Should** |
| Estimacion | 8 h |
| Origen en el SRS | RF-27 |
| Etiquetas | `frontend,dashboard` |

#### US-29 — Consultar el historial de tracking y dibujar el trayecto

Como usuario de Logistica, quiero ver el recorrido historico de un pedido, para reconstruir su viaje y auditar lo ocurrido.

**Criterios de aceptacion**

- Dado un pedido con dos o mas posiciones, cuando abro su historial, entonces veo la secuencia cronologica en tabla y el trayecto sobre el mapa
- Dado un pedido con una sola posicion, cuando abro su historial, entonces se muestra el punto sin trazar trayecto
- Dado un registro del historial, cuando pido su detalle tecnico, entonces se muestra el payload original de la API

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Could** |
| Estimacion | 10 h |
| Origen en el SRS | RF-22 (Media en SRS) / CU-09 |
| Etiquetas | `frontend,mapas,auditoria` |

#### US-30 — Actualizar la nave asignada ante un transbordo

Como usuario de Logistica, quiero sustituir la nave de un pedido cuando hay transbordo, para seguir rastreandolo en el tramo vigente.

**Criterios de aceptacion**

- Dado un pedido maritimo con nave, cuando registro la nueva nave, el puerto y la fecha, entonces el rastreo pasa a la nave nueva
- Dado el tramo anterior, cuando se cierra, entonces su historial de posiciones se conserva asociado a ese tramo
- Dadas varias lineas de OC que comparten la nave anterior, cuando aplico el transbordo, entonces puedo aplicarlo en bloque
- Dado un identificador desconocido por la fuente AIS, cuando lo registro, entonces se acepta y se advierte que no habra lectura hasta que la fuente lo reporte

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 10 h |
| Origen en el SRS | RF-26 / CU-10 |
| Etiquetas | `backend,manual,tracking` |

#### TASK-10 — Politica de retencion y submuestreo del historial de posiciones

Como desarrollador, quiero una politica de retencion del historial, para que su crecimiento no degrade la consulta de pedidos activos.

**Criterios de aceptacion**

- Dado el historial creciendo, cuando aplico la politica, entonces la consulta de pedidos activos mantiene su tiempo de respuesta
- Dado el submuestreo configurado, cuando lo modifico, entonces cambia la granularidad persistida sin desplegar codigo

| | |
|---|---|
| Tipo | Task |
| Objetivo especifico | OE4 |
| MoSCoW | **Could** |
| Estimacion | 8 h |
| Origen en el SRS | RNF-22 / spike TG-10 |
| Etiquetas | `persistencia,rendimiento,opcional` |

---

### Cierre (16-21 nov 2026)

**4 items · 30 h estimadas · capacidad 32 h — dentro de capacidad**

#### TASK-06 — Pruebas de integracion extremo a extremo

Como desarrollador, quiero pruebas que recorran el flujo completo, para demostrar que el sistema opera de punta a punta.

**Criterios de aceptacion**

- Dado un pedido semilla, cuando corre el flujo completo de ingesta, tracking, calculo y consulta, entonces el estado final es el esperado
- Dadas las reglas de calculo, cuando ejecuto su suite, entonces la cobertura de la seccion 7 del SRS supera el 70% conforme a RNF-18

| | |
|---|---|
| Tipo | Task |
| Objetivo especifico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 12 h |
| Origen en el SRS | RNF-18 / Criterios seccion 10 |
| Etiquetas | `pruebas,cierre` |

#### TASK-07 — Manual de instalacion local

Como tecnico del Centro de Competencias, quiero un manual de instalacion reproducible, para levantar el sistema en otro equipo.

**Criterios de aceptacion**

- Dado un equipo limpio, cuando sigo el manual, entonces el sistema queda operativo sin consultar al autor
- Dado el manual, cuando lo reviso, entonces documenta la ejecucion nativa sin contenedores conforme a la seccion 9.3

| | |
|---|---|
| Tipo | Task |
| Objetivo especifico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | Criterios seccion 10 |
| Etiquetas | `documentacion,cierre` |

#### TASK-08 — Manual de usuario del dashboard

Como usuario de Compras, quiero un manual de uso, para operar el dashboard sin capacitacion previa.

**Criterios de aceptacion**

- Dado el manual, cuando lo sigo, entonces puedo filtrar, consultar detalle y confirmar un desembarco
- Dado el manual, cuando lo reviso, entonces esta integramente en espanol conforme a RNF-09

| | |
|---|---|
| Tipo | Task |
| Objetivo especifico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | RNF-10 / Criterios seccion 10 |
| Etiquetas | `documentacion,cierre` |

#### TASK-09 — Guia de despliegue para produccion

Como tecnico del Centro de Competencias, quiero la guia de despliegue, para asumir la puesta en produccion tras la practica.

**Criterios de aceptacion**

- Dada la guia, cuando la reviso, entonces documenta variables de entorno, dependencias y los artefactos de contenedor conservados
- Dada la guia, cuando la sigo, entonces identifico que queda fuera del alcance de la practica conforme a la seccion 1.2.2

| | |
|---|---|
| Tipo | Task |
| Objetivo especifico | OE4 |
| MoSCoW | **Must** |
| Estimacion | 6 h |
| Origen en el SRS | Criterios seccion 10 |
| Etiquetas | `documentacion,cierre` |

---

### Sin asignar (bloqueadas por insumo externo sin fecha)

**3 items · 32 h estimadas — sin calendarizar a proposito.** Su dependencia externa no tiene fecha comprometida; asignarles sprint seria fingir un compromiso que no controlamos.

#### US-31 — Sincronizar los pedidos en transito desde el servicio API de SAP

Como usuario de Compras, quiero que los pedidos lleguen automaticamente desde SAP, para no mantener la informacion a mano.

**Criterios de aceptacion**

- Dado el servicio de SAP disponible, cuando corre la sincronizacion, entonces los pedidos nuevos se insertan y los existentes se actualizan por OC y posicion
- Dado un pedido que ya no figura en SAP, cuando sincronizo, entonces lo senalo para revision manual y NO lo elimino
- Dado el servicio caido, cuando falla, entonces conservo la ultima sincronizacion y senalo la antiguedad en el encabezado
- Dada la sincronizacion, cuando termina, entonces informo recibidos, insertados, actualizados y rechazados

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 16 h |
| Origen en el SRS | RF-01 / CU-01 |
| Etiquetas | `backend,sap,bloqueada` |
| 🔒 Bloqueada por | Especificacion del servicio API de SAP (Centro de Competencias) |

#### US-32 — Validar los datos recibidos de SAP antes de persistirlos

Como sistema, quiero validar cada registro recibido, para que un dato malo no contamine la base ni aborte la sincronizacion.

**Criterios de aceptacion**

- Dado un registro sin campo obligatorio, cuando lo valido, entonces lo rechazo individualmente y continuo con los demas
- Dada una via de transporte fuera de dominio, cuando la valido, entonces rechazo el registro indicando el motivo
- Dado el informe de validacion, cuando lo consulto, entonces identifica cada rechazo con su clave de origen y su motivo

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE2 |
| MoSCoW | **Should** |
| Estimacion | 10 h |
| Origen en el SRS | RF-02 / CU-01 |
| Etiquetas | `backend,sap,bloqueada` |
| 🔒 Bloqueada por | Especificacion del servicio API de SAP (Centro de Competencias) |

#### US-33 — Habilitar el modo de visualizacion permanente en pantalla grande

Como gerencia, quiero un modo de pantalla permanente, para dejar el dashboard visible en planta.

**Criterios de aceptacion**

- Dado el modo de visualizacion, cuando lo activo, entonces la vista se adapta a pantalla grande con tipografia legible a distancia
- Dado el modo activo, cuando pasa el tiempo, entonces la vista se refresca sola sin intervencion

| | |
|---|---|
| Tipo | Story |
| Objetivo especifico | OE3 |
| MoSCoW | **Could** |
| Estimacion | 6 h |
| Origen en el SRS | RNF-11 |
| Etiquetas | `frontend,ux,opcional` |
| 🔒 Bloqueada por | Resolucion y tamano de la pantalla (pendiente de definir con usuarios clave) |

---

## Anexo: fuera del alcance (Won't have)

No se cargan al backlog. Se listan por trazabilidad, tomados de la seccion 1.2.2 del SRS v0.2.

- Despliegue a produccion en la infraestructura corporativa
- Servidor web productivo, balanceo de carga y terminacion SSL
- Integracion con Active Directory / SSO corporativo
- Sistema de colas distribuido en modo productivo
- Monitoreo, logging centralizado y alertas de produccion
- Desarrollo del servicio API del lado de SAP (corresponde al Centro de Competencias)
- Trazabilidad automatica por contenedor, BL o booking sin dato de nave
- Gestion documental de facturas, BL, AWB o DUAs
- Prediccion avanzada de retrasos por congestion portuaria o clima
- Aplicacion movil nativa
- Contratacion de licencias de APIs comerciales de rastreo

