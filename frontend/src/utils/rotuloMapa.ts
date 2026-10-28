/** El texto de un marcador de los mapas del panel (`US-25`). */

import { aparienciaDeEstado } from '@/components/estados'
import type { MarcadorMapa } from '@/types/api'
import { haceCuanto } from '@/utils/fechas'

/** Las partes del rótulo, para mostrarlas en líneas en el mapa (28/10/2026). */
export interface PartesRotulo {
  /** «COSCO PRIDE (BL COSU…)». */
  quien: string
  /** «En Riesgo», y en el aéreo la situación del vuelo: «En Destino · Vuelo LH518 concluido en SJO». */
  estado: string
  /** «Pedidos 4500123456-10, 4500123456-20». */
  pedidos: string
  /** «Lectura hace 2 h», «… , desactualizada» o «Sin lectura». */
  lectura: string
}

export function partesDelRotulo(m: MarcadorMapa): PartesRotulo {
  const lineas = m.pedidos.map((p) => `${p.oc_numero}-${p.posicion_oc}`).join(', ')
  const hace = haceCuanto(m.ultima_lectura)
  const donde = dondeEsta(m)
  return {
    quien: m.nombre ? `${m.nombre} (${m.tipo} ${m.referencia})` : `${m.tipo} ${m.referencia}`,
    estado: `${aparienciaDeEstado(m.estado).texto}${donde ? ` · ${donde}` : ''}`,
    pedidos: `${m.pedidos.length === 1 ? 'Pedido' : 'Pedidos'} ${lineas}`,
    lectura: hace ? `Lectura ${hace}${m.desactualizada ? ', desactualizada' : ''}` : 'Sin lectura',
  }
}

/** Lo que dice el marcador en una frase: para lectores de pantalla y la lista oculta. */
export function rotulo(m: MarcadorMapa): string {
  const donde = dondeEsta(m)
  const p = partesDelRotulo(m)
  return `${p.quien}: ${aparienciaDeEstado(m.estado).texto}.${donde ? ` ${donde}.` : ''} ${p.pedidos}. ${p.lectura}.`
}

/**
 * Lo que agrega la vía aérea (`US-26`): la posición es **estimada** con el
 * horario del vuelo —ShipsGo no da la del avión— y hay que decirlo.
 */
function dondeEsta(m: MarcadorMapa): string | null {
  if (!m.posicion_estimada) return null
  const vuelo = m.vuelo ? ` ${m.vuelo}` : ''
  switch (m.situacion) {
    case 'EN_VUELO':
      return `En vuelo${vuelo}, posición estimada según su horario`
    case 'EN_TIERRA':
      return `En tierra${m.lugar ? ` en ${m.lugar}` : ''}, esperando vuelo`
    case 'FINALIZADO':
      return `Vuelo${vuelo} concluido${m.lugar ? ` en ${m.lugar}` : ''}`
    default:
      return null
  }
}
