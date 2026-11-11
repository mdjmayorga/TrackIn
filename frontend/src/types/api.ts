/**
 * Tipos del contrato HTTP con el backend.
 *
 * Se mantienen a mano por ahora. Cuando la API crezca conviene generarlos
 * desde `/openapi.json` (por ejemplo con `openapi-typescript`) para que no se
 * desincronicen del backend.
 */

export type EstadoServicio = 'ok' | 'degraded'

export type EstadoBase = 'up' | 'down'

/** Respuesta de `GET /health`. */
export interface HealthResponse {
  status: EstadoServicio
  version: string
  environment: string
  database: EstadoBase
  /** Versión de PostGIS, o null si no hay conexión a la base. */
  postgis: string | null
  /** Fuente de pedidos configurada (`ztracking`, `semilla`), o null. */
  ingesta?: string | null
  /** Salud de cada fuente externa, tal como la publicó el worker (`US-51`). */
  fuentes?: SaludFuente[]
  /** Motivo del estado degradado, cuando aplica. */
  detail: string | null
}

/** Una fuente externa en `/health` (`US-51`): la escribe el worker en cada ciclo. */
export interface SaludFuente {
  fuente: string
  degradada: boolean
  fallos_consecutivos: number
  clase_ultimo_fallo: string
  motivo_ultimo_fallo: string | null
  ultimo_contacto_ok: string | null
  /** Segundos desde el último contacto exitoso. */
  antiguedad_s: number | null
  reportado_en: string
}

/** Los cuatro roles de RNF-05 (`US-42`). */
/** `PLANTA` es la pantalla permanente de planta: solo lectura (`US-43`, 20/10). */
export type Rol = 'COMPRAS' | 'LOGISTICA' | 'PLANIFICACION' | 'ADMINISTRADOR' | 'PLANTA'

/** Usuario tal como lo devuelve `/api/v1/auth/login` y `/api/v1/auth/yo`. */
export interface UsuarioPublico {
  id: number
  usuario: string
  nombre_completo: string
  correo: string | null
  rol: Rol
  activo: boolean
  ultimo_acceso: string | null
}

/** Una fila de «Usuarios» (`US-62`, solo Administrador). */
export interface UsuarioAdministrado extends UsuarioPublico {
  /** Hasta cuándo la bloquean los intentos fallidos; en el pasado, ya venció. */
  bloqueado_hasta: string | null
}

/** Respuesta de `POST /api/v1/auth/login`. */
export interface SesionIniciada {
  token: string
  tipo: 'bearer'
  recordada: boolean
  usuario: UsuarioPublico
}

/** Respuesta de `POST /api/v1/auth/contrasena` (`US-61`). */
export interface ContrasenaCambiada {
  /** Las **otras** sesiones de la cuenta que se cerraron; la actual sigue. */
  sesiones_cerradas: number
}

// --- Pedidos (`US-16`, consumidos por la grilla de `US-19`) -----------------

export type Via = 'AEREO' | 'MARITIMO' | 'TERRESTRE'

/** Dónde está la carga (RN-02 a RN-06). No tiene valor terminal: se congela. */
export type EtapaViaje =
  | 'SIN_TRACKING'
  | 'EN_ORIGEN'
  | 'EN_TRANSITO'
  | 'EN_DESTINO'
  | 'EN_PROCESO_ADUANAL'
  | 'RECIBIDO_EN_PLANTA'

/** Si llega a tiempo (RN-07 a RN-09). Nulo cuando no hay fecha proyectada. */
export type Cumplimiento = 'A_TIEMPO' | 'EN_RIESGO' | 'RETRASADO'

/** El estado que pinta el semáforo (RF-11), incluidos los terminales. */
export type EstadoCalculado = EtapaViaje | Cumplimiento | 'CERRADO' | 'CANCELADO'

/** Columnas por las que la API sabe ordenar; con `-` delante, descendente. */
export type ColumnaOrden =
  | 'oc'
  | 'material'
  | 'proveedor'
  | 'via'
  | 'destino'
  | 'eta'
  | 'fecha_proyectada'
  | 'fecha_comprometida'
  | 'etapa'
  | 'cumplimiento'
  | 'estado'
  /** La bandeja de arribos (`US-48`). */
  | 'fecha_arribo'

export type Orden = ColumnaOrden | `-${ColumnaOrden}`

export interface Referencia {
  id: number
  codigo: string
}

/** Una línea de OC tal como la lista `GET /api/v1/pedidos`. */
export interface PedidoResumen {
  id: number
  oc_numero: string
  posicion_oc: number
  tracking_interno: string
  /** Número de la solicitud de pedido (SOLPED), del Z-tracking (`US-63`). */
  solicitud_pedido: string | null
  material: Referencia & { descripcion: string }
  proveedor: Referencia & { nombre: string }
  via_transporte: Via
  destino: Referencia & { nombre: string }
  eta_utilizada: string | null
  /** Fecha sin hora, `AAAA-MM-DD`. */
  fecha_proyectada_disponible: string | null
  /** La fecha comprometida: columna R del Z-Tracking (`US-53`). */
  fecha_entrega_pedido: string
  etapa_viaje: EtapaViaje
  estado_cumplimiento: Cumplimiento | null
  estado_calculado: EstadoCalculado
  rastreable: boolean
  ultima_actualizacion_fuente: string | null
  /** Cuándo llegó a destino: confirmado a mano, fuente o geocerca (RN-05). */
  fecha_arribo: string | null
  ausente_desde: string | null
  fecha_recepcion_planta: string | null
  /** Decimal serializado como texto. */
  cantidad_recibida: string | null
}

export interface PaginaPedidos {
  total: number
  limite: number
  desplazamiento: number
  items: PedidoResumen[]
}

// --- Detalle de un pedido (`GET /api/v1/pedidos/{id}`, `US-20`) --------------

export interface Rastreo {
  /** CONTENEDOR, BL, BOOKING, MAWB, HAWB… */
  tipo: string
  referencia: string
  /** El número como lo registró ShipsGo (`271108898` para `MAEU271108898`). */
  referencia_fuente?: string | null
  via_transporte: Via
  /** Nombre de la nave, si la fuente lo dio. */
  nombre: string | null
  imo: number | null
  eta_fuente: string | null
  ata_fuente: string | null
  posicion: { latitud: number; longitud: number } | null
  /** Decimal como texto. */
  velocidad_nudos: string | null
  /** Cuándo respondió bien la fuente por última vez (RNF-12). */
  ultima_consulta_exitosa: string | null
  guia_madre: string | null
  /** Si el pedido pasó de una guía hija a esta guía madre, la hija (`US-30`). */
  guia_hija?: string | null
  manifiesto_aduana: string | null
  /** `false` cuando ya arribó y no se consulta más. */
  activo: boolean
  /** Los cambios de nave o vuelo que informó ShipsGo, en orden (`US-30`). */
  transbordos: Transbordo[]
  /** Solo aéreo: los vuelos del embarque, también los que ShipsGo no dibuja (02/11/2026). */
  trayecto?: TramoMapa[] | null
  /** Solo aéreo: dónde está ahora, con la regla de nuestro destino final. */
  posicion_aerea?: PosicionAerea | null
}

/** Un vuelo del trayecto, para dibujarlo. */
export interface TramoMapa {
  vuelo: string | null
  /** IATA. */
  origen: string | null
  destino: string | null
  salida: string | null
  llegada: string | null
  /** `[latitud, longitud]`. */
  ruta: Array<[number, number]>
}

export type SituacionVuelo = 'EN_VUELO' | 'EN_TIERRA' | 'FINALIZADO'

/** Un barco sin posición leída, ubicado con su itinerario (11/11/2026). */
export type SituacionBarco = 'NAVEGANDO' | 'EN_PUERTO'

export interface PosicionAerea {
  latitud: number
  longitud: number
  situacion: SituacionVuelo
  vuelo: string | null
  /** Aeropuerto (IATA), si está en tierra. */
  lugar: string | null
}

export interface Transbordo {
  vehiculo_anterior: string
  vehiculo_nuevo: string
  /** UN/LOCODE o IATA. */
  puerto: string | null
  puerto_nombre: string | null
  fecha: string | null
  /** `false` si ShipsGo lo informa como previsto. */
  ocurrido: boolean
}

/** Los tres orígenes del arribo que RN-05 distingue. */
export interface Arribos {
  confirmado: string | null
  fuente: string | null
  inferido: string | null
}

/** El desglose de RN-01 que pide RF-05. */
export interface Calculo {
  /** De qué fecha partió (`ATA_CONFIRMADA`, `ETA_FUENTE`, `ETA_DECLARADA`…). */
  origen: string | null
  eta_utilizada: string | null
  lead_time_dias: number
  lead_time_maestro_dias: number
  ajuste_manual_dias: number
  /** La ETA a Costa Rica registrada a mano (`US-67`), si la hay. */
  eta_manual?: string | null
  fecha_proyectada: string | null
  fecha_comprometida: string
  ventana_aduanal_dias: number | null
  /** Comprometida menos proyectada. Negativo es atraso. */
  margen_dias: number | null
  umbral_riesgo_dias: number
  /** La operación que produjo la fecha, o por qué no hay fecha. */
  desglose: string
  /** `false`: un insumo cambió y falta el recálculo. */
  al_dia: boolean
  desglose_actual: string | null
  fecha_ultimo_recalculo: string | null
}

export interface Cierre {
  fecha_recepcion_planta: string | null
  cantidad_recibida: string | null
  liberacion_estimada: { desde: string; hasta: string } | null
  cantidad_liberada: string | null
  fecha_liberacion_calidad: string | null
  motivo_cierre: string | null
}

export interface PedidoDetalle extends PedidoResumen {
  /** Decimal como texto. */
  cantidad_pedida: string
  unidad_medida: string
  incoterm: string | null
  temperatura: string | null
  tipo_proveedor: string | null
  fabricante: string | null
  pais_origen: { codigo: string; nombre: string } | null
  /** Nulo cuando no es rastreable: se ofrece asociar uno. */
  rastreo: Rastreo | null
  arribos: Arribos
  calculo: Calculo
  cierre: Cierre
  fecha_ultima_carga: string | null
}

/** Una intervención manual (`GET /api/v1/pedidos/{id}/bitacora`, RF-14). */
export interface AsientoBitacora {
  fecha_hora: string
  usuario: string
  nombre_usuario: string
  /** `SISTEMA` en lo automático: cambios de etapa y hitos del viaje (`US-29`). */
  rol: Rol | 'SISTEMA'
  tipo: string
  campo: string | null
  valor_anterior: string | null
  valor_nuevo: string | null
  motivo: string
}

/** Las referencias que se asocian a mano (TASK-30 y la guía hija de US-49). */
export type TipoReferencia = 'CONTENEDOR' | 'BL' | 'BOOKING' | 'MAWB' | 'HAWB'

/** Un indicador de cumplimiento: cuántos y qué parte de los evaluables. */
export interface Porcentaje {
  pedidos: number
  /** Decimal como texto («62.03»). Nulo si no hay ningún activo con proyección. */
  porcentaje: string | null
}

/** `GET /api/v1/pedidos/indicadores` (`US-22`): siempre sobre los activos. */
export interface IndicadoresKpi {
  activos: number
  a_tiempo: Porcentaje
  en_riesgo: Porcentaje
  retrasados: Porcentaje
  /** Activos sin fecha proyectada: no entran en los porcentajes. */
  sin_proyeccion: number
  /** Decimal como texto («14.2»), o nulo sin activos. */
  lead_time_medio_dias: string | null
}

export interface ProximoArribo extends PedidoResumen {
  dias_restantes: number
}

/** `GET /api/v1/pedidos/proximos-arribos` (`US-28`): hasta cinco, sin relleno. */
export interface ProximosArribos {
  /** La fecha de referencia, en hora de Costa Rica. */
  hoy: string
  horizonte_dias: number
  items: ProximoArribo[]
}

// --- Cargas del Z-tracking (`US-58`) -----------------------------------------

export type EstadoCarga = 'APLICADA' | 'RECHAZADA'

/** Una carga en el historial de `GET /api/v1/cargas`. */
export interface CargaResumen {
  id: number
  archivo: string
  tamano_bytes: number
  realizada_en: string
  estado: EstadoCarga
  motivo_rechazo: string | null
  /** De dónde vino: el Excel subido por una persona o un lote de SAP (`US-65`). */
  origen: 'EXCEL' | 'API_SAP'
  /** Quién subió el Excel. Nulo en los lotes de SAP, que no los sube nadie. */
  usuario: { usuario: string; nombre_completo: string } | null
  recibidas: number
  insertadas: number
  actualizadas: number
  sin_cambios: number
  ausentes: number
  no_entraron: number
  entraron_sin_rastreo: number
}

// --- Mapas del panel (`/api/v1/pedidos/mapa/{capa}`, `US-25`) ---------------

export interface MarcadorMapa {
  id_elemento: number
  /** BL, CONTENEDOR, BOOKING, MAWB… */
  tipo: string
  referencia: string
  /** Nombre de la nave o del vuelo, si la fuente lo dio. */
  nombre: string | null
  latitud: number
  longitud: number
  /** El estado más urgente de sus pedidos, como en la grilla. No colorea el mapa. */
  estado: EstadoCalculado
  /** El relleno del marcador y el color de la ruta: la etapa menos avanzada (§2.2). */
  etapa: EtapaViaje
  /** El anillo: el peor cumplimiento a bordo; nulo si ninguno tiene fecha proyectada. */
  cumplimiento: Cumplimiento | null
  ultima_lectura: string | null
  /** Sin lectura en más del doble de la frecuencia de consulta de la vía. */
  desactualizada: boolean
  /** `false` si ya arribó y no se consulta más. */
  activo: boolean
  pedidos: Array<{
    id: number
    oc_numero: string
    posicion_oc: number
    estado_calculado: EstadoCalculado
    /** Las dos dimensiones por separado: el recuadro muestra las dos (03/11/2026). */
    etapa_viaje: EtapaViaje
    estado_cumplimiento: Cumplimiento | null
    // `US-27`: lo que muestra el recuadro del marcador (RF-18).
    material?: string | null
    proveedor?: string | null
    /** La fecha base del cálculo: la ETA a destino, o la llegada si ya llegó. */
    eta?: string | null
    fecha_proyectada?: string | null
  }>
  // --- Solo la vía aérea (`US-26`) ---
  /** La posición sale del horario del vuelo, no de una lectura. */
  posicion_estimada: boolean
  situacion: SituacionVuelo | SituacionBarco | null
  /** El vuelo en curso o el último. */
  vuelo: string | null
  /** Aeropuerto (IATA), si está en tierra. */
  lugar: string | null
  /** El trazado del vuelo en curso, `[latitud, longitud]`. */
  ruta: Array<[number, number]> | null
  /** Todos los vuelos del embarque, para mostrar la ruta al elegirlo (02/11/2026). */
  trayecto?: TramoMapa[] | null
}

export interface MapaPedidos {
  via: 'MARITIMO' | 'AEREO'
  umbral_desactualizada_h: number
  marcadores: MarcadorMapa[]
  /** Pedidos que cumplen los filtros pero no tienen posición. */
  sin_posicion: number
}

// --- Integración con SAP (`/api/v1/integraciones/sap/escucha`, `US-66`) -----

export interface EstadoEscuchaSap {
  habilitada: boolean
  /** Quién la cambió por última vez. Nulo si nadie la tocó desde la instalación. */
  cambiada_por: { usuario: string; nombre_completo: string } | null
  cambiada_en: string | null
  /** Si el servidor tiene `SAP_INTEGRACION_CLAVE`: sin ella SAP no puede enviar. */
  clave_configurada: boolean
  /** El último lote recibido de SAP, o nulo si todavía no llegó ninguno. */
  ultima_recepcion: CargaResumen | null
}

// --- Altas en ShipsGo (`/api/v1/shipsgo/altas`, `US-55`) -------------------

export interface ReferenciaPendiente {
  /** BL, CONTENEDOR, BOOKING o MAWB. */
  tipo: string
  numero: string
  via_transporte: Via
  /** Las líneas que la comparten: ShipsGo cobra por embarque, no por línea. */
  lineas: Array<{ id_pedido: number; oc_numero: string; posicion_oc: number }>
  /** Solo MAWB: si el catálogo de aerolíneas la cubre; `null` si no aplica o no se leyó. */
  cubierta: boolean | null
  aerolinea: string | null
  /** Se puede dar de alta: todo salvo una MAWB sin cobertura. */
  ofrecible: boolean
  /** Algo raro en el número, para revisarlo antes de gastar el crédito (29/10/2026). */
  advertencia?: string | null
}

/** El saldo de créditos de ShipsGo (`GET /api/v1/shipsgo/creditos`, `US-57`). */
export interface EstadoCreditos {
  nivel: 'SIN_PAQUETE' | 'OK' | 'POR_VENCER' | 'BAJO' | 'AGOTADO' | 'VENCIDO'
  mensaje: string
  paquete: {
    cantidad: number
    /** Lo que se sumó del paquete anterior. */
    saldo_arrastrado: number
    /** `AAAA-MM-DD`. */
    comprado_en: string
    vence_en: string | null
    registrado_en: string
    registrado_por: string
  } | null
  /** Lo comprado más lo arrastrado. */
  disponible: number
  consumidos: number
  saldo: number
  porcentaje_consumido: number | null
  dias_para_vencer: number | null
  /** Lo mínimo que hay que comprar para arrastrar el saldo (50 % del paquete). */
  recompra_minima: number | null
}

export interface AltasPendientes {
  pendientes: ReferenciaPendiente[]
  creditos_necesarios: number
  /** Altas que ya costaron crédito hoy, en hora de Costa Rica. */
  altas_hoy: number
  altas_maximas_dia: number
  /** El saldo, para advertir antes de gastar (`US-57`). */
  creditos: EstadoCreditos
}

export interface ResultadoAltaShipsGo {
  tipo: string
  numero: string
  registrado: boolean
  motivo: string
  consumio_credito: boolean
}

export interface AltasHechas {
  resultados: ResultadoAltaShipsGo[]
  /** Los que de verdad se gastaron: un embarque que ya existía sale gratis. */
  creditos_consumidos: number
}

/** `GET /api/v1/cargas/estado` (`US-23`): la carga semanal del Z-tracking. */
export interface EstadoCargas {
  /** Al día, toca cargar (antes del día límite), atrasada (después) o nunca cargada. */
  situacion: 'AL_DIA' | 'TOCA_CARGAR' | 'ATRASADA' | 'NUNCA'
  /** La última carga **aplicada**. */
  ultima: CargaResumen | null
  /** El lunes de la semana en curso, `AAAA-MM-DD`. */
  semana_desde: string
  /** Último día para cargar: 1 lunes … 7 domingo. */
  dia_limite: number
}

export interface IncidenciaCarga {
  /** `OC-posición`, o `hoja!fila` si la fila no tenía OC. */
  clave: string
  motivo: string
  detalle: string
  /** `entro_sin_dato`: entró, pero sin un dato con formato inválido (`US-59`). */
  consecuencia: 'no_entro' | 'entro_sin_rastreo' | 'entro_sin_dato'
}

/** La carga con su informe completo (`POST` y `GET /api/v1/cargas/{id}`). */
export interface CargaDetalle extends CargaResumen {
  por_motivo: Record<string, number>
  incidencias: IncidenciaCarga[]
  avisos: Array<{ clave: string; tipo: string; detalle: string }>
  /** `OC-posición` de los activos sin referencia que la carga cerró (04/11/2026). */
  cerrados_sin_referencia?: string[]
}
