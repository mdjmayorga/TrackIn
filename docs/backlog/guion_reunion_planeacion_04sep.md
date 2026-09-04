# Guion — reunión con Planeación · 30 min · 04/09/2026

**Respaldo completo:** `dudas_reunion_planeacion.md` (32 preguntas). Este guion lleva **6**.
**Técnica:** preguntar por **práctica actual**, no por preferencia. «¿Qué usan hoy?» se
responde en dos minutos; «¿qué preferirían?» abre un debate de diez.

**Apertura (2 min).** Dos frases, sin repasar el proyecto: *«Arrancamos a construir el
lunes. Traigo cinco preguntas cuya respuesta cambia lo que se programa; el resto se los
mando por correo para que confirmen o corrijan.»*

---

## Las 6 preguntas, en este orden

El orden es un hilo: **qué fecha necesitan → cómo la calculo → contra qué la comparo →
quién gana si hay conflicto → qué ven en pantalla → cómo obtengo la llave del rastreo.**

| # | Pregunta (como se dice en voz alta) | Min | Qué desbloquea | Si contestan X, pasa Y |
|---|---|---|---|---|
| **1** | «Si TrackIn les dice que un material importado **llega a planta el 20 de octubre**, ¿pueden programar producción para el 21? ¿O tienen que esperar a que Calidad lo libere?» → si esperan: «¿cuántos días toma? ¿es parejo o depende del material?» | 5 | `US-09`, RF-10 | Si esperan la **liberación**, la fecha proyectada de RN-01 está ~15 días corta para su uso real → **RF nuevo**, a costear hoy y no en el Sprint 4 |
| **2** | «El **lead time que da SAP, ¿hasta dónde llega**: hasta que el barco atraca en Moín, o hasta que el material entra a la planta?» | 5 | RN-01, `TASK-01`, `TASK-03` | Si llega **hasta planta**, sumarlo a la ETA del puerto **cuenta el tramo local dos veces**. La fórmula de RN-01 se parte |
| **3** | «Cuando dicen que un pedido llegó tarde, **¿contra cuál de estas fechas lo miden?**» — mostrar las cuatro columnas del Z-tracking en pantalla | 4 | RN-02 a RN-11, `US-10` | Define el lado derecho del semáforo. Son cuatro columnas con nombres casi iguales; sin esto el semáforo no tiene referencia |
| **4** | «El archivo ya trae **`Estatus` y `Diferencia Días` calculados por SAP**. ¿Los usan hoy para decidir? ¿Les creen?» | 3 | `US-10`, `US-12` | Si los usan y TrackIn recalcula distinto, quedan **dos semáforos que se contradicen en pantalla**. Hay que decidir cuál manda antes de construirlo |
| **5** | «Esta es la pantalla que verían ustedes» — **mostrar el wireframe de la vista simple** y callarse | 3 | `US-43`, `US-33` | Hoy es Material · Etapa · Cumplimiento: **no muestra para cuándo ni cuánto**. Si lo notan solos, la respuesta vale el doble |
| **6** | **Tuya:** los números de referencia de embarque — cuáles son y cómo te los van a entregar | 4 | `TASK-30`, `US-01`, `TASK-28` | Si dicen «eso lo maneja Logística», **cortala ahí** y agendá el seguimiento. No la pelees en esta reunión |

**Cierre (3 min).** Repetir en voz alta las decisiones tomadas y quién queda de dueño de
cada pendiente. Que nadie salga sin saber qué le toca.

---

## Si se acorta

Caen en este orden: **6 → 5 → 4**. Las tres primeras son innegociables: sin ellas
`US-09` no se puede construir y el Sprint 4 arranca sobre una fórmula inventada.

## Si sobra tiempo (poco probable)

En este orden, todas de un minuto:

- **Umbral de «En riesgo»:** hoy son 2 días. ¿Alcanza para reprogramar producción?
- **Exportar a Excel:** ¿es requerimiento? (decisión abierta #5, sin dueño desde el 20/08)
- **Pantalla de planta:** ¿existe la pantalla comprada? Si no, `US-33` no se hace.

## Lo que va por correo hoy mismo, ya resuelto y solo para confirmar

No son preguntas: son **propuestas con valor por defecto**. Si nadie contesta en 48 h,
se toman por aceptadas y quedan documentadas como supuesto.

| Tema | Lo que propongo |
|---|---|
| Lead time provisional mientras no exista el API de SAP | 7 días marítimo / 3 aéreo, parámetro editable |
| Fecha proyectada en fin de semana | Corre al siguiente día hábil |
| Quién aplica el ajuste manual de días | Logística |
| Entregas parciales | La línea sigue activa hasta `Ctd. pendiente` = 0 |
| Pedidos cerrados | Visibles 15 días bajo filtro «recibidos» |
| Filtros de la grilla | Material, país y estado |
| Sesión y bloqueo | 8 h de sesión · 30 min de inactividad · bloqueo a los 5 intentos |
| Contraseña olvidada | Reinicio por el administrador |
| Recepción en planta | La registra Bodega o Logística, no Planeación |

## Después de la reunión — para que esto se cierre de verdad

| Cuándo | Qué |
|---|---|
| **Hoy, 04/09** | Enviar el correo de propuestas con la frase explícita: *«si no recibo comentarios antes del lunes 8 a mediodía, se toman por aceptadas y quedan documentadas como supuesto»* |
| **Hoy, 04/09** | Volcar las 6 respuestas a `dudas_reunion_planeacion.md` y marcar cuáles quedaron derivadas (P4, P5, S2, R5) |
| **Viernes 5** | Agendar la sesión con **Logística** para R1–R6 y T2 — es la que desbloquea `US-43` y `US-46` |
| **Viernes 5** | Llevar a **Greivin**: Plan A de `TASK-28`, decisión abierta #5 (T4), pantalla de planta (S3/S4), administrador de cuentas (U2) y —si aparece— el RF de liberación de Calidad |
| **Lunes 8** | Arranca el Sprint 3. `TASK-01` ya con esquema definido |

**Si `#1` vuelve como «esperamos la liberación de Calidad»:** no se resuelve en esta
reunión. Anotar los días que toma, seguir con `#2`, y llevarlo a Greivin el viernes —
es alcance y presupuesto, no una decisión de Planeación.

## Lo que NO va a esta reunión

- **ETD/ATD y el segundo Excel** (sección R) → es de **Logística**, no de Planeación.
- **61 % de líneas sin tipo de transporte** (T2) → calidad de datos, **Logística**.
- **Plan A de `TASK-28`, Vizion y Portcast** → alcance y presupuesto, **Greivin**.
