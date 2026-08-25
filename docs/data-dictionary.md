# Diccionario de datos

Referencia normativa campo por campo del esquema de TrackIn. Se deriva del
modelo entidad-relación de [`data-model.md`](data-model.md): **el modelo explica
por qué, este documento define qué.** Ante una discrepancia, prevalece el
modelo y este archivo se corrige.

## Estado de avance

| Tabla | Tarea | Estado |
|---|---|---|
| `pedidos_transito` | `TASK-16` | ✅ 25/08/2026 |
| `maestro_destinos` | `TASK-17` | ✅ 25/08/2026 |
| `historial_tracking` | `TASK-18` | ✅ 25/08/2026 |
| `elementos_rastreados`, `proveedores`, `materiales` | `TASK-24` | ✅ 25/08/2026 |
| `usuarios` | `TASK-19` | ⏳ Pendiente (Sprint 3) |
| `auditoria_intervenciones`, `parametros_sistema`, `pedido_elemento_rastreado` | `TASK-26` | ⏳ Pendiente (Sprint 2) |

## Convenciones de lectura

- **Tipo** es el tipo PostgreSQL, no el tipo Python. La correspondencia con
  SQLAlchemy se resuelve en `TASK-01`.
- **Nulo** indica si la columna admite `NULL`. Cuando la nulidad tiene
  significado de negocio —y no es solo «dato opcional»— se señala en la
  descripción.
- **Clave**: `PK` primaria · `UK(n)` componente *n* de una clave única ·
  `FK` foránea.
- **Dominio** es el conjunto de valores admitidos, con la restricción que lo
  hace cumplir cuando existe.
- Todos los `TIMESTAMPTZ` se almacenan en **UTC**; la conversión a hora de Costa
  Rica ocurre en la capa de presentación.

---

## 1. `pedidos_transito`

Registro central de cada **línea de orden de compra** en tránsito. La fila es la
línea, no la orden: ver [`data-model.md` §1.1](data-model.md).

### 1.1 Campos

| # | Campo | Tipo | Nulo | Clave | Dominio | Descripción |
|---|---|---|---|---|---|---|
| 1 | `id` | `BIGSERIAL` | no | `PK` | Entero positivo, autogenerado | Identificador interno. No se expone al usuario ni proviene de SAP; es el que usan las tablas relacionadas y las rutas de la API REST. |
| 2 | `oc_numero` | `VARCHAR(20)` | no | `UK(1)` | Texto según formato de SAP, **pendiente de confirmar** | Número de orden de compra tal como lo emite SAP. Longitud provisional: el contrato del servicio no se ha recibido (riesgo R2). |
| 3 | `posicion_oc` | `INTEGER` | no | `UK(2)` | `> 0` | Línea o posición dentro de la orden de compra. Junto con `oc_numero` forma la clave natural del pedido. |
| 4 | `tracking_interno` | `VARCHAR(30)` | no | `UK` | Único en la tabla | Código interno de seguimiento que genera TrackIn durante la ingesta. Es el identificador que ve el usuario; no confundir con el identificador de rastreo externo, que vive en `elementos_rastreados`. |
| 5 | `id_proveedor` | `BIGINT` | no | `FK` → `proveedores(id)` | Existente en `proveedores` | Proveedor de la línea. Normalizado; el texto libre que hoy viaja en el pedido se resuelve contra el catálogo durante la ingesta. |
| 6 | `id_material` | `BIGINT` | no | `FK` → `materiales(id)` | Existente en `materiales` | Material solicitado. Normalizado desde el código y descripción concatenados que describe el SRS §8.2. |
| 7 | `id_destino` | `BIGINT` | no | `FK` → `maestro_destinos(id, via_transporte)` | Existente y **de la misma vía** | Puerto o aeropuerto de destino. La foránea es compuesta con `via_transporte` para impedir que un pedido marítimo apunte a un aeropuerto. |
| 8 | `id_elemento_rastreado` | `BIGINT` | **sí** | `FK` → `elementos_rastreados(id)` | Existente, o `NULL` | Nave o vuelo que transporta el pedido **en el tramo vigente**. `NULL` no es «sin dato»: significa que el pedido carece de identificador de rastreo y, por RN-02, está `SIN_TRACKING`. |
| 9 | `via_transporte` | `VARCHAR(10)` | no | parte del `FK` compuesto | `AEREO` · `MARITIMO` (`ck_pedidos_transito_via_transporte`) | Vía por la que viaja la línea. Determina qué fuente externa la rastrea: AISStream para marítimo, OpenSky para aéreo. |
| 10 | `cantidad_pedida` | `NUMERIC(14,3)` | no | | `> 0` (`ck_pedidos_transito_cantidad_pedida`) | Cantidad solicitada en la línea. Es el término contra el que RN-10 compara lo recibido para decidir el cierre. |
| 11 | `unidad_medida` | `VARCHAR(10)` | no | | Texto | Unidad de medida **de la línea de pedido**, que puede diferir de la unidad base del material. |
| 12 | `fecha_entrega_pedido` | `DATE` | no | | Fecha | Fecha comprometida de entrega según el pedido. Es la referencia contra la que RN-07 a RN-09 evalúan el cumplimiento. Se tipa `DATE` y no `TIMESTAMPTZ` porque es un compromiso comercial sin hora. |
| 13 | `lead_time_destino_dias` | `INTEGER` | no | | `>= 0` (`ck_pedidos_transito_lead_time`) | **Copia** del lead time del destino en el momento del último recálculo, no el valor vigente del maestro. Desnormalizado a propósito para que el desglose que exige RF-05 sea reproducible aunque el maestro cambie después. |
| 14 | `ajuste_manual_dias` | `INTEGER` | no, *default* `0` | | Entero, puede ser negativo | Ajuste manual opcional que RN-01 suma a la fórmula. Un valor distinto de cero es una intervención y debe quedar registrada en `auditoria_intervenciones`. |
| 15 | `eta_utilizada` | `TIMESTAMPTZ` | sí | | Instante UTC | ETA **empleada en el último cálculo**, copiada de `elementos_rastreados` o estimada por RN-16. Se guarda para que la cifra sea auditable; la ETA vigente cambia con cada lectura. |
| 16 | `ata_confirmada` | `TIMESTAMPTZ` | sí | | Instante UTC | Llegada confirmada manualmente por Logística. Cuando existe, **prevalece sobre la ETA** por RN-14. `NULL` significa que nadie la ha confirmado. |
| 17 | `fecha_proyectada_disponible` | `DATE` | sí | | Fecha | Resultado de RN-01: ETA o ATA + lead time + ajuste. `NULL` es significativo: indica «ETA no estimable» conforme a RN-16, situación de nave fondeada o por debajo de la velocidad mínima. |
| 18 | `etapa_viaje` | `VARCHAR(20)` | no | | `SIN_TRACKING` · `EN_ORIGEN` · `EN_TRANSITO` · `EN_DESTINO` · `EN_PROCESO_ADUANAL` (`ck_pedidos_transito_etapa_viaje`) | Dónde se encuentra la carga, según RN-02 a RN-06. Es una de las **dos** dimensiones del estado; ver §1.4 del modelo. |
| 19 | `estado_cumplimiento` | `VARCHAR(20)` | **sí** | | `A_TIEMPO` · `EN_RIESGO` · `RETRASADO`, o `NULL` (`ck_pedidos_transito_estado_cumplimiento`) | Si la línea llegará a tiempo, según RN-07 a RN-09. `NULL` cuando no hay `fecha_proyectada_disponible`: sin proyección no se puede afirmar nada, y ningún valor del dominio expresa eso. |
| 20 | `estado_calculado` | `VARCHAR(20)` | no | | Los ocho anteriores más `CERRADO` y `CANCELADO` (`ck_pedidos_transito_estado_calculado`) | Estado único que exige RF-11, **derivado** de las dos columnas anteriores por la precedencia de §1.4 del modelo. Es el que consumen la grilla, los filtros y el semáforo de RNF-08. Se almacena, no se calcula en consulta, para poder indexarlo. |
| 21 | `fecha_ultimo_recalculo` | `TIMESTAMPTZ` | sí | | Instante UTC | Momento del último recálculo de estado y fecha proyectada. `NULL` distingue «nunca recalculado» de «recalculado sin cambios», que es lo que necesita US-23 para indicar frescura. |
| 22 | `fecha_recepcion_planta` | `TIMESTAMPTZ` | sí | | Instante UTC | Ingreso efectivo a planta o almacén (RF-25). Obligatorio cuando `motivo_cierre = 'RECEPCION_CONFORME'`. |
| 23 | `cantidad_recibida` | `NUMERIC(14,3)` | sí | | `>= 0` (`ck_pedidos_transito_cantidad_recibida`) | Cantidad efectivamente recibida. RN-10 la compara con `cantidad_pedida` dentro del margen de tolerancia, que **no** está en el esquema sino en `parametros_sistema`. |
| 24 | `motivo_cierre` | `VARCHAR(25)` | sí | | `RECEPCION_CONFORME` · `CIERRE_FORZADO` · `CANCELACION`, o `NULL` (`ck_pedidos_transito_motivo_cierre`) | Causa del estado terminal según RN-13. `NULL` equivale a pedido vivo, y es la condición que usan los índices parciales del dashboard. |
| 25 | `creado_en` | `TIMESTAMPTZ` | no, *default* `now()` | | Instante UTC | Alta de la fila. Metadato técnico: **no** sustituye a la auditoría de RF-14. |
| 26 | `actualizado_en` | `TIMESTAMPTZ` | no, *default* `now()` | | Instante UTC | Última modificación de la fila. Metadato técnico. |

### 1.2 Restricciones de tabla

Además de los `CHECK` de columna listados arriba:

| Restricción | Definición | Qué garantiza |
|---|---|---|
| `pk_pedidos_transito` | `PRIMARY KEY (id)` | |
| `uq_pedidos_transito_oc_numero` | `UNIQUE (oc_numero, posicion_oc)` | Una sola fila por línea de orden de compra |
| `uq_pedidos_transito_tracking_interno` | `UNIQUE (tracking_interno)` | |
| `fk_pedidos_transito_id_destino_maestro_destinos` | `FOREIGN KEY (id_destino, via_transporte)` → `maestro_destinos (id, via_transporte)`, `ON DELETE RESTRICT` | Que la vía del pedido y la del destino coincidan |
| `fk_pedidos_transito_id_elemento_rastreado_elementos_rastreados` | `ON DELETE SET NULL` | Que borrar una nave devuelva el pedido a `SIN_TRACKING` en vez de eliminarlo |
| `ck_pedidos_transito_sin_tracking` | `(id_elemento_rastreado IS NULL) = (etapa_viaje = 'SIN_TRACKING')` | **RN-02** como invariante de base, no como regla de código |
| `ck_pedidos_transito_terminal` | `(motivo_cierre IS NULL) = (estado_calculado NOT IN ('CERRADO','CANCELADO'))` | **RN-13**: no hay estado terminal sin causa, ni causa sin estado terminal |
| `ck_pedidos_transito_recepcion` | `motivo_cierre = 'RECEPCION_CONFORME'` ⇒ `fecha_recepcion_planta` y `cantidad_recibida` no nulos | **RN-10**: no se cierra por recepción sin los datos de la recepción |

### 1.3 Qué deliberadamente no está en el esquema

| Regla | Dónde vive | Por qué no es un `CHECK` |
|---|---|---|
| Margen de tolerancia del 10 % (RN-10) | `parametros_sistema.tolerancia_recepcion_pct` | Es un parámetro de negocio ajustable; codificarlo obligaría a migrar el esquema para cambiarlo |
| Umbral de 48 h del estado `EN_RIESGO` (RN-11) | `parametros_sistema.umbral_riesgo_horas` | El SRS exige explícitamente que resida en la tabla de parámetros |
| Precedencia que deriva `estado_calculado` (§1.4 del modelo) | Motor de cálculo de `US-10` | Depende de comparar fechas contra parámetros; no es expresable como restricción de fila |

### 1.4 Notas para la implementación de `TASK-01`

- `NUMERIC(14,3)` en las cantidades: 11 enteros y 3 decimales. Cubre unidades
  farmacéuticas con fracción sin recurrir a punto flotante, que no debe usarse
  para cantidades comparadas contra un margen.
- Los dominios se implementan como `VARCHAR` + `CHECK`, no como `ENUM` nativo:
  un `ENUM` exige `ALTER TYPE` y produce migraciones cuyo `downgrade` no es
  aplicable.
- Los nombres de restricción de este documento siguen la `naming_convention` de
  `backend/app/db/base.py`. Si se declaran a mano, deben coincidir, o Alembic
  generará un `downgrade` inaplicable.

---

## 2. `maestro_destinos`

Catálogo de puertos y aeropuertos con su lead time. Alimenta RN-01 —fecha
proyectada— y RN-05 —geocerca de arribo—. Modelo: [`data-model.md` §2](data-model.md).

### 2.1 Campos

| # | Campo | Tipo | Nulo | Clave | Dominio | Descripción |
|---|---|---|---|---|---|---|
| 1 | `id` | `BIGSERIAL` | no | `PK` | Entero positivo, autogenerado | Identificador interno del destino. |
| 2 | `codigo` | `VARCHAR(10)` | no | `UK` | UN/LOCODE para puertos, ICAO para aeropuertos | Código normalizado del destino. Para la vía aérea **no es decorativo**: es el valor con que se consulta OpenSky (`/flights/arrival?airport=MROC`). Para puertos es identificador administrativo: AIS no reporta UN/LOCODE. |
| 3 | `nombre` | `VARCHAR(80)` | no | | Texto libre | Etiqueta legible para la interfaz («Puerto Moín», «Juan Santamaría»). No se usa para identificar ni para unir. |
| 4 | `pais` | `CHAR(2)` | no | | ISO 3166-1 alfa-2 (`ck_maestro_destinos_pais`) | País del destino. Código y no nombre, para que «Estados Unidos», «EEUU» y «USA» no convivan en la columna. |
| 5 | `via_transporte` | `VARCHAR(10)` | no | `UK(2)` de `uq_maestro_destinos_id_via` | `AEREO` · `MARITIMO` (`ck_maestro_destinos_via_transporte`) | Vía que atiende el destino. Un puerto es marítimo y un aeropuerto aéreo; no hay destinos mixtos. Participa en la clave que referencia el pedido. |
| 6 | `ubicacion` | `GEOGRAPHY(Point,4326)` | no | | Punto WGS 84 | Coordenadas del destino. Es el centro desde el que RN-05 mide la proximidad. `GEOGRAPHY` y no `GEOMETRY` para que `ST_Distance` devuelva metros. **No estaba en el SRS §8.3**; sin ella RN-05 no se puede evaluar. |
| 7 | `radio_geocerca_km` | `INTEGER` | **sí** | | `> 0`, o `NULL` (`ck_maestro_destinos_radio`) | Radio de la geocerca **para este destino**. `NULL` significa «usar el valor global de `parametros_sistema.radio_geocerca_km`», que es el «por defecto» de 50 km que menciona RN-05. Existe porque 50 km alrededor de un aeropuerto capturan tráfico en sobrevuelo. |
| 8 | `lead_time_dias` | `INTEGER` | no | | `>= 0` (`ck_maestro_destinos_lead_time`) | Días de desembarque, nacionalización y traslado hasta planta. **Único por destino** (RN-12): no existe lead time crítico, el SRS lo eliminó por error de redacción. **No incluye** el circuito interno de Control de Calidad —unos 15 días entre ingreso y liberación—, que el SRS §7.1 deja fuera de RN-01. |
| 9 | `activo` | `BOOLEAN` | no, *default* `true` | | `true` · `false` | Si el destino se emplea para los cálculos. Es la baja lógica: los destinos no se borran, porque el FK desde el pedido es `RESTRICT`. |
| 10 | `observacion` | `TEXT` | sí | | Texto libre | Comentarios logísticos. Sin uso funcional. |
| 11 | `creado_en` | `TIMESTAMPTZ` | no, *default* `now()` | | Instante UTC | Alta de la fila. |
| 12 | `actualizado_en` | `TIMESTAMPTZ` | no, *default* `now()` | | Instante UTC | Última modificación. Relevante: cambiar `lead_time_dias` no reescribe los pedidos ya calculados, que conservan su copia. |

### 2.2 Restricciones de tabla

| Restricción | Definición | Qué garantiza |
|---|---|---|
| `pk_maestro_destinos` | `PRIMARY KEY (id)` | |
| `uq_maestro_destinos_codigo` | `UNIQUE (codigo)` | Un destino por código; es la clave de resolución en la ingesta |
| `uq_maestro_destinos_id_via` | `UNIQUE (id, via_transporte)` | Redundante por definición, pero **necesaria**: es el destino del FK compuesto desde `pedidos_transito` |

### 2.3 Notas

- Es un catálogo de **decenas de filas**. No lleva más índices que sus claves, y
  **no lleva índice GIST** sobre `ubicacion`: la consulta de RN-05 llega al
  destino por clave primaria y calcula una sola distancia, así que no hay
  búsqueda espacial que acelerar.
- `US-13` implementa el mantenimiento. Al editar `lead_time_dias`, el efecto
  sobre los pedidos vivos ocurre en el siguiente recálculo de `US-12`, no de
  inmediato.

---

## 3. `historial_tracking`

Secuencia **inmutable** de posiciones por elemento rastreado, con el payload
íntegro de la fuente. Es la tabla que sostiene RNF-13 y la que domina el
crecimiento de la base. Modelo: [`data-model.md` §3](data-model.md).

### 3.1 Campos

| # | Campo | Tipo | Nulo | Clave | Dominio | Descripción |
|---|---|---|---|---|---|---|
| 1 | `id` | `BIGSERIAL` | no | `PK` | Entero positivo, autogenerado | Identificador del registro histórico. |
| 2 | `id_elemento_rastreado` | `BIGINT` | no | `FK` → `elementos_rastreados(id)`, `UK(1)` | Existente en `elementos_rastreados` | Elemento que reportó la posición. El historial cuelga **del elemento, no del pedido**: si cinco líneas de OC viajan en el mismo buque, la lectura se guarda una sola vez. El SRS §8.4 lo tipa `VARCHAR`, que es un error: la clave a la que apunta es `BIGSERIAL`. |
| 3 | `fecha_registro` | `TIMESTAMPTZ` | no | `UK(2)` | Instante UTC | Momento de la captura reportado por la fuente, no el de la inserción. |
| 4 | `posicion` | `GEOGRAPHY(Point,4326)` | no | | Punto WGS 84 | Posición reportada. **Sustituye a `latitud` y `longitud`** de §8.4: el propio SRS §8.6 declara insuficiente guardarlas como numéricos sueltos. Los valores crudos siguen íntegros en `payload_api`. |
| 5 | `velocidad` | `NUMERIC(6,2)` | sí | | `>= 0` (`ck_historial_tracking_velocidad`) | Velocidad sobre tierra. Anulable porque AIS no siempre la reporta, pero **una fila sin velocidad no sirve para inferir arribo**: RN-05 la exige bajo umbral y RN-16 la usa para estimar la ETA. `US-08` y `US-11` deben tratar el nulo explícitamente y no asumir cero. |
| 6 | `rumbo` | `NUMERIC(5,2)` | sí | | `0` a `360` (`ck_historial_tracking_rumbo`) | Curso o rumbo reportado. |
| 7 | `estado_api` | `VARCHAR(40)` | sí | | Texto crudo de la fuente | Estado tal como lo reporta la fuente externa, sin traducir (por ejemplo el estado de navegación AIS). Se guarda sin normalizar a propósito: normalizarlo aquí perdería información que RNF-13 exige conservar. |
| 8 | `payload_api` | `JSONB` | no | | Objeto JSON | Respuesta **completa** de la API. Es el campo que hace cumplible RNF-13: cualquier estado calculado debe poder reconstruirse a partir de él. No se recorta ni se filtra. |

### 3.2 Restricciones de tabla

| Restricción | Definición | Qué garantiza |
|---|---|---|
| `pk_historial_tracking` | `PRIMARY KEY (id)` | |
| `uq_historial_tracking_elemento_fecha` | `UNIQUE (id_elemento_rastreado, fecha_registro)` | **Idempotencia de la ingesta.** La conexión de AISStream se cae y al reconectar puede reenviar mensajes ya procesados; con esta clave, `US-02` escribe con `ON CONFLICT DO NOTHING` y los duplicados no ensucian el trayecto |
| `fk_historial_tracking_id_elemento_rastreado_elementos_rastreados` | `ON DELETE RESTRICT` | Que borrar un elemento **no** se lleve su historial. Un `CASCADE` haría irreconstruible lo que RNF-13 exige conservar |

### 3.3 La tabla es append-only

| Consecuencia | Motivo |
|---|---|
| **No tiene `actualizado_en`** | Una fila que nunca se modifica no necesita sello de modificación, y tenerlo invitaría a modificarla |
| **No tiene borrado lógico** | La depuración del histórico es política de retención (`TASK-10`), no un estado de la fila |
| **El rol de aplicación no debería tener `UPDATE` ni `DELETE`** | Es la forma barata de que la inmutabilidad sea una propiedad del sistema y no una promesa. Se resuelve al crear el rol en `TASK-01` |

### 3.4 Índices y volumen

| Índice | Definición | Motivo |
|---|---|---|
| `uq_historial_tracking_elemento_fecha` | `(id_elemento_rastreado, fecha_registro DESC)` | Hace doble trabajo: la idempotencia de §3.2 y las dos únicas consultas reales — última lectura de un elemento, y trayecto ordenado de RF-22 |
| `ix_historial_tracking_fecha_registro` | `BRIN (fecha_registro)` | Tabla *append-only* cuyo orden físico coincide con el temporal: el caso de manual para BRIN. Un btree sobre 25 millones de filas ocuparía cientos de MB; el BRIN, decenas de KB |

**Dimensionamiento medido, no estimado a ojo:** con los intervalos de los spikes
—62,2 s entre mensajes AIS por buque, 31 s de consulta ADS-B— y 30 buques más 10
aeronaves activos, la tabla crece **~69 600 filas/día, ~25 millones al año,
~20 GB con el payload**. De ahí que `US-04` deba nacer con un intervalo mínimo
entre lecturas persistidas, y que el submuestreo de `TASK-10` sea estructural y
no un `Could`.

**Sin índice GIST sobre `posicion`:** no existe la consulta «qué se movió cerca
de este punto». El trayecto se recupera por elemento y fecha.

---

## 4. `elementos_rastreados`

Nave o vuelo objeto de seguimiento. Desacopla el identificador externo, la ETA y
la última posición del pedido individual. Modelo:
[`data-model.md` §4](data-model.md).

### 4.1 Campos

| # | Campo | Tipo | Nulo | Clave | Dominio | Descripción |
|---|---|---|---|---|---|---|
| 1 | `id` | `BIGSERIAL` | no | `PK` | Entero positivo, autogenerado | Identificador del elemento rastreado. |
| 2 | `tipo_tracking_externo` | `VARCHAR(20)` | no | `UK(1)` parcial | `MMSI` · `IMO` · `NOMBRE_BUQUE` · `VUELO` · `ICAO24` · `AWB` · `CONTENEDOR` · `BOOKING` (`ck_elementos_rastreados_tipo`) | Tipo del identificador externo. El dominio sale de RF-03, más `ICAO24`, que RF-03 no menciona pese a ser el que OpenSky devuelve y `US-06` resuelve. |
| 3 | `tracking_externo` | `VARCHAR(50)` | no | `UK(2)` parcial | Valor según el tipo | Valor del identificador externo: el MMSI de nueve dígitos para buques, el `icao24` hexadecimal para aeronaves. |
| 4 | `via_transporte` | `VARCHAR(10)` | no | `UK(2)` de `uq_elementos_rastreados_id_via` | `AEREO` · `MARITIMO` (`ck_elementos_rastreados_via`) | Vía del elemento. Determina qué fuente lo consulta. |
| 5 | `eta_api` | `TIMESTAMPTZ` | sí | | Instante UTC | ETA **declarada por la fuente**, con carácter informativo. Rara vez existe en la vía marítima: el spike TG-10 halló que la ETA solo viaja en mensajes `ShipStaticData`, presentes en ~12 % de las naves. La ETA que alimenta el cálculo es `pedidos_transito.eta_utilizada`. |
| 6 | `ata_api` | `TIMESTAMPTZ` | sí | | Instante UTC | Llegada real reportada por la fuente, si existe. Distinta de `pedidos_transito.ata_confirmada`, que es la manual y prevalece por RN-14. |
| 7 | `posicion_actual` | `GEOGRAPHY(Point,4326)` | sí | | Punto WGS 84 | Última posición conocida. **Desnormalizada a propósito**: es copia de la lectura más reciente del historial, y existe para que el dashboard no consulte una tabla de 25 millones de filas. Es lo que hace compatibles RNF-01 y RNF-22. El SRS §8.5 la tipa `GEOMETRY`; se corrige a `GEOGRAPHY` por la convención del repositorio. |
| 8 | `velocidad_actual` | `NUMERIC(6,2)` | sí | | `>= 0` (`ck_elementos_rastreados_velocidad`) | Velocidad de la última lectura. Desnormalizada por la misma razón: RN-05 y RN-16 la consultan en cada recálculo. **No estaba en el SRS §8.5.** |
| 9 | `ultima_actualizacion_api` | `TIMESTAMPTZ` | sí | | Instante UTC | Fecha y hora de la última consulta exitosa. Es el insumo del indicador de frescura de RF-20 y `US-23`. |
| 10 | `activo` | `BOOLEAN` | no, *default* `true` | | `true` · `false` | Si el elemento sigue siendo objeto de rastreo automático. Participa en el índice único parcial: **un identificador externo puede repetirse en el histórico, pero solo uno puede estar activo**. |
| 11 | `creado_en` | `TIMESTAMPTZ` | no, *default* `now()` | | Instante UTC | Alta de la fila. |
| 12 | `actualizado_en` | `TIMESTAMPTZ` | no, *default* `now()` | | Instante UTC | Última modificación, típicamente por una lectura nueva. |

### 4.2 Restricciones de tabla

| Restricción | Definición | Qué garantiza |
|---|---|---|
| `pk_elementos_rastreados` | `PRIMARY KEY (id)` | |
| `uq_elementos_rastreados_externo_activo` | `UNIQUE (tipo_tracking_externo, tracking_externo) WHERE activo` | Un solo seguimiento activo por identificador externo, permitiendo que el mismo valor reaparezca en el histórico |
| `uq_elementos_rastreados_id_via` | `UNIQUE (id, via_transporte)` | Destino del FK compuesto desde `pedidos_transito` |
| `ix_elementos_rastreados_activos` | `(via_transporte) WHERE activo` | El planificador de `US-07` recorre los elementos activos por vía en cada ciclo |

### 4.3 Por qué el índice único es parcial

Es la diferencia entre las dos vías, y conviene tenerla presente al implementar
la ingesta:

| Vía | Identificador | Estabilidad |
|---|---|---|
| Marítima | MMSI o IMO | **Estable**: un MMSI identifica un buque durante años |
| Aérea | `icao24` | **Efímero**: la misma aeronave vuela rutas distintas cada día |

`US-06` lo dice en su título: el `icao24` es un *«vínculo temporal del tramo»*.
Un `UNIQUE` global impediría registrar el vuelo de mañana de la misma aeronave.
Con el único parcial, la ingesta busca el elemento **activo** para ese
identificador y, si no existe, lo crea.

### 4.4 Un campo del SRS que no está aquí

`tramo` aparece en el SRS §8.5 como columna de esta tabla y **no se incluyó**.
El motivo está en [`data-model.md` §4.4](data-model.md): si un buque transporta
un pedido para el que es su segundo tramo y otro para el que es el primero, la
columna no tiene valor correcto. El número de tramo pertenece a la relación
pedido↔elemento, no al elemento.

Vive en `pedido_elemento_rastreado`, **aprobada en la revisión del 25/08**. La
decisión es firme: `tramo` no vuelve a esta tabla.

---

## 5. `proveedores`

Normalización del proveedor, hoy texto libre dentro del pedido. Modelo:
[`data-model.md` §5](data-model.md).

### 5.1 Campos

| # | Campo | Tipo | Nulo | Clave | Dominio | Descripción |
|---|---|---|---|---|---|---|
| 1 | `id` | `BIGSERIAL` | no | `PK` | Entero positivo, autogenerado | Identificador del proveedor. |
| 2 | `codigo` | `VARCHAR(20)` | no | `UK` | Código de proveedor en SAP | Clave natural. **Depende de la especificación de SAP, que no se ha recibido** (riesgo R2). Si SAP no expone código y solo manda texto, la normalización requiere coincidencia difusa, trabajo que hoy no está estimado en ninguna historia. |
| 3 | `nombre` | `VARCHAR(120)` | no | | Texto libre | Razón social del proveedor. |
| 4 | `pais` | `CHAR(2)` | sí | | ISO 3166-1 alfa-2 | País de origen. Habilita el análisis de desempeño por origen que motiva la entidad. |
| 5 | `activo` | `BOOLEAN` | no, *default* `true` | | `true` · `false` | Baja lógica. No se borran: el FK desde el pedido es `RESTRICT`. |
| 6 | `creado_en` | `TIMESTAMPTZ` | no, *default* `now()` | | Instante UTC | Alta de la fila. |
| 7 | `actualizado_en` | `TIMESTAMPTZ` | no, *default* `now()` | | Instante UTC | Última modificación. |

---

## 6. `materiales`

Normalización del material, hoy código y descripción concatenados. Modelo:
[`data-model.md` §6](data-model.md).

### 6.1 Campos

| # | Campo | Tipo | Nulo | Clave | Dominio | Descripción |
|---|---|---|---|---|---|---|
| 1 | `id` | `BIGSERIAL` | no | `PK` | Entero positivo, autogenerado | Identificador del material. |
| 2 | `codigo` | `VARCHAR(20)` | no | `UK` | Código de material en SAP | Clave natural. Misma dependencia de SAP que `proveedores.codigo`. |
| 3 | `descripcion` | `VARCHAR(200)` | no | | Texto libre | Descripción del material, **separada del código**. Esa separación es la razón de ser de la entidad: permite que el filtro de RF-19 opere sobre el código en vez de hacer `LIKE` sobre una cadena concatenada. |
| 4 | `unidad_medida` | `VARCHAR(10)` | sí | | Texto | Unidad **base** del material. Puede diferir de `pedidos_transito.unidad_medida`, que es la de la línea de pedido; por eso existe en ambas tablas. |
| 5 | `activo` | `BOOLEAN` | no, *default* `true` | | `true` · `false` | Baja lógica. |
| 6 | `creado_en` | `TIMESTAMPTZ` | no, *default* `now()` | | Instante UTC | Alta de la fila. |
| 7 | `actualizado_en` | `TIMESTAMPTZ` | no, *default* `now()` | | Instante UTC | Última modificación. |
