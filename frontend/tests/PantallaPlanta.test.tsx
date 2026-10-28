import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, renderHook, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PanelPedidos, ROTACION_MS } from '@/components/PanelPedidos'
import { REFRESCO_PANEL_MS } from '@/hooks/usePedidos'
import { usePantallaCompleta, useWakeLock } from '@/hooks/usePantallaPermanente'
import { listarPedidos } from '@/services/pedidos'
import { FILTROS_VACIOS } from '@/utils/filtros'

import { pagina, pedido } from './fixtures'

vi.mock('@/services/pedidos', async (original) => ({
  ...(await original<typeof import('@/services/pedidos')>()),
  listarPedidos: vi.fn(),
}))

function montar(rotarPaginas: boolean) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PanelPedidos
          filtros={FILTROS_VACIOS}
          onCambioFiltros={() => undefined}
          onLimpiarFiltros={() => undefined}
          versionFiltros={0}
          vista="simple"
          rotarPaginas={rotarPaginas}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** 25 pedidos: tres páginas de 10. */
function veinticinco() {
  vi.mocked(listarPedidos).mockImplementation(async ({ desplazamiento }) =>
    pagina(
      Array.from({ length: Math.min(10, 25 - desplazamiento) }, (_, i) =>
        pedido({ id: desplazamiento + i + 1, posicion_oc: (desplazamiento + i + 1) * 10 }),
      ),
      { total: 25, desplazamiento },
    ),
  )
}

const desplazamientos = () =>
  vi.mocked(listarPedidos).mock.calls.map(([consulta]) => consulta.desplazamiento)

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

afterEach(() => {
  vi.useRealTimers()
  vi.mocked(listarPedidos).mockReset()
})

describe('pantalla de planta (US-33)', () => {
  it('pasa sola de página y al llegar a la última vuelve a la primera', async () => {
    veinticinco()
    montar(true)
    expect(await screen.findByText(/cambian solas cada 20 s/)).toBeInTheDocument()

    for (let i = 0; i < 3; i++) {
      await act(() => vi.advanceTimersByTimeAsync(ROTACION_MS))
    }

    expect(desplazamientos()).toEqual([0, 10, 20, 0])
  })

  it('sin rotación, la página no cambia sola', async () => {
    veinticinco()
    montar(false)
    await screen.findAllByRole('row')

    await act(() => vi.advanceTimersByTimeAsync(ROTACION_MS * 2))

    expect(desplazamientos()).toEqual([0])
    expect(screen.queryByText(/cambian solas/)).toBeNull()
  })

  it('con una sola página no rota', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([pedido()]))
    montar(true)
    await screen.findAllByRole('row')

    await act(() => vi.advanceTimersByTimeAsync(ROTACION_MS * 2))

    expect(desplazamientos()).toEqual([0])
  })

  it('la grilla se vuelve a pedir sola, antes de que venza la sesión', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([pedido()]))
    montar(false)
    await screen.findAllByRole('row')

    await act(() => vi.advanceTimersByTimeAsync(REFRESCO_PANEL_MS))

    expect(listarPedidos).toHaveBeenCalledTimes(2)
    // La sesión se cierra tras 30 min sin uso: el refresco la mantiene abierta.
    expect(REFRESCO_PANEL_MS).toBeLessThan(30 * 60_000)
  })
})

describe('pantalla encendida y completa', () => {
  it('pide al navegador que no apague la pantalla, y lo suelta al salir', async () => {
    const liberar = vi.fn().mockResolvedValue(undefined)
    const pedir = vi.fn().mockResolvedValue({ release: liberar })
    Object.defineProperty(navigator, 'wakeLock', { value: { request: pedir }, configurable: true })

    const { unmount } = renderHook(() => useWakeLock(true))
    await act(() => Promise.resolve())
    expect(pedir).toHaveBeenCalledWith('screen')

    unmount()
    expect(liberar).toHaveBeenCalled()
    Reflect.deleteProperty(navigator, 'wakeLock')
  })

  it('sin soporte del navegador no falla', () => {
    expect(() => renderHook(() => useWakeLock(true))).not.toThrow()
  })

  it('el botón entra en pantalla completa', async () => {
    const entrar = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(document.documentElement, 'requestFullscreen', {
      value: entrar,
      configurable: true,
    })

    function Boton() {
      const { alternar, posible } = usePantallaCompleta()
      return posible ? <button onClick={alternar}>Pantalla completa</button> : null
    }
    render(<Boton />)
    vi.useRealTimers()
    await userEvent.click(screen.getByRole('button', { name: 'Pantalla completa' }))

    expect(entrar).toHaveBeenCalled()
    Reflect.deleteProperty(document.documentElement, 'requestFullscreen')
  })
})
