# TrackIn

Seguimiento de las compras internacionales de Gutis desde que salen del proveedor hasta que la planta puede usarlas, para anticipar si cada una llegará a tiempo.

## Language

### Compras

**Pedido**:
Una línea de una orden de compra: un material, de un proveedor, con su cantidad y fecha comprometida. Es la unidad que TrackIn rastrea y evalúa.
_Avoid_: Línea, posición, orden, embarque

**Orden de compra**:
El documento de Compras que agrupa uno o más pedidos.
_Avoid_: OC suelta para referirse a un pedido, pedido

**Fecha comprometida**:
El día en que Compras planificó que el pedido llegue a Gutis. Es la vara contra la que se mide si el pedido va a tiempo.
_Avoid_: Fecha de entrega, fecha de entrega del pedido

**Z-tracking**:
El archivo de seguimiento de compras que Gutis exporta de SAP y que alimenta a TrackIn con los pedidos vivos.
_Avoid_: Archivo de seguimiento, Excel, archivo de carga

**Pedido ausente**:
Pedido vivo que dejó de aparecer en el último Z-tracking y espera que alguien revise qué pasó con él.
_Avoid_: Huérfano, eliminado, desaparecido

**Tracking interno**:
El código propio que TrackIn asigna a cada pedido y que ven los usuarios.
_Avoid_: Tracking (a secas), referencia

### Rastreo

**Elemento rastreado**:
Cualquier cosa que una fuente externa sabe seguir a partir de un identificador: una nave, un vuelo, un contenedor, un BL, un booking o una guía aérea.
_Avoid_: Nave, vuelo (cuando se habla del concepto general)

**Referencia de embarque**:
El identificador externo con que una fuente encuentra un elemento rastreado: número de contenedor, BL, booking, MAWB, HAWB, etc.
_Avoid_: Tracking externo, número de tracking

**Tramo**:
Parte del viaje de un pedido hecha en un mismo elemento rastreado. Todo pedido rastreado tiene al menos uno.
_Avoid_: Etapa (eso es la etapa de viaje), pierna

**Transbordo**:
El paso de un pedido de un elemento rastreado a otro a mitad de camino, que cierra un tramo y abre el siguiente.
_Avoid_: Trasbordo, cambio de nave

### Llegada

**Llegada confirmada**:
La llegada real del pedido a destino, declarada por una persona de Logística. Prevalece sobre cualquier otra llegada o ETA.
_Avoid_: Desembarco, ATA manual

**Llegada reportada**:
La llegada real que informa una fuente externa (la naviera, la aerolínea o la aduana).
_Avoid_: ATA de la API, ATA (a secas)

**Llegada inferida**:
La llegada que TrackIn deduce por su cuenta al ver el elemento rastreado detenido en el destino.
_Avoid_: ATA (a secas), arribo detectado

**Fecha disponible proyectada**:
El día en que se estima que el pedido podrá usarse: la llegada (o, sin ella, la ETA) más el lead time del destino y cualquier ajuste manual.
_Avoid_: Fecha proyectada, fecha disponible, ETA

### Estado

**Etapa de viaje**:
Dónde está la carga del pedido: sin tracking, en origen, en tránsito, en destino, en proceso aduanal o recibida en planta.
_Avoid_: Estado (cuando se habla solo de la ubicación)

**Estado de cumplimiento**:
Si el pedido llegará a tiempo respecto de su fecha comprometida: a tiempo, en riesgo o retrasado. No existe mientras no haya fecha disponible proyectada.
_Avoid_: Semáforo (es su representación visual, no el concepto)

**Estado**:
El valor único que se muestra de un pedido. Si el pedido está cerrado o cancelado, es eso; si no tiene tracking, es sin tracking; si está en riesgo o retrasado, manda el cumplimiento; en otro caso, la etapa de viaje.
_Avoid_: Estado calculado

### Recepción y cierre

**Recepción en planta**:
La entrada física de la carga del pedido a la planta o al almacén de Gutis. Solo se admite si la cantidad recibida está dentro de la tolerancia de recepción; aún no permite usar el material.
_Avoid_: Recibido (a secas), entrega

**Tolerancia de recepción**:
Cuánto puede faltar respecto de lo pedido para que la recepción en planta se acepte.
_Avoid_: Margen

**Liberación de calidad**:
La autorización de Control de Calidad para usar lo recibido en planta. Puede darse por partes.
_Avoid_: Aprobación, recepción

**Cerrado**:
Pedido que TrackIn ya no sigue porque terminó, sea por una recepción conforme o por un cierre forzado.
_Avoid_: Recibido, entregado, completado, disponible

**Recepción conforme**:
El cierre normal de un pedido: Calidad liberó todo lo recibido en planta y el material está disponible para producción.
_Avoid_: Cierre normal, completado

**Cierre forzado**:
Cerrar un pedido a mano sin recepción conforme, por ejemplo cuando llegó menos de lo tolerado.
_Avoid_: Cierre manual

**Cancelado**:
Pedido que dejó de esperarse antes de llegar.
_Avoid_: Anulado, eliminado
