/**
 * Texto y color de cada estado del semáforo (RNF-08, wireframes §1.6, `US-24`).
 *
 * El color nunca va solo: cada distintivo lleva su texto, porque hay dos grises
 * y tres azules en la paleta y el daltonismo rojo-verde es frecuente.
 *
 * **La letra se elige por contraste, no por gusto** (decisión del 20/10). Con
 * letra blanca, cinco tonos del Figma quedaban por debajo de 4,5:1 (WCAG AA),
 * ilegibles a la distancia de la pantalla de planta: Sin Tracking, En Origen,
 * P. Aduanal, A Tiempo y En Riesgo. Llevan letra negra y conservan el tono
 * aprobado. Las pruebas de `estados.test.ts` verifican el contraste de todos.
 *
 * `fondo` y `letra` son los mismos colores en hexadecimal, para lo que no usa
 * clases: los marcadores de Leaflet. Salen de `paleta.ts`, igual que las
 * clases `bg-estado-*`, así que la grilla y el mapa no pueden discrepar.
 */

import { BLANCO, NEGRO, PALETA_ESTADOS as P } from '@/components/paleta'
import type { Cumplimiento, EstadoCalculado, EtapaViaje, PedidoResumen } from '@/types/api'

export type EtapaVisible = EtapaViaje | 'CERRADO' | 'CANCELADO'

export interface Apariencia {
  texto: string
  /** Literales completos: Tailwind solo genera las clases que encuentra escritas. */
  clases: string
  fondo: string
  letra: string
}

export const ETAPAS: Record<EtapaVisible, Apariencia> = {
  SIN_TRACKING: {
    texto: 'Sin Tracking',
    clases: 'bg-estado-sin-tracking text-black',
    fondo: P['sin-tracking'],
    letra: NEGRO,
  },
  EN_ORIGEN: {
    texto: 'En Origen',
    clases: 'bg-estado-origen text-black',
    fondo: P.origen,
    letra: NEGRO,
  },
  EN_TRANSITO: {
    texto: 'En Tránsito',
    clases: 'bg-estado-transito text-white',
    fondo: P.transito,
    letra: BLANCO,
  },
  EN_DESTINO: {
    texto: 'En Destino',
    clases: 'bg-estado-destino text-white',
    fondo: P.destino,
    letra: BLANCO,
  },
  EN_PROCESO_ADUANAL: {
    texto: 'P. Aduanal',
    clases: 'bg-estado-aduanal text-black',
    fondo: P.aduanal,
    letra: NEGRO,
  },
  // Sin color en el SRS ni en el Figma: el café quedó definitivo el 14/10.
  RECIBIDO_EN_PLANTA: {
    texto: 'Recibido',
    clases: 'bg-estado-recibido text-white',
    fondo: P.recibido,
    letra: BLANCO,
  },
  // Validado el 01/09: blanco con letras negras, y contorno para no perderse.
  CERRADO: {
    texto: 'Cerrado',
    clases: 'bg-white text-black ring-1 ring-slate-400',
    fondo: BLANCO,
    letra: NEGRO,
  },
  CANCELADO: {
    texto: 'Cancelado',
    clases: 'bg-estado-cancelado text-white ring-1 ring-slate-600',
    fondo: P.cancelado,
    letra: BLANCO,
  },
}

export const CUMPLIMIENTOS: Record<Cumplimiento, Apariencia> = {
  A_TIEMPO: {
    texto: 'A Tiempo',
    clases: 'bg-estado-a-tiempo text-black',
    fondo: P['a-tiempo'],
    letra: NEGRO,
  },
  EN_RIESGO: {
    texto: 'En Riesgo',
    clases: 'bg-estado-riesgo text-black',
    fondo: P.riesgo,
    letra: NEGRO,
  },
  RETRASADO: {
    texto: 'Retrasado',
    clases: 'bg-estado-retrasado text-white',
    fondo: P.retrasado,
    letra: BLANCO,
  },
}

/**
 * El color de `estado_calculado`, el que pinta el semáforo (RF-11): una etapa,
 * un cumplimiento o un terminal. Es el que usarán los marcadores de los mapas
 * (`US-25`, `US-26`), con la misma apariencia que la grilla.
 */
export function aparienciaDeEstado(estado: EstadoCalculado): Apariencia {
  return estado in CUMPLIMIENTOS
    ? CUMPLIMIENTOS[estado as Cumplimiento]
    : ETAPAS[estado as EtapaVisible]
}

/**
 * De más a menos urgente, el mismo orden de `consulta_pedidos._URGENCIA` en el
 * backend: primero el cumplimiento, después la etapa más avanzada. Colorea los
 * grupos de marcadores del mapa (`US-25`).
 */
const URGENCIA: readonly EstadoCalculado[] = [
  'RETRASADO',
  'EN_RIESGO',
  'A_TIEMPO',
  'EN_PROCESO_ADUANAL',
  'EN_DESTINO',
  'EN_TRANSITO',
  'EN_ORIGEN',
  'SIN_TRACKING',
  'RECIBIDO_EN_PLANTA',
  'CERRADO',
  'CANCELADO',
]

export function estadoMasUrgente(estados: readonly EstadoCalculado[]): EstadoCalculado {
  return [...estados].sort((a, b) => URGENCIA.indexOf(a) - URGENCIA.indexOf(b))[0]
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
