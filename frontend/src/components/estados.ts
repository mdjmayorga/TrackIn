/**
 * Texto y color de cada estado del semáforo (RNF-08, wireframes §1.6).
 *
 * El color nunca va solo: cada distintivo lleva su texto, porque hay dos grises
 * y tres azules en la paleta y el daltonismo rojo-verde es frecuente.
 */

import type { Cumplimiento, EstadoCalculado, EtapaViaje, PedidoResumen } from '@/types/api'

export type EtapaVisible = EtapaViaje | 'CERRADO' | 'CANCELADO'

interface Apariencia {
  texto: string
  clases: string
}

export const ETAPAS: Record<EtapaVisible, Apariencia> = {
  SIN_TRACKING: { texto: 'Sin Tracking', clases: 'bg-estado-sin-tracking text-white' },
  EN_ORIGEN: { texto: 'En Origen', clases: 'bg-estado-origen text-white' },
  EN_TRANSITO: { texto: 'En Tránsito', clases: 'bg-estado-transito text-white' },
  EN_DESTINO: { texto: 'En Destino', clases: 'bg-estado-destino text-white' },
  EN_PROCESO_ADUANAL: { texto: 'P. Aduanal', clases: 'bg-estado-aduanal text-white' },
  // Sin color en el SRS ni en el Figma: provisional hasta validarlo en `US-24`.
  RECIBIDO_EN_PLANTA: { texto: 'Recibido', clases: 'bg-estado-recibido text-white' },
  // Validado el 01/09: blanco con letras negras, y contorno para no perderse.
  CERRADO: { texto: 'Cerrado', clases: 'bg-white text-black ring-1 ring-slate-400' },
  CANCELADO: { texto: 'Cancelado', clases: 'bg-estado-cancelado text-white ring-1 ring-slate-600' },
}

export const CUMPLIMIENTOS: Record<Cumplimiento, Apariencia> = {
  A_TIEMPO: { texto: 'A Tiempo', clases: 'bg-estado-a-tiempo text-white' },
  EN_RIESGO: { texto: 'En Riesgo', clases: 'bg-estado-riesgo text-white' },
  RETRASADO: { texto: 'Retrasado', clases: 'bg-estado-retrasado text-white' },
}

const TERMINALES: ReadonlySet<EstadoCalculado> = new Set(['CERRADO', 'CANCELADO'])

export function esTerminal(pedido: Pick<PedidoResumen, 'estado_calculado'>): boolean {
  return TERMINALES.has(pedido.estado_calculado)
}

/**
 * En una fila terminal la columna Etapa muestra el estado terminal, no la
 * etapa: `etapa_viaje` se congela en su último valor real y mostrarlo sería
 * engañoso (wireframes §1.11).
 */
export function etapaVisible(
  pedido: Pick<PedidoResumen, 'estado_calculado' | 'etapa_viaje'>,
): EtapaVisible {
  if (pedido.estado_calculado === 'CERRADO' || pedido.estado_calculado === 'CANCELADO') {
    return pedido.estado_calculado
  }
  return pedido.etapa_viaje
}
