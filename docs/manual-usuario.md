# Manual de usuario

Cómo se usa TrackIn día a día: leer el panel, buscar un pedido, ver su detalle,
registrar lo que pasa con él (la llegada, la aduana, la recepción, la liberación)
y mantener los pedidos al día con la carga semanal del Z-tracking.

Está organizado **por tarea**. Cada sección dice al inicio qué roles pueden
hacerla; la [tabla de permisos](#tabla-de-permisos-por-rol) las reúne todas. La
instalación y la puesta en producción no son parte de este manual: están en
[manual-instalacion.md](manual-instalacion.md) y [deployment.md](deployment.md).

**Convenciones**

- Los nombres de botones, menús y columnas van **en negrita**, tal como se leen
  en pantalla.
- Las fechas de TrackIn están en hora de Costa Rica.
- Los marcadores **[Captura: …]** indican dónde va una imagen de la pantalla.
  La [lista de capturas](#lista-de-capturas) del final dice qué debe mostrar cada
  una.

---

## Contenido

1. [Conceptos básicos](#1-conceptos-básicos)
2. [Entrar y salir](#2-entrar-y-salir)
3. [El panel de control](#3-el-panel-de-control)
4. [Buscar pedidos: filtros y grilla](#4-buscar-pedidos-filtros-y-grilla)
5. [Los mapas](#5-los-mapas)
6. [El detalle de un pedido](#6-el-detalle-de-un-pedido)
7. [Registrar lo que pasa con un pedido](#7-registrar-lo-que-pasa-con-un-pedido)
8. [La bandeja de arribos pendientes](#8-la-bandeja-de-arribos-pendientes)
9. [La carga semanal del Z-tracking](#9-la-carga-semanal-del-z-tracking)
10. [Altas y créditos de ShipsGo](#10-altas-y-créditos-de-shipsgo)
11. [Administración](#11-administración)
12. [La pantalla de planta](#12-la-pantalla-de-planta)
- [Tabla de permisos por rol](#tabla-de-permisos-por-rol)
- [Problemas frecuentes](#problemas-frecuentes)
- [Lista de capturas](#lista-de-capturas)

---

## 1. Conceptos básicos

Un **pedido** en TrackIn es una línea de orden de compra: el número de **OC** y
la **posición** (POS). Una misma OC con tres posiciones son tres pedidos. Los
pedidos entran con el Z-tracking de SAP ([sección 9](#9-la-carga-semanal-del-z-tracking))
y se siguen por su **referencia de embarque**:

| Vía | Referencias que admite |
|---|---|
| Marítima | BL, número de contenedor o booking |
| Aérea | MAWB (guía madre) o HAWB (guía hija) |

Con la referencia, TrackIn consulta la posición del envío en **ShipsGo** (y en
TICA, para las guías aéreas en Costa Rica) y calcula cuándo va a estar
disponible el material en planta.

### Etapa y cumplimiento

Cada pedido tiene dos estados distintos, que se leen por separado:

**Etapa:** dónde está el envío.

| Etapa | Qué significa |
|---|---|
| **Sin Tracking** | No tiene referencia que seguir, o la fuente todavía no respondió |
| **En Origen** | Tiene referencia, pero todavía no salió |
| **En Tránsito** | Salió del origen y va en camino |
| **En Destino** | Llegó al puerto o aeropuerto de Costa Rica |
| **P. Aduanal** | Se registró el paso a proceso aduanal |
| **Recibido** | Se registró la recepción en planta |
| **Cerrado** / **Cancelado** | Terminado: ya no cambia |

**Cumplimiento:** si llega a tiempo para la fecha comprometida (la de entrega
del pedido en SAP).

| Cumplimiento | Qué significa |
|---|---|
| **A Tiempo** | La fecha proyectada queda más de 2 días antes de la comprometida |
| **En Riesgo** | Queda a 2 días o menos de la comprometida |
| **Retrasado** | Queda después de la comprometida |
| **–** (guion) | No se puede evaluar: el pedido no tiene fecha proyectada |

El umbral de 2 días es un parámetro del sistema y puede cambiar.

### La fecha proyectada

Es la fecha en que se espera el material disponible en planta:

> **Fecha proyectada = llegada (o llegada estimada) + lead time del destino + ajuste manual**

La llegada se toma de la mejor fuente disponible, en este orden: la llegada
confirmada a mano, la que reporta la fuente de rastreo, la que deduce el sistema
por la posición, la ETA de la fuente, la ETA registrada a mano, la ETA estimada
por posición y velocidad y, por último, la ETA escrita en el Z-tracking. El
detalle del pedido dice cuál se usó ([sección 6](#6-el-detalle-de-un-pedido)).

Sin ninguna de esas fechas, o si el destino no tiene lead time, el pedido queda
**sin fecha proyectada** y su cumplimiento sale con guion.

---

## 2. Entrar y salir

*Todos los roles.*

### Iniciar sesión

1. Abrir la dirección de TrackIn en el navegador.
2. Escribir el **usuario o el correo** de la cuenta y la **contraseña**.
3. Marcar **Recordar sesión** solo en un equipo propio: la sesión queda abierta
   30 días en ese navegador.
4. Pulsar **Iniciar sesión**.

> **[Captura: login.png]** Pantalla de inicio de sesión.

El mensaje de error es el mismo para un usuario inexistente, una contraseña
equivocada o una cuenta bloqueada: así no se revela cuál de las tres es. Tras
**5 intentos fallidos seguidos** la cuenta se bloquea **15 minutos**.

### Contraseña olvidada

No hay recuperación por correo. Se pide al Administrador que la reinicie
([sección 11.1](#111-usuarios)).

### Cerrar sesión e inactividad

Para salir: menú **Configuración** (arriba a la izquierda) → **Cerrar sesión**.

Una sesión sin uso durante **30 minutos** se cierra sola y vuelve al inicio de
sesión. El panel se refresca solo, así que con el panel abierto la sesión no se
cierra mientras el equipo esté encendido y con red.

### Cambiar la contraseña

1. **Configuración** → **Cambiar contraseña**.
2. Escribir la contraseña actual y la nueva dos veces. La nueva debe tener al
   menos **10 caracteres** y ser distinta de la actual.
3. Pulsar **Cambiar contraseña**.

Al cambiarla se cierran las **demás** sesiones de la cuenta. En una cuenta
compartida (por ejemplo, la de Compras), las otras personas conectadas tienen
que volver a entrar con la contraseña nueva. La pantalla dice cuántas sesiones
se cerraron.

---

## 3. El panel de control

*Todos los roles.* Es la pantalla que se abre al entrar.

> **[Captura: panel.png]** El panel completo en pantalla ancha.

| Zona | Qué muestra |
|---|---|
| Encabezado, izquierda | Menú **Configuración** y el título del panel |
| Encabezado, derecha | La insignia de **ShipsGo**, **Arribos pendientes** y **Ajustes Z-tracking** |
| Arriba, a los lados | **Mapa Marítimo** (izquierda) y **Mapa Aéreo** (derecha) |
| Arriba, al centro | Los **indicadores** y los **Próximos Arribos** |
| Abajo, a la izquierda | La **leyenda** de los dos mapas |
| Abajo | La **Grilla de Pedidos**, con sus filtros |

En pantallas angostas (una tableta, un teléfono) todo va en una columna, con
los indicadores y la grilla primero.

**Todo el panel muestra el mismo conjunto de pedidos.** Al filtrar
([sección 4](#4-buscar-pedidos-filtros-y-grilla)) cambian juntos la grilla, los
indicadores, los próximos arribos y los mapas.

**Se refresca solo.** La grilla, los indicadores y los próximos arribos se
actualizan cada 2 minutos, y los mapas cada 5, sin recargar la página.

### Insignia de ShipsGo

Dice si el rastreo está funcionando. Al pasar el cursor sobre ella se ve la
hora de la última consulta buena a ShipsGo.

| Insignia | Qué significa |
|---|---|
| **ShipsGo API Online** (verde) | El rastreo está al día |
| **ShipsGo sin lectura reciente** (amarillo) | Hace más de 15 minutos que no hay una consulta buena |
| **ShipsGo sin datos** (amarillo) | El servicio de rastreo todavía no informó nada |
| **ShipsGo con fallas** (rojo) | ShipsGo está fallando; el texto emergente dice por qué |
| **Sin conexión con TrackIn** (rojo) | El servidor de TrackIn no responde |

Con la insignia en amarillo o rojo, las posiciones del panel pueden estar
viejas: ver [Problemas frecuentes](#problemas-frecuentes).

### Indicadores

Cinco recuadros sobre los **pedidos activos** (no cuentan los cerrados ni los
cancelados):

| Indicador | Qué cuenta |
|---|---|
| **Pedidos Activos** | Cuántos pedidos están en curso |
| **A Tiempo**, **En Riesgo**, **Retrasados** | Qué porcentaje de los activos **con fecha proyectada** está en cada estado; entre paréntesis, cuántos pedidos |
| **Lead Time Medio** | El promedio, en días, del lead time de los destinos de los activos |

Los tres porcentajes suman 100 %. Los activos sin fecha proyectada no entran en
ellos, y una línea debajo de los recuadros dice cuántos son.

### Próximos Arribos

Los **cinco** pedidos activos que llegan antes dentro de los **próximos 7 días**,
con su OC y posición, el destino, la fecha y los días que faltan. El punto de
color es su cumplimiento. Si hay menos de cinco, se muestran menos; si no hay
ninguno, se dice.

---

## 4. Buscar pedidos: filtros y grilla

*Todos los roles.*

> **[Captura: grilla.png]** La grilla de pedidos con sus filtros.

### Filtrar

En el recuadro **Filtros de consulta**:

| Filtro | Cómo se usa |
|---|---|
| **Orden de compra** | Escribir la OC entera o el comienzo («4500016» trae todas las que empiezan así) |
| **Posición** | El número de posición |
| **Material** | Parte del código o de la descripción |
| **Vía** | Marítimo o Aéreo |
| **Etapa** | Una de las etapas de la [sección 1](#etapa-y-cumplimiento) |
| **Cumplimiento** | A Tiempo, En Riesgo, Retrasado o **Sin proyección (–)** |

Los filtros se combinan: Vía **Aéreo** con Cumplimiento **Retrasado** trae los
aéreos retrasados. La grilla responde sola al dejar de escribir; no hay botón de
buscar. **Limpiar filtros** los quita todos.

**Los pedidos cerrados y cancelados no aparecen por omisión.** Para verlos, se
elige **Cerrado** o **Cancelado** en el filtro **Etapa**. En ese caso la columna
de fecha pasa a ser **F. Recepción**.

### Leer la grilla

| Columna | Qué muestra |
|---|---|
| **Material** | Código y descripción |
| **Etapa** | Dónde está el envío |
| **Cumplimiento** | Si llega a tiempo; guion si no se puede evaluar |
| **OC** | Número de orden de compra. **Es un enlace al detalle del pedido** |
| **POS** | Posición |
| **F. Proyectada** | Cuándo se espera el material en planta (con cerrados: **F. Recepción**) |
| **F. Comprometida** | La fecha de entrega del pedido en SAP |
| **Vía** | Marítimo o Aéreo |
| **Destino** | Puerto o aeropuerto de llegada; el nombre completo, al pasar el cursor |

**Ordenar:** clic en el encabezado de una columna con flechas (↕). Un segundo
clic invierte el orden. Por omisión la grilla va ordenada por fecha proyectada:
primero lo que llega antes.

### Páginas y carrusel

La grilla muestra **10 pedidos por página**. **Anterior** y **Siguiente** pasan
de página, y debajo se lee qué pedidos se ven de cuántos («1–10 de 87 pedidos»).

Con más de una página, **la grilla pasa de página sola cada 20 segundos** y, al
llegar a la última, vuelve a la primera. Para que no cambie mientras se está
leyendo:

- **Con el cursor sobre la grilla, el carrusel se detiene**, y retoma al sacarlo.
- **Pausar** (arriba a la derecha de los filtros) lo detiene hasta pulsar
  **Reanudar**.
- Pasar de página a mano vuelve a contar los 20 segundos.

---

## 5. Los mapas

*Todos los roles.*

El **Mapa Marítimo** muestra los buques y el **Mapa Aéreo** las guías aéreas.
Cada marcador es un **embarque**, no un pedido: un BL con cinco posiciones es un
solo marcador. Los mapas respetan los filtros del panel.

> **[Captura: mapa-maritimo.png]** El mapa marítimo con marcadores y una ruta.

### Cómo se lee un marcador

La **leyenda**, debajo del mapa marítimo, lo resume:

| Elemento | Qué indica |
|---|---|
| **Relleno** | La etapa, con los mismos colores de la grilla |
| **Anillo** | El cumplimiento: **rojo** si algún pedido del embarque va retrasado, **naranja** si alguno va en riesgo, **blanco** si no |
| **Opacidad** | Un marcador tenue, con borde punteado, es una **lectura vieja**: sin posición nueva en más de 12 h (marítimo) o 2 h (aéreo) |
| **Trazo** | La ruta del embarque, del color de su etapa. Continuo: tramo ya hecho; punteado: tramo pendiente |
| **✈** | Un avión en vuelo. Su posición es estimada con el horario del vuelo |

Los buques que ya llegaron se dibujan en su puerto de destino.

### Ver un embarque

- **Pasar el cursor** sobre un marcador muestra un rótulo corto: qué es, dónde
  está y de cuándo es la lectura.
- **Hacer clic** abre un recuadro con cada pedido del embarque, su etapa y su
  cumplimiento, y el enlace a su detalle. Si el embarque tiene ruta, se dibuja
  en el mapa.

### Marcadores agrupados

Cuando varios embarques quedan encimados, se muestran como **un círculo con el
número** de embarques. Al hacer clic:

- si se pueden separar, el mapa se acerca hasta separarlos;
- si no se separan ni de cerca (por ejemplo, dos guías en el mismo aeropuerto),
  se abre un recuadro con cada embarque y su botón **Ver ruta**, para elegir de
  cuál dibujar la ruta.

> **[Captura: mapa-grupo.png]** El recuadro de un grupo con el botón «Ver ruta».

Un pedido sin posición conocida no aparece en el mapa; el título del mapa dice
cuántos embarques se muestran.

---

## 6. El detalle de un pedido

*Todos los roles, salvo la pantalla de planta.* Se abre con el enlace de la
**OC** en la grilla, desde el recuadro de un marcador del mapa o desde la
bandeja de arribos.

> **[Captura: detalle.png]** El detalle de un pedido marítimo en tránsito.

**Encabezado:** OC y posición, material, proveedor, cantidad, país de origen, y
la **etapa** y el **cumplimiento** juntos.

### Desglose del cálculo

Explica de dónde sale la fecha proyectada:

| Fila | Qué dice |
|---|---|
| **ETA utilizada** | La fecha de llegada que se usó, y de qué fuente salió (por ejemplo, «llegada reportada por la fuente» o «ETA CR del Z-tracking») |
| **+ Lead time del destino** | Los días del puerto o aeropuerto a la planta |
| **+ Ajuste manual** | Los días que alguien sumó o restó a mano ([sección 7.6](#76-ajustar-días)) |
| **= Fecha proyectada** | El resultado |
| **Fecha comprometida** | La de entrega en SAP |
| **Margen** | Días entre la proyectada y la comprometida: en rojo si es negativo |

### Elemento rastreado y arribo

- **Tracking:** la referencia que se sigue (BL, contenedor, guía), el buque o
  vuelo, los transbordos, la última posición y la **última consulta** a la
  fuente, con su antigüedad.
- **Arribo:** las tres llegadas por separado: **Manual** (confirmada por una
  persona), **Fuente** (reportada por ShipsGo o TICA) e **Inferido** (deducida
  por la posición).
- **Recepción y cierre:** aparece cuando el pedido ya se recibió o se cerró.

Si el pedido no tiene referencia, el bloque lo dice y ofrece asociarla
([sección 7.7](#77-asociar-o-corregir-la-referencia)).

### Línea de tiempo

La historia del pedido, con lo más reciente arriba: cada intervención manual
(quién, con qué rol, qué cambió y el motivo) y cada hito del viaje que informó
ShipsGo (salida del origen, transbordos, llegada a destino).

### Mapa del envío

El recorrido del envío: para las guías aéreas, todos los vuelos con la posición
actual; para los envíos marítimos, el mapa de ShipsGo o la última posición
conocida.

---

## 7. Registrar lo que pasa con un pedido

Al pie del detalle está la **barra de acciones**. Cada rol ve solo las que
puede hacer. Las que no aplican a la etapa actual se ven **deshabilitadas**, y
al pasar el cursor dicen por qué.

> **[Captura: acciones.png]** La barra de acciones con un formulario abierto.

Todas siguen los mismos pasos:

1. Pulsar la acción: se abre su formulario.
2. Completar los datos. El **motivo es opcional** en todas; si se escribe,
   queda en la línea de tiempo.
3. Pulsar **Confirmar**, o **Cancelar** para cerrar sin cambios.

Al confirmar, el pedido se recalcula y el panel se actualiza. **Un pedido
cerrado no admite ninguna acción.**

El orden normal de un pedido es: llega → **Confirmar desembarco** (si la fuente
no lo informó) → **Pasar a proceso aduanal** → **Registrar recepción en planta**
→ **Registrar liberación de Calidad**.

### 7.1 Confirmar desembarco

*Logística, Compras y Administrador.*

Registra la fecha y hora en que el envío llegó a Costa Rica. Se usa cuando la
fuente no la reportó, o la reportó mal. El pedido pasa a **En Destino** y la
llegada confirmada manda sobre cualquier otra fecha.

Si ya había una llegada confirmada, TrackIn la muestra y pregunta si se
reemplaza: **Reemplazar la llegada**.

### 7.2 Pasar a proceso aduanal

*Planificación, Logística, Compras y Administrador.* Solo desde **En Destino**.

Registra que el pedido entró en trámite de aduana. No pide datos, solo el motivo
opcional. También se puede hacer desde la [bandeja de arribos](#8-la-bandeja-de-arribos-pendientes).

### 7.3 Registrar recepción en planta

*Logística, Compras y Administrador.* Solo desde **P. Aduanal**.

Registra la fecha y hora de recepción y la **cantidad recibida** (propone la
cantidad pedida). El pedido pasa a **Recibido**.

Si lo recibido no llega al mínimo conforme (por omisión, 10 % menos que lo
pedido), el pedido no avanza y TrackIn lo dice. Si el resto no va a llegar, se
puede cerrar igual con **Cerrar con recepción parcial**.

### 7.4 Registrar liberación de Calidad

*Planificación, Logística, Compras y Administrador.* Solo desde **Recibido**.

Registra la fecha y hora en que Calidad liberó el material y la **cantidad
liberada** (propone lo que falta liberar). Mientras no se libera, el detalle
muestra la **liberación estimada** (de 7 a 15 días hábiles desde la recepción).

### 7.5 Registrar ETA

*Compras y Administrador.* Solo antes de la llegada (**Sin Tracking**,
**En Origen** o **En Tránsito**).

Registra la llegada estimada a Costa Rica que da el agente de carga cuando la
fuente no la tiene; por ejemplo, cuando la guía termina en un transbordo fuera
del país. Se elige la fecha en un calendario.

Si después la fuente da una ETA a destino, **manda la de la fuente**. Para
borrar la ETA registrada: **Quitar la ETA**.

### 7.6 Ajustar días

*Logística, Compras y Administrador.* Requiere que el pedido tenga fecha
proyectada.

Mueve la fecha proyectada cuando se sabe algo que el cálculo no ve (una demora
en el transbordo, un feriado en el puerto). Se elige la **nueva fecha
proyectada** en un calendario y el formulario dice cuántos días de ajuste
quedan, hasta 365 en cada sentido. Para quitar el ajuste, se elige la fecha
calculada sin ajuste, que el formulario también muestra.

Si el pedido no tiene fecha proyectada, primero hay que darle una con
[Registrar ETA](#75-registrar-eta).

### 7.7 Asociar o corregir la referencia

*Logística, Compras y Administrador.* En el bloque **Elemento rastreado y
arribo** del detalle.

- **Asociar:** si el pedido no tiene referencia y se tiene por otro medio, se
  elige el tipo (BL, Contenedor, Booking, MAWB o HAWB), se escribe el número y se
  pulsa **Asociar**. Lo normal es que la referencia llegue en el Z-tracking.
- **Corregir referencia:** si el número está mal escrito, el enlace abre el
  mismo formulario con la referencia actual para editarla.
- **Guía hija (HAWB):** ninguna fuente sigue las guías hijas, sí la guía madre
  que las ampara. El detalle ofrece seguir el pedido por su guía madre: viene
  escrita si TICA la encontró, o se escribe a mano. Si la guía madre resultó
  equivocada, se puede corregir.

Una referencia nueva se rastrea recién cuando se da de alta en ShipsGo
([sección 10](#10-altas-y-créditos-de-shipsgo)). Si falta, el detalle muestra el
enlace **Dar de alta en ShipsGo** (Compras y Administrador).

---

## 8. La bandeja de arribos pendientes

*Planificación, Logística, Compras y Administrador.* Botón **Arribos pendientes**
del encabezado.

Son los pedidos que llegaron a destino y esperan que se registre el paso a
proceso aduanal. La burbuja del botón dice cuántos son; sin pendientes, no hay
burbuja.

> **[Captura: bandeja.png]** La bandeja con dos arribos pendientes.

La lista va ordenada por espera: primero los que llevan más tiempo. Cada
pedido muestra su OC y posición (enlace al detalle), el material, el destino,
cuándo llegó y la fecha comprometida.

Para registrar el paso a aduana desde aquí: **Pasar a proceso aduanal** →
motivo opcional → **Confirmar**. El pedido sale de la bandeja y el contador baja.

---

## 9. La carga semanal del Z-tracking

*Cargar: Compras y Administrador. Ver el historial: todos menos la pantalla de
planta.* Menú **Ajustes Z-tracking** del encabezado.

Los pedidos entran a TrackIn **solo** con el Z-tracking exportado de SAP. SAP
se actualiza los lunes, y la carga se hace **a más tardar el martes**.

### El aviso de la carga

El botón **Ajustes Z-tracking** lleva una burbuja cuando hay que cargar:

| Burbuja | Situación |
|---|---|
| Ninguna | La carga de esta semana está hecha |
| **Naranja** | Toca cargar (todavía dentro del plazo), o nunca se cargó |
| **Roja** | El plazo pasó y falta la carga |

Al abrir el menú se ve el mensaje, la última carga (cuándo y quién) y los
enlaces **Cargar Z-tracking** (o **Historial de cargas**) y **Altas en ShipsGo**.

### Cargar el archivo

1. Exportar el Z-tracking de SAP como Excel (.xlsx). TrackIn toma las hojas
   **PRODUCCION** e **IDA**.
2. **Ajustes Z-tracking** → **Cargar Z-tracking**.
3. Elegir el archivo y pulsar **Cargar**. Tarda unos segundos: recalcula todos
   los pedidos.
4. Leer el informe que aparece debajo.
5. Dar de alta en ShipsGo las referencias nuevas
   ([sección 10](#10-altas-y-créditos-de-shipsgo)).

> **[Captura: carga.png]** La pantalla de carga con el informe de una carga.

**Descargar plantilla** baja un Excel con las columnas que usa TrackIn y cuáles
son obligatorias: sirve la primera vez o cuando cambia el formato del archivo.

**Las líneas sin referencia de embarque no entran.** Cada línea necesita
«TIPO DE DOCUMENTO AWB / BL» y «# DE DOCUMENTO»: BL, contenedor o booking si es
marítima, MAWB o HAWB si es aérea. Sin eso el pedido no se puede seguir.

### Descargar los pedidos

*Compras y Administrador.* En **Cargar Z-tracking**, **Descargar pedidos en
Excel** baja `TrackIn pedidos AAAA-MM-DD.xlsx` con todos los pedidos activos
(la grilla sin filtros):

- La hoja **Grilla**, la que se ve al abrir, los muestra con las mismas
  columnas y textos que el panel.
- La hoja **PRODUCCION** tiene la estructura de la plantilla: el archivo se
  puede cargar tal cual en otro equipo, y los pedidos quedan con los mismos
  datos. Los pedidos sin documento de embarque solo van en la grilla, porque la
  carga no los acepta.

Cargarlo en el **mismo** equipo marca como «ya no vienen» los pedidos que se
agregaron después de descargarlo: es una foto de ese momento.

### Qué hace la carga

- Los pedidos **nuevos** se agregan.
- Los **existentes** se actualizan con lo que traiga el archivo.
- Los que **ya no vienen** en el archivo **no se borran**: quedan marcados para
  revisión.
- Los pedidos activos que **seguían sin referencia** y tampoco la trae esta
  carga se **cierran**: no hay forma de seguirlos. Quedan en el filtro de
  cerrados, con el motivo en su línea de tiempo.

### Leer el informe

| Total | Qué cuenta |
|---|---|
| **Líneas en el archivo** | Todas las que se leyeron |
| **Nuevos**, **Actualizados**, **Sin cambios** | Lo que pasó con las que entraron |
| **Ya no vienen** | Pedidos que estaban en TrackIn y no vinieron en este archivo |
| **No entraron** | Líneas rechazadas, en rojo si hay alguna |

Debajo:

- **Qué corregir en SAP:** los problemas agrupados por motivo, con qué hacer en
  cada caso. Ver la tabla de abajo.
- **Líneas con problemas:** cada línea con su OC-posición (u hoja y fila), el
  problema y el detalle. Se muestran 15; **Ver las N líneas** las muestra todas.
- **Cerrados por no tener referencia de embarque:** los pedidos que esta carga
  cerró ([arriba](#qué-hace-la-carga)).
- **Entraron, pero conviene revisar en SAP:** avisos sobre líneas que sí
  entraron.

Los motivos más frecuentes:

| Motivo | Qué hacer |
|---|---|
| **Sin referencia de embarque** | Completar el tipo y el número de documento en SAP |
| **Referencia de embarque inválida** | Revisar el número: un dígito de más o de menos, letras de otra referencia, o una guía aérea en un pedido marítimo |
| **Sin vía de transporte** | Completar la vía (Aéreo o Marítimo) |
| **Sin destino reconocible** | Agregar el BL o la guía madre, o indicar el puerto de llegada en el incoterm (CIF LIMON). Con EXW, FCA o FOB el incoterm nombra el origen, no el destino |
| **Vía fuera del alcance** | Nada: TrackIn sigue solo envíos aéreos y marítimos |
| **Formato inválido** | Corregir la celda que dice el detalle, con el formato que pide |
| **Dato descartado** | La línea entró sin ese dato; corregirlo en SAP para la próxima carga |

Corregido en SAP, la línea entra en la próxima carga.

Si **el archivo entero se rechaza** (no es un Z-tracking, le faltan columnas
obligatorias), no se carga nada y el informe dice por qué.

### Historial

**Cargas recientes**, en la misma pantalla, lista cada carga con su fecha, el
archivo, quién la hizo, el resultado y los totales. Clic en el nombre del
archivo para ver su informe. Las cargas que llegan por la API de SAP también
aparecen aquí ([sección 11.2](#112-integración-con-sap)).

---

## 10. Altas y créditos de ShipsGo

*Compras y Administrador.* **Ajustes Z-tracking** → **Altas en ShipsGo**, o el
enlace de la pantalla de carga.

Una referencia se rastrea solo si está dada de alta en la cuenta de ShipsGo, y
**cada alta cuesta un crédito**. Esta pantalla lista las referencias de pedidos
activos que todavía no están en la cuenta. Ver la lista no gasta nada.

> **[Captura: altas.png]** Las referencias pendientes de alta y el saldo de créditos.

### Dar de alta

1. Revisar la lista. Vienen **marcadas** todas, salvo las que traen un aviso
   (⚠): conviene revisarlas antes de gastar el crédito, y corregirlas en el
   detalle del pedido si están mal.
2. Desmarcar las que no se quieren dar de alta. Las guías aéreas de una
   aerolínea que ShipsGo no cubre aparecen sin casilla: costarían un crédito y
   no devolverían nada.
3. Pulsar **Dar de alta (N créditos)**.
4. Confirmar: **Confirmar: gastar N créditos**. **No se puede deshacer.**

El resultado dice cuántas altas se hicieron y cuántos créditos se gastaron. El
rastreo empieza en un par de minutos.

**Topes.** Hay un tope diario de altas (5 por omisión). Si las marcadas lo
superan, o si no alcanza el saldo registrado, hay que aceptarlo con una casilla
antes de confirmar.

### Créditos

Arriba de la lista está el **saldo** del paquete vigente. Al comprar un paquete
en ShipsGo, se registra con **Registrar paquete comprado**: los créditos comprados, la
fecha de compra y, si vence, la fecha de vencimiento. El formulario dice si el saldo que queda se suma
al paquete nuevo o se pierde.

El panel muestra un aviso bajo el título, solo a Compras y al Administrador,
cuando el saldo pide atención: 80 % consumido, agotado, vencido, a 60 días del
vencimiento o sin paquete registrado.

El saldo es el que lleva TrackIn y puede no coincidir exactamente con el de
ShipsGo.

---

## 11. Administración

### 11.1 Usuarios

*Solo el Administrador.* **Configuración** → **Usuarios**.

> **[Captura: usuarios.png]** La lista de cuentas.

La lista muestra cada cuenta con su usuario, nombre, correo, rol, estado y
último acceso.

| Acción | Cómo | Qué tener en cuenta |
|---|---|---|
| **Crear una cuenta** | **Nueva cuenta** → usuario, nombre, correo, rol y contraseña inicial (al menos 10 caracteres) → **Crear cuenta** | Entregar la contraseña inicial a la persona por un medio seguro |
| **Editar** | **Editar** en la fila → cambiar los datos o el rol | Un Administrador no puede quitarse su propio rol |
| **Reiniciar contraseña** | **Reiniciar contraseña** → la contraseña nueva dos veces | Cierra **todas** las sesiones abiertas de la cuenta |
| **Desactivar** / **Reactivar** | En la fila, con confirmación | Desactivar cierra sus sesiones e impide entrar. No se puede desactivar la propia cuenta |

**Las cuentas no se borran, se desactivan:** la línea de tiempo de los pedidos
guarda quién hizo cada intervención.

Los roles:

| Rol | Para quién |
|---|---|
| **Compras** | Carga el Z-tracking, gestiona ShipsGo y registra todo en los pedidos |
| **Logística** | Registra llegadas, recepciones y referencias |
| **Planificación** | Registra la aduana y la liberación de Calidad |
| **Administrador** | Todo, más usuarios e integración con SAP |
| **Planta (solo lectura)** | La pantalla permanente de planta ([sección 12](#12-la-pantalla-de-planta)) |

### 11.2 Integración con SAP

*Ver: todos menos la pantalla de planta. Cambiar: solo el Administrador.*
**Configuración** → **Integración con SAP**.

TrackIn está preparado para recibir los pedidos directamente de una API de SAP,
además del Excel. Mientras esa API no exista, la escucha queda **apagada**.

La pantalla dice si la escucha está encendida, quién la cambió y cuándo. Con
**Encender la escucha** (o **Apagar la escucha**) y su confirmación, el
Administrador la cambia:

- **Encendida:** TrackIn acepta los pedidos que envíe SAP y los crea o
  actualiza igual que la carga del Excel, salvo que no marca los que «ya no
  vienen».
- **Apagada:** deja de aceptarlos. Lo ya cargado no cambia.

---

## 12. La pantalla de planta

*Rol Planta.* Pensada para un monitor fijo en planta que nadie opera.

> **[Captura: planta.png]** La pantalla de planta.

Es el mismo panel, con estas diferencias:

- **Grilla simple:** solo **Material**, **Etapa**, **Cumplimiento**, **OC** y
  **POS**. La OC no es un enlace.
- **Sin acciones:** no carga archivos, no abre el detalle ni registra nada. No
  tiene **Arribos pendientes** ni **Ajustes Z-tracking**.
- **Pantalla completa:** el botón **Pantalla completa** del encabezado la
  activa (el navegador exige ese clic). Mientras el panel está abierto, TrackIn
  pide al navegador que no apague la pantalla.

Para dejarla funcionando:

1. Entrar con la cuenta de planta y marcar **Recordar sesión**: si el equipo se
   apaga o se corta la red más de 30 minutos, la sesión no se pierde.
2. Pulsar **Pantalla completa**.

El carrusel de la grilla y el refresco automático hacen el resto.

---

## Tabla de permisos por rol

✓ = puede. — = no puede. Los botones que un rol no puede usar no aparecen.

| Tarea | Compras | Logística | Planificación | Administrador | Planta |
|---|:-:|:-:|:-:|:-:|:-:|
| Ver el panel, la grilla y los mapas | ✓ | ✓ | ✓ | ✓ | ✓ (grilla simple) |
| Ver el detalle de un pedido | ✓ | ✓ | ✓ | ✓ | — |
| Confirmar desembarco | ✓ | ✓ | — | ✓ | — |
| Pasar a proceso aduanal (y ver la bandeja) | ✓ | ✓ | ✓ | ✓ | — |
| Registrar recepción en planta | ✓ | ✓ | — | ✓ | — |
| Registrar liberación de Calidad | ✓ | ✓ | ✓ | ✓ | — |
| Registrar ETA | ✓ | — | — | ✓ | — |
| Ajustar días | ✓ | ✓ | — | ✓ | — |
| Asociar o corregir la referencia | ✓ | ✓ | — | ✓ | — |
| Cargar el Z-tracking | ✓ | — | — | ✓ | — |
| Ver el historial de cargas | ✓ | ✓ | ✓ | ✓ | — |
| Altas y créditos de ShipsGo | ✓ | — | — | ✓ | — |
| Ver la integración con SAP | ✓ | ✓ | ✓ | ✓ | — |
| Encender o apagar la escucha de SAP | — | — | — | ✓ | — |
| Administrar usuarios | — | — | — | ✓ | — |
| Cambiar la propia contraseña | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## Problemas frecuentes

**Un pedido no aparece en la grilla.**

1. Revisar los filtros: **Limpiar filtros**.
2. Si se cerró o se canceló, no sale por omisión: filtrar **Etapa** →
   **Cerrado** o **Cancelado**.
3. Si no está ni ahí, no entró con el Z-tracking: buscar su OC-posición en el
   informe de la última carga, en **Líneas con problemas**. Lo más común es que
   le falte la referencia de embarque.

**Un pedido no aparece en el mapa.**
Solo se dibujan los pedidos con posición conocida. Los que están en **Sin
Tracking** no tienen fuente que consultar, y una referencia sin alta en ShipsGo
todavía no tiene posición: ver la sección 10.

**Un pedido está en Sin Tracking aunque tiene referencia.**
La referencia no está dada de alta en ShipsGo, o la fuente todavía no respondió.
En el detalle, si aparece **Dar de alta en ShipsGo**, falta el alta. Si la
referencia está mal escrita, **Corregir referencia**.

**La posición o la fecha del mapa no coinciden con ShipsGo.**
Mirar la insignia de ShipsGo y, en el detalle, la **Últ. consulta**. Si es
vieja, el rastreo está detenido o fallando: avisar al Administrador. Si es
reciente y la diferencia sigue, revisar en el detalle que la referencia sea la
correcta.

**El pedido no tiene fecha proyectada (guion en Cumplimiento).**
Falta una fecha de llegada de cualquier fuente, o el destino no tiene lead time.
Si el agente de carga dio una ETA, registrarla con **Registrar ETA** (sección
7.5).

**Un botón de acción está deshabilitado.**
Pasar el cursor sobre él: dice por qué. Casi siempre falta el paso anterior
(por ejemplo, la recepción exige el paso a aduana). Un pedido cerrado no admite
ninguna acción.

**La recepción no avanza el pedido.**
La cantidad recibida no llega al mínimo conforme. Si el resto no va a llegar,
**Cerrar con recepción parcial** (sección 7.3).

**La carga rechazó líneas.**
El informe dice qué corregir en SAP para cada motivo (sección 9). Corregidas,
entran en la próxima carga; no hay que hacer nada en TrackIn.

**La carga rechazó el archivo entero.**
No es un Z-tracking reconocible o le falta una columna obligatoria. Comparar
con **Descargar plantilla** y volver a exportarlo desde SAP.

**La insignia dice «ShipsGo con fallas» o «sin lectura reciente».**
Las posiciones del panel pueden tener horas. El sistema reintenta solo; si
sigue así más de una hora, avisar al Administrador. Con «Sin conexión con
TrackIn», el servidor no responde: recargar la página y, si sigue, avisar.

**Las altas en ShipsGo fallan.**
Revisar el saldo de créditos en **Altas en ShipsGo**. Si el paquete se agotó o
venció, hay que comprar uno en ShipsGo y registrarlo.

**La sesión se cerró sola.**
Pasaron 30 minutos sin uso, o el Administrador reinició la contraseña o
desactivó la cuenta, o alguien cambió la contraseña de una cuenta compartida.
Volver a entrar.

**La cuenta está bloqueada.**
Tras 5 intentos fallidos se bloquea 15 minutos. Esperar, o pedir al
Administrador que reinicie la contraseña.

**La grilla cambia de página sola.**
Es el carrusel (sección 4). Se detiene con el cursor encima o con **Pausar**.

---

## Lista de capturas

Guardar cada imagen en `docs/manual/img/` con el nombre indicado y reemplazar el
marcador por `![descripción](manual/img/<archivo>)`. Conviene tomarlas con datos
de desarrollo, no con pedidos reales, y en una ventana de al menos 1440 px de
ancho.

| Archivo | Sección | Qué debe mostrar |
|---|---|---|
| `login.png` | 2 | La pantalla de inicio de sesión vacía |
| `panel.png` | 3 | El panel completo, con marcadores en los dos mapas, los indicadores, los próximos arribos y la grilla |
| `grilla.png` | 4 | La grilla con un filtro aplicado (por ejemplo, Vía Marítimo) y el aviso del carrusel |
| `mapa-maritimo.png` | 5 | El mapa marítimo con un embarque seleccionado: su recuadro abierto y la ruta dibujada |
| `mapa-grupo.png` | 5 | El recuadro de un grupo que no se separa, con los botones «Ver ruta» |
| `detalle.png` | 6 | El detalle de un pedido marítimo en tránsito, con el desglose, el tracking y la línea de tiempo |
| `acciones.png` | 7 | La barra de acciones con el formulario de «Registrar ETA» abierto |
| `bandeja.png` | 8 | La bandeja con al menos un arribo y el formulario de paso a aduana abierto |
| `carga.png` | 9 | La pantalla de carga con el informe de una carga que tenga líneas rechazadas |
| `altas.png` | 10 | Las altas pendientes con el saldo de créditos arriba |
| `usuarios.png` | 11.1 | La lista de cuentas |
| `planta.png` | 12 | La pantalla de planta con la grilla simple |
