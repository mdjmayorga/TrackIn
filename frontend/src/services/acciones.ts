/**
 * Las intervenciones sobre un pedido (`US-60`). Cada una devuelve el detalle
 * ya recalculado, y dos responden 409 con datos para decidir:
 *
 * - el desembarco, si ya había una llegada confirmada (`ConflictoDesembarco`);
 * - la recepción, si lo recibido no llega al mínimo de RN-10 (`RecepcionCorta`).
 */

import { AxiosError } from 'axios'

import { API_V1, api } from '@/services/api'
import type { PedidoDetalle } from '@/types/api'

export interface ConMotivo {
  motivo: string
}

export interface Desembarco extends ConMotivo {
  /** Con zona horaria: `2026-10-15T08:15:00-06:00`. */
  ata: string
  confirmar?: boolean
}

export interface Cantidad extends ConMotivo {
  fecha: string
  cantidad: string
}

export interface Ajuste extends ConMotivo {
  dias: number
}

async function intervenir(id: number, accion: string, datos: object): Promise<PedidoDetalle> {
  const { data } = await api.post<PedidoDetalle>(`${API_V1}/pedidos/${id}/${accion}`, datos)
  return data
}

export const confirmarDesembarco = (id: number, d: Desembarco) => intervenir(id, 'desembarco', d)
/** El motivo es opcional (27/10/2026): `null` si no se escribió. */
export const pasarAAduana = (id: number, d: { motivo: string | null }) =>
  intervenir(id, 'paso-aduanal', d)
export const registrarRecepcion = (id: number, d: Cantidad) => intervenir(id, 'recepcion', d)
export const cerrarForzado = (id: number, d: Cantidad) => intervenir(id, 'cierre-forzado', d)
export const liberarCalidad = (id: number, d: Cantidad) => intervenir(id, 'liberacion-calidad', d)
export const ajustarDias = (id: number, d: Ajuste) => intervenir(id, 'ajuste-manual', d)

/** El 409 del desembarco: ya había una llegada confirmada. */
export interface ConflictoDesembarco {
  detail: string
  ata_confirmada_actual: string
  requiere_confirmacion: true
}

/** El 409 de la recepción: no llega al mínimo conforme de RN-10. */
export interface RecepcionCorta {
  detail: string
  cantidad_pedida: string
  cantidad_recibida: string
  minimo_conforme: string
  ofrece_cierre_forzado: true
}

function conflicto(error: unknown): Record<string, unknown> | null {
  if (error instanceof AxiosError && error.response?.status === 409) {
    const datos = error.response.data
    return typeof datos === 'object' && datos !== null ? (datos as Record<string, unknown>) : null
  }
  return null
}

export function comoConflictoDesembarco(error: unknown): ConflictoDesembarco | null {
  const datos = conflicto(error)
  return datos?.requiere_confirmacion ? (datos as unknown as ConflictoDesembarco) : null
}

export function comoRecepcionCorta(error: unknown): RecepcionCorta | null {
  const datos = conflicto(error)
  return datos?.ofrece_cierre_forzado ? (datos as unknown as RecepcionCorta) : null
}
