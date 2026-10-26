import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { EstadoShipsGo } from '@/components/EstadoShipsGo'
import { obtenerHealth } from '@/services/health'
import type { HealthResponse } from '@/types/api'
import { formatearFechaHora } from '@/utils/fechas'

vi.mock('@/services/health', () => ({ obtenerHealth: vi.fn() }))

const CONTACTO = '2026-10-22T15:30:00Z'

function salud(contacto: string | null): HealthResponse {
  return {
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
        ultimo_contacto_ok: contacto,
        antiguedad_s: 30,
        reportado_en: CONTACTO,
      },
    ],
    detail: null,
  }
}

function montar() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <EstadoShipsGo />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.mocked(obtenerHealth).mockReset()
})

describe('la última consulta a ShipsGo, al pasar el cursor por la insignia (US-23, 26/10)', () => {
  it('va en un texto emergente propio, con fecha, hora y antigüedad', async () => {
    vi.mocked(obtenerHealth).mockResolvedValue(salud(CONTACTO))
    montar()

    const insignia = await screen.findByRole('status')
    expect(insignia).toHaveTextContent('ShipsGo API Online')
    const emergente = screen.getByRole('tooltip', { hidden: true })
    expect(emergente).toHaveTextContent(
      `Última consulta a ShipsGo: ${formatearFechaHora(CONTACTO)}`,
    )
    // La insignia lo anuncia como su descripción, y no usa el `title` del navegador.
    expect(insignia).toHaveAttribute('aria-describedby', emergente.id)
    expect(insignia).not.toHaveAttribute('title')
  })

  it('está oculto hasta pasar el cursor o enfocar la insignia', async () => {
    vi.mocked(obtenerHealth).mockResolvedValue(salud(CONTACTO))
    montar()

    await screen.findByRole('status')
    const emergente = screen.getByRole('tooltip', { hidden: true })
    expect(emergente).toHaveClass('invisible', 'group-hover:visible', 'group-focus-within:visible')
  })

  it('se puede enfocar con el teclado, para leer el texto emergente', async () => {
    vi.mocked(obtenerHealth).mockResolvedValue(salud(CONTACTO))
    montar()

    expect(await screen.findByRole('status')).toHaveAttribute('tabindex', '0')
  })

  it('sin ninguna consulta todavía, el texto emergente lo dice', async () => {
    vi.mocked(obtenerHealth).mockResolvedValue(salud(null))
    montar()

    await screen.findByRole('status')
    expect(screen.getByRole('tooltip', { hidden: true })).toHaveTextContent(
      'Todavía no hay consultas a ShipsGo.',
    )
  })
})
