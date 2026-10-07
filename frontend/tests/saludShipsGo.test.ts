import { describe, expect, it } from 'vitest'

import { ANTIGUEDAD_MAXIMA_S, estadoShipsGo } from '@/utils/saludShipsGo'
import type { HealthResponse, SaludFuente } from '@/types/api'

function salud(fuentes: SaludFuente[]): HealthResponse {
  return {
    status: 'ok',
    version: '0.1.0',
    environment: 'test',
    database: 'up',
    postgis: '3.6',
    fuentes,
    detail: null,
  }
}

function shipsgo(cambios: Partial<SaludFuente> = {}): SaludFuente {
  return {
    fuente: 'shipsgo',
    degradada: false,
    fallos_consecutivos: 0,
    clase_ultimo_fallo: 'ninguno',
    motivo_ultimo_fallo: null,
    ultimo_contacto_ok: '2026-10-07T14:00:00Z',
    antiguedad_s: 60,
    reportado_en: '2026-10-07T14:00:00Z',
    ...cambios,
  }
}

describe('estado de ShipsGo', () => {
  it('en línea: sin fallas y con contacto reciente', () => {
    expect(estadoShipsGo(salud([shipsgo()]), false)).toMatchObject({
      nivel: 'ok',
      texto: 'ShipsGo API Online',
    })
  })

  it('sin fallas pero con la última lectura vieja no es «Online»: el worker puede estar detenido', () => {
    const vieja = shipsgo({ antiguedad_s: ANTIGUEDAD_MAXIMA_S + 1 })

    expect(estadoShipsGo(salud([vieja]), false)).toMatchObject({
      nivel: 'aviso',
      texto: 'ShipsGo sin lectura reciente',
    })
    expect(estadoShipsGo(salud([shipsgo({ antiguedad_s: null })]), false).nivel).toBe('aviso')
  })

  it('degradada: muestra el motivo', () => {
    const caida = shipsgo({ degradada: true, motivo_ultimo_fallo: 'HTTP 503' })

    expect(estadoShipsGo(salud([caida]), false)).toEqual({
      nivel: 'falla',
      texto: 'ShipsGo con fallas',
      detalle: 'HTTP 503',
    })
  })

  it('degradada sin motivo: cuenta los fallos', () => {
    const caida = shipsgo({ degradada: true, fallos_consecutivos: 4 })

    expect(estadoShipsGo(salud([caida]), false).detalle).toBe('4 fallos seguidos.')
  })

  it('si el worker nunca reportó ShipsGo, lo dice', () => {
    const otra = shipsgo({ fuente: 'tica' })

    expect(estadoShipsGo(salud([otra]), false).texto).toBe('ShipsGo sin datos')
    expect(estadoShipsGo(undefined, false).texto).toBe('ShipsGo sin datos')
  })

  it('sin backend no se sabe nada de ShipsGo', () => {
    expect(estadoShipsGo(undefined, true)).toMatchObject({
      nivel: 'falla',
      texto: 'Sin conexión con TrackIn',
    })
  })
})
