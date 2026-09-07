# Contrato de captura de la referencia de embarque

**`TASK-30` · Sprint 3 · 5 de septiembre de 2026**
Destinatario: **Planeación y Logística** · Autor: Mariano Mayorga

---

## Por qué esto va primero

TrackIn rastrea los pedidos consultando a **Vizion** (marítimo) y **Portcast** (aéreo). Ambas
fuentes buscan un envío por su **número de referencia**. Sin ese número no devuelven nada, por
buenas que sean.

Hoy el archivo de seguimiento **no tiene ninguno** en sus 429 líneas. Pero sí aparece en los
comentarios del comprador:

> *«En Tránsito a CR // **BL recibido** // ETA 28 ago»*
> *«Pendiente **BL** y ETA SEP 25»*

O sea: **el dato existe y alguien lo conoce**, solo que se escribe en prosa y se pierde. Este
documento define dónde ponerlo para que el sistema lo pueda usar.

> **Cuanto antes se empiece, mejor.** La integración estará lista a finales de octubre; cada
> semana que se capture desde ya es una semana de histórico con la que arrancar.

---

## Las tres columnas nuevas

Se agregan al final del archivo de seguimiento, en las hojas **PRODUCCION** e **IDA**:

| Columna | Contenido | Ejemplo |
|---|---|---|
| `Tipo de referencia` | Uno de: `CONTENEDOR`, `BL`, `BOOKING`, `MAWB` | `CONTENEDOR` |
| `Número de referencia` | El número, sin espacios | `MSKU1234567` |
| `Transportista` | Naviera o aerolínea | `MAERSK` |

Y una cuarta, muy recomendable:

| Columna | Contenido | Para qué |
|---|---|---|
| `Fecha en que se obtuvo` | Fecha en que llegó la referencia | Medir con **cuánta antelación** al arribo la tenemos. Es el dato que dirá si el rastreo aporta o no. |

---

## Qué número poner según la vía

### Marítimo — cualquiera de los tres, en este orden de preferencia

1. **Número de contenedor** — el que mejor funciona.
   Formato: **4 letras + 7 dígitos**. Ejemplo: `MSKU1234567`, `TGHU7654321`.
2. **BL máster (MBL)** — el conocimiento de embarque del transportista.
3. **Booking** — sirve desde antes de que zarpe.

Si un embarque trae **varios contenedores**, se puede poner el BL una sola vez: cubre todos.

### Aéreo — el MAWB, y solo el MAWB

Formato: **11 dígitos**, con prefijo de 3 de la aerolínea. Ejemplo: `176-12345678`.

> ### ⚠️ Cuidado con el HAWB
>
> El agente de carga suele entregar un **HAWB** (guía *hija*, la que él emite). **Ese número no
> sirve**: los sistemas de las aerolíneas no lo reconocen y la consulta vuelve vacía.
>
> Hay que pedir el **MAWB** (guía *madre*, la de la aerolínea) o, si solo entregan el HAWB,
> pedirle al agente la **correspondencia entre ambos**.
>
> Cómo distinguirlos: el MAWB **siempre** empieza con el prefijo de 3 dígitos de la aerolínea
> (`176-`, `045-`, `020-`…). Si el número no tiene esa forma, es un HAWB.

---

## Quién tiene la referencia — depende del incoterm

Esto es lo que determina si conseguirla es fácil o hay que insistir:

| Incoterm | Órdenes | Quién la tiene | Qué hacer |
|---|---|---|---|
| `EXW` · `FOB` · `FCA` | **56** | **El agente de carga de Gutis** — él hace el booking | Pedirle un **reporte periódico**. Es la vía rápida. |
| `CIF` · `CIP` · `CPT` | **71** | **El proveedor** — él contrata el flete | **Exigirla**, idealmente como condición en la orden de compra: enviar BL o MAWB dentro de X días del zarpe. |
| `LOCAL` | 26 | No aplica | Compra local, no se rastrea. |

**La vía más rápida para llenar el histórico** es pedirle al agente de carga un reporte con
todas las referencias que ya maneja. Él las tiene todas: es su negocio.

---

## Reglas de validación que aplicará el sistema

Cuando se cargue el archivo (`US-32`), el sistema revisará:

| Regla | Si no se cumple |
|---|---|
| El `Tipo de referencia` es uno de los cuatro valores admitidos | Se marca la línea para revisión |
| Un contenedor tiene 4 letras + 7 dígitos | Se marca para revisión |
| Un MAWB tiene 11 dígitos con prefijo de aerolínea | Se marca para revisión, con el aviso de que puede ser un HAWB |
| La vía de transporte concuerda con el tipo de referencia | Un `MAWB` en un pedido marítimo se marca |

**Nada de esto detiene la carga.** Una línea con problemas se señala y el resto del archivo
entra normalmente. Un campo vacío tampoco es un error: simplemente ese pedido queda **sin
rastreo** hasta que aparezca la referencia.

---

## Lo que hay que completar además

Aparte de las columnas nuevas, hay un hueco que ya existe:

- **La vía de transporte está vacía en 165 órdenes.** Sin ella el sistema no sabe a qué fuente
  preguntar —Vizion o Portcast— ni cuántos envíos cotizar de cada tipo. Completarla es tan
  importante como la referencia misma.

---

## Resumen para llevar a la reunión

1. **Tres columnas nuevas** en PRODUCCION e IDA: tipo, número y transportista. Más la fecha en
   que se obtuvo.
2. **Marítimo:** contenedor, BL o booking. **Aéreo:** MAWB, **nunca** el HAWB.
3. **Pedirle el reporte al agente de carga** — es la forma más rápida de llenar lo existente.
4. **En las compras CIF y CIP hay que exigirle la referencia al proveedor**, porque hoy llega
   tarde o no llega.
5. **Completar la vía de transporte** en las 165 órdenes donde falta.
