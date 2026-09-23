# Contrato de captura de la referencia de embarque

**`TASK-30` · Sprint 3 · 5 de septiembre de 2026**
**Revisado el 23/09/2026:** proveedor (ShipsGo), ejemplos con dígito verificador válido y conteo por líneas.
Destinatario: **Planeación y Logística** · Autor: Mariano Mayorga

---

## Por qué esto va primero

TrackIn rastrea los pedidos consultando a **ShipsGo**, para las dos vías. La fuente busca un
envío por su **número de referencia**. Sin ese número no devuelve nada, por buena que sea.

Hoy el archivo de seguimiento **no tiene ninguno** en sus 429 líneas. Pero sí aparece en los
comentarios del comprador:

> *«En Tránsito a CR // **BL recibido** // ETA 28 ago»*
> *«Pendiente **BL** y ETA SEP 25»*

O sea: **el dato existe y alguien lo conoce**, solo que se escribe en prosa y se pierde. Este
documento define dónde ponerlo para que el sistema lo pueda usar.

> **La integración ya está lista** (23/09/2026): el sistema carga el archivo, consulta a ShipsGo,
> detecta el arribo y calcula el semáforo. Lo único que le falta son las referencias. Cada semana
> que se capture desde ya es una semana de histórico con la que arrancar.

---

## Las tres columnas nuevas

Se agregan al final del archivo de seguimiento, en las hojas **PRODUCCION** e **IDA**:

| Columna | Contenido | Ejemplo |
|---|---|---|
| `Tipo de referencia` | Uno de: `CONTENEDOR`, `BL`, `BOOKING`, `MAWB` | `CONTENEDOR` |
| `Número de referencia` | El número, sin espacios | `MSKU1234565` |
| `Transportista` | Naviera o aerolínea | `MAERSK` |

Y una cuarta, muy recomendable:

| Columna | Contenido | Para qué |
|---|---|---|
| `Fecha en que se obtuvo` | Fecha en que llegó la referencia | Medir con **cuánta antelación** al arribo la tenemos. Es el dato que dirá si el rastreo aporta o no. |

---

## Qué número poner según la vía

### Marítimo — cualquiera de los tres, en este orden de preferencia

1. **Número de contenedor** — el que mejor funciona.
   Formato: **4 letras + 7 dígitos**. Ejemplo: `MSKU1234565`, `TGHU7654320`.
   El último dígito es un **verificador**: se calcula desde los diez anteriores, y el sistema
   lo comprueba antes de enviar nada.
2. **BL máster (MBL)** — el conocimiento de embarque del transportista.
3. **Booking** — sirve desde antes de que zarpe.

Si un embarque trae **varios contenedores**, se puede poner el BL una sola vez: cubre todos.

### Aéreo — el MAWB, y solo el MAWB

Formato: **11 dígitos**, con prefijo de 3 de la aerolínea. Ejemplo: `176-12345675`.
El último dígito también es verificador.

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

## Lo que se midió después de escribir esto

El spike `TASK-28` cerró el 14/09/2026 con **ShipsGo** para las dos vías, y midió tres cosas que
cambian cómo hay que capturar la referencia:

- **ShipsGo cobra las referencias que no puede resolver.** Se probó con un contenedor inventado:
  devolvió éxito, creó el embarque y descontó el crédito igual. Un número mal transcrito cuesta
  **2 USD** y después devuelve vacío, indistinguible de un envío sin novedades. Por eso el sistema
  comprueba el dígito verificador **antes** de enviar nada.
- **En la vía aérea se puede verificar la cobertura gratis.** ShipsGo publica su catálogo de 207
  aerolíneas, y los **22 prefijos** que usa Gutis están todos cubiertos. Si el prefijo de una guía
  no aparece ahí, el sistema se detiene antes de gastar el crédito.
- **El presupuesto arranca en 50 créditos** (50 embarques), con 150 más en diciembre. Un BL cuesta
  un crédito sin importar cuántos contenedores ampare, y consultarlo después es gratis: **el cobro
  es por embarque registrado, no por consulta**.

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

- **La vía de transporte falta o no se puede resolver en 290 de las 424 líneas** (165 órdenes).
  Son 259 en blanco, 15 con `PENDIENTE`, 12 con `N/A`, 3 que dicen `INDIA` —un país en la
  columna de la vía— y una que dice `AEREO` y `MARITIMO` a la vez. Sin vía el sistema no sabe
  a qué fuente preguntar ni cuántos envíos cotizar de cada tipo. **Es el escalón que tira el
  68 % del archivo**, y completarla es tan importante como la referencia misma.

  > El conteo por **líneas** es el que refleja lo que pierde el sistema: una orden tiene varias
  > líneas y cada una se rastrea por separado.

---

## Resumen para llevar a la reunión

1. **Tres columnas nuevas** en PRODUCCION e IDA: tipo, número y transportista. Más la fecha en
   que se obtuvo.
2. **Marítimo:** contenedor, BL o booking. **Aéreo:** MAWB, **nunca** el HAWB.
3. **Pedirle el reporte al agente de carga** — es la forma más rápida de llenar lo existente.
4. **En las compras CIF y CIP hay que exigirle la referencia al proveedor**, porque hoy llega
   tarde o no llega.
5. **Completar la vía de transporte**: falta en 290 de las 424 líneas (165 órdenes).
