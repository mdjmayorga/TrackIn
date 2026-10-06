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
  fuentes?: Array<Record<string, unknown>>
  /** Motivo del estado degradado, cuando aplica. */
  detail: string | null
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
