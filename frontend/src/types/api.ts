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
export type Rol = 'COMPRAS' | 'LOGISTICA' | 'PLANIFICACION' | 'ADMINISTRADOR'

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

/** Respuesta de `POST /api/v1/auth/login`. */
export interface SesionIniciada {
  token: string
  tipo: 'bearer'
  recordada: boolean
  usuario: UsuarioPublico
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
