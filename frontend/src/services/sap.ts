/** La escucha de la API de SAP (`/api/v1/integraciones/sap/escucha`, `US-66`). */

import { API_V1, api } from '@/services/api'
import type { EstadoEscuchaSap } from '@/types/api'

export async function obtenerEscuchaSap(): Promise<EstadoEscuchaSap> {
  const { data } = await api.get<EstadoEscuchaSap>(`${API_V1}/integraciones/sap/escucha`)
  return data
}

/** Solo el Administrador: el backend responde 403 a cualquier otro rol. */
export async function cambiarEscuchaSap(habilitada: boolean): Promise<EstadoEscuchaSap> {
  const { data } = await api.put<EstadoEscuchaSap>(`${API_V1}/integraciones/sap/escucha`, {
    habilitada,
  })
  return data
}
