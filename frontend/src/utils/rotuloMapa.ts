/** El texto de un marcador de los mapas del panel (`US-25`). */

import { aparienciaDeEstado } from '@/components/estados'
import type { MarcadorMapa } from '@/types/api'
import { haceCuanto } from '@/utils/fechas'

/** Lo que dice el marcador: qué es, en qué estado, qué lleva y de cuándo es el dato. */
export function rotulo(m: MarcadorMapa): string {
  const quien = m.nombre ? `${m.nombre} (${m.tipo} ${m.referencia})` : `${m.tipo} ${m.referencia}`
  const lineas = m.pedidos.map((p) => `${p.oc_numero}-${p.posicion_oc}`).join(', ')
  const lectura = haceCuanto(m.ultima_lectura)
  const antiguedad = lectura
    ? `lectura ${lectura}${m.desactualizada ? ', desactualizada' : ''}`
    : 'sin lectura'
  return `${quien}: ${aparienciaDeEstado(m.estado).texto}. ${m.pedidos.length === 1 ? 'Pedido' : 'Pedidos'} ${lineas}. ${antiguedad[0].toUpperCase()}${antiguedad.slice(1)}.`
}
