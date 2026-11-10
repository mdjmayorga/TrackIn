import { describe, expect, it } from 'vitest'

import { ATRIBUCION_OSM, MOSAICOS_OSM, mosaicos } from '@/utils/mosaicos'

describe('fondo de los mapas (PROD-05)', () => {
  it('por omisión usa OpenStreetMap sin el subdominio {s}', () => {
    const fondo = mosaicos(undefined, undefined)

    expect(fondo.url).toBe('https://tile.openstreetmap.org/{z}/{x}/{y}.png')
    expect(fondo.url).not.toContain('{s}')
    expect(fondo.atribucion).toContain('OpenStreetMap')
  })

  it('una variable vacía, como la pasa docker-compose, no deja el mapa sin fondo', () => {
    expect(mosaicos('', '  ')).toEqual({ url: MOSAICOS_OSM, atribucion: ATRIBUCION_OSM })
  })

  it('el plan B es cambiar las variables, sin tocar el código', () => {
    const url = 'https://tiles.stadiamaps.com/tiles/osm_bright/{z}/{x}/{y}{r}.png?api_key=k'
    const atribucion = '&copy; Stadia Maps &copy; OpenMapTiles &copy; OpenStreetMap'

    expect(mosaicos(url, atribucion)).toEqual({ url, atribucion })
  })

  it('si solo cambia la URL, conserva la atribución de OpenStreetMap', () => {
    expect(mosaicos('https://otro.example/{z}/{x}/{y}.png', '').atribucion).toBe(ATRIBUCION_OSM)
  })
})
