# SRS v0.5 — Plan de cambios

**Base:** `SRS_TrackIn_v0.4.docx` (03/09/2026) · **Motivo:** reunión con **Planeación** del
**04/09/2026** y **aprobación de la compra** de Vizion (marítimo) y Portcast (aéreo).

> Se aplica **directamente sobre el `.docx`**, como v0.4. Tras editar, actualizar la tabla
> de contenidos con **F9** y registrar v0.5 en el historial de revisiones.

Decisiones que respaldan estos cambios (04/09):

1. **El lead time de SAP es del proveedor a la planta**, desde la creación de la SolPed. **No**
   es el lead time de RN-01, que va del puerto a la planta. Conviven; no se sustituyen.
2. **Fecha comprometida:** `Fecha entrega SolPed`.
3. **El pedido cierra cuando Control de Calidad libera**, 7–15 días hábiles después de la
   recepción. La recepción en planta deja de cerrar.
4. **El paso a proceso aduanal es manual.** Anula la transición automática de 30 minutos.
5. **Cuatro destinos:** Caldera, Moín, Limón y Juan Santamaría. Revierte el «destino único».
6. **Las referencias de embarque (contenedor y MAWB) llegan en el archivo** de Planeación.
7. **APIs de pago aprobadas:** Vizion + Portcast.

---

## 1. Historial de revisiones

> **v0.5 · 04/09/2026 · Mariano Mayorga** — Reunión con Planeación. Se separa el lead time
> de aprovisionamiento (SAP) del lead time logístico (RN-01). El cierre del pedido pasa a
> depender de la liberación de Control de Calidad, con un estado nuevo. El paso a proceso
> aduanal se vuelve manual. Se reponen los cuatro destinos reales. Se aprueban Vizion y
> Portcast como fuentes de rastreo.

## 2. §7.1 · RN-01 — se reescribe la fórmula

El texto vigente suma «ETA o ATA + lead time + ajuste manual» sin decir **qué** lead time.
Con lo confirmado el 04/09, esa ambigüedad es peligrosa: hay dos lead times y usar el de SAP
contaría el tramo del proveedor dos veces.

Redacción propuesta:

> **RN-01.** La fecha proyectada de disponibilidad resulta de la **ETA o ATA en el puerto o
> aeropuerto de destino**, más el **lead time logístico del destino** —desembarque,
> nacionalización y traslado a planta—, más un ajuste manual opcional. **No debe emplearse el
> lead time de aprovisionamiento de SAP**, que se mide desde la creación de la solicitud de
> pedido hasta la planta y por tanto ya incluye el tránsito internacional.

**Añadir RN-18 — Línea base de SAP.** *«La fecha de entrega sistema de SAP —creación de la
SolPed más el lead time del proveedor, expuesta en la columna `Fecha entrega`— se conserva
como línea base de comparación junto con el `Estatus` y la `Diferencia Días` que SAP calcula.
Se ingestan tal como vienen, no se recalculan, y no alimentan ningún cálculo del sistema.»*

## 3. §7.1 · RN-10 — el cierre se mueve a Calidad

> **RN-10 (revisada).** La recepción en planta transita el pedido a `RECIBIDO_EN_PLANTA`. El
> pedido pasa a `CERRADO` **únicamente cuando Control de Calidad libera el material**, entre
> **7 y 15 días hábiles** después. Mientras no se libere, el pedido **sigue computando como
> activo**: el material está en planta pero no es utilizable.

**Consecuencia sobre §7.2 (dominio de estados):** `etapa_viaje` gana el valor
`RECIBIDO_EN_PLANTA` entre `EN_PROCESO_ADUANAL` y `CERRADO`. Pasan de diez a **once** estados.

**Añadir RN-19 — Ventana de Calidad.** *«La fecha estimada de liberación se calcula sumando
la ventana de Calidad en **días hábiles** a la fecha de recepción. Por ser un rango de 7 a 15
días, se presenta como rango y no como fecha exacta.»*

## 4. §7.1 · RN-05 y RN-06 — el paso a aduanal es manual

- **RN-06 (revisada):** el paso de `EN_DESTINO` a `EN_PROCESO_ADUANAL` **lo dispara una
  confirmación humana** (RF-13), nunca el transcurso del tiempo.
- **Eliminar** del §7.1 y del §8.5 la regla de que `EN_DESTINO` dura 30 minutos, y con ella el
  parámetro `duracion_en_destino_minutos`.
- **RN-05 se mantiene:** el arribo puede inferirse por geocerca o reportarlo la fuente. Lo que
  cambia es que inferir el arribo **ya no avanza la etapa por sí solo**.
- `EN_DESTINO` deja de ser un estado de paso: dura lo que tarde la confirmación.

## 5. §4 · Requerimientos funcionales

- **RF-13 (ampliado):** la confirmación manual de desembarco **es además el disparador** del
  paso a proceso aduanal.
- **RF-25 (revisado):** registrar la recepción en planta **ya no cierra** el pedido.
- **RF-32 (nuevo) — Liberación de Control de Calidad.** El sistema registra la liberación,
  cierra el pedido, la audita conforme a RF-14 y estima la fecha de liberación en días hábiles.
- **RF-03 (revisado):** el identificador de rastreo **llega en el archivo de entrada**
  (contenedor y MAWB). La asociación manual queda como **vía de excepción**.
- *(Actualizar la cuenta de RF: de 31 a **32**.)*

## 6. §8 · Modelo de datos

| Cambio | Detalle |
|---|---|
| `pedidos_transito.etapa_viaje` | Añadir `RECIBIDO_EN_PLANTA` al `CHECK` |
| `pedidos_transito` | Nuevos: `fecha_recepcion_planta`, `fecha_liberacion_calidad`, `fecha_estimada_liberacion` |
| `pedidos_transito` | Nuevo `fecha_entrega_sistema` — la línea base de SAP (RN-18), tomada de la columna `Fecha entrega` |
| `maestro_destinos` | **Se repuebla con cuatro destinos**: `CRCAL`, `CRMOB`, `CRLIO`, `CRSJO`. Se revierte el «destino único» de v0.4 |
| `maestro_destinos.radio_geocerca_km` | Pasa de opcional a **recomendado**: Moín y Limón distan 6 km y el radio global de 50 km los solapa |
| `maestro_destinos.lead_time_dias` | Se aclara en el diccionario que es el **logístico** (puerto→planta), nunca el de SAP |
| `parametros_sistema` | **Eliminar** `duracion_en_destino_minutos`. **Añadir** `ventana_calidad_habiles_min` (7) y `_max` (15) |
| `auditoria_intervenciones.tipo_intervencion` | Añadir `LIBERACION_CALIDAD` e `INICIO_PROCESO_ADUANAL`. Pasa de seis a **ocho** valores |

## 7. §2.5 · Suposiciones — dos que hay que declarar

1. **El lead time logístico puerto→planta no existe en ninguna fuente.** No está en SAP —que
   mide otro tramo— ni en el Z-tracking. Se opera con un valor provisional por destino,
   documentado como supuesto, hasta que Planeación lo entregue.
2. **La línea base de SAP se ingesta, no se recalcula.** La *fecha entrega sistema* de RN-18
   es la columna **`Fecha entrega`** del archivo. La regla de signos se verificó exacta
   contra la muestra, pero la aritmética no reproduce `Diferencia Días` —probablemente por
   ser un valor congelado en un corte anterior—. Por indicación de Planeación **se toman
   `Estatus` y `Diferencia Días` tal como vienen**, sin recalcularlos.

## 8. Anexo B — columnas nuevas del archivo de entrada

Planeación confirmó que incluirá lo que el sistema necesite. Añadir al contrato:

| Campo | Tipo | Obligatorio | Observación |
|---|---|---|---|
| **Número de contenedor** | Texto(11) | Marítimo | ISO 6346: 4 letras + 7 dígitos. Alimenta Vizion |
| **MAWB** | Texto(11) | Aéreo | 11 dígitos con prefijo de aerolínea. **El HAWB del agente no resuelve.** Alimenta Portcast |
| **Puerto de destino** | Texto | Marítimo | Caldera, Moín o Limón. Antes se asumía único |
| **Fecha de liberación de Calidad** | Fecha | No | Si Calidad ya la registra en algún sistema |

## 9. Anexo C.5 — se cierra la evaluación

Sustituir la lista de candidatos por la decisión: **Vizion** (marítimo) y **Portcast** (aéreo),
**aprobados el 04/09**. **OpenSky** se conserva, gratuito y **solo** para la posición de la
aeronave en el mapa; el estado del envío aéreo lo da Portcast. Registrar como **riesgo
abierto** que la cobertura en **Caldera (Pacífico)** no está verificada: TG-10 solo evaluó el
Caribe, y lo resuelve `TASK-28`.

---

## Pendiente de Planeación (bloquea partes del v0.5)

1. **Lead time logístico puerto→planta**, por destino y vía — insumo de RN-01.
2. **Columna «fecha entrega sistema»** en el archivo — sin ella RN-18 no es calculable.
3. **Ventana de Calidad:** si los 7–15 días hábiles dependen del tipo de material.
4. **Reparto por puerto:** qué proporción entra por Caldera y qué por Moín/Limón.
5. **Fecha de liberación de Calidad:** si existe registrada en algún sistema o se captura a mano.
