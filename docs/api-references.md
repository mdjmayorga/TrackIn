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

- [ ] 🔴 Confirmar límites del plan gratuito (conexiones y mensajes) — **hay
      indicios de haber topado uno**, ver «Réplica desde red Gutis». Riesgo
      **R1**, abierto desde el 19/08/2026
- [x] ~~Definir qué mensajes AIS interesan~~ — resuelto el 08/09 al implementar
      `US-02`, y **no eran los dos que decía este documento**: ver abajo
- [x] Política de reconexión → **no depender de `close()` limpio** (ver spike)
- [x] ~~Estrategia de submuestreo antes de persistir~~ — la resuelve `US-04`
      con `intervalo_minimo_persistencia_s`, ajustable sin desplegar código

### Qué mensajes interesan — resuelto el 08/09/2026

Este documento decía «`PositionReport`, `ShipStaticData`». Al implementar `US-02`
se contaron los tipos de los **161 mensajes reales** de la captura del 18/08 y
son **cuatro**, no dos: cada uno tiene su gemelo de Class B.

| Tipo | Mensajes | Qué aporta |
|---|---|---|
| `PositionReport` | 76 | Posición Class A |
| `StandardClassBPositionReport` | 39 | Posición Class B |
| `StaticDataReport` | 20 | Identidad Class B: solo el nombre, en la parte A |
| `ShipStaticData` | 19 | Identidad Class A: IMO, nombre, destino y ETA |
| `BaseStationReport`, `AidsToNavigationReport`, `UnknownMessage` | 7 | Nada; se ignoran |

Quedarse con los dos que este documento nombraba habría descartado **59 de 161
mensajes**, más de un tercio.

#### Cuatro trampas del formato, medidas sobre la captura

Ninguna es evidente leyendo la documentación de AISStream, y las cuatro están
cubiertas por `tests/test_aisstream.py`:

| Trampa | Detalle |
|---|---|
| **`time_utc` es formato Go, no ISO** | `2026-08-18 20:18:15.331999764 +0000 UTC`. `datetime.fromisoformat` lanza `ValueError`; la fracción trae 9, 8 o 6 dígitos y Python admite 6 |
| **Los estáticos no traen posición en el cuerpo** | 40 de 161 mensajes. Solo está en `MetaData` |
| **Los centinelas no son datos** | `TrueHeading = 511` en 44 de 115 posiciones, `Cog = 360` en 11. El segundo **viola el `CHECK`** `rumbo < 360` de `historial_tracking`: guardarlo da `IntegrityError`, no un dato malo |
| **La ETA no lleva año** | Solo mes, día, hora y minuto, y 11 de 19 la traen en ceros. El año se resuelve por cercanía al mensaje, no como «próxima ocurrencia» |

Los nombres y destinos vienen **rellenos a ancho fijo** (`'MARISOL             '`):
sin recortar, el mismo buque entra dos veces según por qué mensaje llegó.

#### Dónde vive la implementación

| Módulo | Qué hace |
|---|---|
| `app/services/rastreo/aisstream.py` | Parseo puro: tipos, centinelas, instante, ETA, suscripción |
| `app/services/rastreo/colector_ais.py` | El bucle de suscripción y la persistencia |

**El colector no tiene backoff propio.** Usa la política de `US-03`, leída de
`parametros_sistema`, así que la recomendación de «1 s con techo de 60 s» de la
Fase 5 dejó de ser código y es un `UPDATE`. El valor vigente por defecto —5 s con
techo de 300 s— es más conservador, que es lo que conviene con **R1** abierto.

---

## AISStream — Spike técnico (TG-10)

> **Estado: fases técnicas completadas** el **18/08/2026** desde **red
> personal** (fases 0 y 2–6; la Fase 1 se absorbió en la Fase 0).
>
> **Fase 0 replicada desde red Gutis el 19/08/2026.** La red corporativa
> queda **descartada** como causa del bloqueo original, pero la réplica
> destapó un problema distinto, del lado de la cuenta: ver «Réplica desde
> red Gutis» más abajo.
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

### Réplica desde red Gutis (19/08/2026)

> Corrida desde `gcorp.gutis.com` (Wi-Fi con dominio autenticado, DNS
> corporativo `10.0.10.12` / `10.0.10.11`). Evidencia en
> `01_connectivity_gutis.json`.

| Capa | Red personal (18/08) | **Red Gutis (19/08)** |
|---|---|---|
| 1. DNS | ✅ `136.243.173.177` | ✅ **misma IP** `136.243.173.177` |
| 2. TCP:443 | ✅ 201 ms | ✅ **21 ms** |
| 3. TLS | ✅ TLSv1.3, Let's Encrypt | ✅ TLSv1.3, **Let's Encrypt** |
| 4. HTTPS | ✅ HTTP 200 | ✅ HTTP 200 |
| 5. Handshake WebSocket | ✅ 1096 ms | ✅ **601 ms** |
| 6. Suscripción y datos | ✅ 25 msg en 0.6 s | ❌ **0 msg en 30 s** |

**No hay inspección TLS en la red Gutis.** El certificado lo firma Let's
Encrypt, igual que desde la red personal, y el host resuelve a la misma IP: no
hay proxy terminando el TLS ni DNS corporativo redirigiendo. Las capas 1–5 son
iguales o **más rápidas** que desde la red personal.

Pero la capa 6 da cero. El veredicto automático del script deja dos causas
abiertas —API key rechazada en silencio, o proxy que descarta los frames—, así
que se corrieron tres pruebas para separarlas:

| Prueba | Resultado | Qué descarta |
|---|---|---|
| Echo WebSocket público (`ws.postman-echo.com`) | ✅ eco recibido | Los frames **servidor → cliente** sí atraviesan la red Gutis |
| AISStream con key **inválida** | Servidor **cierra** a los 747 ms | La suscripción **llega** al servidor y el servidor **reacciona** |
| AISStream con la key **real** | Conexión **viva y muda**: 0 msg en 120 s, sin cierre | La key **no** está siendo rechazada |

La discriminación es limpia. Con una key inválida el servidor cierra la
conexión (el comportamiento documentado en la Fase 5); con la key real **no
cierra**, la mantiene abierta respondiendo ping/pong durante 120 s, y no manda
un solo frame de datos con bounding box **global**.

#### ⚠️ No es la red: es la cuenta

El argumento decisivo es la capa 3. **Sin inspección TLS, ningún intermediario
puede descartar selectivamente los frames de datos**: para un middlebox el
tráfico son bytes cifrados hacia `136.243.173.177:443`. Podría cortar la
conexión entera, pero no suprimir el payload dejando viva la conexión y
pasando los pings. Sumado a que el echo WebSocket sí funciona, la red queda
descartada.

Queda entonces el lado de AISStream: **la key es válida pero la cuenta no está
entregando datos.** La hipótesis más plausible es haber topado un **límite del
plan gratuito**, que es justamente el punto que seguía abierto en este
documento. La corrida del 18/08 fue intensiva: captura larga de 45 min, ocho
minutos de test controlado, tres minutos de Caribe y varias reconexiones.

**Pendiente de confirmar** — dos verificaciones baratas:

1. Revisar el estado de la cuenta y el consumo en <https://aisstream.io>.
2. Repetir la Fase 0 desde el hotspot del celular. Si desde otra red también
   da cero, la causa es la cuenta y queda cerrado.

**Esto no cambia la conclusión del spike**: la limitación grave sigue siendo la
falta de cobertura AIS en la costa caribe de Costa Rica, que se estableció con
datos capturados el 18/08 y no depende de este hallazgo.

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

> ⚠️ **Corregido el 20/08/2026.** Este párrafo afirmaba que la causa era
> «cobertura de receptores, **no** limitación del plan». **Esa inferencia quedó
> desmentida**: se verificó que VesselFinder y MyShipTracking publican escalas
> de Moín en vivo, con nombres y horas —`CHARLOTTE`, `GUADALUPE`,
> `ATLANTIC SUNFLOWER`, remolcadores maniobrando—. Si dos proveedores
> comerciales ven ese tráfico, **los receptores existen**. La medición de cero
> mensajes sigue siendo válida; lo que falla es la explicación causal. La
> carencia es **del plan gratuito de AISStream**, no del lugar.

La distribución geográfica de lo que sí llegó concentra el 95% de los mensajes
en 8 celdas, todas costeras:

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
traza en el último tramo.

### Verificación cruzada contra proveedores comerciales (20/08/2026)

Antes de asumir que el tramo final es irrecuperable, se comprobó si el hueco es
del lugar o de la fuente. **Es de la fuente.**

| Proveedor | Qué muestra para Moín |
|---|---|
| **VesselFinder** (`CRMOB001`) | 25 arribos en 24 h · 10 buques en puerto · declara que los detecta «processing of AIS data» |
| **MyShipTracking** | Nombres y horas: `CHARLOTTE` 20/08 11:46 · `GUADALUPE` 19/08 18:03 → 20/08 11:18 · `ATLANTIC SUNFLOWER` (183 m) · remolcador `SVITZER HANNE` · esperados `DEL MONTE SPIRIT` y `DOLE INCA` |

Los nombres son consistentes con la operación real de Limón —reefers bananeros
y un remolcador de Svitzer—, así que no es data reciclada.

**Consecuencia para la decisión de negocio:** deja de ser «¿pueden vivir sin
confirmación de arribo?» y pasa a ser **«confirmar el arribo cuesta del orden de
€330 al año»**. VesselFinder mantiene créditos prepago (10 000 créditos por
€330, 2 créditos por registro de escala, vigencia 12 meses) y su Port Calls API
entrega **ATA y ATD reales por puerto**, además de ETA reportada y predicha —lo
que ataca de paso el problema de que la ETA cruda del AIS sólo viaje en el 12%
de los mensajes.

> **Pendiente antes de comprar:** esta verificación se hizo contra las webs
> públicas, no contra la Port Calls API. Confirmar con el paquete mínimo de
> créditos, y medir la latencia del evento de arribo: un ATA con horas de
> retraso sirve para conciliar, no para el dashboard en vivo.

**Nota sobre MarineTraffic:** ya no es comparable en precio. Kpler lo adquirió
junto con Spire Maritime y FleetMon, y **descontinuó el modelo de créditos**:
hoy es sólo suscripción empresarial.

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

- [x] ~~**Replicar la Fase 0 desde red Gutis**~~ — hecho el 19/08: sin
      inspección TLS, la red queda descartada como causa
- [ ] 🔴 **Confirmar el límite del plan gratuito.** La key es válida (el
      servidor no la rechaza) pero no entrega datos desde el 19/08. Revisar la
      cuenta en <https://aisstream.io> y repetir la Fase 0 desde el hotspot del
      celular. **Bloquea cualquier captura nueva de AIS**
- [x] ~~Confirmar si la ausencia en CR es falta de cobertura o bajo tráfico~~ —
      resuelto por la Fase 6: falta de cobertura
- [ ] **Plantear a Compras** si un seguimiento sin el tramo final hasta Moín
      cubre la necesidad del negocio
- [ ] Si la respuesta es no: evaluar AIS satelital de pago para el tramo final

---

### Cobertura AIS en el Pacífico: Puerto Caldera — medido el 14/09/2026

Responde la pregunta 3 de `TASK-28`: *«¿Hay cobertura en Caldera? Está en el
Pacífico y el spike TG-10 solo evaluó el Caribe.»* Script en
`backend/scripts/spikes/task28/03_cobertura_caldera.py`.

**Veredicto: `SIN_COBERTURA_REGIONAL`.** No es que Caldera esté oscuro — el feed
gratuito de AISStream **no cubre el Pacífico oriental**.

| Zona | Mensajes | Buques |
|---|---|---|
| Geocerca de Caldera (10 km) | 0 | 0 |
| Golfo de Nicoya (~65 km) | 0 | 0 |
| **Balboa — control, entrada pacífica del Canal** | **0** | **0** |
| Pacífico abierto (resto de las cajas) | 2 | 1 |
| **Caribe — línea base del mismo día** | **254** | **173** |

Misma llave, mismos 180 s, capturas consecutivas.

#### Los dos controles son lo que hace válida la prueba

«Cero buques en Caldera» no prueba nada por sí solo. Hicieron falta dos:

1. **Balboa, dentro de la misma captura.** Una de las aguas más transitadas del
   mundo, a 600 km y en el mismo océano. Cero.
2. **El Caribe del mismo día.** TG-10 midió 161 mensajes en 180 s sobre esa caja
   el 18/08; hoy rindió **254**.

El segundo control **cierra de paso la duda que TG-10 dejó abierta** en «⚠️ No es
la red: es la cuenta». La cuenta entrega datos con normalidad: el cero del 18/08
fue transitorio y no era un límite del plan gratuito agotado de forma
permanente. La conclusión de TG-10 sobre la costa caribe **no cambia** —eso se
midió con datos propios— pero su pendiente número 1 queda resuelta.

#### ⚠️ La trampa del istmo

La primera versión de este script usó una sola caja «del Pacífico oriental»,
`[[5,-90],[15,-77]]`, y **seis de los siete buques capturados estaban en Bocas
del Toro** (lat 9.3, lon −82.2), que es **costa Caribe**. A estas latitudes el
istmo corre en diagonal y cualquier rectángulo grande abarca los dos océanos.

La versión corregida usa **dos cajas estrictamente pacíficas**: la costa de
Costa Rica y Nicaragua sin pasar de `lon −83.6`, y el Golfo de Panamá sin pasar
de `lat 9.0` (Colón está a 9.35 y es Caribe). Con las cajas bien puestas, el
Pacífico entero rindió **3 mensajes y 1 buque**.

#### Consecuencias

- **`US-11` (inferir el arribo por geocerca, RN-05) no es viable por AIS gratuito
  en ningún puerto marítimo.** TG-10 lo descartó para Moín y Limón; esto lo
  descarta para Caldera. La geocerca sigue existiendo en el maestro y sirve si
  la posición llega **de la fuente comercial**, no del AIS gratuito.
- **`US-14` (confirmación manual del desembarco) se refuerza como el único
  mecanismo de arribo marítimo, en los cuatro destinos.** Ya había subido de
  `Should` a `Must` el 01/09 por el hallazgo de Moín; ahora no queda ningún
  puerto que pudiera librarse.
- **Sube la exigencia sobre `ShipsGo`.** Si el AIS gratuito no ve ninguno de los
  puertos de entrada, el hito de descarga tiene que venir del proveedor
  comercial. Es lo que mide la fase 3 con una referencia real.
- **`US-02` no cambia.** Su papel ya era «¿por dónde va?» entre hitos, no
  «¿llegó?», y eso lo cumple en el Caribe, que es por donde entra el grueso de
  la carga marítima.

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

> **Estado: fases técnicas completadas** el **18/08/2026** desde **red
> personal** y **replicadas íntegras (fases 1–6) desde red Gutis el
> 19/08/2026**. La Fase 5 (rate limits) se absorbió en las fases 1, 3, 4 y 6.
>
> **El contraste A/B no encontró ninguna diferencia atribuible a la red
> corporativa**: ver «Réplica desde red Gutis» al final de esta sección.
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

### Réplica desde red Gutis (19/08/2026)

Fases 1–6 corridas íntegras desde `gcorp.gutis.com`. Evidencia en los archivos
`*_gutis.json`. **Ningún hallazgo del spike cambió**: la red corporativa no
degrada ni bloquea nada de OpenSky.

| Medición | Red personal (18/08) | **Red Gutis (19/08)** |
|---|---|---|
| Token OAuth2 | HTTP 200, ~1000 ms | HTTP 200, **1085 ms** |
| TTL del token | 1800 s | **1800 s** |
| Latencia `/states/all` | 780–850 ms | **915 ms** |
| Cuota autenticada | 4000 | **4000** |
| Cuota anónima (por IP) | 400 | **400** |
| Delta entre posiciones | mediana 7 s | **mediana 7 s** |
| Retraso de `/flights/arrival` | ~16.5 h | **17.0 h** |
| Señal perdida en 60 s | 7.7% | **9.1%** |

Las diferencias de latencia (~100 ms) están dentro del ruido de dos corridas en
momentos distintos, y no siguen un patrón de degradación: el handshake TLS a
OpenSky desde Gutis fue incluso más rápido. **Sin inspección TLS** en ninguno de
los dos hosts de OpenSky (`opensky-network.org` y `auth.opensky-network.org`,
ambos con certificado de Let's Encrypt).

**Cobertura (Fase 2), tercera muestra independiente:** 8 aeronaves únicas, 1 en
el radio de MROC (12.5%), frescura mediana de 2 s. Ninguna en tierra en esta
franja, a diferencia de las corridas del 18/08.

**MRLB (Liberia) volvió a dar cero.** Van **tres muestras** en tres franjas
horarias distintas con el mismo resultado. La recomendación de diseñar Sprint 3
sin depender de Liberia se sostiene.

**Tarifa por área (Fase 5): confirmada exactamente.** Los cinco tramos medidos
reprodujeron la tabla de umbrales 25 / 100 / 400:

| Zona | Área | Costo medido |
|---|---|---|
| Costa Rica | 12 deg² | **1** |
| Centroamérica | 176 deg² | **3** |
| Caribe amplio | 1000 deg² | **4** |
| Américas | 6375 deg² | **4** |
| Global | 64800 deg² | **4** |

> El script marca «NO coincide» en dos tramos, pero eso es un defecto de su
> tabla interna de valores esperados, no de la medición: los costos reales
> coinciden con los umbrales documentados. **Conviene corregir el modelo
> esperado dentro de `05_rate_limits.py`** para que el veredicto automático no
> confunda en futuras corridas.

**Cuotas separadas por endpoint: reconfirmado.** Durante la corrida los tres
contadores avanzaron de forma independiente — `/flights/*` bajó 3970 → 3940 →
3910 → 3880 (30 por consulta), `/states/*` iba por 3933, y `/tracks/*` marcaba
3996 tras su única llamada de 4 créditos.

**Contrato de errores (Fase 6): idéntico.** `states: null` en vez de lista
vacía, `401` y `400` sin consumir cuota, y el `404` por aeropuerto inexistente
cobrando igual sus 30 créditos.

#### Pendientes antes de cerrar TG-11 en Jira

- [x] ~~Segunda corrida vespertina de la Fase 2~~ — hecha, internacionales
      confirmados, MRLB sigue sin cobertura
- [x] ~~Replicar las fases 1–6 desde la **red corporativa de Gutis**~~ — hecho
      el 19/08: sin diferencias atribuibles a la red
- [ ] Corregir la tabla de costos esperados de `05_rate_limits.py`, que marca
      «NO coincide» dos tramos que en realidad sí cumplen los umbrales

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

## ShipsGo — tracking marítimo y aéreo

> **Medido el 14/09/2026** en el spike `TASK-28`, fases 1 y 2. Scripts en
> `backend/scripts/spikes/task28/`, evidencia cruda en su `output/`.
> Llave de prueba gratuita, red personal.

### Cómo funciona

REST de consulta. Base `https://api.shipsgo.com/v2`, credencial en el header
**`X-Shipsgo-User-Token`** (un UUID). Cubre **las dos vías**: `/ocean/*` y
`/air/*`, lo que abre la posibilidad de resolver `US-45` y `US-46` con un solo
proveedor.

### Endpoints medidos

| Endpoint | Método | Resultado |
|---|---|---|
| `/ocean/shipments?limit=1` | GET | `200` · `{"message":"SUCCESS","shipments":[],"meta":{"more":false,"total":0}}` |
| `/air/shipments?limit=1` | GET | `200` · misma forma |
| `/air/airlines` | GET | `200` · catálogo de aerolíneas, 25 por página |
| `/air/carriers`, `/airlines` | GET | `404` · no existen |

Errores de credencial, los dos con `401`:

| Situación | Cuerpo |
|---|---|
| Sin header | `{"message":"TOKEN_MISSING"}` |
| Token inválido | `{"message":"TOKEN_NOT_FOUND"}` |

Los `401` **no descuentan** del contador de cuota.

### ⚠️ Paginación: es `skip`, y los parámetros desconocidos se ignoran en silencio

**La trampa más cara de este spike.** ShipsGo acepta cualquier parámetro de
consulta, devuelve `200` con `meta.more = true`, y sirve **siempre la primera
página**. `?page=2`, `?limit=100`, `?name=LUFTHANSA`, `?iata=LH` y `?offset=25`
devuelven todos los mismos 25 registros, sin ningún error.

Costó una conclusión falsa: con `?page=N` se descargaron 5000 registros que
resultaron ser la misma página 200 veces, y media docena de aerolíneas se dieron
por ausentes cuando sí estaban.

**La paginación real es `?skip=N`**, en saltos de 25. El tamaño de página es
fijo: `limit`, `size`, `perPage`, `per_page` y `pageSize` se ignoran todos.

> Consecuencia para el adaptador de `US-45`/`US-46`: hay que **deduplicar** los
> lotes y cortar cuando un lote no aporte registros nuevos. Confiar en
> `meta.more` solo es un bucle infinito.

### Catálogo de aerolíneas y prefijos MAWB

`/air/airlines` devuelve **207 aerolíneas únicas**, 202 de ellas con el prefijo
de 3 dígitos del MAWB:

```json
{"iata": "LH", "name": "LUFTHANSA CARGO", "status": "ACTIVE", "prefixes": ["020", "220"]}
```

**Cobertura de los tramos de Gutis: 22 de 22 prefijos objetivo.** India, China,
Europa y el tramo final a SJO están todos.

**El catálogo se cruza por prefijo, no por nombre.** ShipsGo nombra las
divisiones de carga, no las aerolíneas de pasajeros:

| Se busca | Aparece como | Prefijo |
|---|---|---|
| British Airways | `IAG CARGO` | `125` |
| KLM | dentro de `AIR FRANCE` | `057` |
| China Eastern | `CHINA CARGO AIRLINES` | `112` |
| Lufthansa | `LUFTHANSA CARGO` | `020` / `220` |

Buscar «KLM» por nombre da ausente y sería un falso negativo. El prefijo es la
llave estable.

> **Esto alimenta `TASK-30` y `US-32` directamente.** El contrato de captura de
> la referencia distingue un MAWB de un HAWB por el prefijo de aerolínea. Este
> catálogo **es** esa tabla de prefijos, y se puede descargar y cachear para
> validar la guía localmente, sin gastar una llamada.

### Cuota

`x-ratelimit-limit: 100`, con `x-ratelimit-remaining` decreciente. **No expone
`x-ratelimit-reset`**, así que la duración de la ventana no está publicada.

Lo medido: el contador se reinició entre dos corridas separadas por minutos, y
más de 200 llamadas seguidas nunca dispararon un `429`. **La ventana es corta**
—del orden del minuto— pero la duración exacta queda abierta.

---

## TrackingMore — tracking por número de guía

> **Medido el 14/09/2026**, mismo spike y misma corrida.

### Cómo funciona

REST de consulta. Base `https://api.trackingmore.com/v4`, credencial en el
header **`Tracking-Api-Key`**. El cuerpo **duplica** el status HTTP en
`meta.code`, así que el cliente tiene que leer el cuerpo y no solo el status.

### Endpoints medidos

| Endpoint | Método | Resultado |
|---|---|---|
| `/couriers/all` | GET | `200` · 1678 couriers. Sonda barata ideal para el healthcheck: valida la llave sin crear nada |
| `/trackings/get?tracking_numbers=<inexistente>` | GET | **`400`** · `meta.code: 4102` |
| `/couriers/detect` | GET | `400` · existe, pero pide otros parámetros |

Errores de credencial, `401` con `meta.code: 401` y el mensaje
*«Authentication failed or has no permission»*, tanto sin header como con llave
inválida.

El `4102` dice literalmente: *«Tracking No. no exists. Please use「Create a
tracking」API first to create shipment.»*

### ⚠️ La trampa del `200` vacío

**TrackingMore devuelve `200` con `data: []` para rutas que no existen.**
Medido en `/users/quota`, `/users/info`, `/account/quota`, `/air/couriers` y
`/aircargo/couriers`: las cinco responden

```json
{"meta": {"code": 200, "type": "Success", "message": "The request was successful."}, "data": []}
```

y ninguna existe. Solo `/trackings/quota` devuelve un `404` honesto.

> **Un `200` de TrackingMore no prueba que el endpoint exista.** Hay que exigir
> que `data` traiga contenido. Va directo al mapeo de `resiliencia.clasificar()`.

### Lo que no tiene: catálogo de carga aérea

`/couriers/all` trae 1678 couriers, pero por tipo son **`express` = 1505** y
**`globalpost` = 173**. **Cero aerolíneas de carga.** No hay Lufthansa Cargo, ni
Air China, ni Iberia, ni Avianca.

Buscar por nombre produce falsos positivos que hay que descartar a mano:
«Emirates Post», «Qatar Post», «Turkish Post (PTT)», «South American Post»,
«Deltafille» y «LATAM YOU» son servicios postales, no aerolíneas.

Ninguna ruta candidata de catálogo aéreo respondió de verdad, y
`?courier_type=air` se ignora: devuelve los 1678 igual.

**No es un veredicto definitivo.** TrackingMore comercializa rastreo de carga
aérea; puede que el catálogo no se exponga por esta vía. Lo que sí queda
establecido es que **no se puede verificar la cobertura sin gastar créditos**,
mientras que en ShipsGo se verifica gratis. La prueba definitiva es la fase 3,
con un MAWB real.

### Cuota

No expone ningún header de rate limit ni endpoint de saldo. El consumo del
trial hay que mirarlo en el panel web.

---

## `TASK-28` — Spike de fuentes comerciales

> **Reasignado el 14/09/2026.** `Vizion` y `Portcast`, aprobados el 04/09, quedan
> fuera: **ninguno de los dos proveedores respondió**. El Plan A se mantiene en
> su principio —fuente comercial REST por referencia de embarque— y cambia de
> proveedor a `ShipsGo` y `TrackingMore`, ambos con llave de prueba gratuita.

### El hallazgo de arquitectura: los dos son *create-then-poll*

**Ninguno responde «¿dónde está el contenedor X?» en frío.** Primero hay que
dar de alta el embarque en la cuenta —eso es lo que cuesta— y después se
consulta. TrackingMore lo dice en el `4102`; en ShipsGo, `/ocean/shipments`
lista los embarques **de la cuenta**, no el universo de contenedores.

Cuatro consecuencias de diseño:

1. **`US-45` y `US-46` necesitan un paso de alta** que hoy no está en sus
   criterios de aceptación. Encaja con `ASOCIACION_TRACKING`, que ya existe en
   `TIPOS_INTERVENCION` (`app/models/enums.py`).
2. **El costo es por embarque registrado, no por consulta.** Buena noticia para
   `US-07`: sondear seguido no quema créditos, solo roza el rate limit.
3. **`resiliencia.clasificar()` necesita un tercer caso.** Hoy separa permanente
   de transitorio. El `4102` es permanente *para esa referencia* pero
   **accionable**: no es «no reintentar nunca», es «hay que darla de alta
   primero». No es ninguno de los dos que existen.
4. Se confirma el principio 1 de la tabla de `US-03`: *«una respuesta vacía con
   `200` es un contacto exitoso»*. ShipsGo hace exactamente eso.

### Mapeo para `resiliencia.clasificar()`

Es lo que `US-03` dejó pendiente al cerrarse el 08/09: *«el mapeo de los errores
concretos de cada proveedor»*.

| Señal | Clase | Acción |
|---|---|---|
| ShipsGo `401` (`TOKEN_MISSING` / `TOKEN_NOT_FOUND`) | permanente · credencial | Degradar la fuente, no reintentar |
| TrackingMore `401` / `meta.code 401` | permanente · credencial | Igual |
| TrackingMore `400` / `meta.code 4102` | permanente · **referencia sin alta** | No reintentar; requiere alta previa |
| ShipsGo `200` con `shipments: []` | éxito sin datos | `registrar_exito(con_datos=False)` |
| TrackingMore `200` con `data: []` | **sospechoso** | Verificar que la ruta exista; no contarlo como éxito |
| `timeout` · `5xx` · `429` | transitorio | Backoff, respetar `Retry-After` |

### Lo que la fase 2 **no** respondió

- **Si una referencia inexistente da `404` o `200` vacío en ShipsGo.** La sonda
  se hizo contra una cuenta vacía, así que el `200` con `shipments: []` no
  distingue «el contenedor no existe» de «la cuenta no tiene nada».
- **La duración exacta de la ventana de cuota de ShipsGo.**
- **El saldo del trial de TrackingMore**, que no se expone por API.

### Fase 3 — alta de embarques reales y payload (14/09/2026)

Referencias reales de Gutis, validadas en local antes de gastar
(`04_validar_referencias.py`). Scripts `05_alta_y_poll.py` y
`06_payload_maduro.py`.

#### ⚠️ El trial son 3 créditos de alta, y ShipsGo no valida el formato

Dos hallazgos que van juntos y cuestan dinero:

1. **El trial gratuito permite 3 altas.** La cuarta y la quinta devolvieron
   `402 NOT_ENOUGH_CREDITS`.
2. **ShipsGo acepta y cobra cualquier cosa.** Un `POST` con el contenedor
   inventado `XXXX0000000` devolvió `200 SUCCESS` y creó el embarque (id
   6734880, borrado después). No hay validación de formato del lado del
   proveedor.

> **Consecuencia directa para `US-32`:** la validación local del dígito de
> control ISO 6346 y del prefijo MAWB **deja de ser una comodidad y pasa a ser
> lo que protege el presupuesto**. Una referencia mal transcrita consume
> crédito y devuelve vacío, y después no se distingue de una sin cobertura.

Por gastar un crédito comprobando el punto 2, las altas del BL de COSCO y del
MAWB de Lufthansa se quedaron sin cupo. **Quedan pendientes de créditos.**

#### *Create-then-poll* con maduración: hay un tercer estado

A los 45 s del alta, los dos embarques devolvían `status: NEW`, `route: null` y
`containers: []`. A los ~90 s pasaron a `SAILING` con todo completo.

> **Para `US-07`:** el planificador necesita contemplar **«dado de alta pero sin
> datos todavía»**. No es un fallo ni una respuesta vacía definitiva, y tratarlo
> como cualquiera de las dos da un falso negativo.

#### Los datos viven en DOS endpoints

| Endpoint | Qué aporta |
|---|---|
| `GET /ocean/shipments/{id}` | ruta, puertos, ETA, hitos, buque por tramo |
| `GET /ocean/shipments/{id}/geojson` | **posición actual** y trayecto |

El `geojson` **no estaba documentado** en la guía. Sin él la conclusión habría
sido que ShipsGo no entrega posición, que es falso.

#### Qué campos de TrackIn llegan

Medido sobre `MRSU8507472` (Santos → Cartagena → Puerto Moín):

| Campo | ¿Llega? | De dónde |
|---|---|---|
| Posición actual | ✅ | `geojson … properties.current.coordinates` → `[-79.885643, 9.36328]` |
| Trayecto | ✅ | `LineString` PAST / CURRENT / FUTURE |
| ETA | ✅ | `route.port_of_discharge.date_of_discharge_predicted` |
| ETD / ATD | ✅ | `route.port_of_loading.date_of_loading` |
| Hitos | ✅ | `containers[].movements[]` — 8 eventos, `ACT` vs `EST` |
| Buque | ✅ | `movements[].vessel.name` |
| IMO | ✅ | `geojson … properties.vessel.imo` → `9525388` |
| **Transbordo** | ✅ | cambio de `vessel` entre tramos |
| Puerto de destino | ✅ | `CRPMN` = Puerto Moín |
| **Velocidad** | ❌ | no viene |
| **Rumbo** | ❌ | no viene |

**Los hitos distinguen `ACT` de `EST`**, que es exactamente la separación que
RN-14 necesita entre lo ocurrido y lo estimado.

#### El transbordo viene gratis — `US-30`

El primer contenedor cambió de `MAERSK CHACHAI` a `POLAR BRASIL` en Cartagena;
el segundo encadena **tres** naves (`MAERSK CHACHAI` → `MAERSK NACALA` →
`MAERSK MONTE PASCOAL`). `US-30` está especificada como una intervención manual
para sustituir la nave. Con ShipsGo **el transbordo llega en el payload**, así
que la historia puede pasar de «capturarlo a mano» a «detectarlo y auditarlo».
Conviene reestimarla.

#### Velocidad y rumbo no llegan, y no hacen falta

`historial_tracking` los tiene anulables. RN-16 los quería para **estimar** la
ETA, y ShipsGo la entrega ya calculada, con `date_of_discharge_predicted` y un
porcentaje de tránsito. RN-05 usaba la velocidad para inferir el arribo, y los
hitos `DISC`/`ARRV` lo dicen directamente.

> **Cierra la decisión que la salida de Vizion había reabierto:** `US-08`
> (estimar la ETA desde posición y velocidad) **se mantiene `Could`**. El
> supuesto «la fuente comercial ya entrega la ETA» se cumple con ShipsGo.

**Salvedad:** en uno de los dos embarques `date_of_discharge_predicted` no vino
poblado. Con dos casos no alcanza para saber si es transitorio o depende del
carrier. Hay que verificarlo cuando haya créditos.

#### TrackingMore con el MAWB: no resuelve

| Paso | Resultado |
|---|---|
| `POST /couriers/detect` con `02050685434` | Propone `dachser`, `famiport`, `old-dominion`, `exapaq` — **ningún transportista aéreo** |
| `POST /trackings/create` con `dachser` | `200`, tracking creado |
| `GET /trackings/get` | `delivery_status: "pending"`, `updating: true`, sin ningún dato |

TrackingMore **acepta el MAWB bajo un courier que no puede resolverlo** y no
avisa. Sumado a que su catálogo son 1505 couriers `express` y 173 `globalpost`
sin una sola aerolínea, y a que buscar «cargo» solo devuelve transitarios
terrestres, **no sirve para rastrear una guía aérea madre**.

#### Fase 3e — la vía aérea y la segunda naviera (14/09/2026)

Con una cuenta de prueba nueva se completaron las dos altas que el trial
anterior dejó sin cupo. Script `07_altas_pendientes.py`.

##### ShipsGo Air resuelve el MAWB — `US-46` go

`020-50685434`, la guía de Lufthansa Cargo:

| Dato | Valor |
|---|---|
| Aerolínea | `LH` · LUFTHANSA CARGO |
| Ruta | **PEK** (Beijing) → **FRA** (Fráncfort) → **SJO** (Juan Santamaría) |
| Vuelos | `LH8431`, `LH518` |
| Salida | 2026-09-04 07:05 `+08:00` |
| Llegada (`RCF`) | 2026-09-05 18:43 `-06:00` |
| Hitos | 10 eventos, **todos `ACT`** |
| Estado | `DELIVERED` |

Los hitos son **códigos IATA CIMP estándar**: `RCS` (recibido del expedidor),
`DEP`, `MAN` (manifestado), `ARR`, `RCF` (recibido del vuelo) y `DLV`
(entregado). Es exactamente lo que pide el criterio de `US-46` —*«obtengo los
hitos de carga, no la posición de la aeronave»*— y mapea directo a RN-02…RN-06.

> **La conexión en Fráncfort aparece como cambio de vuelo** (`LH8431` → `LH518`),
> igual que el transbordo marítimo aparece como cambio de nave. El mismo
> tratamiento sirve para las dos vías.

##### La cobertura no depende del carrier

El BL `COSU6508789000` con el contenedor `TGBU4872990` respondió igual de bien
que los dos de Maersk: `SAILING`, ETA **2026-10-05**, salida 2026-08-15, 6
hitos (3 `ACT` / 3 `EST`), naves `YANTIAN` → `MEDKON ZOE`, IMO `9305594`.

Su destino es **`CRCAL` — Puerto Caldera**, el puerto del Pacífico. Que ShipsGo
entregue sus hitos **cierra el hueco que dejó la medición de cobertura AIS**: el
AIS gratuito no ve Caldera, pero la fuente comercial sí lo cubre.

##### ⚠️ La posición en vivo NO está garantizada

| Embarque | `geojson … current` |
|---|---|
| Maersk `MRSU8507472` | ✅ `[-79.885643, 9.36328]` |
| COSCO `TGBU4872990` | ❌ `current: null` en todas las *features* |
| Lufthansa (aéreo) | ❌ — pero está `DELIVERED`, no hay nada que posicionar |

**Para `US-45` y el mapa (RF-16): la posición es opcional, los hitos no.** El
adaptador tiene que funcionar sin coordenadas, y `US-02` (AIS como respaldo del
mapa) recupera sentido justamente para esos casos.

##### Resumen de campos, las dos vías

| Campo | Marítimo | Aéreo |
|---|---|---|
| Hitos con `ACT`/`EST` | ✅ | ✅ |
| ETA / llegada | ✅ | ✅ |
| Salida (ETD/ATD) | ✅ | ✅ |
| Transportista + identificador | ✅ IMO | ✅ IATA |
| Cambio de transporte | ✅ transbordo | ✅ conexión |
| Destino normalizado | ✅ `CRPMN`, `CRCAL` | ✅ `SJO` |
| Trayecto | ✅ | ✅ |
| **Posición en vivo** | ⚠️ a veces | ⚠️ a veces |
| **Velocidad / rumbo** | ❌ | ❌ |

##### Decisión: **ShipsGo para las dos vías**

Queda resuelta la bifurcación que estaba abierta para el cierre del sprint.

| | ShipsGo | TrackingMore |
|---|---|---|
| Catálogo aéreo | 207 aerolíneas, **22/22** prefijos de Gutis | **0 aerolíneas** |
| MAWB real | ✅ resuelve, 10 hitos, ruta completa | ❌ `pending` sin datos bajo `dachser` |
| Marítimo | ✅ dos navieras probadas | no aplica |
| Verificar cobertura antes de gastar | ✅ gratis, por catálogo | ❌ imposible |

**TrackingMore queda fuera.** No es que rastree peor: no rastrea carga aérea.

##### Un detalle operativo: los `DELIVERED` se auto-archivan

El embarque aéreo trajo `discarded_at` poblado en la misma respuesta que lo dio
por entregado. ShipsGo archiva solo lo terminado, así que el adaptador **no
puede asumir que un embarque siga consultable** después del `DLV`. Es un motivo
más para que `historial_tracking` guarde el payload completo (RNF-13).

---

#### Modelo de cobro: qué consume un crédito (14/09/2026)

Medido agotando dos trials de 3 créditos cada uno.

##### El alta es idempotente por referencia — y no vuelve a cobrar

Repetir el alta de una referencia ya registrada devuelve **`409 ALREADY_EXISTS`
con el embarque existente**, sin crear nada y **sin descontar crédito**:

```
POST /ocean/shipments  {"booking_number": "COSU6508789000"}
409 {"message":"ALREADY_EXISTS","shipment":{"id":6734941, …}}
```

> **Para `US-45` y para `resiliencia.clasificar()`:** un `409` **no es un fallo**.
> Es «ya está registrado, aquí tienes el id». Y tiene una consecuencia
> presupuestaria concreta: si un alta se corta por *timeout*, el adaptador no
> sabe si prosperó — **reintentarla es seguro y gratis**. Sin esta garantía
> habría que llevar un registro propio de «qué ya registré» solo para no pagar
> dos veces.

##### Un BL se da de alta sin enumerar contenedores

Basta el `booking_number`; ShipsGo resuelve los contenedores solo:

```
POST /ocean/shipments  {"booking_number": "271102440"}
→ container_count: 1, containers: [ MRSU8507472 · 40 HC ]
```

##### La unidad de cobro es el embarque, no el contenedor

Los créditos se descuentan **por registro de embarque creado**. El modelo de
datos pone los contenedores *dentro* del embarque (`container_count` y
`containers[]` son campos del shipment), y dar de alta por BL los trae todos en
un solo registro.

> **`1 BL = 1 crédito`, confirmado por ShipsGo el 14/09/2026**, sin importar
> cuántos contenedores ampare. El spike lo había inferido de la estructura del
> API; el proveedor lo confirmó por escrito. No hizo falta gastar un crédito en
> medirlo.

**Lo que esto elimina:** la duda entre cobrar por embarque y cobrar por
contenedor era la mayor fuente de incertidumbre del presupuesto — valía unos
400 USD al año. Queda cerrada.

**Lo que queda abierto** es una incertidumbre distinta y menor: **cuántos BL
genera una orden**. Una OC partida en dos entregas produce dos BL y por tanto dos
créditos. En la muestra, **71 % de las OCs internacionales tienen una sola
línea**, así que el reparto es la excepción y no la regla.

##### Consecuencia para el presupuesto

Con `1 BL = 1 crédito`, el consumo anual se calcula sobre **embarques**, no
sobre líneas de orden. Partiendo de 117 OCs internacionales rastreables y una
rotación de 2,64 vueltas al año (lead time medido de 138 días):

| Escenario | Créditos/año | Costo |
|---|---|---|
| Piso — 1 BL por orden | 309 | 619 USD |
| **Base** — +10 % órdenes partidas, +10 % merma | **374** | **749 USD** |
| Techo — +25 % partidas, +15 % merma | 446 | 891 USD |

La **merma** no es teórica: ShipsGo cobra por referencias que no puede resolver
—medido con `XXXX0000000`— y los HAWB que entrega el agente de carga se cuelan
hasta que Logística exija el MAWB. El validador local de `US-32` la reduce, no
la elimina.

---

### Conclusión: **VIABLE — ShipsGo para las dos vías**

**`ShipsGo` para las dos vías: go.** Probado con tres embarques marítimos de dos
navieras y una guía aérea real. Entrega todo lo que `US-45` y `US-46` necesitan,
más el transbordo que `US-30` iba a capturar a mano.

**`TrackingMore` queda descartado.** Su catálogo no tiene aerolíneas y con el
mismo MAWB se quedó en `pending` bajo un courier que no podía resolverlo.

**Costo:** **2 USD por crédito**, y los créditos **vencen un año después de la
compra** (cotización del 14/09). El trial gratuito son **3 altas por cuenta** y
ShipsGo no expone saldo por API: el consumo se sigue por el listado de
embarques.

Con `1 BL = 1 crédito` confirmado y el volumen estimado desde el Z-tracking
—117 de 119 OCs internacionales rastreables, lead time de 138 días, 2,64 vueltas
al año— el consumo ronda los **374 créditos anuales (~750 USD)**, en un rango de
309 a 446.

**El vencimiento anual desaconseja comprar antes del arranque:** la ventana corre
desde la compra, y con producción prevista para diciembre se perderían ~2,6 meses
(92 créditos, 185 USD, si se comprasen 400 de golpe hoy).

---

## Otras fuentes evaluadas

| Fuente | Estado | Nota |
|---|---|---|
| MarineTraffic | Descartada por ahora | API de pago |
| VesselFinder | A evaluar | Tiene plan gratuito limitado |
| FlightAware | Descartada por ahora | API de pago |
| Vizion | **Descartada 14/09/2026** | Aprobada el 04/09, pero el proveedor nunca respondió a la solicitud |
| Portcast | **Descartada 14/09/2026** | Igual que Vizion: sin respuesta |
| Terminal49 | No evaluada | Alternativa marítima listada en `TASK-28`; no se solicitó llave |
