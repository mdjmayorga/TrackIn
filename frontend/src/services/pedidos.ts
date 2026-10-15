/** Consulta de pedidos (`/api/v1/pedidos`, `US-16`, `US-21`, `US-22`, `US-28`). */

import { API_V1, api } from '@/services/api'
import type {
  AsientoBitacora,
  IndicadoresKpi,
  Orden,
  PaginaPedidos,
  PedidoDetalle,
  ProximosArribos,
  TipoReferencia,
} from '@/types/api'
import { FILTROS_VACIOS, type FiltrosPanel, aParametros } from '@/utils/filtros'

export interface ConsultaPedidos {
  orden: Orden
  limite: number
  desplazamiento: number
}

export async function listarPedidos(
  consulta: ConsultaPedidos,
  filtros: FiltrosPanel = FILTROS_VACIOS,
): Promise<PaginaPedidos> {
  const { data } = await api.get<PaginaPedidos>(`${API_V1}/pedidos`, {
    params: { ...aParametros(filtros), ...consulta },
  })
  return data
}

export async function obtenerPedido(id: number): Promise<PedidoDetalle> {
  const { data } = await api.get<PedidoDetalle>(`${API_V1}/pedidos/${id}`)
  return data
}

export async function obtenerBitacora(id: number): Promise<AsientoBitacora[]> {
  const { data } = await api.get<AsientoBitacora[]>(`${API_V1}/pedidos/${id}/bitacora`)
  return data
}

export interface NuevaReferencia {
  tipo: TipoReferencia
  numero: string
  motivo: string
}

/** Asocia el identificador de rastreo (`US-20`); devuelve el detalle ya recalculado. */
export async function asociarReferencia(
  id: number,
  referencia: NuevaReferencia,
): Promise<PedidoDetalle> {
  const { data } = await api.post<PedidoDetalle>(`${API_V1}/pedidos/${id}/referencia`, referencia)
  return data
}

export async function obtenerIndicadores(
  filtros: FiltrosPanel = FILTROS_VACIOS,
): Promise<IndicadoresKpi> {
  const { data } = await api.get<IndicadoresKpi>(`${API_V1}/pedidos/indicadores`, {
    params: aParametros(filtros),
  })
  return data
}

export async function obtenerProximosArribos(
  filtros: FiltrosPanel = FILTROS_VACIOS,
): Promise<ProximosArribos> {
  const { data } = await api.get<ProximosArribos>(`${API_V1}/pedidos/proximos-arribos`, {
    params: aParametros(filtros),
  })
  return data
}
