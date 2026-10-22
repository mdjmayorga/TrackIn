import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { FrescuraDatos } from '@/components/FrescuraDatos'
import { obtenerEstadoCargas } from '@/services/cargas'
import { obtenerHealth } from '@/services/health'
import type { CargaResumen, EstadoCargas, HealthResponse, Rol } from '@/types/api'
import { formatearFechaHora } from '@/utils/fechas'

vi.mock('@/services/cargas', () => ({ obtenerEstadoCargas: vi.fn() }))
vi.mock('@/services/health', () => ({ obtenerHealth: vi.fn() }))

const CONTACTO = '2026-10-22T15:30:00Z'

const SALUD: HealthResponse = {
  status: 'ok',
  version: '0.1.0',
  environment: 'test',
  database: 'up',
  postgis: '3.6',
  fuentes: [
    {
      fuente: 'shipsgo',
      degradada: false,
      fallos_consecutivos: 0,
      clase_ultimo_fallo: 'ninguno',
      motivo_ultimo_fallo: null,
      ultimo_contacto_ok: CONTACTO,
      antiguedad_s: 30,
      reportado_en: CONTACTO,
    },
  ],
  detail: null,
}

const ULTIMA = {
  id: 3,
  archivo: 'ZTRACKING WK43.xlsx',
  realizada_en: '2026-10-20T14:00:00Z',
  estado: 'APLICADA',
  usuario: { usuario: 'compras', nombre_completo: 'Equipo de Compras' },
} as CargaResumen

function estado(cambios: Partial<EstadoCargas> = {}): EstadoCargas {
  return {
    situacion: 'AL_DIA',
    ultima: ULTIMA,
    semana_desde: '2026-10-19',
    dia_limite: 2,
    ...cambios,
  }
}

function montar(rol: Rol = 'COMPRAS') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <FrescuraDatos rol={rol} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(obtenerHealth).mockResolvedValue(SALUD)
})

afterEach(() => {
  vi.mocked(obtenerEstadoCargas).mockReset()
  vi.mocked(obtenerHealth).mockReset()
})

describe('frescura de los datos en el encabezado (US-23)', () => {
  it('dice cuándo fue la última consulta a ShipsGo y la última carga, y quién la hizo', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado())
    montar()

    expect(
      await screen.findByText(formatearFechaHora(CONTACTO)!, { exact: false }),
    ).toBeInTheDocument()
    expect(
      await screen.findByText(`Z-tracking: ${formatearFechaHora(ULTIMA.realizada_en)}`, {
        exact: false,
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('(por Equipo de Compras)')).toBeInTheDocument()
    // Al día: nada que avisar.
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('el lunes y el martes, sin la carga de la semana, lo recuerda', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado({ situacion: 'TOCA_CARGAR' }))
    montar()

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Toca cargar el Z-tracking de esta semana (a más tardar el martes).',
    )
  })

  it('desde el miércoles avisa que falta, y a Compras le da el enlace para cargar', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado({ situacion: 'ATRASADA' }))
    montar('COMPRAS')

    const aviso = await screen.findByRole('alert')
    expect(aviso).toHaveTextContent('Falta la carga del Z-tracking de esta semana')
    expect(screen.getByRole('link', { name: 'Cargar Z-tracking' })).toHaveAttribute(
      'href',
      '/cargas',
    )
  })

  it('a quien no carga le avisa igual, pero sin el enlace', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado({ situacion: 'ATRASADA' }))
    montar('LOGISTICA')

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Cargar Z-tracking' })).toBeNull()
  })

  it('si nunca se cargó, lo dice en vez de mostrar una fecha vacía', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado({ situacion: 'NUNCA', ultima: null }))
    montar()

    expect(await screen.findByText('nunca se cargó desde TrackIn')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(
      'El Z-tracking todavía no se cargó desde TrackIn.',
    )
  })

  it('el día límite sale del parámetro', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(
      estado({ situacion: 'TOCA_CARGAR', dia_limite: 3 }),
    )
    montar()

    expect(await screen.findByRole('status')).toHaveTextContent('a más tardar el miércoles')
  })
})
