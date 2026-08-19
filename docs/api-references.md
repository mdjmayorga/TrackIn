# Referencias de APIs externas

Fuentes de datos de tracking que consumirá TrackIn. **Ninguna está integrada
todavía** — esto es documentación de referencia para los sprints de
implementación.

---

## AISStream — tracking marítimo

Posiciones de buques vía AIS (Automatic Identification System), por WebSocket.

- **Documentación:** <https://aisstream.io/documentation>
- **Protocolo:** WebSocket (`wss://stream.aisstream.io/v0/stream`)
- **Autenticación:** API key, en `AISSTREAM_API_KEY` del `.env`
- **Registro:** <https://aisstream.io/authenticate>

### Cómo funciona

Es una suscripción persistente, no un endpoint de consulta: se abre el socket,
se manda un mensaje de suscripción con las áreas (bounding boxes) y/o los MMSI
de interés, y el servidor empuja mensajes a medida que llegan.

Implicaciones de diseño:

- La conexión **se cae**. Hace falta reconexión con backoff exponencial y
  re-suscripción automática.
- Los mensajes llegan cuando el buque transmite, no a intervalos fijos. En
  alta mar las posiciones pueden espaciarse horas.
- Identificador del buque: **MMSI** (9 dígitos). El IMO es más estable en el
  tiempo pero no viaja en todos los tipos de mensaje AIS.

### Puntos a resolver en implementación

- [ ] Confirmar límites del plan gratuito (conexiones y mensajes)
- [ ] Definir qué mensajes AIS interesan (`PositionReport`, `ShipStaticData`)
- [x] Política de reconexión → **no depender de `close()` limpio** (ver spike)
- [ ] Estrategia de submuestreo antes de persistir (no guardar cada mensaje)

---

## AISStream — Spike técnico (TG-10)

> **Estado: fases técnicas completadas** el **18/08/2026** desde **red
> personal** (fases 0 y 2–6; la Fase 1 se absorbió en la Fase 0).
>
> Falta **replicar desde la red corporativa de Gutis** — esa comparación
> responde la pregunta 1 del spike.
>
> **Conclusión: viable con una limitación grave** (detalle al final).
>
> Script en `backend/scripts/spikes/aisstream/`, evidencia en `output/`.

### Diagnóstico de conectividad por capas (Fase 0)

El intento previo desde la laptop corporativa terminó en *«el WebSocket conecta,
la suscripción no da error, pero no llegan mensajes»*. Ese síntoma es compatible
con causas muy distintas, así que el script prueba **seis capas por separado** y
reporta en cuál se rompe. Se suscribe al **bounding box global** a propósito:
así la ausencia de mensajes no se puede atribuir a haber elegido una zona sin
tráfico, que fue el punto ciego del intento anterior con el ejemplo de Japón.

| Capa | Resultado desde **red personal** |
|---|---|
| 1. DNS | ✅ `stream.aisstream.io` → `136.243.173.177` |
| 2. TCP:443 | ✅ 201 ms |
| 3. TLS | ✅ TLSv1.3, emisor **Let's Encrypt** → **sin inspección TLS** |
| 4. HTTPS a `aisstream.io` | ✅ HTTP 200 |
| 5. Handshake WebSocket | ✅ 1096 ms |
| 6. Suscripción y datos | ✅ **25 mensajes en 0.6 s**, primero a los 314 ms |

**La API key es válida y la cuenta funciona.** Ese punto queda descartado como
causa del bloqueo original.

La capa 3 es la decisiva para el diagnóstico corporativo: si desde Gutis el
emisor del certificado **no** es una CA pública, hay un proxy terminando y
reescribiendo el TLS, lo que explicaría un handshake exitoso con frames
descartados.

### El cierre del WebSocket se cuelga con volumen alto

Descubierto al depurar el propio script de diagnóstico, que se colgaba
indefinidamente pese a tener un deadline interno de 30 s.

**Causa:** el bucle recibía sus mensajes en menos de un segundo, pero se
bloqueaba al salir del context manager. Con bounding box global el servidor
emite decenas de mensajes por segundo; `websockets` intenta un cierre negociado
que **nunca completa**, porque no alcanza a drenar el backlog mientras el
servidor sigue enviando.

**Solución:** abortar el transporte (`websocket.transport.abort()`) en lugar de
negociar el cierre.

**Para Sprint 3:** la estrategia de reconexión **no puede depender de un
`close()` limpio**. Hay que forzar el socket y considerar la conexión muerta sin
esperar el handshake de cierre. Un timeout interno en el bucle de recepción
**no basta**: el bloqueo ocurre fuera de ese bucle.

### Volumen preliminar

25 mensajes en 0.6 s con bounding box global ≈ **40+ mensajes/segundo**. Cifra
provisional, tomada en una ráfaga corta; la Fase 4 del spike la medirá en serio
para dimensionar el backend.

### Cobertura en el Caribe (Fase 2)

Captura de 3 minutos sobre el Caribe occidental
(`lat 7–25`, `lon −90 a −59`), con el dataset crudo guardado en
`02_caribbean_raw_personal.jsonl` para analizarlo sin volver a capturar.

| Métrica | Valor |
|---|---|
| Mensajes | 161 en 181 s (**0.9 msg/s**) |
| Buques únicos (MMSI) | 133 |
| Mensajes por buque | **1.2** |
| Volumen | 92 KB (0.51 KB/s) |
| En radio de Puerto Moín (50 km) | **0** |
| En aproximación a Limón (165 km) | 2 |

Con bounding box **global** la Fase 0 recibía ~40 msg/s; el Caribe entero da
0.9. Y 1.2 mensajes por buque en tres minutos es anómalo: un buque con AIS
transmite cada 2–10 s.

### ⚠️ No hay cobertura AIS en la costa caribe de Costa Rica — CONFIRMADO

> Las fases 2 y 4 solo observaron la zona ~11 minutos, insuficiente para
> descartar bajo tráfico momentáneo. La **Fase 6 lo resolvió** con una captura
> de 45 minutos: ver más abajo.

La causa de la anomalía apunta a **cobertura de receptores, no a limitación del
plan**. El 95% de los mensajes se concentra en 8 celdas, todas costeras:

| Celda (lat, lon) | Mensajes | Zona |
|---|---|---|
| +10, −62 | 63 | Trinidad / Venezuela |
| +10, −76 | 41 | Cartagena / Santa Marta |
| +12, −62 | 16 | Trinidad |
| +18, −72 | 15 | La Española |
| +24, −82 · +22, −84 | 9 | Cuba |
| +20, −88 | 4 | Yucatán |

**Ninguna cerca de Costa Rica.** El AIS terrestre es VHF con alcance de 40–70 km
desde la costa; el AIS satelital, que cubriría mar abierto, no está incluido en
el plan gratuito.

#### Test controlado (Fase 4)

Para descartar que fuera simple ausencia de tráfico, se capturaron 8 minutos
suscrito **simultáneamente** a la zona de interés y a una **zona de control**
(Cartagena) donde ya se sabía que hay receptores activos.

| Zona | Mensajes | Buques |
|---|---|---|
| Control — Cartagena | 116 | **55** |
| Interés — CR/Panamá caribe | 11 | 7 |
| **De los cuales, costarricenses** | **0** | **0** |

Los 7 buques de la zona de interés resultaron ser **yates recreativos fondeados
en Bocas del Toro, Panamá** (9.33 N, 82.24 W; MMSI estadounidenses y
canadienses, `StandardClassBPositionReport`), a **~118 km de Puerto Moín**.

> **Nota metodológica:** la primera versión del script definía la zona de
> interés como un solo bounding box que cruzaba la frontera, y su veredicto
> automático concluyó «hay cobertura en Costa Rica» contando tráfico panameño.
> El script se corrigió para subdividir por longitud (frontera en −82.56).
> El grupo de control cumplió su función: descarta fallo de conexión o de
> suscripción como explicación del cero.

#### El vacío geográfico

Distancia a Puerto Moín de los buques más cercanos detectados en toda la captura
del Caribe (133 buques):

| Distancia | Buque | Zona |
|---|---|---|
| 118 km | `DELPHINUS` | Bocas del Toro, Panamá |
| 119 km | *(sin nombre)* | Bocas del Toro |
| 354 km | `DOMICIL` | Canal de Panamá |
| 407 km | *(sin nombre)* | Canal de Panamá |
| 793 km | `LE HAVRE EXPRESS` | Cartagena |

Solo **2 de 133 buques** a menos de 200 km de Moín, y ambos en Panamá. El vacío
entre 119 y 354 km es contiguo y cubre toda la costa caribe costarricense. Un
hueco geográfico continuo se parece más a ausencia de receptores que a
casualidad estadística — pero deriva de la misma captura corta.

**Ningún buque del dataset declara destino costarricense**, aunque eso no prueba
nada: solo 16 de 133 declararon destino de cualquier tipo.

#### Argumento a favor de la hipótesis

Un buque Clase A **atracado o fondeado sigue transmitiendo cada ~3 minutos**. En
Moín opera la terminal de contenedores de APM, donde es raro que no haya al
menos un buque en muelle o esperando. Si existiera un receptor cubriendo la
zona, deberían haberse visto mensajes de buques estáticos sin necesidad de que
pasara ninguno navegando.

#### Captura larga de control (Fase 6) — la prueba decisiva

45 minutos suscrito simultáneamente a la costa caribe de **Costa Rica y
Nicaragua** (bounding box `lat 9.5–15.0`, `lon −84.5 a −82.6`, que **excluye
Panamá** para que Bocas del Toro no contamine) y a Cartagena como control.

| Minuto | CR + Nicaragua | Control — Cartagena |
|---|---|---|
| 5 | 0 msg / 0 buques | 56 msg / 37 buques |
| 20 | **0 / 0** | 281 / 65 |
| 35 | **0 / 0** | 511 / 74 |
| **45** | **0 msg / 0 buques** | **641 msg / 76 buques** |

**Cero reconexiones** durante toda la captura: la conexión estuvo estable de
principio a fin. Misma conexión, misma suscripción, mismo parseo — un bounding
box recibió 641 mensajes y el otro ni un byte.

Para atribuir esto a bajo tráfico tendría que no haber habido **ni una sola
embarcación con AIS** en cientos de kilómetros de costa de dos países —
incluyendo Moín, Limón, Bluefields y Puerto Cabezas — durante 45 minutos. Ni un
carguero, ni un pesquero con Clase B, ni un remolcador de puerto. Y cualquier
buque atracado habría emitido ~15 veces en esa ventana.

**Conclusión establecida: no hay receptores AIS cubriendo la costa caribe de
Costa Rica ni de Nicaragua en el plan gratuito de AISStream.** El receptor útil
más cercano está en Bocas del Toro, Panamá, a ~118 km de Moín, fuera de alcance
VHF.

**Impacto en TrackIn:** no se puede confirmar la llegada de un buque a Moín con
esta fuente. Sí se le puede seguir en los tramos con cobertura — salida del
puerto de origen, Cartagena, aproximación al Canal de Panamá — perdiendo la
traza en el último tramo. **Es una decisión de negocio, no técnica**, si eso
alcanza: hay que plantearlo con Compras.

### Tipos de mensaje y relación nave ↔ carga (Fase 3)

| Tipo | % | Utilidad para TrackIn |
|---|---|---|
| `PositionReport` | 47.2% | Posición de buque comercial (Clase A) — **núcleo** |
| `StandardClassBPositionReport` | 24.2% | Posición de embarcación menor |
| `StaticDataReport` | 12.4% | Estáticos de Clase B — sin IMO ni destino |
| `ShipStaticData` | 11.8% | **IMO, destino, ETA, nombre — liga nave y carga** |
| `BaseStationReport` | 2.5% | Estación costera — ignorable |
| `AidsToNavigationReport` | 1.2% | Boya o baliza — ignorable |

**Completitud de la identificación** (sobre 133 buques):

| Campo | Cobertura |
|---|---|
| MMSI | **100%** |
| Nombre | 93.2% |
| IMO | **13.5%** |
| Destino | **12.0%** |
| ETA | 13.5% |

Los datos que ligan la nave con su carga viajan **solo** en `ShipStaticData`,
que es el 12% de los mensajes. Hay que **persistirlos aparte** y no esperarlos
en cada posición.

**⚠️ `Destination` es texto libre escrito por la tripulación.** Ejemplos reales
capturados:

```
COSMR        CO SMR       SANTA MARTA COSMR      CHAGUARAMAS TRINIDAD
TTCHA        IT LIV       CARTAGENA              CO POC
```

Mezcla de UN/LOCODE con texto arbitrario, mayúsculas inconsistentes y
abreviaturas propias. **No se puede parsear como código de puerto sin
normalizar.** Varias ETA vienen como `0-0 0:00` (no declarada) y al menos una
apuntaba a mayo estando en agosto.

**Identificador estable: MMSI** (100% de cobertura). El IMO es más estable en el
tiempo pero solo aparece en el 13.5% de los buques.

### Frecuencia y volumen

| Métrica | Valor |
|---|---|
| Buques con un solo mensaje | 111 de 133 |
| Intervalo entre mensajes del mismo buque | mediana **62 s** (min 7 s, max 167 s) |
| Extrapolación diaria (Caribe completo) | ~77 000 mensajes ≈ **43 MB/día** en bruto |

43 MB/día en bruto es manejable, pero **no hay que persistir cada mensaje**:
con submuestreo de una posición por buque cada N minutos el volumen baja
drásticamente.

### Resiliencia y reconexión (Fase 5)

Pruebas sobre la zona de Cartagena, donde hay receptores confirmados, para que
la ausencia de datos signifique fallo de conexión y no falta de tráfico.

| Prueba | Resultado |
|---|---|
| API key inválida | El servidor **cierra la conexión** (`ConnectionClosedError`, sin close frame) |
| Suscripción malformada | **Idéntico**: cierra la conexión igual |
| Dos conexiones simultáneas, misma key | ✅ Ambas reciben datos — el plan lo permite |
| Reconexión ×3 | 3/3 con datos; **1.1 s → 4.9 s → 14.7 s** hasta el primer mensaje |
| Gaps entre mensajes (120 s en Cartagena) | mediana 1.47 s · p95 12.85 s · máx 15.28 s |

#### Estrategia recomendada para Sprint 3

**1. Los errores no son distinguibles entre sí.** Una API key inválida y una
suscripción malformada producen exactamente el mismo cierre. El módulo detecta
*que* falló pero no *por qué*. Hay que validar el formato de la suscripción
antes de enviarla y tratar el cierre inmediato tras conectar como problema de
credencial, distinguiéndolo por el momento en que ocurre.

**2. Backoff exponencial obligatorio, arrancando en 1 s con techo de 60 s.** El
tiempo hasta recibir datos se degradó de 1.1 s a 14.7 s en tres reconexiones
seguidas. La muestra es pequeña, pero apunta a que reconectar agresivamente se
penaliza. No reintentar en bucle cerrado.

**3. El watchdog NO puede basarse en ausencia de datos.** Los gaps medidos
son de una zona activa. Como **Moín no tiene cobertura** (Fase 4), un watchdog
que reconecte tras N segundos de silencio entraría en **bucle infinito** al
suscribirse justamente a la zona que le interesa a TrackIn. La detección de
socket muerto debe apoyarse en el **ping/pong del protocolo WebSocket**, que es
independiente del tráfico de datos.

**4. Una sola conexión multiplexando bounding boxes.** El plan admite varias
conexiones simultáneas, pero usar una sola con todos los bounding boxes deja
menos estado que reconciliar tras una caída.

**5. Cerrar abortando el transporte**, nunca esperando el `close()` negociado
(ver hallazgo de la Fase 0).

### Conclusión: **VIABLE CON UNA LIMITACIÓN GRAVE**

La API funciona, es estable y la integración es sencilla. Pero **no cubre el
destino final** de las importaciones marítimas de Gutis, confirmado con una
captura controlada de 45 minutos.

Lo que **sí** permite:

- Seguimiento en tramos con cobertura: puerto de origen, Cartagena, aproximación
  al Canal de Panamá.
- Identificación por MMSI con 100% de cobertura.
- Reconexión fiable y volumen de datos manejable (~43 MB/día en bruto).

Lo que **no** permite:

- Confirmar la llegada de un buque a **Puerto Moín**: cero cobertura AIS en la
  costa caribe de Costa Rica y Nicaragua, confirmado en 45 minutos de captura
  con grupo de control.
- Depender de `Destination` o `ETA`: solo el 12% de los buques los declara, y
  el destino es texto libre sin normalizar.

**Decisión pendiente, y es de negocio más que técnica:** si el seguimiento
marítimo sin el tramo final es suficiente para Compras. Si se necesita
confirmación de arribo a Moín, hay que evaluar AIS satelital de pago o una
fuente alternativa (ver «Otras fuentes evaluadas» al final del documento).

### Pendientes

- [ ] **Replicar la Fase 0 desde red Gutis** (`--network gutis`) — cierra la
      pregunta 1 del spike
- [x] ~~Confirmar si la ausencia en CR es falta de cobertura o bajo tráfico~~ —
      resuelto por la Fase 6: falta de cobertura
- [ ] **Plantear a Compras** si un seguimiento sin el tramo final hasta Moín
      cubre la necesidad del negocio
- [ ] Si la respuesta es no: evaluar AIS satelital de pago para el tramo final

---

## OpenSky Network — tracking aéreo

Posiciones de aeronaves por REST.

- **Documentación:** <https://openskynetwork.github.io/opensky-api/>
- **API REST:** <https://openskynetwork.github.io/opensky-api/rest.html>
- **Protocolo:** HTTP REST, polling
- **Autenticación:** OAuth2 *client credentials* — `OPENSKY_CLIENT_ID` /
  `OPENSKY_CLIENT_SECRET` en el `.env`. La autenticación Basic con usuario y
  contraseña **fue retirada** (ver spike TG-11 abajo)
- **Registro:** <https://opensky-network.org/index.php?option=com_users&view=registration>

### Cómo funciona

Se consulta el estado actual (`/states/all`) filtrando por bounding box o por
`icao24`. Al ser polling, la frecuencia la define el cliente — y ahí está el
límite real.

Implicaciones de diseño:

- Hay **cuota de créditos diarios**, y las cuentas anónimas tienen mucha menos
  resolución temporal que las autenticadas. Conviene cachear y no consultar
  más seguido de lo que el negocio necesita.
- Identificador de la aeronave: **icao24** (hexadecimal de 24 bits).
- La cobertura depende de receptores voluntarios: sobre océano hay huecos.

### Puntos a resolver en implementación

- [x] Confirmar la cuota vigente para cuenta autenticada → **4000 créditos/día**
- [x] Definir el intervalo de polling según el SLA del dashboard → **31 s
      continuo, 10 s con ventanas**
- [ ] Comportamiento cuando no hay cobertura (¿última posición conocida?)
- [ ] Mapear número de vuelo del courier a `icao24`

---

## OpenSky Network — Spike técnico (TG-11)

> **Estado: fases técnicas completadas** el **18/08/2026**, todas desde **red
> personal**. Falta replicar desde la red corporativa de Gutis para el
> contraste A/B y una segunda corrida vespertina para MRLB. La Fase 5 (rate
> limits) se absorbió en las fases 1, 3, 4 y 6.
>
> **Conclusión: viable con ajustes** (detalle al final de esta sección).
>
> Scripts en `backend/scripts/spikes/opensky/`, evidencia JSON en
> `backend/scripts/spikes/opensky/output/`. Código descartable, no productivo.

### Autenticación — OAuth2 (Fase 1)

**Hallazgo bloqueante resuelto:** OpenSky retiró la autenticación Basic. El
`.env` del proyecto tenía las claves nombradas `OPENSKY_USERNAME` /
`OPENSKY_PASSWORD`, pero los valores guardados ahí ya eran las credenciales
OAuth2. Se renombraron las claves; **no hubo que regenerar credenciales**.

| Parámetro | Valor medido |
|---|---|
| Endpoint de token | `https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token` |
| Grant type | `client_credentials` |
| Formato del `client_id` | `<usuario>-api-client` |
| **TTL del token** | **1800 s (30 min)**, verificado contra los claims `iat`/`exp` del JWT |
| Latencia de obtención | ~1000 ms |
| Latencia de `/states/all` | 780–850 ms |

**Para Sprint 3:** el refresco del token debe ser proactivo (renovar al ~80%
del TTL, es decir a los 24 min), no reactivo al primer 401.

### Cuotas y rate limits (Fases 1 y 3)

El servidor devuelve el header **`x-rate-limit-remaining`** en cada respuesta,
lo que permite monitorear la cuota sin llevar contabilidad propia.

| Tipo de cuenta | Cuota diaria medida |
|---|---|
| Autenticada (OAuth2) | **4000 créditos** |
| Anónima (por IP) | **400 créditos** |

Una consulta con bounding box de ~11.5 grados² costó **1 crédito**, confirmado
muestra a muestra.

**Cálculo de viabilidad del polling:**

| Escenario | Intervalo sostenible |
|---|---|
| Piso teórico (100% de la cuota) | 21.6 s — **inutilizable**: no deja crédito para `/flights/*`, reintentos ni un segundo bbox |
| Continuo 24/7, reservando 30% de la cuota | **31 s** |
| Ventana de 12 h/día | **15 s** |
| Ventana de 8 h/día | **10 s** |

**Recomendación para Sprint 3:** sondeo por *ventanas activas*, no continuo. Un
embarque no está en vuelo las 24 horas; sondear de madrugada sin ningún vuelo
rastreado quema cuota sin obtener información. Con ventanas de 8 h se alcanzan
10 s, prácticamente el refresco real del servidor.

### Frecuencia de actualización (Fase 3)

Medido con 30 muestras cada 6 s sobre el bbox de Costa Rica.

| Métrica | Valor |
|---|---|
| Delta entre posiciones (mediana) | **7 s** |
| Delta mínimo / máximo | 1 s / 62 s |
| Consultas redundantes sondeando a 6 s | **39.5%** |

Sondear más rápido que ~7 s devuelve datos ya conocidos. **El límite real del
diseño lo impone la cuota, no la frescura del dato.**

### Cobertura sobre Costa Rica (Fase 2)

Medido con 5 muestras cada 30 s, bbox `lat 8.0–11.3`, `lon -86.0–-82.5`.

| Métrica | Resultado |
|---|---|
| Aeronaves por muestra | 12–14 (media 13.4) |
| Únicas por `icao24` | 14 |
| En radio de 28 km de **MROC** (SJO) | **8 (57%)** |
| En radio de 28 km de **MRLB** (LIR) | **0** |
| En tierra | 3 (21%) |
| En aproximación o salida (<3000 m) | 8 (57%) |
| En crucero | 3 (21%) |
| Frescura de posición | mediana **1 s**, máx 207 s |
| `position_source` | **0 (ADS-B puro)** en las 14 — ninguna MLAT ni FLARM |

**Hay cobertura de superficie y aproximación en Juan Santamaría**, incluidas
aeronaves detectadas en tierra. Eso permite confirmar un aterrizaje, no solo
inferirlo.

#### Segunda corrida — franja vespertina (13:52 hora local)

Evidencia en `02_coverage_personal.json`; la corrida matutina se conservó en
`02_coverage_personal_manana.json`.

| Métrica | Mañana (9:26) | Tarde (13:52) |
|---|---|---|
| Aeronaves únicas | 14 | **18** |
| En radio de MROC | 8 (57%) | **13 (72%)** |
| En tierra | 3 (21%) | **9 (50%)** |
| En radio de MRLB | 0 | **0** |
| Sin callsign | 1 (7%) | 4 (22%) |

**La salvedad de la corrida matutina queda resuelta.** En la franja vespertina
aparecen los vuelos internacionales que faltaban:

- `IBE02SJ` (Iberia, España) en aproximación a **2675 m** — transatlántico
- `UAL1560` (United) en aproximación a **892 m**
- `CJT5240` (**Cargojet**, Canadá) **en tierra en MROC** — carguero, que es el
  perfil exacto de un embarque farmacéutico
- `AMX691` (Aeroméxico) y `VOI3939` (Volaris) en tierra

**La cobertura sirve para el caso de uso de TrackIn.** Lo que faltaba en la
mañana era tráfico de largo alcance, no cobertura de receptores.

**MRLB (Liberia) dio cero en ambas corridas**, en franjas horarias distintas.
Dos muestras independientes con el mismo resultado apuntan a ausencia de
receptores ADS-B en Guanacaste. No es definitivo — agosto es temporada baja en
LIR — pero conviene **asumir que Liberia no tiene cobertura** hasta que se
demuestre lo contrario, y diseñar Sprint 3 sin depender de ella.

### Casos borde detectados (material para la Fase 6)

Capturados con datos reales, no hipotéticos:

| Caso | Evidencia |
|---|---|
| **Señal perdida en descenso** | `LRS1018`, a 2256 m con `vertical_rate` −4.88 m/s, `staleness` de **207 s**. Se pierde línea de vista con el receptor al bajar de altitud — justo cuando se quiere confirmar el aterrizaje |
| **Posición congelada** | `TIANI` apareció en las 30 muestras de la Fase 3 con **una sola posición distinta**: el registro sigue "vivo" pero no se mueve |
| **Callsign nulo y tardío** | `0ae105` reportó `callsign: null` en la Fase 2 y `TIAGO` tres minutos después. **`icao24` es el identificador estable; el callsign no es confiable de inmediato** |
| **Altitud nula en tierra** | Con `on_ground: true`, `baro_altitude` viene `null` en el 100% de los casos. Es correcto por diseño, pero el modelo de datos debe admitirlo |
| **Squawk inútil** | `squawk: null` en las 14 aeronaves. Descartado como vía de identificación |

### Identificación de un vuelo (Fase 4)

La cadena que hay que cerrar es:

```
AWB  ->  número de vuelo  ->  callsign  ->  icao24  ->  posición
        (courier)          (?)           (OpenSky)    (OpenSky)
```

OpenSky no conoce ni AWB ni número de vuelo. Se probaron las cuatro vías
disponibles:

| Vía | Endpoint | Resultado | Costo medido |
|---|---|---|---|
| A | `/states/all?icao24=` | ✅ Operativa | **4 créditos** |
| A' | `/states/all` con bounding box | ✅ Operativa | **1 crédito** |
| B | `/flights/arrival?airport=MROC` | ✅ Operativa, 69–103 llegadas/día | **30 créditos** |
| C | `/flights/aircraft?icao24=` | ✅ Operativa | **30 créditos** |
| D | `/tracks/all` (experimental) | ✅ Operativa, 64 puntos de trayectoria | sin medir |

**Costo plano por `icao24`:** pedir 1 aeronave o 5 cuesta lo mismo (4 créditos),
porque filtrar por `icao24` **sin** bounding box es una consulta global y paga
la tarifa máxima. Rastrear todos los embarques activos en **una sola consulta
agrupada** no tiene costo marginal. Un bounding box de Costa Rica cuesta solo
1 crédito, así que conviene aún más si todos los embarques convergen al mismo
destino.

**Los endpoints `/flights/*` cuestan 30 créditos** — 30 veces una consulta de
posición. Usarlos en un bucle de polling agotaría la cuota en 93 consultas.
Reservar para conciliación puntual.

**Regla de ventana de `/flights/aircraft`:** el límite de 2 particiones es por
**días UTC calendario tocados, no por duración**. Una ventana de 48 h alineada
a medianoche (`16T00 → 18T00`) funciona; una de 47 h que empiece a media tarde
toca tres días y devuelve `400`. Fácil de equivocar.

#### Latencia: dos comportamientos distintos

| Endpoint | Latencia observada |
|---|---|
| `/flights/aircraft` | **~17 min** — pero con `estArrivalAirport` en `null` |
| `/flights/arrival` | **~16.5 h** |

Un vuelo entra en `/flights/aircraft` casi de inmediato **sin destino
resuelto**, y solo aparece en `/flights/arrival` cuando ese destino se resuelve.
Eso es lo que tarda ~16 h.

**Consecuencia:** `/flights/arrival` **no sirve para detección de aterrizaje en
vivo**, solo para conciliación posterior. La detección en tiempo real debe
hacerse por posición: `on_ground = true` dentro del radio del aeropuerto,
validado en la Fase 2.

#### ⚠️ El `icao24` no es un atributo permanente del embarque

Historial real de la aeronave `0ac9e1` (Avianca) en 48 horas:

```
AVA072  SKBO → ?        AVA068  SKBO → MMUN
AVA263  KORD → SKBO     AVA262  SKBO → KORD
AVA021  KJFK → SKBO
```

**Cinco vuelos, cinco callsigns, una sola aeronave.** El `icao24` identifica el
avión; el callsign identifica el vuelo. El modelo de Sprint 3 **no debe guardar
el `icao24` como atributo fijo de un embarque**: hay que resolverlo en el
momento a partir del callsign y la fecha, y tratarlo como un vínculo temporal
válido solo para ese tramo. Guardarlo fijo haría que TrackIn siguiera un avión
que ya está volando a otro destino con otra carga.

#### Cuotas separadas por endpoint — confirmado

El header `x-rate-limit-remaining` **no es monótono entre endpoints distintos**
(serie observada: 3960, 3956, **3970**, 3940, **3996**). La causa quedó
confirmada por aritmética en la Fase 6: **cada familia de endpoints tiene su
propio contador, cada uno con cuota de 4000/día.**

Comprobación: 8 llamadas contabilizadas a `/flights/*` × 30 créditos = 240, y
el contador de `/flights/*` marcaba exactamente **3760 = 4000 − 240**, mientras
`/states/all` iba por 3941 con su propio consumo acumulado.

| Familia | Cuota diaria | Costo por consulta | Consultas/día |
|---|---|---|---|
| `/states/*` con bounding box | 4000 | 1 a 4 según área | 1000–4000 |
| `/states/*` por `icao24` (global) | 4000 | 4 | 1000 |
| `/flights/*` | 4000 | **30** | **133** |
| `/tracks/*` | 4000 | 4 | 1000 |

**Tarifa por área del bounding box** (Fase 5, medida en seis tramos):

| Área | Costo | Ejemplo medido |
|---|---|---|
| < 25 grados² | **1** | Costa Rica (12 deg²) → 1 |
| < 100 grados² | **2** | 54 deg² → 2 |
| < 400 grados² | **3** | Centroamérica (176 deg²) → 3 |
| ≥ 400 grados² | **4** | Caribe (1000), Américas (6375), global (64800) → 4 |

Los umbrales son **25 / 100 / 400**. Ampliar el área para cubrir la ruta
completa de un vuelo cuadruplica el costo: conviene sondear el área de destino,
no la ruta entera.

`/tracks/all` cuesta 4 créditos y devuelve `404` cuando no hay trayectoria
disponible para esa aeronave — no depende de que esté en vuelo (se verificó con
una aeronave en tierra que devolvió `200`).

**Presupuesto real para Sprint 3:** el polling de posiciones y las consultas de
conciliación **no compiten entre sí**. Eso relaja el cálculo de la Fase 3: la
reserva del 30% para `/flights/*` no era necesaria, porque salen de otra bolsa.
Pero `/flights/*` solo admite **133 consultas diarias**, así que hay que usarlo
con parsimonia.

### Casos borde y contrato de errores (Fase 6)

| Caso provocado | Respuesta de la API | ¿Consume cuota? |
|---|---|---|
| `icao24` inexistente | `200` con **`states: null`** | Sí |
| Bounding box sin tráfico | `200` con **`states: null`** | Sí |
| Token inválido | `401`, sin header de cuota | **No** |
| Ventana de 3 particiones | `400` con mensaje explicativo | **No** |
| Falta `begin`/`end` | `400` con JSON de error | **No** |
| Aeropuerto inexistente | `404` con cuerpo `[]` | **Sí — 30 créditos** |

**⚠️ Trampa de deserialización:** cuando no hay aeronaves, la API devuelve
`states: null`, **no una lista vacía**. Iterar el resultado sin comprobar `null`
lanza `TypeError`. El módulo de Sprint 3 debe normalizar `null → []` al
deserializar. Esto ocurre tanto por `icao24` inexistente como por bounding box
sin tráfico, que son situaciones normales, no excepcionales.

**Un `404` por aeropuerto mal escrito cuesta 30 créditos** — el 0.75% de la
cuota diaria de `/flights/*`. Validar los códigos OACI antes de consultar.

#### Señal perdida: la API no distingue tres situaciones distintas

Dos muestras separadas 60 s: **7.7% de las aeronaves desapareció** del bounding
box. El caso observado fue `CMP884` (Copa), en crucero a 10 668 m, con
`staleness` de 257 s al desaparecer.

La API **deja de listar** una aeronave sin decir por qué. Puede ser que salió
del área, que aterrizó, o que se perdió la señal — para el dashboard son
estados completamente distintos.

**Recomendación para Sprint 3:**

1. Persistir siempre la última posición conocida con su timestamp.
2. Mostrar *«última posición hace N min»* en lugar de afirmar *«en ruta»*.
3. Inferir aterrizaje **solo** si la última posición tenía `on_ground = true`
   dentro del radio del aeropuerto; si no, marcar **«señal perdida»**.
4. Confirmar a posteriori con `/flights/arrival` (con ~16 h de retraso).

### Conclusión: **VIABLE con ajustes**

OpenSky Network sirve como fuente aérea de TrackIn. Condiciones:

- **Detección en vivo por posición**, no por `/flights/arrival`.
- **Polling por ventanas activas** a ~10–31 s según la ventana.
- **Consulta agrupada** de todos los embarques activos: costo plano de 4
  créditos, o 1 si se usa bounding box.
- **`icao24` como vínculo temporal**, nunca como atributo fijo del embarque.
- Manejo explícito de `states: null` y de señal perdida.

#### Pendientes antes de cerrar TG-11 en Jira

- [x] ~~Segunda corrida vespertina de la Fase 2~~ — hecha, internacionales
      confirmados, MRLB sigue sin cobertura
- [ ] Replicar las fases 1–6 desde la **red corporativa de Gutis** (contraste A/B)

**No medido a propósito:** el comportamiento exacto ante `429`. Provocarlo
exige agotar 4000 créditos deliberadamente; el costo no justifica el dato. Se
maneja defensivamente leyendo `x-rate-limit-remaining`, presente en todas las
respuestas.

---

## Reglas de negocio: cálculo de estados

> **Pendiente de definir con Greivin.** Es el corazón funcional del sistema y
> no se puede inferir del código ni de las APIs: hay que levantarlo con el
> área de Compras en Sprint 1.

Preguntas abiertas:

- [ ] ¿Cuáles son los estados posibles de un pedido y sus transiciones válidas?
- [ ] ¿Contra qué fecha se mide una demora: ETA original, ETA vigente, o fecha
      comprometida con el cliente interno?
- [ ] ¿Cuántos días de atraso convierten un pedido en "crítico"?
- [ ] ¿El estado se recalcula continuamente o se congela en ciertos hitos?
- [ ] ¿Qué pasa cuando un pedido viene partido en varios embarques? ¿El estado
      es el del peor embarque?
- [ ] ¿Quién puede corregir manualmente un estado calculado, y queda trazado?
- [ ] ¿Hay que notificar a alguien al cambiar de estado? ¿Por qué canal?

Cuando estén definidas, documentar acá la tabla de transiciones y enlazar la
implementación en `backend/app/services/`.

---

## Otras fuentes evaluadas

| Fuente | Estado | Nota |
|---|---|---|
| MarineTraffic | Descartada por ahora | API de pago |
| VesselFinder | A evaluar | Tiene plan gratuito limitado |
| FlightAware | Descartada por ahora | API de pago |
