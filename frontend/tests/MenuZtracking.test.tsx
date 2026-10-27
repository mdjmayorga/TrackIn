import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MenuZtracking } from '@/components/MenuZtracking'
import { obtenerEstadoCargas } from '@/services/cargas'
import type { CargaResumen, EstadoCargas, Rol } from '@/types/api'
import { formatearFechaHora } from '@/utils/fechas'

vi.mock('@/services/cargas', () => ({ obtenerEstadoCargas: vi.fn() }))

const ULTIMA = {
  id: 3,
  archivo: 'ZTRACKING WK43.xlsx',
  realizada_en: '2026-10-20T14:00:00Z',
  estado: 'APLICADA',
  origen: 'EXCEL',
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
        <MenuZtracking rol={rol} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.mocked(obtenerEstadoCargas).mockReset()
})

const boton = () => screen.getByRole('button', { name: /^Ajustes Z-tracking/ })

describe('«Ajustes Z-tracking» en el encabezado (US-23, 26/10)', () => {
  it('al día: sin burbuja, y el menú dice la última carga y quién la hizo', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado())
    montar()

    expect(
      await screen.findByRole('button', { name: 'Ajustes Z-tracking (al día)' }),
    ).toBeInTheDocument()
    expect(screen.queryByText('!')).toBeNull()

    await userEvent.click(boton())
    expect(screen.getByRole('status')).toHaveTextContent('La carga de esta semana está hecha.')
    expect(
      screen.getByText(
        `Última carga: ${formatearFechaHora(ULTIMA.realizada_en)}, por Equipo de Compras`,
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Cargar Z-tracking' })).toHaveAttribute(
      'href',
      '/cargas',
    )
  })

  it('el lunes y el martes sin carga: burbuja naranja y el recordatorio', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado({ situacion: 'TOCA_CARGAR' }))
    montar()

    await screen.findByRole('button', { name: 'Ajustes Z-tracking (toca cargar)' })
    expect(screen.getByText('!')).toHaveClass('bg-estado-riesgo')

    await userEvent.click(boton())
    expect(screen.getByRole('status')).toHaveTextContent(
      'Toca cargar el Z-tracking de esta semana (a más tardar el martes).',
    )
  })

  it('desde el miércoles sin carga: burbuja roja y el aviso de que falta', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado({ situacion: 'ATRASADA' }))
    montar()

    await screen.findByRole('button', { name: 'Ajustes Z-tracking (carga atrasada)' })
    expect(screen.getByText('!')).toHaveClass('bg-estado-retrasado')

    await userEvent.click(boton())
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Falta la carga del Z-tracking de esta semana',
    )
  })

  it('si nunca se cargó: burbuja naranja y lo dice en vez de una fecha vacía', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado({ situacion: 'NUNCA', ultima: null }))
    montar()

    await screen.findByRole('button', { name: 'Ajustes Z-tracking (nunca cargado)' })
    expect(screen.getByText('!')).toHaveClass('bg-estado-riesgo')

    await userEvent.click(boton())
    expect(screen.getByText('Todavía no hay cargas hechas desde TrackIn.')).toBeInTheDocument()
  })

  it('quien no carga ve el historial en vez de «Cargar»', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado({ situacion: 'ATRASADA' }))
    montar('LOGISTICA')

    await userEvent.click(await screen.findByRole('button', { name: /^Ajustes Z-tracking/ }))

    expect(screen.getByRole('link', { name: 'Historial de cargas' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Cargar Z-tracking' })).toBeNull()
  })

  it('el día límite sale del parámetro', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(
      estado({ situacion: 'TOCA_CARGAR', dia_limite: 3 }),
    )
    montar()

    await userEvent.click(await screen.findByRole('button', { name: /^Ajustes Z-tracking/ }))

    expect(screen.getByRole('status')).toHaveTextContent('a más tardar el miércoles')
  })
})

describe('acceso a «Altas en ShipsGo» (US-55)', () => {
  it('Compras lo tiene en el menú', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado())
    montar('COMPRAS')

    await userEvent.click(await screen.findByRole('button', { name: /^Ajustes Z-tracking/ }))

    expect(screen.getByRole('link', { name: 'Altas en ShipsGo' })).toHaveAttribute(
      'href',
      '/shipsgo/altas',
    )
  })

  it('quien no autoriza altas no lo ve', async () => {
    vi.mocked(obtenerEstadoCargas).mockResolvedValue(estado())
    montar('LOGISTICA')

    await userEvent.click(await screen.findByRole('button', { name: /^Ajustes Z-tracking/ }))

    expect(screen.queryByRole('link', { name: 'Altas en ShipsGo' })).toBeNull()
  })
})
