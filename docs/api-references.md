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
- [ ] Política de reconexión y detección de socket zombi
- [ ] Estrategia de submuestreo antes de persistir (no guardar cada mensaje)

---

## OpenSky Network — tracking aéreo

Posiciones de aeronaves por REST.

- **Documentación:** <https://openskynetwork.github.io/opensky-api/>
- **API REST:** <https://openskynetwork.github.io/opensky-api/rest.html>
- **Protocolo:** HTTP REST, polling
- **Autenticación:** credenciales en `OPENSKY_USERNAME` / `OPENSKY_PASSWORD`
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

- [ ] Confirmar la cuota vigente para cuenta autenticada
- [ ] Definir el intervalo de polling según el SLA del dashboard
- [ ] Comportamiento cuando no hay cobertura (¿última posición conocida?)
- [ ] Mapear número de vuelo del courier a `icao24`

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
