import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { estadoMasUrgente } from '@/components/estados'
import { MapaEmbarques } from '@/components/MapaEmbarques'
import { obtenerMapa } from '@/services/pedidos'
import type { MapaPedidos, MarcadorMapa } from '@/types/api'
import { agrupar } from '@/utils/agrupamiento'
import { FILTROS_VACIOS } from '@/utils/filtros'
import { rotulo } from '@/utils/rotuloMapa'

vi.mock('@/services/pedidos', () => ({ obtenerMapa: vi.fn() }))

const AHORA = new Date()
const haceHoras = (h: number) => new Date(AHORA.getTime() - h * 3_600_000).toISOString()

function marcador(cambios: Partial<MarcadorMapa> = {}): MarcadorMapa {
  return {
    id_elemento: 1,
    tipo: 'BL',
    referencia: 'COSU6508789000',
    nombre: 'COSCO PRIDE',
    latitud: 9.3,
    longitud: -79.5,
    estado: 'EN_RIESGO',
    ultima_lectura: haceHoras(2),
    desactualizada: false,
    activo: true,
    pedidos: [
      { id: 1, oc_numero: '4500123456', posicion_oc: 10, estado_calculado: 'EN_RIESGO' },
      { id: 2, oc_numero: '4500123456', posicion_oc: 20, estado_calculado: 'A_TIEMPO' },
    ],
    posicion_estimada: false,
    situacion: null,
    vuelo: null,
    lugar: null,
    ruta: null,
    ...cambios,
  }
}

function mapa(cambios: Partial<MapaPedidos> = {}): MapaPedidos {
  return {
    via: 'MARITIMO',
    umbral_desactualizada_h: 12,
    marcadores: [marcador()],
    sin_posicion: 3,
    ...cambios,
  }
}

function montar(filtros = FILTROS_VACIOS) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MapaEmbarques
        titulo="Mapa Marítimo"
        capa="MARITIMO"
        centro={[16, -77]}
        zoom={4}
        filtros={filtros}
      />
    </QueryClientProvider>,
  )
}

const lista = () => screen.findByRole('list', { name: 'Embarques en el Mapa Marítimo' })

afterEach(() => {
  vi.mocked(obtenerMapa).mockReset()
})

describe('MapaEmbarques (US-25)', () => {
  it('pide los embarques de su vía con los filtros del panel', async () => {
    vi.mocked(obtenerMapa).mockResolvedValue(mapa())
    const filtros = { ...FILTROS_VACIOS, oc: '4500' }
    montar(filtros)

    await lista()
    expect(obtenerMapa).toHaveBeenCalledWith('MARITIMO', filtros)
  })

  it('cuenta embarques, pedidos y los que no tienen posición', async () => {
    vi.mocked(obtenerMapa).mockResolvedValue(mapa())
    montar()

    expect(await screen.findByText('1 embarque · 2 pedidos · 3 sin posición')).toBeInTheDocument()
  })

  it('repite cada marcador en una lista para lectores de pantalla', async () => {
    vi.mocked(obtenerMapa).mockResolvedValue(mapa())
    montar()

    const items = await within(await lista()).findAllByRole('listitem')
    expect(items).toHaveLength(1)
    expect(items[0]).toHaveTextContent(
      'COSCO PRIDE (BL COSU6508789000): En Riesgo. Pedidos 4500123456-10, 4500123456-20. Lectura hace 2 h.',
    )
  })

  it('una lectura vieja se distingue y explica el umbral', async () => {
    vi.mocked(obtenerMapa).mockResolvedValue(
      mapa({ marcadores: [marcador({ ultima_lectura: haceHoras(30), desactualizada: true })] }),
    )
    montar()

    expect(await within(await lista()).findByRole('listitem')).toHaveTextContent(
      'Lectura hace 1 día, desactualizada.',
    )
    expect(screen.getByText(/borde punteado: sin lectura en más de 12 h/)).toBeInTheDocument()
  })

  it('dos embarques en el mismo puerto se agrupan en un marcador con el número', async () => {
    vi.mocked(obtenerMapa).mockResolvedValue(
      mapa({
        marcadores: [
          marcador(),
          marcador({ id_elemento: 2, referencia: 'MEDU1234567', latitud: 9.31, longitud: -79.51 }),
        ],
      }),
    )
    montar()

    expect(await screen.findByTitle('2 embarques: acercar')).toHaveTextContent('2')
  })

  it('sin embarques con posición lo dice', async () => {
    vi.mocked(obtenerMapa).mockResolvedValue(mapa({ marcadores: [], sin_posicion: 0 }))
    montar()

    expect(await screen.findByText('Ningún embarque con posición')).toBeInTheDocument()
  })
})

describe('agrupar', () => {
  it('junta los puntos cercanos en pantalla y deja aparte los lejanos', () => {
    const grupos = agrupar([
      { x: 0, y: 0, dato: 'a' },
      { x: 10, y: 0, dato: 'b' },
      { x: 100, y: 100, dato: 'c' },
    ])

    expect(grupos.map((g) => g.datos)).toEqual([['a', 'b'], ['c']])
    expect(grupos[0]).toMatchObject({ x: 5, y: 0 })
  })

  it('al acercar, la misma separación en grados ocupa más píxeles y se separan', () => {
    const lejos = agrupar([
      { x: 0, y: 0, dato: 'a' },
      { x: 40, y: 0, dato: 'b' },
    ])

    expect(lejos).toHaveLength(2)
  })
})

describe('el color de un grupo', () => {
  it('es el del estado más urgente', () => {
    expect(estadoMasUrgente(['A_TIEMPO', 'RETRASADO', 'EN_TRANSITO'])).toBe('RETRASADO')
    expect(estadoMasUrgente(['EN_ORIGEN', 'EN_DESTINO'])).toBe('EN_DESTINO')
  })
})

describe('rotulo', () => {
  it('sin nombre de nave usa la referencia; sin lectura lo dice', () => {
    expect(
      rotulo(
        marcador({
          nombre: null,
          ultima_lectura: null,
          estado: 'EN_TRANSITO',
          pedidos: [
            { id: 1, oc_numero: '4500000001', posicion_oc: 10, estado_calculado: 'EN_TRANSITO' },
          ],
        }),
      ),
    ).toBe('BL COSU6508789000: En Tránsito. Pedido 4500000001-10. Sin lectura.')
  })
})

describe('mapa aéreo (US-26)', () => {
  const vuelo = (cambios: Partial<MarcadorMapa> = {}) =>
    marcador({
      tipo: 'MAWB',
      referencia: '020-50685434',
      nombre: null,
      estado: 'EN_TRANSITO',
      posicion_estimada: true,
      situacion: 'EN_VUELO',
      vuelo: 'LH518',
      ruta: [
        [50, 8],
        [10, -84],
      ],
      pedidos: [
        { id: 3, oc_numero: '4500123789', posicion_oc: 20, estado_calculado: 'EN_TRANSITO' },
      ],
      ...cambios,
    })

  function montarAereo() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <MapaEmbarques titulo="Mapa Aéreo" capa="AEREO" centro={[17, -78]} zoom={4} />
      </QueryClientProvider>,
    )
  }

  it('un vuelo en curso se dibuja como avión y se rotula como estimado', async () => {
    vi.mocked(obtenerMapa).mockResolvedValue(mapa({ via: 'AEREO', marcadores: [vuelo()] }))
    montarAereo()

    expect(await screen.findByTitle('MAWB 020-50685434: en vuelo')).toHaveTextContent('✈')
    expect(obtenerMapa).toHaveBeenCalledWith('AEREO', FILTROS_VACIOS)
    expect(screen.getByText(/posición estimada según el horario del vuelo/)).toBeInTheDocument()
    expect(
      await within(screen.getByRole('list', { name: 'Embarques en el Mapa Aéreo' })).findByRole(
        'listitem',
      ),
    ).toHaveTextContent('En vuelo LH518, posición estimada según su horario.')
  })

  it('un vuelo concluido lo dice, con el aeropuerto', () => {
    expect(rotulo(vuelo({ situacion: 'FINALIZADO', lugar: 'SJO', ruta: null }))).toContain(
      'Vuelo LH518 concluido en SJO.',
    )
  })

  it('en un transbordo, en tierra en el aeropuerto donde espera', () => {
    expect(rotulo(vuelo({ situacion: 'EN_TIERRA', lugar: 'FRA', ruta: null }))).toContain(
      'En tierra en FRA, esperando vuelo.',
    )
  })
})
