import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import type { ReactElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CintaKpis } from '@/components/CintaKpis'
import { ProximosArribos } from '@/components/ProximosArribos'
import { api } from '@/services/api'
import { obtenerIndicadores, obtenerProximosArribos } from '@/services/pedidos'
import type { IndicadoresKpi, ProximoArribo } from '@/types/api'
import { destinoCorto, formatearDias, formatearPorcentaje } from '@/utils/formatos'

import { pedido } from './fixtures'

vi.mock('@/services/pedidos', async (original) => ({
  ...(await original<typeof import('@/services/pedidos')>()),
  obtenerIndicadores: vi.fn(),
  obtenerProximosArribos: vi.fn(),
}))

const KPI: IndicadoresKpi = {
  activos: 187,
  a_tiempo: { pedidos: 116, porcentaje: '62.03' },
  en_riesgo: { pedidos: 39, porcentaje: '20.86' },
  retrasados: { pedidos: 32, porcentaje: '17.11' },
  sin_proyeccion: 0,
  lead_time_medio_dias: '14.2',
}

function arribo(cambios: Partial<ProximoArribo> = {}): ProximoArribo {
  return {
    ...pedido({ fecha_proyectada_disponible: '2026-10-16' }),
    dias_restantes: 3,
    ...cambios,
  }
}

function montar(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('cinta de KPIs (US-22)', () => {
  it('los cinco indicadores como en el Figma', async () => {
    vi.mocked(obtenerIndicadores).mockResolvedValue(KPI)
    montar(<CintaKpis />)

    expect(await screen.findByText('187')).toBeInTheDocument()
    const recuadros = screen.getAllByRole('listitem').map((r) => r.textContent)
    expect(recuadros).toEqual([
      '187Pedidos Activos',
      '62,0%(116 pedidos)A Tiempo',
      '20,9%(39 pedidos)En Riesgo',
      '17,1%(32 pedidos)Retrasados',
      '14,2 dLead Time Medio',
    ])
    expect(screen.queryByText(/sin fecha proyectada/)).toBeNull()
  })

  it('dice cuántos activos no tienen proyección, porque no entran en los porcentajes', async () => {
    vi.mocked(obtenerIndicadores).mockResolvedValue({
      ...KPI,
      activos: 107,
      sin_proyeccion: 98,
      a_tiempo: { pedidos: 1, porcentaje: '100.00' },
    })
    montar(<CintaKpis />)

    expect(await screen.findByText(/98 de 107 activos sin fecha proyectada/)).toBeInTheDocument()
    expect(screen.getByText(/\(1 pedido\)/)).toBeInTheDocument()
  })

  it('sin nada que evaluar, guion en vez de 0 %', async () => {
    vi.mocked(obtenerIndicadores).mockResolvedValue({
      activos: 0,
      a_tiempo: { pedidos: 0, porcentaje: null },
      en_riesgo: { pedidos: 0, porcentaje: null },
      retrasados: { pedidos: 0, porcentaje: null },
      sin_proyeccion: 0,
      lead_time_medio_dias: null,
    })
    montar(<CintaKpis />)

    expect(await screen.findByText('0')).toBeInTheDocument()
    expect(screen.getAllByText('–')).toHaveLength(4)
  })

  it('si falla, lo dice', async () => {
    vi.mocked(obtenerIndicadores).mockRejectedValue(new Error('caído'))
    montar(<CintaKpis />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudieron calcular los indicadores',
    )
  })
})

describe('próximos arribos (US-28)', () => {
  it('cada tarjeta con OC, material, vía, destino y días', async () => {
    vi.mocked(obtenerProximosArribos).mockResolvedValue({
      hoy: '2026-10-13',
      horizonte_dias: 7,
      items: [
        arribo({
          id: 1,
          via_transporte: 'AEREO',
          destino: { id: 1, codigo: 'MROC', nombre: 'Aeropuerto Juan Santamaría' },
          estado_cumplimiento: 'EN_RIESGO',
        }),
        arribo({ id: 2, oc_numero: '4500012993', posicion_oc: 30, dias_restantes: 0 }),
      ],
    })
    montar(<ProximosArribos />)

    const tarjetas = await screen.findAllByRole('listitem')
    expect(tarjetas).toHaveLength(2)
    const primera = within(tarjetas[0])
    expect(primera.getByText('4500012847 - 10')).toBeInTheDocument()
    expect(primera.getByText('Lactosa monohidrato')).toBeInTheDocument()
    expect(primera.getByRole('img', { name: 'Aéreo' })).toBeInTheDocument()
    expect(primera.getByRole('img', { name: 'En riesgo' })).toBeInTheDocument()
    expect(primera.getByText('MROC')).toBeInTheDocument()
    expect(primera.getByText('16/10 - 3d')).toBeInTheDocument()
    expect(within(tarjetas[1]).getByText('16/10 - hoy')).toBeInTheDocument()
  })

  it('sin pedido evaluado, el cuadro va gris y lo dice', async () => {
    vi.mocked(obtenerProximosArribos).mockResolvedValue({
      hoy: '2026-10-13',
      horizonte_dias: 7,
      items: [arribo({ estado_cumplimiento: null })],
    })
    montar(<ProximosArribos />)

    expect(await screen.findByRole('img', { name: 'Sin evaluar' })).toBeInTheDocument()
  })

  it('sin arribos en el horizonte no rellena: lo dice', async () => {
    vi.mocked(obtenerProximosArribos).mockResolvedValue({
      hoy: '2026-10-13',
      horizonte_dias: 7,
      items: [],
    })
    montar(<ProximosArribos />)

    expect(
      await screen.findByText('Ningún pedido tiene fecha proyectada en los próximos 7 días.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('list')).toBeNull()
  })

  it('si falla, lo dice', async () => {
    vi.mocked(obtenerProximosArribos).mockRejectedValue(new Error('caído'))
    montar(<ProximosArribos />)

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudieron cargar')
  })
})

describe('formatos', () => {
  it('porcentajes y días con un decimal y coma decimal', () => {
    expect(formatearPorcentaje('62.03')).toBe('62,0%')
    expect(formatearPorcentaje('20.86')).toBe('20,9%')
    expect(formatearPorcentaje('100.00')).toBe('100,0%')
    expect(formatearPorcentaje(null)).toBeNull()
    expect(formatearDias('14.2')).toBe('14,2 d')
    expect(formatearDias(null)).toBeNull()
  })

  it('destino: código del aeropuerto, nombre del puerto', () => {
    expect(destinoCorto(pedido())).toBe('Puerto Limón')
    expect(
      destinoCorto(
        pedido({
          via_transporte: 'AEREO',
          destino: { id: 1, codigo: 'MROC', nombre: 'Aeropuerto Juan Santamaría' },
        }),
      ),
    ).toBe('MROC')
  })
})

describe('servicio', () => {
  it('pide los KPIs y los arribos a sus rutas', async () => {
    const real = await vi.importActual<typeof import('@/services/pedidos')>('@/services/pedidos')
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: {} })

    await real.obtenerIndicadores()
    await real.obtenerProximosArribos()

    expect(get).toHaveBeenNthCalledWith(1, '/api/v1/pedidos/indicadores')
    expect(get).toHaveBeenNthCalledWith(2, '/api/v1/pedidos/proximos-arribos')
  })
})
