import { describe, expect, it } from 'vitest'

import { urlMapaShipsGo } from '@/utils/mapaShipsGo'
import type { Rastreo } from '@/types/api'

function rastreo(cambios: Partial<Rastreo> = {}): Rastreo {
  return {
    tipo: 'BL',
    referencia: 'COSU6508789000',
    via_transporte: 'MARITIMO',
    nombre: null,
    imo: null,
    eta_fuente: null,
    ata_fuente: null,
    posicion: null,
    velocidad_nudos: null,
    ultima_consulta_exitosa: '2026-10-21T12:00:00Z',
    guia_madre: null,
    manifiesto_aduana: null,
    activo: true,
    transbordos: [],
    ...cambios,
  }
}

describe('dirección del mapa en vivo de ShipsGo', () => {
  it('un BL marítimo va a la pestaña ocean, sin las pestañas de la cuenta', () => {
    const url = new URL(urlMapaShipsGo(rastreo(), 'MARITIMO', 'tok')!)

    expect(url.origin).toBe('https://embed.shipsgo.com')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      token: 'tok',
      tabs: 'none',
      transport: 'ocean',
      query: 'COSU6508789000',
    })
  })

  it('una MAWB va a la pestaña air', () => {
    const url = new URL(
      urlMapaShipsGo(rastreo({ tipo: 'MAWB', referencia: '020-25244995' }), 'AEREO', 'tok')!,
    )

    expect(url.searchParams.get('transport')).toBe('air')
    expect(url.searchParams.get('query')).toBe('020-25244995')
  })

  it.each([
    ['sin token configurado', rastreo(), ''],
    ['sin rastreo', null, 'tok'],
    ['una HAWB: la sigue TICA, que no tiene mapa', rastreo({ tipo: 'HAWB' }), 'tok'],
    ['nunca respondió: no está dado de alta', rastreo({ ultima_consulta_exitosa: null }), 'tok'],
  ])('no aplica %s', (_, r, token) => {
    expect(urlMapaShipsGo(r, 'MARITIMO', token)).toBeNull()
  })
})
