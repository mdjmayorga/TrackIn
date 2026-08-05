import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import { describe, expect, it, vi } from 'vitest'

import Dashboard from '@/pages/Dashboard'

vi.mock('@/services/health', () => ({
  obtenerHealth: vi.fn().mockResolvedValue({
    status: 'ok',
    version: '0.1.0',
    environment: 'test',
    database: 'up',
    postgis: '3.4 USE_GEOS=1 USE_PROJ=1',
    detail: null,
  }),
}))

function renderConProviders(ui: ReactElement) {
  // retry: false — si no, un fallo tarda varios segundos en propagarse al test.
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('Dashboard', () => {
  it('muestra el título y el placeholder de Sprint 1', () => {
    renderConProviders(<Dashboard />)

    expect(screen.getByRole('heading', { name: /TrackIn Dashboard/i })).toBeInTheDocument()
    expect(screen.getByText(/Sprint 1 pendiente/i)).toBeInTheDocument()
  })

  it('reporta la versión de PostGIS cuando el backend responde', async () => {
    renderConProviders(<Dashboard />)

    expect(await screen.findByText(/3\.4 USE_GEOS=1/)).toBeInTheDocument()
    expect(screen.getByText(/Conectada/)).toBeInTheDocument()
  })
})
