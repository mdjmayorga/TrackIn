import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Dashboard from '@/pages/Dashboard'
import { obtenerHealth } from '@/services/health'
import { listarPedidos } from '@/services/pedidos'
import type { HealthResponse } from '@/types/api'

import { pagina, pedido } from './fixtures'

vi.mock('@/services/health', () => ({ obtenerHealth: vi.fn() }))
vi.mock('@/services/pedidos', () => ({ listarPedidos: vi.fn() }))

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
      ultimo_contacto_ok: '2026-10-07T14:00:00Z',
      antiguedad_s: 30,
      reportado_en: '2026-10-07T14:00:00Z',
    },
  ],
  detail: null,
}

function renderConProviders(ui: ReactElement) {
  // retry: false — si no, un fallo tarda varios segundos en propagarse al test.
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  vi.mocked(obtenerHealth).mockResolvedValue(SALUD)
  vi.mocked(listarPedidos).mockResolvedValue(
    pagina([pedido({ id: 1 }), pedido({ id: 2, posicion_oc: 20 })], { total: 2 }),
  )
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Dashboard', () => {
  it('muestra el título del Figma y el estado de ShipsGo', async () => {
    renderConProviders(<Dashboard />)

    expect(
      screen.getByRole('heading', { name: /Panel de Control Logístico - Compras en Tránsito/ }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('status')).toHaveTextContent('ShipsGo API Online')
  })

  it('los dos mapas a los lados y, al centro, arribos y grilla', async () => {
    renderConProviders(<Dashboard />)

    const titulos = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(titulos).toEqual([
      'Mapa Marítimo',
      'Próximos Arribos',
      'Grilla de Pedidos',
      'Mapa Aéreo',
    ])
  })

  it('avisa si el backend no responde', async () => {
    vi.mocked(obtenerHealth).mockRejectedValue(new Error('caído'))
    renderConProviders(<Dashboard />)

    // `useHealth` reintenta una vez antes de rendirse: más de un segundo.
    expect(
      await screen.findByText('Sin conexión con TrackIn', undefined, { timeout: 4000 }),
    ).toBeInTheDocument()
  })

  it('carga la grilla con el orden por omisión: lo que llega antes', async () => {
    renderConProviders(<Dashboard />)

    const grilla = await screen.findByRole('table')
    expect(within(grilla).getAllByRole('row')).toHaveLength(3)
    expect(listarPedidos).toHaveBeenCalledWith({
      orden: 'fecha_proyectada',
      limite: 10,
      desplazamiento: 0,
    })
  })

  it('ordenar vuelve a consultar desde la primera página', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([pedido()], { total: 60 }))
    renderConProviders(<Dashboard />)

    await userEvent.click(await screen.findByRole('button', { name: 'Siguiente' }))
    await userEvent.click(screen.getByRole('button', { name: /^OC/ }))

    expect(listarPedidos).toHaveBeenCalledWith({
      orden: 'fecha_proyectada',
      limite: 10,
      desplazamiento: 10,
    })
    expect(listarPedidos).toHaveBeenLastCalledWith({ orden: 'oc', limite: 10, desplazamiento: 0 })
  })

  it('si la consulta falla, lo dice en vez de mostrar una grilla vacía', async () => {
    vi.mocked(listarPedidos).mockRejectedValue(new Error('se cayó la base'))
    renderConProviders(<Dashboard />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudieron cargar los pedidos: se cayó la base',
    )
    expect(screen.queryByRole('table')).toBeNull()
  })
})
