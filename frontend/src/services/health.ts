/** Llamadas al endpoint de salud del backend. */

import { api } from '@/services/api'
import type { HealthResponse } from '@/types/api'

export async function obtenerHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/health')
  return data
}
