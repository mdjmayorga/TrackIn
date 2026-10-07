/** Consulta de pedidos (`GET /api/v1/pedidos`, `US-16`). */

import { API_V1, api } from '@/services/api'
import type { Orden, PaginaPedidos } from '@/types/api'

export interface ConsultaPedidos {
  orden: Orden
  limite: number
  desplazamiento: number
}

export async function listarPedidos(consulta: ConsultaPedidos): Promise<PaginaPedidos> {
  const { data } = await api.get<PaginaPedidos>(`${API_V1}/pedidos`, { params: consulta })
  return data
}
