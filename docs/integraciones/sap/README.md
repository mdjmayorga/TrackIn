# Integración con SAP — contrato de pedidos

**Versión 1.0 · 27/10/2026 · `US-64`.** Pedido en la reunión de entrega del Informe 2: dejar
listos todos los campos que TrackIn necesitaría de SAP, el destino del envío y el interruptor
para habilitar la escucha. **La API de SAP todavía no existe.** Este contrato es lo que tiene
que cumplir quien la construya, y lo que TrackIn va a esperar.

| Archivo | Para qué |
|---|---|
| `README.md` | Este documento: el contrato legible |
| `lote_pedidos.schema.json` | La validación exacta (JSON Schema 2020-12) |
| `ejemplo_lote.json` | Un lote con todos los campos, válido contra el esquema |
| `TrackIn_SAP.postman_collection.json` | Los envíos de ejemplo, con pruebas |
| `TrackIn_local.postman_environment.json` | `base_url` = `http://localhost:8000` |
| `TrackIn_produccion.postman_environment.json` | `base_url` = `https://…` (provisional, lo define TI) |

## 1. Cómo funciona

**SAP empuja, TrackIn escucha.** SAP envía los pedidos a un endpoint de TrackIn; TrackIn no
consulta a SAP. Así TrackIn no necesita credenciales de SAP ni acceso a su red, y el contrato
queda del lado de TrackIn.

```
SAP ──POST /api/v1/integraciones/sap/pedidos──▶ TrackIn
     X-API-Key: <clave de integración>          ├─ escucha apagada → 503, no toca nada
     { lote, pedidos[] }                         └─ encendida → misma carga que el Excel
```

- **El Excel sigue siendo la carga de los martes.** La API es una segunda entrada: entra por
  el mismo camino (`FuentePedidos`), con la misma normalización, la misma carga idempotente por
  `(oc_numero, posicion_oc)` y el mismo informe.
- **La escucha arranca apagada** (`US-66`). La enciende el Administrador desde la interfaz.
- **Frecuencia:** libre. Lo recomendado es un envío diario incremental. Reenviar un lote no
  duplica nada.

## 2. El destino

| Entorno | `base_url` | Notas |
|---|---|---|
| Local | `http://localhost:8000` | El backend de desarrollo |
| Producción | `https://trackin.gutis.com` | **Provisional.** El dominio, el certificado y si queda expuesto fuera de la red de Gutis los define TI |

**Endpoint:** `POST {base_url}/api/v1/integraciones/sap/pedidos`

**Encabezados:**

| Encabezado | Valor |
|---|---|
| `Content-Type` | `application/json` |
| `X-API-Key` | La clave de integración: `SAP_INTEGRACION_CLAVE` en el `.env` del servidor. Es propia de la integración, no la de un usuario, y no se versiona |

En producción, **siempre HTTPS**: la clave viaja en un encabezado.

## 3. El cuerpo

```json
{
  "lote": {
    "id": "SAP-20261027-080000",
    "generado_en": "2026-10-27T08:00:00-06:00",
    "tipo": "INCREMENTAL",
    "sistema": "SAP S/4HANA PRD 300"
  },
  "pedidos": [ { "oc_numero": "4500123456", "posicion_oc": 10, "...": "..." } ]
}
```

### `lote`

| Campo | Tipo | Oblig. | Descripción |
|---|---|:-:|---|
| `id` | texto (≤ 64) | ✅ | Identificador único del envío en SAP |
| `generado_en` | fecha-hora ISO 8601 con zona | ✅ | Cuándo se extrajeron los datos |
| `tipo` | `INCREMENTAL` \| `COMPLETO` | ✅ | Hoy los dos se tratan como incremental: **no** se marcan ausentes los pedidos que no vienen. `COMPLETO` queda reservado |
| `sistema` | texto (≤ 60) | | Sistema y mandante, para el historial |

### `pedidos[]` — de 1 a 5 000 por lote

Cada elemento es **una línea de OC con su reparto**, la misma unidad que una fila del
Z-tracking. Fechas en `AAAA-MM-DD`. Un campo opcional sin dato va como `null` o se omite.

**A. Campos que TrackIn usa hoy** (los mismos que lee del Excel)

| # | Campo JSON | Tipo | Oblig. | Columna del Z-tracking | Referencia SAP* | Ejemplo |
|---|---|---|:-:|---|---|---|
| 1 | `oc_numero` | texto, solo dígitos (≤ 10) | ✅ | Documento Compra | EKKO-EBELN | `"4500123456"` |
| 2 | `posicion_oc` | entero ≥ 1 | ✅ | Posición (la primera) | EKPO-EBELP | `10` |
| 3 | `proveedor_codigo` | texto (≤ 20) | ✅ | Proveedor | EKKO-LIFNR | `"100234"` |
| 4 | `proveedor_nombre` | texto (≤ 200) | ✅ | Nombre del Proveedor | LFA1-NAME1 | `"Proveedor Farmacéutico S.A."` |
| 5 | `material_codigo` | texto (≤ 40) | ✅ | Material | EKPO-MATNR | `"MP-001234"` |
| 6 | `material_descripcion` | texto (≤ 200) | ✅ | Texto breve Material | EKPO-TXZ01 | `"Paracetamol polvo USP"` |
| 7 | `cantidad` | número > 0 | ✅ | Cantidad reparto | EKET-MENGE | `1500.0` |
| 8 | `unidad_medida` | texto (≤ 10) | ✅ | UMP | EKPO-MEINS | `"KG"` |
| 9 | `fecha_entrega_pedido` | fecha | ✅ | Fecha Entrega (**no** «Fecha Entrega Solped») | EKET-EINDT | `"2026-12-15"` |
| 10 | `destino_codigo` | `CRMOB` \| `CRLIO` \| `CRCAL` \| `MROC` | | *(no existe en el Excel)* | — | `"CRMOB"` |
| 11 | `via_transporte` | `MARITIMO` \| `AEREO` \| `TERRESTRE` | | Tipo de transporte | campo Z | `"MARITIMO"` |
| 12 | `pais_origen` | texto (≤ 60), mejor ISO alfa-2 | | Pais de Origen | campo Z | `"IN"` |
| 13 | `incoterm` | texto (≤ 60): código + lugar | | Incoterm | EKKO-INCO1 + INCO2 | `"CIF LIMON"` |
| 14 | `temperatura` | texto (≤ 40) | | Temperatura | campo Z | `"2-8 C"` |
| 15 | `tipo_proveedor` | `LOCAL` \| `INTERNACIONAL` | | Tipo de proveedor | campo Z | `"INTERNACIONAL"` |
| 16 | `fabricante` | texto (≤ 200) | | Fabricante | EKPO-EMNFR | `"Fabricante Ltd."` |
| 17 | `eta_declarada` | fecha | | ETA CR | campo Z | `"2026-12-01"` |
| 18 | `arribo_declarado` | `SI` \| `NO` \| `PENDIENTE` \| `N/A` | | ATA CR | campo Z | `"NO"` |
| 19 | `tipo_referencia` | `BL` \| `CONTENEDOR` \| `BOOKING` \| `MAWB` \| `HAWB` | | Tipo de referencia | campo Z | `"BL"` |
| 20 | `numero_referencia` | texto (≤ 40) | | Número de referencia | campo Z | `"COSU6508789000"` |
| 21 | `transportista` | texto (≤ 120) | | Transportista | campo Z | `"COSCO"` |
| 22 | `fecha_referencia` | fecha | | Fecha de obtención de la referencia | campo Z | `"2026-10-20"` |
| 23 | `comentario` | texto (≤ 1 000) | | Comentario comprador | campo Z / texto de posición | `"Zarpó el 18/10"` — no se guarda: TrackIn busca en él referencias escritas a mano |
| 24 | `solicitud_pedido` | texto (≤ 20) | | Solicitud de pedido | EKPO-BANFN | `"10012345"` |

\* **La referencia SAP es orientativa**: son los campos estándar donde ese dato suele vivir
(tablas EKKO, EKPO, EKET, LFA1). «Campo Z» quiere decir que hoy lo llena el reporte del
Z-tracking y su origen exacto lo confirma el equipo de SAP de Gutis.

**B. Campos reservados** — TrackIn los acepta y hoy **no los usa**. Se dejan en el contrato para
que la API los traiga desde el principio; usarlos necesita una decisión de negocio.

| Campo JSON | Tipo | Referencia SAP | Para qué serviría |
|---|---|---|---|
| `fecha_entrega_solped` | fecha | EBAN-LFDAT | Cuándo lo necesita producción (la columna K del Z-tracking) |
| `centro` | texto (≤ 10) | EKPO-WERKS | Filtrar por planta |
| `grupo_compras` | texto (≤ 10) | EKKO-EKGRP | Saber qué comprador lleva la OC |
| `fecha_documento` | fecha | EKKO-BEDAT | Medir el ciclo completo de la compra |
| `indicador_borrado` | booleano | EKPO-LOEKZ | Cancelar en TrackIn lo borrado en SAP |
| `entrega_final` | booleano | EKPO-ELIKZ | Cerrar en TrackIn lo que SAP da por entregado |
| `cantidad_recibida` | número ≥ 0 | EKBE (mov. 101) | Recepciones parciales |
| `modificado_en` | fecha-hora | CDHDR / AEDAT | Envíos incrementales confiables |

### Reglas que aplica TrackIn

Son las mismas del Excel; conviene que SAP las respete para que nada quede rechazado.

- **Clave natural:** `(oc_numero, posicion_oc)`. Si la línea ya existe, se actualiza; si no
  cambió nada, cuenta como «sin cambios». Los ajustes manuales hechos en TrackIn (fechas,
  hitos, intervenciones) no se pisan.
- **Destino:** si no viene `destino_codigo`, se deduce del lugar del incoterm (`CIF LIMON` →
  Puerto Limón) o de la vía (`AEREO` → `MROC`, la única entrada aérea). Una línea marítima sin
  destino deducible **no entra** y queda en el informe.
- **La referencia tiene que corresponder a la vía:** marítima → `BL`, `CONTENEDOR` o
  `BOOKING`; aérea → `MAWB` o `HAWB`; terrestre → ninguna. Formatos: `CONTENEDOR`
  `^[A-Z]{4}\d{7}$`, `MAWB` `^\d{3}-?\d{8}$`, `HAWB` `^[A-Z0-9-]{4,25}$`; `BL` y `BOOKING`
  libres. Una referencia que no cumple no rechaza la línea: entra sin rastreo.
- **Texto libre:** se normaliza (mayúsculas, sin tildes). `PENDIENTE`, `N/A`, `-` y vacío
  cuentan como «sin dato».
- **Con la referencia, el rastreo es automático:** una línea con BL, contenedor, booking o
  MAWB queda lista para darse de alta en ShipsGo desde *Altas en ShipsGo*.

## 4. Las respuestas

| Código | Cuándo | Cuerpo |
|---|---|---|
| `200` | Lote procesado (aunque haya líneas rechazadas) | El informe de la carga, abajo |
| `401` | Falta `X-API-Key` o no es válida, o el servidor no tiene clave configurada | `{"detail": "…"}` |
| `409` | Hay otra carga en curso (Excel u otro lote) | `{"detail": "…"}` — reintentar en unos minutos |
| `413` | Más de 5 000 pedidos | `{"detail": "…"}` — partir el lote |
| `422` | El cuerpo no cumple el esquema | El detalle de cada error. **No se procesa nada del lote** |
| `503` | **La escucha está apagada** (hoy) | `{"detail": "…", "escucha_habilitada": false}` |

**El orden de las comprobaciones es fijo:** clave → escucha → tamaño → formato. Con la escucha
apagada, un envío con clave válida recibe `503` aunque el cuerpo sea inválido.

Informe de un `200`:

```json
{
  "id_carga": 128,
  "lote_id": "SAP-20261027-080000",
  "estado": "APLICADA",
  "recibidas": 2,
  "insertadas": 1,
  "actualizadas": 1,
  "sin_cambios": 0,
  "no_entraron": 0,
  "entraron_sin_rastreo": 0,
  "incidencias": [
    {
      "clave": "4500123789-20",
      "motivo": "destino_por_via",
      "detalle": "Sin destino_codigo: se tomó MROC por ser la única entrada aérea.",
      "consecuencia": "entro_sin_rastreo"
    }
  ]
}
```

El envío queda en el **historial de cargas** de TrackIn, con origen «API de SAP», junto a las
cargas del Excel.

## 5. Probarlo con Postman

1. En el servidor (o en local), poner una clave en `SAP_INTEGRACION_CLAVE` del `.env` del
   backend y reiniciarlo.
2. Importar `TrackIn_SAP.postman_collection.json` y los dos entornos.
3. Elegir el entorno y cargar en `sap_clave` **la misma clave** (tipo *secret*, vacía en el
   repositorio).
4. Ejecutar la colección. Antes de cada envío, un script pone un `lote_id` nuevo y la hora.

| Petición | Qué prueba | Hoy (escucha apagada) |
|---|---|---|
| 1. Lote con todos los campos | El contrato completo, con los reservados | `503` |
| 2. Lote mínimo | Solo los nueve obligatorios | `503` |
| 3. Sin clave | La autenticación | `401` |
| 4. Formato inválido | La validación | `503` (la escucha se revisa antes) |
| 5. Salud | Que TrackIn esté arriba | `200` |

Cada petición trae guardadas las respuestas de ejemplo, también la del `200` con la escucha
encendida.

> **Estado al 27/10/2026.** Contrato (`US-64`), receptor (`US-65`) e interruptor (`US-66`)
> construidos. Con la escucha apagada, la corrida completa de la colección sale en verde: `503`
> en los envíos, `401` sin clave, `200` en la salud. Encendida, el lote de ejemplo entra y queda
> en el historial de cargas con origen «API de SAP». Los nombres de columna del Z-tracking se
> revisan contra el Excel final que Compras entrega esta semana.

## 7. El interruptor

*Configuración → Integración con SAP* (`US-66`). Lo ve cualquier rol salvo Planta; **solo el
Administrador lo cambia** (decisión del 27/10/2026), con confirmación, y queda quién y cuándo.
La misma pantalla avisa si el servidor no tiene `SAP_INTEGRACION_CLAVE` y muestra el último
lote recibido. `/health` informa `sap_escucha_habilitada`.

| Endpoint | Quién | Para qué |
|---|---|---|
| `GET /api/v1/integraciones/sap/escucha` | Cualquier usuario | Estado, quién la cambió, si hay clave y el último lote |
| `PUT /api/v1/integraciones/sap/escucha` `{"habilitada": true}` | Administrador | Encender o apagar |

Apagarla no deshace nada de lo ya cargado: solo deja de aceptar envíos.

## 6. Versiones

| Versión | Fecha | Cambio |
|---|---|---|
| 1.0 | 27/10/2026 | Primera versión: 24 campos en uso y 8 reservados. Receptor e interruptor construidos el mismo día |

Un campo nuevo opcional sube la versión menor (1.1) y no rompe a SAP. Un campo que pasa a ser
obligatorio, o que cambia de nombre o de tipo, sube la mayor (2.0) y se acuerda antes con
quien mantenga la API.
