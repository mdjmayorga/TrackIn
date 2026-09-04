# Borrador de correo a Planeación — enviar el 04/09 después de la reunión

**Para:** los asistentes de Planeación · **Copia:** Greivin
**Los `[corchetes]` se llenan con lo que salga de la reunión.** Si algún supuesto quedó
contestado en vivo, sale de la tabla y sube al acta.

---

**Asunto:** TrackIn — acuerdos de hoy y supuestos que aplico salvo comentario (antes del lunes 8 a mediodía)

Buenas tardes:

Gracias por el tiempo de hoy. Les resumo lo que quedó decidido y, al final, una lista de
puntos menores que resolví por mi cuenta para no consumirles más reuniones. **Si algo de
la primera parte no quedó como lo escribí, corríjanme**: es más fácil arreglarlo ahora que
cuando esté programado.

## Lo que decidimos

1. **Fecha que necesita Planeación.** [Llega a planta / liberación de Calidad]. El sistema
   calculará [la fecha de entrada a planta / esa fecha más los N días de liberación].
2. **Lead time de SAP.** Cubre hasta [el puerto de Moín / la planta], de modo que la fecha
   proyectada se arma [sumando el traslado local / usando el dato de SAP directamente].
3. **Fecha de referencia del cumplimiento.** Un pedido se considera atrasado contra
   **[nombre exacto de la columna]**. Es la fecha contra la que el sistema pintará verde,
   naranja o rojo.
4. **Estado calculado por SAP.** [TrackIn recalcula y su estado es el que manda; el de SAP
   queda visible como referencia / se respeta el de SAP].
5. **Vista de Planeación.** Mostrará [columnas acordadas].
6. **Referencias de embarque.** [Quién las entrega, en qué formato y con qué frecuencia].

## Lo que asumo salvo que me digan lo contrario

Ninguno de estos puntos justifica otra reunión, pero todos hay que decidirlos para poder
programar. **Van con un valor por defecto.** Si no recibo comentarios **antes del lunes 8
a mediodía**, los doy por aceptados y quedan registrados como supuesto del proyecto. Todos
son configurables después sin rehacer trabajo.

| # | Punto | Lo que aplico |
|---|---|---|
| 1 | Lead time mientras el API de SAP no exista | [7] días marítimo y [3] aéreo, ajustable |
| 2 | Fecha proyectada que cae sábado o domingo | Se corre al siguiente día hábil |
| 3 | Quién ajusta manualmente los días de un pedido | Logística, con motivo obligatorio y registro de quién lo hizo |
| 4 | Entregas parciales | La línea sigue activa hasta que la cantidad pendiente llegue a cero |
| 5 | Pedidos ya recibidos | Siguen visibles 15 días bajo un filtro aparte, luego salen del tablero |
| 6 | Filtros del tablero | Material, país de origen y estado |
| 7 | Sesión | 8 horas de duración, cierre a los 30 minutos de inactividad, bloqueo tras 5 intentos fallidos |
| 8 | Contraseña olvidada | La reinicia el administrador (no hay servidor de correo disponible) |

Basta con responder señalando el número y qué cambiar; no hace falta contestar los demás.

## Pendientes que no dependen de ustedes

Los anoto para que sepan por qué algunas cosas todavía no tienen respuesta:

- **Fechas de salida del embarque (ETD/ATD).** Hoy no se registran; Logística las entregará
  en un archivo aparte. Coordino con ellos esta semana.
- **Quién registra la recepción en planta.** Lo confirmo con Logística y Bodega.
- **Exportar a Excel y notificaciones automáticas.** Hoy no están en el alcance. Lo reviso
  con Greivin y les aviso.
- **Pantalla permanente de planta.** Depende de si el equipo está disponible.

[Si salió el tema de Control de Calidad:]
- **Fecha de liberación de Calidad.** Lo que conversamos hoy amplía lo previsto
  originalmente. Lo reviso con Greivin esta semana y les confirmo si entra y cuándo.

Quedo atento.

Mariano
