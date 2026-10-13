/** Números y destinos como los muestra el panel. */

import type { PedidoResumen } from '@/types/api'

const unDecimal = new Intl.NumberFormat('es-CR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

/**
 * «62.03» de la API → «62,0%». Un decimal y no los dos del Figma, para que los
 * recuadros de la cinta quepan (pedido del 13/10). La API conserva los dos.
 */
export function formatearPorcentaje(valor: string | null): string | null {
  if (valor === null) return null
  return `${unDecimal.format(Number(valor))}%`
}

/** «14.2» de la API → «14,2 d». */
export function formatearDias(valor: string | null): string | null {
  if (valor === null) return null
  return `${unDecimal.format(Number(valor))} d`
}

/**
 * El destino como en el Figma: el aeropuerto por su código («MROC»), el puerto
 * por su nombre («Puerto Limón»).
 */
export function destinoCorto(pedido: Pick<PedidoResumen, 'destino' | 'via_transporte'>): string {
  return pedido.via_transporte === 'AEREO' ? pedido.destino.codigo : pedido.destino.nombre
}
