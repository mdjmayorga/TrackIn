/** Cliente HTTP compartido contra la API de TrackIn. */

import axios, { AxiosError } from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
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
      const detalle = (error.response.data as { detail?: string } | undefined)?.detail
      return detalle ?? `El servidor respondió ${error.response.status}`
    }
    if (error.request) {
      return `No se pudo contactar la API en ${API_BASE_URL}. ¿Está corriendo el backend?`
    }
  }
  return error instanceof Error ? error.message : 'Error desconocido'
}

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    console.error('[api]', mensajeDeError(error))
    return Promise.reject(error)
  },
)
