/** Subida del Excel del Z-tracking y su historial (`/api/v1/cargas`, `US-58`). */

import { API_V1, api } from '@/services/api'
import type { CargaDetalle, CargaResumen, EstadoCargas } from '@/types/api'

/**
 * El WK38 real tarda ~2 s, pero con ShipsGo completando destinos puede tardar
 * bastante más: un minuto de margen antes de dar la carga por perdida.
 */
const ESPERA_CARGA_MS = 60_000

export async function subirZtracking(archivo: File): Promise<CargaDetalle> {
  const formulario = new FormData()
  formulario.append('archivo', archivo)
  const { data } = await api.post<CargaDetalle>(`${API_V1}/cargas`, formulario, {
    // Sin esto axios mandaría el `application/json` por omisión del cliente.
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: ESPERA_CARGA_MS,
  })
  return data
}

/**
 * Descarga la plantilla vacía del Z-tracking (`US-59`). Va por `api` y no por
 * un enlace porque la sesión viaja en la cabecera, que un enlace no manda.
 */
export async function descargarPlantilla(): Promise<void> {
  const { data } = await api.get<Blob>(`${API_V1}/cargas/plantilla`, { responseType: 'blob' })
  const url = URL.createObjectURL(data)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = 'Plantilla Z-tracking.xlsx'
  enlace.click()
  URL.revokeObjectURL(url)
}

export async function listarCargas(): Promise<CargaResumen[]> {
  const { data } = await api.get<CargaResumen[]>(`${API_V1}/cargas`)
  return data
}

/** Si el Z-tracking de esta semana ya se cargó (`US-23`). */
export async function obtenerEstadoCargas(): Promise<EstadoCargas> {
  const { data } = await api.get<EstadoCargas>(`${API_V1}/cargas/estado`)
  return data
}

export async function obtenerCarga(id: number): Promise<CargaDetalle> {
  const { data } = await api.get<CargaDetalle>(`${API_V1}/cargas/${id}`)
  return data
}
