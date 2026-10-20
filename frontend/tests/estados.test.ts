/**
 * El semáforo es uno solo en toda la interfaz (`US-24`, RNF-08): cada estado
 * tiene un color, su letra se lee y las clases dicen lo mismo que el
 * hexadecimal que usarán los mapas.
 */

import { describe, expect, it } from 'vitest'

import { type Apariencia, CUMPLIMIENTOS, ETAPAS, aparienciaDeEstado } from '@/components/estados'
import { BLANCO, NEGRO, PALETA_ESTADOS } from '@/components/paleta'
import type { EstadoCalculado } from '@/types/api'

/** Contraste WCAG 2.1 entre dos colores `#rrggbb`. */
function contraste(a: string, b: string): number {
  const luminancia = (hex: string) => {
    const n = parseInt(hex.slice(1), 16)
    const canal = (c: number) => {
      const s = c / 255
      return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
    }
    return 0.2126 * canal(n >> 16) + 0.7152 * canal((n >> 8) & 255) + 0.0722 * canal(n & 255)
  }
  const [claro, oscuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x)
  return (claro + 0.05) / (oscuro + 0.05)
}

const TODOS: [string, Apariencia][] = [...Object.entries(ETAPAS), ...Object.entries(CUMPLIMIENTOS)]

/** Los estados que puede tener `estado_calculado` (RF-11). */
const ESTADOS: EstadoCalculado[] = [
  'SIN_TRACKING',
  'EN_ORIGEN',
  'EN_TRANSITO',
  'EN_DESTINO',
  'EN_PROCESO_ADUANAL',
  'RECIBIDO_EN_PLANTA',
  'A_TIEMPO',
  'EN_RIESGO',
  'RETRASADO',
  'CERRADO',
  'CANCELADO',
]

describe('semáforo (US-24)', () => {
  it.each(TODOS)('%s: la letra se lee sobre su fondo (WCAG AA, 4,5:1)', (_, apariencia) => {
    expect(contraste(apariencia.fondo, apariencia.letra)).toBeGreaterThanOrEqual(4.5)
  })

  it.each(TODOS)('%s: las clases dicen el mismo color que el hexadecimal', (_, apariencia) => {
    const fondo = /\bbg-(estado-[\w-]+|white)\b/.exec(apariencia.clases)?.[1]
    const esperado =
      fondo === 'white'
        ? BLANCO
        : PALETA_ESTADOS[fondo?.replace('estado-', '') as keyof typeof PALETA_ESTADOS]
    expect(apariencia.fondo).toBe(esperado)
    expect(apariencia.clases).toContain(apariencia.letra === NEGRO ? 'text-black' : 'text-white')
  })

  it('cada estado de la paleta pinta uno solo: dos estados nunca comparten color', () => {
    const fondos = TODOS.map(([, a]) => a.fondo)
    expect(new Set(fondos).size).toBe(fondos.length)
  })

  it('todo estado calculado tiene apariencia, la de la grilla', () => {
    for (const estado of ESTADOS) {
      const apariencia = aparienciaDeEstado(estado)
      expect(apariencia, estado).toBeDefined()
      expect(TODOS.map(([, a]) => a)).toContain(apariencia)
    }
    expect(aparienciaDeEstado('RETRASADO')).toBe(CUMPLIMIENTOS.RETRASADO)
    expect(aparienciaDeEstado('EN_DESTINO')).toBe(ETAPAS.EN_DESTINO)
    expect(aparienciaDeEstado('CERRADO')).toBe(ETAPAS.CERRADO)
  })
})
