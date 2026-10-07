/** Cliente HTTP compartido contra la API de TrackIn. */

import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

import { borrarSesion, sesionActual } from '@/auth/sesion'

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** Prefijo de la API versionada. `/health` vive fuera de él. */
export const API_V1 = '/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
  // FastAPI lee los filtros de lista repetidos (`?via=AEREO&via=MARITIMO`);
  // axios, por omisión, los mandaría como `via[]=...`, que no reconoce.
  paramsSerializer: { indexes: null },
})

/**
 * Normaliza los errores de axios a un mensaje mostrable.
 *
 * Sin esto, un backend caído produce `Network Error` a secas, que no dice
 * nada útil ni en la UI ni en los logs.
 */
export function mensajeDeError(error: unknown): string {
  if (error instanceof AxiosError) {
    if (error.response) {
      const detalle = (error.response.data as { detail?: unknown } | undefined)?.detail
      // FastAPI devuelve `detail` como texto en los errores propios y como
      // lista en los de validación (422).
      if (typeof detalle === 'string') return detalle
      return `El servidor respondió ${error.response.status}`
    }
    if (error.request) {
      return `No se pudo contactar la API en ${API_BASE_URL}. ¿Está corriendo el backend?`
    }
  }
  return error instanceof Error ? error.message : 'Error desconocido'
}

/** Pone el token de la sesión en cada petición (`US-42`). */
export function agregarToken(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  const sesion = sesionActual()
  if (sesion) {
    config.headers.set('Authorization', `Bearer ${sesion.token}`)
  }
  return config
}

/**
 * Un 401 fuera del login es una sesión vencida o cerrada en el servidor
 * —por inactividad, por desactivar al usuario o por reiniciar su contraseña—.
 * Se borra la sesión local y `AuthProvider` manda a la pantalla de login.
 *
 * El 401 del propio login **no** borra nada: son credenciales incorrectas, y
 * la pantalla muestra el mensaje genérico del backend.
 */
export function manejarError(error: unknown): Promise<never> {
  if (error instanceof AxiosError && error.response?.status === 401) {
    const esLogin = error.config?.url?.endsWith('/auth/login') ?? false
    if (!esLogin) borrarSesion()
  }
  console.error('[api]', mensajeDeError(error))
  return Promise.reject(error)
}

api.interceptors.request.use(agregarToken)
api.interceptors.response.use((response) => response, manejarError)
