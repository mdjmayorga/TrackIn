/** El texto de un marcador de los mapas del panel (`US-25`). */

import { aparienciaDeEstado } from '@/components/estados'
import type { MarcadorMapa } from '@/types/api'
import { haceCuanto } from '@/utils/fechas'

/** Lo que dice el marcador: qué es, en qué estado, qué lleva y de cuándo es el dato. */
export function rotulo(m: MarcadorMapa): string {
  const quien = m.nombre ? `${m.nombre} (${m.tipo} ${m.referencia})` : `${m.tipo} ${m.referencia}`
  const lineas = m.pedidos.map((p) => `${p.oc_numero}-${p.posicion_oc}`).join(', ')
  const lectura = haceCuanto(m.ultima_lectura)
  const donde = dondeEsta(m)
  const antiguedad = lectura
    ? `lectura ${lectura}${m.desactualizada ? ', desactualizada' : ''}`
    : 'sin lectura'
  return `${quien}: ${aparienciaDeEstado(m.estado).texto}.${donde ? ` ${donde}.` : ''} ${m.pedidos.length === 1 ? 'Pedido' : 'Pedidos'} ${lineas}. ${antiguedad[0].toUpperCase()}${antiguedad.slice(1)}.`
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
