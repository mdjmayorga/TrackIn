/** El texto de un marcador de los mapas del panel (`US-25`). */

import { CUMPLIMIENTOS, ETAPAS } from '@/components/estados'
import type { MarcadorMapa, SituacionBarco, SituacionVuelo } from '@/types/api'
import { haceCuanto } from '@/utils/fechas'

/** Las partes del rótulo, para mostrarlas en líneas en el mapa (28/10/2026). */
export interface PartesRotulo {
  /** «COSCO PRIDE (BL COSU…)». */
  quien: string
  /**
   * La etapa y el peor cumplimiento, juntos (03/11/2026): «En Tránsito · Retrasado»;
   * en el aéreo, más la situación del vuelo: «En Destino · A Tiempo · Vuelo LH518 concluido en SJO».
   */
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
    estado: [ETAPAS[m.etapa].texto, m.cumplimiento && CUMPLIMIENTOS[m.cumplimiento].texto, donde]
      .filter(Boolean)
      .join(' · '),
    pedidos: `${m.pedidos.length === 1 ? 'Pedido' : 'Pedidos'} ${lineas}`,
    lectura: hace ? `Lectura ${hace}${m.desactualizada ? ', desactualizada' : ''}` : 'Sin lectura',
  }
}

/** Lo que dice el marcador en una frase: para lectores de pantalla y la lista oculta. */
export function rotulo(m: MarcadorMapa): string {
  const p = partesDelRotulo(m)
  return `${p.quien}: ${p.estado}. ${p.pedidos}. ${p.lectura}.`
}

/**
 * Lo que agrega una posición **estimada**: la del avión, con el horario del vuelo
 * (`US-26`), o la de un barco sin lectura, con su itinerario (11/11/2026). ShipsGo
 * no da ninguna de las dos, y hay que decirlo.
 */
function dondeEsta(m: MarcadorMapa): string | null {
  if (!m.posicion_estimada) return null
  return textoSituacion(m.situacion, m.vuelo, m.lugar)
}

/**
 * «En vuelo LH518…», «En tierra en FRA, esperando vuelo», «Vuelo LH518 concluido en SJO»;
 * de un barco, «Navegando en MAERSK MONTE ALTO…» o «En el puerto PAMIT…».
 */
export function textoSituacion(
  situacion: SituacionVuelo | SituacionBarco | null,
  vueloEnCurso: string | null,
  lugar: string | null,
): string | null {
  const vuelo = vueloEnCurso ? ` ${vueloEnCurso}` : ''
  const en = lugar ? ` en ${lugar}` : ''
  switch (situacion) {
    case 'EN_VUELO':
      return `En vuelo${vuelo}, posición estimada según su horario`
    case 'EN_TIERRA':
      return `En tierra${en}, esperando vuelo`
    case 'FINALIZADO':
      return `Vuelo${vuelo} concluido${en}`
    case 'NAVEGANDO':
      return `Navegando${vueloEnCurso ? ` en ${vueloEnCurso}` : ''}, posición estimada según su itinerario`
    case 'EN_PUERTO':
      return `En el puerto${lugar ? ` ${lugar}` : ''}, según su itinerario`
    default:
      return null
  }
}
