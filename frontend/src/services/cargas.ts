/** Subida del Excel del Z-tracking y su historial (`/api/v1/cargas`, `US-58`). */

import { API_V1, api } from '@/services/api'
import type { CargaDetalle, CargaResumen } from '@/types/api'

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

export async function listarCargas(): Promise<CargaResumen[]> {
  const { data } = await api.get<CargaResumen[]>(`${API_V1}/cargas`)
  return data
}

export async function obtenerCarga(id: number): Promise<CargaDetalle> {
  const { data } = await api.get<CargaDetalle>(`${API_V1}/cargas/${id}`)
  return data
}
