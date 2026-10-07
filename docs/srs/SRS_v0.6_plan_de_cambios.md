# SRS v0.6 — Plan de cambios

**Base:** `SRS_TrackIn_v0.4.docx` con el plan de v0.5 aplicado · **Motivo:** reuniones con
**Compras** y con los **usuarios clave** del **29/09/2026**, y decisiones del **30/09/2026**.

> Se aplica **directamente sobre el `.docx`**, como v0.4 y v0.5. Tras editar, actualizar la
> tabla de contenidos con **F9** y registrar v0.6 en el historial de revisiones.

Decisiones que respaldan estos cambios:

1. **Fecha comprometida:** `Fecha Entrega`, la llegada a Gutis que planifica Compras.
   **Revierte la decisión 2 de v0.5** (`Fecha entrega SolPed`). — `US-53`
2. **El puerto de llegada lo declara la naviera** en la fuente de rastreo y manda sobre el
   del incoterm, que Compras escribe en SAP. — `US-54`
3. **RF-19 tiene seis filtros**, los del dashboard: orden de compra, posición, material
   (por texto), vía, etapa y cumplimiento. **Salen proveedor y destino**, que el dashboard
   principal nunca tuvo.
4. **Una cuenta compartida para Compras** (`compras@gutis.com`): varias personas a la vez,
   tratadas como un solo usuario también en la auditoría. — `US-42`
5. **El Z-tracking se leerá de SAP por API.** El Excel usado hasta ahora es una copia
   estática. — `US-56`
6. **ShipsGo sigue como fuente comercial**; Parcels se probó y se descartó. — `TASK-32`

---

## 1. Historial de revisiones

> **v0.6 · 30/09/2026 · Mariano Mayorga** — Reuniones con Compras y usuarios clave. La fecha
> comprometida pasa a ser la llegada a Gutis. El puerto de llegada lo declara la naviera.
> RF-19 se ajusta a los filtros reales del dashboard. Compras opera con una cuenta
> compartida. El Z-tracking se leerá de SAP por API.

## 2. §7.1 · RN-07 a RN-09 — contra qué fecha se mide

Donde dice `Fecha entrega SolPed`, decir **`Fecha Entrega` (llegada a Gutis)**. Añadir que la
diferencia entre la llegada a Costa Rica (fecha base de RN-01) y la fecha comprometida es el
tiempo que el plan de Compras deja al proceso aduanal.

> Nota para Planeación: su estatus de SAP es `Fecha entrega SolPed − Fecha entrega`. Medir
> contra la segunda responde «¿llega cuando Compras dijo?», no «¿llega cuando producción lo
> necesita?».

## 3. §4 · RF-19 — filtros

Sustituir la lista por: **orden de compra (prefijo), posición, material (búsqueda por
código o descripción), vía, etapa y cumplimiento**. La etapa admite los estados terminales
(«Cerrado», «Cancelado»); el cumplimiento admite «sin proyección».

## 4. §4 · RF-01 y RF-31 — origen de los pedidos

RF-31 (carga manual del archivo) queda como **vía transitoria**. RF-01 pasa a leer de **la
API de SAP** cuando exista su contrato; la lógica de carga no cambia.

## 5. §7.1 · RN-05 y RF-03 — destino del pedido

Añadir: si la referencia de embarque está registrada en la fuente de rastreo, **el destino
es el puerto de descarga que declara la naviera**, aunque el incoterm nombre otro; las
discrepancias se informan en la carga.

## 6. §5 · RNF-05 — usuarios y roles

Añadir: el rol Compras opera con **una cuenta compartida** y sesiones simultáneas. La
auditoría (RF-14) la registra como un solo usuario.

Y lo que `US-42` fijó del mecanismo propio (RNF-04): cuatro roles con Administrador,
contraseñas con argon2id, bloqueo tras 5 intentos fallidos durante 15 minutos, cierre de
sesión tras 30 minutos sin actividad, «Recordar sesión» de 30 días y reinicio de
contraseña por el Administrador. Los cuatro plazos son parámetros ajustables.

## 6b. §7.1 · RN-02 — la llegada confirmada saca a un pedido de «Sin tracking»

Añadir a RN-02: un pedido sin identificador de rastreo permanece en `SIN_TRACKING` **salvo
que una persona confirme su llegada** (`US-14`); con la llegada confirmada avanza a «En
destino». Y a RN-02 a RN-06: **las etapas solo avanzan**. — `US-14`, 01/10/2026

## 6c. §7.1 · RN-10 — la recepción en planta

Precisar: la recepción es conforme si lo recibido llega **al menos** a lo pedido menos la
tolerancia (10 %, parámetro `tolerancia_recepcion_pct`); recibir de más no lo impide. Solo
se recibe un pedido que pasó aduana. Por debajo de la tolerancia el pedido no avanza y se
ofrece el **cierre forzado**, que cierra con lo recibido. — `US-18`, 01/10/2026

## 6d. §7.1 · RN-19 y §4 · RF-32 — la liberación de Calidad

Precisar en RN-19: la ventana se cuenta en días hábiles (lunes a viernes) desde el **día
local** de la recepción; el día de la recepción no cuenta. **Los feriados no se descuentan**
mientras no exista un calendario. Precisar en RF-32: Calidad puede liberar **por partes**;
la línea sigue activa hasta que lo liberado iguala lo recibido, y no se libera más de lo
recibido. La registran Planificación o Logística. — `US-47`, 05/10/2026

## 7. Anexo C.5 — fuentes de rastreo

Registrar la prueba de **Parcels** (29/09): sirve para aéreo, no para marítimo (sin ETA, sin
puerto de descarga, sin posición) ni para seguimiento en vivo. **Se mantiene ShipsGo**;
volumen estimado por Ventas: 70–110 embarques al mes.

## Pendiente

- ~~Respuesta de **Planeación** al cambio de fecha comprometida (punto 2).~~ **Confirmado el
  06/10/2026:** la fecha comprometida es la columna R.
- Contrato de la **API de SAP** (punto 4).
- ~~Respuesta de **ShipsGo** a la licencia anual plana (punto 7).~~ **06/10:** se aprueba la
  compra anual de créditos, condicionada a US$1,70 por crédito. **07/10: ShipsGo aceptó**
  1.100 créditos a US$1,70 (US$1.870) más US$250 únicos por la API; recargas al mismo precio
  y arrastre de créditos sobrantes si la recompra es al menos el 50 % del paquete.

## Acuerdos del 06/10/2026 que también entran en v0.6

- **RF-17 (mapa aéreo):** la posición de la aeronave es **estimada** sobre la ruta que entrega
  la fuente comercial, y se rotula como tal. OpenSky queda fuera mientras no haya licencia.
- **RF-03:** el MAWB se provee para cada pedido aéreo; la guía hija (HAWB) se conserva para
  confirmar el arribo por TICA.
