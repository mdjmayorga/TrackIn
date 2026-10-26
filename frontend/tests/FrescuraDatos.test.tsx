import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FrescuraDatos } from '@/components/FrescuraDatos'
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
      <FrescuraDatos />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.mocked(obtenerHealth).mockReset()
})

describe('frescura del rastreo en el encabezado (US-23)', () => {
  it('dice cuándo fue la última consulta buena a ShipsGo', async () => {
    vi.mocked(obtenerHealth).mockResolvedValue(salud(CONTACTO))
    montar()

    expect(
      await screen.findByText(formatearFechaHora(CONTACTO)!, { exact: false }),
    ).toBeInTheDocument()
  })

  it('sin ninguna consulta todavía, lo dice', async () => {
    vi.mocked(obtenerHealth).mockResolvedValue(salud(null))
    montar()

    expect(await screen.findByText('todavía no hay')).toBeInTheDocument()
  })
})
