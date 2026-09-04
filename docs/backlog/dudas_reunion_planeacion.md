# Dudas abiertas — reunión con Planeación

**Fecha:** 04/09/2026 · **Objetivo:** cerrar los insumos que faltan para **arrancar el Sprint 3 el 7 de septiembre**
**Insumos:** SRS v0.4 · `backlog_trackin.md` (congelado 03/09) · muestra Z-tracking (`docs/analisis/2026-Agosto-WK36_anonimizado.csv`, 429 líneas PRODUCCION+IDA) · `dudas_sesion_validacion.md`

> Mismo formato que la sesión de validación: la columna **«Recomiendo»** es una
> propuesta razonada desde el SRS y los datos, **no una decisión tomada**. Anotar
> la respuesta en la última columna.
>
> Las secciones están ordenadas por lo que desbloquean: **P** y **Q** bloquean el
> cálculo (Sprints 3–4), **R** y **S** son alcance de vista (Sprints 6–7), **T** y
> **U** son operación.

---

## Lo que cambió desde el 03/09 (contexto para abrir la reunión)

Tres hallazgos de Logística y una decisión técnica mueven el tablero:

| Hallazgo (Logística) | Efecto sobre lo que había |
|---|---|
| El **lead time real por origen está en SAP**; el API está en desarrollo, con fecha próxima | Reabre `C1`. `maestro_destinos.lead_time_dias` deja de ser el dato maestro y pasa a ser **respaldo**. Toca `US-09`, `US-13` y los datos semilla de `TASK-03` |
| El **puerto de origen no hace falta**: basta el país | Cierra `C3`. `maestro_destinos` se reduce a Moín (`CRMOB`) y SJO; el origen se modela solo como país (`TASK-29`) |
| **ETD/ATD no se registran hoy**; los entregarán en **otro Excel** | `US-43` (vista completa) y `US-46` dependen de una **segunda fuente de entrada** que no está en ninguna historia |

| Decisión técnica (03–04/09) | Efecto |
|---|---|
| **Vizion** para rastreo marítimo, **Portcast** para carga aérea, **OpenSky** (gratuito) solo para la posición de la aeronave | `TASK-28` deja de ser «¿qué proveedor?» y pasa a ser «¿estos dos responden con referencias reales?». Es de hecho el **Plan A** de la bifurcación |

---

## P · Fecha proyectada y lead time — RN-01

**Lo que bloquea:** `TASK-01` y `TASK-03` (Sprint 3), `US-09` (Sprint 4), `US-13` (Sprint 5).

| # | Pregunta | Por qué importa | Recomiendo | Respuesta |
|---|---|---|---|---|
| P1 | ¿Cuál de las fechas del Z-tracking es la **fecha comprometida** contra la que se mide el cumplimiento? Candidatas: `Fecha entrega SolPed`, `Fecha de llegada a Gutis`, `Fecha según Lead Time de SAP`, `ETA CR` | Es el lado derecho de RN-02 a RN-11. Sin ella el semáforo no tiene contra qué comparar, y son cuatro columnas de fecha con nombres parecidos | **`Fecha entrega SolPed`** (llena en 426/429 líneas). Es la única con cobertura casi total y la única que representa un compromiso y no una estimación | |
| P2 | La columna **`Fecha según Lead Time de SAP`** viene llena en solo **113 de 429** líneas, y en **90 de esas 113 es idéntica a la fecha de SolPed**. ¿Está bien calculada, o la columna quedó rota? | El SRS v0.4 §9 la registró como «SAP ya calcula un lead time». Si en realidad copia la fecha de SolPed, esa afirmación es falsa y `US-09` se queda sin insumo | **Revisarla en pantalla durante la reunión.** Si está rota, el lead time solo llega cuando llegue el API | |
| P3 | El lead time que devolverá SAP, ¿llega **hasta el puerto (Moín/SJO)** o **hasta la planta de Gutis**? | RN-01 es *ETA + lead time + ajuste*. Si el lead time de SAP ya incluye nacionalización y traslado, sumarlo a la ETA del puerto **cuenta ese tramo dos veces** | **Hasta planta.** Si es así, RN-01 debe partirse: ETA de puerto + tramo local, o la fecha de SAP sola. **Decidirlo antes de `US-09`** | |
| P4 | ¿Con qué **granularidad** define SAP el lead time: por país de origen, por proveedor, por material, o por línea de pedido? | Determina si el lead time vive en `maestro_paises` (`TASK-29`), en `pedidos_transito`, o en ambas. Es estructura de tablas, no configuración | **Por línea**, con un valor por país como respaldo cuando la línea no lo traiga | |
| P5 | Mientras el API de SAP no exista, ¿qué **valor provisional** usamos? | El Sprint 4 empieza el 21/09 y `US-09` no puede esperar al API. Sin un número no hay fecha proyectada ni semáforo que demostrar | **Un lead time por vía**, como parámetro editable. En la muestra, la diferencia entre `ETA CR` y `Fecha de llegada a Gutis` da una **mediana de 7 días** (n=13, indicativo). Proponer **7 días marítimo / 3 aéreo** y que Planeación corrija | |
| P6 | Si TrackIn dice que un material **llega a planta el 20 de octubre**, ¿se puede programar producción para el 21, o hay que esperar la **liberación de Control de Calidad**? ¿Cuántos días toma? | El SRS §7.1 deja los ~15 días de CC **fuera** de RN-01. Pero para el cálculo de necesidades de materiales, un lote recibido y no liberado **no sirve**: la fecha útil sería 15 días después | **Mostrar las dos.** La fecha de RN-01 se queda como está y el detalle añade una fecha estimada de liberación. Si solo importa la liberación, es un **RF nuevo** con costo que hay que declarar | |
| P7 | La fecha proyectada, ¿debe caer en **día hábil**? ¿Se saltan fines de semana y feriados? | `fecha_proyectada_disponible` es `DATE`. Si se usa para programar producción, un sábado no sirve | **Sí, correr al siguiente día hábil**, con calendario de feriados como parámetro. Barato ahora, caro después | |
| P8 | El **ajuste manual de días** (`US-40`), ¿lo aplica Planeación o Logística? ¿Hay rango máximo? | RF-14 exige autoría y motivo. Con login (`US-42`) el rol decide quién ve el botón | **Logística**, que conoce el motivo del atraso. Planeación lo consulta en el desglose de `US-20` | |

---

## Q · Cumplimiento, semáforo y cierre — RN-02 a RN-11

**Lo que bloquea:** `US-10` y `US-12` (Sprints 4–5), `US-18` (Sprint 5).

| # | Pregunta | Por qué importa | Recomiendo | Respuesta |
|---|---|---|---|---|
| Q1 | El Z-tracking **ya trae `Estatus` («Atrasado»/«A Tiempo») y `Diferencia Días` calculados por SAP**. ¿TrackIn los muestra tal cual, o recalcula con RN-02 a RN-11? | Es la pregunta más peligrosa de la lista: **dos fuentes de verdad para el mismo semáforo**. En la muestra `Diferencia Días` va de −456 a +445, señal de que SAP mide algo distinto de lo que mide RN-01 | **TrackIn recalcula y manda**, porque es el único que ve la posición real. El valor de SAP se guarda y se muestra como referencia, nunca como estado | |
| Q2 | El umbral de «En riesgo» son **2 días**. ¿Le sirve a Planeación? | Es lo único que separa verde de naranja (RN-07/RN-08). Dos días de aviso puede ser poco para reprogramar producción | **Subirlo y diferenciarlo por vía**: ~7 días marítimo, ~2 aéreo. Es parámetro, no código (`US-17`) | |
| Q3 | ¿El umbral debería depender de la **criticidad del material** o de la **cadena de frío**? | La muestra trae `Temperatura` (Ambiente / 2–8 °C / 15–25 °C). Un material refrigerado atrasado no pesa igual que uno ambiente | **No en esta versión.** Anotarlo como evolución; si Planeación insiste, es un RF nuevo y sale de horas de otro lado | |
| Q4 | Una línea con **entrega parcial** (`Ctd. entregada` > 0 y `Ctd. pendiente` > 0), ¿sigue activa en el dashboard? | Hay **8 líneas así** en la muestra. RN-10 y `US-18` cierran el pedido pero no dicen qué pasa con lo parcial. Afecta el KPI de «pedidos activos» | **Sigue activa** hasta que `Ctd. pendiente` llegue a 0. El KPI cuenta líneas, no cantidades | |
| Q5 | Un pedido **cerrado**, ¿desaparece del dashboard de inmediato o queda visible unos días? | RF-25 lo saca del activo. Si desaparece el mismo día, Planeación pierde el registro de lo que acaba de llegar | **Visible 15 días** bajo un filtro «recibidos», con parámetro. La grilla ya intercambia columnas para estados terminales (respuesta A7) | |

---

## R · ETD/ATD y el segundo archivo

**Lo que bloquea:** `US-43` (Sprint 6), `US-46` (Sprint 4) y una **historia de ingesta que hoy no existe**.

> Logística confirmó que **ETD/ATD no se registran hoy** y que los entregarán en
> **otro Excel**. Eso es una segunda fuente de entrada además del Z-tracking, y
> `RF-31` solo contempla una.

| # | Pregunta | Por qué importa | Recomiendo | Respuesta |
|---|---|---|---|---|
| R1 | ¿Cuál es la **llave** para cruzar ese Excel con el Z-tracking: OC + posición, contenedor, o número de embarque? | Sin llave común los dos archivos no se unen y ETD/ATD no llegan a ninguna fila | **OC + posición**, la misma llave natural que ya usa `pedidos_transito` | |
| R2 | ¿Con qué **frecuencia** se entrega y quién lo mantiene? | `RF-31` define la carga manual como vía oficial. Un archivo que se actualiza cuando alguien se acuerda no sostiene un dashboard | **Semanal, junto al Z-tracking**, con el mismo responsable | |
| R3 | ETD/ATD, ¿son de la **nave o vuelo** o del **embarque**? ¿Uno por OC o uno por contenedor? | Cinco líneas de una OC en el mismo barco comparten ETD; si el envío se parte —la muestra trae una línea `AEREO`+`MARITIMO`— no | **Por embarque**, ligado a la referencia de `TASK-30`, no a la OC | |
| R4 | **Vizion y Portcast también devuelven ETD/ATD.** Cuando el Excel y la API difieran, ¿cuál manda? | Van a diferir. Sin regla escrita, el dato mostrado depende de cuál se cargó de último | **La API manda**; el Excel queda como respaldo y para lo que la API no cubra. Mostrar el origen del dato en pantalla | |
| R5 | ¿ETD/ATD los consume **Planeación**, o son solo de Compras y Logística? | `US-43` los pone únicamente en la **vista completa**. Si Planeación los necesita, la vista simple deja de ser simple | **Solo vista completa**, como está. Confirmar | |
| R6 | ¿Se acepta abrir la ingesta de ese archivo como **historia nueva del Sprint 4** (~6 h)? | No existe hoy. Si no se abre, `US-43` llega al Sprint 6 con dos columnas vacías | **Sí, abrirla ahora** en vez de descubrirla a mitad del Sprint 6 | |

---

## S · Vista simple y pantalla de planta — `US-43`, `US-33`

| # | Pregunta | Por qué importa | Recomiendo | Respuesta |
|---|---|---|---|---|
| S1 | La vista simple es **Material · Etapa · Cumplimiento**. ¿De verdad no lleva **fecha proyectada** ni **cantidad**? | Es la vista del rol Planificación. Un planificador que ve «Retrasado» pero no *para cuándo* ni *cuánto* **no puede planear**: le falta justo el resultado de RN-01 | **Añadir fecha proyectada y cantidad pendiente.** Cinco columnas siguen siendo una vista simple | |
| S2 | ¿Cuál es el **ordenamiento por defecto** de la vista simple? | RF-04 permite ordenar por columna, pero alguien debe decidir cómo abre | **Por fecha proyectada ascendente**: lo que llega primero, arriba | |
| S3 | La **pantalla permanente de planta** (`US-33`, RNF-11): ¿qué resolución, cuántas filas caben, rota automáticamente? | Es la decisión abierta **#4** del backlog, sin dueño desde el 20/08. Determina si `US-33` es viable en el Sprint 7 | **Full HD horizontal, ~15 filas, rotación cada 30 s.** Si no hay pantalla comprada, `US-33` se queda en `Could` y probablemente no se hace | |
| S4 | Esa pantalla, ¿**exige login**? | Nadie teclea una contraseña cada mañana en planta, y la sesión expira por inactividad (RNF-24) | **Usuario de kiosco**, sesión que no expira, solo lectura. Es un caso especial que hay que escribir en `US-42` | |
| S5 | Los **KPIs** son: activos, % a tiempo, % en riesgo, % retrasados y lead time promedio. ¿Le sirven a Planeación o quiere otros? | `US-22` los implementa en el Sprint 6; cambiarlos después cuesta | **Confirmarlos tal cual.** Si Planeación pide «materiales sin cobertura», ese indicador necesita datos de inventario que TrackIn **no tiene** | |

---

## T · Alcance de datos y filtros

| # | Pregunta | Por qué importa | Recomiendo | Respuesta |
|---|---|---|---|---|
| T1 | Logística fijó el alcance en **PRODUCCION + IDA**. ¿Planeación necesita ver también las compras locales? | Son 429 líneas contra las 2.045 del archivo completo. Cambia volumen, filtros y el sentido de los KPIs | **Mantener PRODUCCION + IDA.** Lo local no se rastrea y ensuciaría los porcentajes | |
| T2 | En la muestra, **262 de 429 líneas (61 %) no traen `Tipo de transporte`** y **250 (58 %) no traen `País de Origen`**. ¿Qué hace el dashboard con ellas? | Sin vía de transporte no hay mapa, no hay rastreo y no hay etapa. Es más de la mitad de la cartera | **Mostrarlas como `SIN_TRACKING`** con un contador visible de «pedidos sin clasificar», para que el hueco se vea en vez de esconderse | |
| T3 | ¿Qué **filtros** necesita Planeación además de estado y vía: grupo de compra, comprador, material, proveedor, país? | `US-21` los implementa de una vez en el Sprint 6; agregarlos después es retrabajo | **Material, país y estado.** Grupo de compra y comprador sirven a Compras, no a Planeación | |
| T4 | ¿**Exportación a Excel** y **notificaciones** son requerimientos? | Es la decisión abierta **#5**, sin resolver desde el 20/08. Hoy **no están en ningún RF ni en ninguna historia** | **Exportación sí** (~4 h, barata y la van a pedir igual). **Notificaciones no**: exigen correo o mensajería que no existe. Si se piden, salen de otras horas | |

---

## U · Operación, roles y sesión

| # | Pregunta | Por qué importa | Recomiendo | Respuesta |
|---|---|---|---|---|
| U1 | ¿Quién registra la **recepción en planta** (`US-18`): Planeación, Bodega o Logística? | RF-25 cierra el pedido y RF-14 exige autoría. Con login, el rol decide quién ve el botón | **Bodega o Logística.** Planeación consulta, no registra | |
| U2 | ¿Cuántos usuarios de Planeación habrá y **quién administra las cuentas**? | El rol Administrador entró al alcance el 03/09 (revierte B9). Alguien tiene que ser el primero | **Un administrador nombrado**, más los usuarios que Planeación indique | |
| U3 | **Duración de sesión**, cierre por inactividad y bloqueo tras N intentos | Decisiones abiertas del wireframe de login (`US-41` §0.4). `US-42` no se puede cerrar sin ellas | **8 h de sesión, 30 min de inactividad, bloqueo a los 5 intentos**, salvo el kiosco de S4 | |
| U4 | «Olvidó su contraseña»: sin servidor de correo, ¿**reinicio por el administrador**? | Es la única vía sin infraestructura de correo | **Sí, reinicio por administrador.** Documentarlo en el manual de usuario | |

---

## Consecuencias sobre el backlog (para Greivin, no para Planeación)

Elegir **Vizion + Portcast + OpenSky** resuelve de hecho `TASK-28` a favor del
**Plan A**. Si se confirma, el backlog congelado cambia así:

| Item | Efecto del Plan A |
|---|---|
| `US-45` Rastreo marítimo comercial (Vizion) | **Entra** · 12 h |
| `US-46` Rastreo aéreo por MAWB (Portcast) | **Entra** · 10 h |
| `US-02` AIS por WebSocket | Se **reduce** a respaldo del mapa: 16 h → ~6 h |
| `US-08` Estimar ETA por posición y velocidad | Baja a **`Could`**: Vizion ya entrega ETA |
| `US-11` Arribo por geocerca | Se **simplifica**: 8 h → ~4 h |
| `TASK-27` Spike de cuota de AISStream | Se **cancela** |
| `US-14` Confirmar desembarco a mano | Baja de `Must` a `Should` (revisa B2) |
| `TASK-28` | Se **reformula**: ya no elige proveedor, **valida** que Vizion y Portcast respondan con un BL y un MAWB reales |

**Balance: +22 h de integración contra −34 h de cálculo propio.** El Sprint 3 no se
desborda y `TASK-27` liberaría 4 h.

**OpenSky** queda **solo** para el punto de la aeronave en el mapa (`US-05`, `US-06`);
el **estado del envío aéreo** lo da Portcast. Conviene escribirlo así en el SRS para que
nadie espere de OpenSky lo que no puede dar.

**C4, C5 y C6 dejan de ser preguntas para Logística.** Con Vizion entregando hitos y
ETA, el umbral de velocidad de arribo (C4) y la velocidad mínima para estimar ETA (C5)
solo aplican al AIS de respaldo, y el intervalo entre lecturas (C6) es decisión técnica
nuestra, no un dato del negocio. **Se cierran como parámetros de sistema con valor por
defecto.**

---

## Resumen para abrir la reunión

- **8 preguntas** sobre fecha proyectada y lead time (P) — bloquean `TASK-01`, `TASK-03` y `US-09`.
- **5 preguntas** sobre semáforo y cierre (Q) — **Q1 es la más peligrosa**: hoy hay dos fuentes de verdad para el mismo estado.
- **6 preguntas** sobre el segundo Excel de ETD/ATD (R) — destapan una **historia de ingesta que no existe**.
- **5 preguntas** de vista simple y pantalla de planta (S) — **S1 dice que la vista simple, como está especificada, no le sirve a un planificador**.
- **4 de alcance y filtros** (T) y **4 de operación** (U), incluidas las dos decisiones abiertas sin dueño desde el 20/08 (#4 y #5).

**Lo más urgente si la reunión se acorta: P1, P3, Q1 y S1.**

- **P1 y P3** deciden qué fecha se compara y si el lead time se cuenta dos veces. Sin ellas `US-09` no se puede construir.
- **Q1** evita entregar un sistema que contradice a SAP en pantalla.
- **S1** evita construir en el Sprint 6 una vista que su propio usuario no puede usar.

**Lo que se puede cerrar por correo si no da tiempo:** P7, P8, Q5, T3, U2, U3, U4.

---

## Respuestas — reunión del 04/09/2026

| # | Respuesta |
|---|---|
| **P1** | ✅ **`Fecha entrega SolPed`.** Es la comprometida contra la que se mide el cumplimiento |
| **P2** | ✅ **Resuelta.** La fórmula es `Diferencia Días = Fecha entrega SolPed − Fecha entrega`, y la *fecha entrega sistema* es la columna **`Fecha entrega`**, que sí viene (423/429). `Fecha según Lead Time de SAP` no se usa. La regla de signos se verificó exacta; la aritmética no reproduce el valor, pero **Planeación indicó dejarlo de lado**: se ingesta como línea base sin recalcular |
| **P3** | ✅ **Hasta la planta de Gutis.** Y arranca en la creación de la SolPed, no en el puerto: es un lead time de **aprovisionamiento**, no logístico. **No sirve para RN-01** |
| **P4** | ✅ Por **proveedor**, aplicado por línea |
| **P5** | ❌ **Sigue abierto.** El tramo puerto→planta no está en SAP ni en el archivo. Primer pendiente del correo |
| **P6** | ✅ **Se espera la liberación de Calidad**, 7–15 días hábiles. El pedido **cierra con la liberación**, no con la recepción → `US-47`, `RF-32`, estado `RECIBIDO_EN_PLANTA` |
| **P7** | Pendiente del correo (días hábiles, ahora también para la ventana de Calidad) |
| **P8** | Pendiente del correo |
| **Q1** | ✅ Resuelto vía P2: TrackIn calcula lo suyo y conserva la línea base de SAP (RN-18) |
| **S1** | Ver acta de la reunión |
| **Referencias** | ✅ **Planeación las incluye en el archivo**: número de contenedor y MAWB → `TASK-30` se simplifica, `US-01` se reformula |

### Hallazgos no previstos

| Hallazgo | Consecuencia |
|---|---|
| **El paso a proceso aduanal es manual** | Anula la transición automática de 30 min del 26/08. `US-14` se queda en `Must`. Se elimina `duracion_en_destino_minutos` |
| **Cuatro destinos: Caldera, Moín, Limón y SJO** | Revierte el «destino único» del 03/09 → `TASK-31`. **Caldera está en el Pacífico** y su cobertura AIS nunca se evaluó |
| **Vizion y Portcast aprobados** | `TASK-28` pasa de elegir a validar. Plan A aplicado |

**Aplicado en:** `backlog_trackin.md` §«Cambios de la reunión con Planeación (04/09/2026)» ·
`SRS_v0.5_plan_de_cambios.md`
