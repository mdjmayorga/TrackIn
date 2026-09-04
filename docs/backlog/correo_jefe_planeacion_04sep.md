# Correo al jefe de Planeación — 04/09/2026

**Copia:** Greivin · **Objetivo:** cerrar los cuatro insumos que faltan para liberar los
requerimientos y arrancar el backend el lunes 8.

---

**Asunto:** TrackIn — 4 datos que necesito para cerrar requerimientos (antes del lunes 8)

Buenas tardes:

Gracias por la reunión de hoy. Con lo conversado quedan definidos el cálculo de fechas, el
cierre por Calidad y el paso manual a proceso aduanal. **Me faltan cuatro datos para dejar
los requerimientos cerrados y empezar a construir el lunes.**

## Lo que necesito

**1. Lead time del puerto a la planta, por destino.**
El lead time de SAP va del proveedor a la planta y arranca con la SolPed, así que no me
sirve para proyectar desde la posición del barco: contaría el tránsito internacional dos
veces. Necesito los **días de desembarque, nacionalización y traslado**, medidos desde que
la nave atraca:

| Destino | Días |
|---|---|
| Caldera | |
| Moín | |
| Limón | |
| Juan Santamaría (aéreo) | |

Si no hay un número oficial, un estimado por experiencia me sirve para arrancar; lo dejo
documentado como provisional y lo corregimos después.

**2. Las columnas de referencia de embarque.**
Quedamos en que las incluyen. Para que las APIs las acepten, el formato debe ser:

| Columna | Formato | Aplica a |
|---|---|---|
| Número de contenedor | 4 letras + 7 dígitos (ej. `MSCU1234567`) | Marítimo |
| MAWB | 11 dígitos con prefijo de aerolínea (ej. `020-12345675`) | Aéreo |
| Puerto de destino | Caldera, Moín o Limón | Marítimo |

Dos advertencias que importan:

- En aéreo tiene que ser el **MAWB de la aerolínea**, no el HAWB que emite el agente de
  carga. Con el HAWB la consulta no devuelve nada.
- **¿Con cuánta antelación al arribo se conoce la referencia?** Es lo que determina si el
  rastreo sirve. Si se conoce tres días antes de que el barco atraque, avisen: replanteo el
  alcance antes de gastar la suscripción.

**3. La ventana de Calidad.**
Los 7 a 15 días hábiles, ¿dependen del tipo de material? Si el refrigerado o un material
específico tiene una ventana distinta, la parametrizo por categoría; si no, uso el rango
único. También: **¿la fecha de liberación queda registrada en algún sistema**, o hay que
capturarla a mano en TrackIn?

**4. Reparto por puerto.**
Aproximadamente, ¿qué proporción de los embarques entra por Caldera y qué proporción por
Moín o Limón? No es para el cálculo: **Caldera está en el Pacífico** y la cobertura de
rastreo que evaluamos fue solo del Caribe. Si por Caldera entra un volumen relevante, tengo
que verificarla esta semana.

## Lo que ya doy por definido

Si algo quedó distinto a como lo escribí, corríjanme:

1. La fecha comprometida es **`Fecha entrega SolPed`**, y el estatus sale de restarle la
   columna **`Fecha entrega`**. Ambas vienen en el archivo; tomo `Estatus` y `Diferencia
   Días` tal como los calcula SAP, sin recalcularlos.
2. El pedido **cierra cuando Calidad libera**, no cuando llega a planta. Hasta entonces sigue
   contando como pendiente.
3. El paso a **proceso aduanal lo hace una persona**, no el sistema.
4. Los destinos son **Caldera, Moín, Limón y Juan Santamaría**.
5. Se aprobaron **Vizion** (marítimo) y **Portcast** (aéreo) como fuentes de rastreo.

## Además, aplico esto salvo comentario

Puntos menores, todos configurables después. **Si no hay comentarios antes del lunes 8 a
mediodía**, los doy por aceptados y quedan documentados. Basta responder con el número.

| # | Punto | Lo que aplico |
|---|---|---|
| 1 | Fechas que caen sábado o domingo | Se corren al siguiente día hábil |
| 2 | Ventana de Calidad | Se cuenta en días hábiles, y se muestra como rango (no fecha exacta) |
| 3 | Entregas parciales | La línea sigue activa hasta que la cantidad pendiente llegue a cero |
| 4 | Pedidos ya liberados | Visibles 15 días bajo un filtro aparte, luego salen del tablero |
| 5 | Umbral de «en riesgo» | 7 días en marítimo, 2 en aéreo |
| 6 | Filtros del tablero | Material, país de origen y estado |
| 7 | Ajuste manual de días | Lo hace Logística, con motivo obligatorio y registro de autor |

Con los cuatro datos de arriba cierro los requerimientos y arranco el lunes. Quedo atento.

Mariano
