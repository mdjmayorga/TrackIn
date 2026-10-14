/** Consulta de pedidos (`/api/v1/pedidos`, `US-16`, `US-22`, `US-28`). */

import { API_V1, api } from '@/services/api'
import type { IndicadoresKpi, Orden, PaginaPedidos, ProximosArribos } from '@/types/api'

export interface ConsultaPedidos {
  orden: Orden
  limite: number
  desplazamiento: number
}

export async function listarPedidos(consulta: ConsultaPedidos): Promise<PaginaPedidos> {
  const { data } = await api.get<PaginaPedidos>(`${API_V1}/pedidos`, { params: consulta })
  return data
}

export async function obtenerIndicadores(): Promise<IndicadoresKpi> {
  const { data } = await api.get<IndicadoresKpi>(`${API_V1}/pedidos/indicadores`)
  return data
}

export async function obtenerProximosArribos(): Promise<ProximosArribos> {
  const { data } = await api.get<ProximosArribos>(`${API_V1}/pedidos/proximos-arribos`)
  return data
}
