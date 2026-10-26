import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError } from 'axios'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ContextoSesion } from '@/auth/contexto'
import type { SesionGuardada } from '@/auth/sesion'
import Bandeja from '@/pages/Bandeja'
import Dashboard from '@/pages/Dashboard'
import { pasarAAduana } from '@/services/acciones'
import { obtenerHealth } from '@/services/health'
import { listarPedidos } from '@/services/pedidos'
import type { PedidoDetalle, Rol } from '@/types/api'
import { FILTROS_VACIOS } from '@/utils/filtros'

import { pagina, pedido } from './fixtures'
import { USUARIO } from './sesion.test'

vi.mock('@/services/pedidos', async (original) => ({
  ...(await original<typeof import('@/services/pedidos')>()),
  listarPedidos: vi.fn(),
  obtenerIndicadores: vi.fn(() => new Promise(() => undefined)),
  obtenerProximosArribos: vi.fn(() => new Promise(() => undefined)),
}))

vi.mock('@/services/acciones', async (original) => ({
  ...(await original<typeof import('@/services/acciones')>()),
  pasarAAduana: vi.fn(),
}))

// El encabezado pide si el Z-tracking de la semana está cargado (`US-23`): sin
// esto la prueba intentaría salir a la red.
vi.mock('@/services/cargas', async (original) => ({
  ...(await original<typeof import('@/services/cargas')>()),
  obtenerEstadoCargas: vi.fn(() => new Promise(() => undefined)),
}))

vi.mock('@/services/health', () => ({ obtenerHealth: vi.fn() }))

/** Lo que pide la bandeja: los llegados, lo más antiguo primero. */
const CONSULTA_BANDEJA = [
  { orden: 'fecha_arribo', limite: 200, desplazamiento: 0 },
  { ...FILTROS_VACIOS, etapa: 'EN_DESTINO' },
]

function llegado(id: number, posicion: number, fecha_arribo: string) {
  return pedido({
    id,
    posicion_oc: posicion,
    etapa_viaje: 'EN_DESTINO',
    estado_calculado: 'EN_DESTINO',
    fecha_arribo,
  })
}

function montar(ui: ReactElement, rol: Rol = 'PLANIFICACION') {
  const sesion: SesionGuardada = { token: 't', usuario: { ...USUARIO, rol }, recordada: false }
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ContextoSesion.Provider value={sesion}>
        <MemoryRouter>{ui}</MemoryRouter>
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
  vi.mocked(obtenerHealth).mockReturnValue(new Promise(() => undefined))
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.mocked(listarPedidos).mockReset()
  vi.mocked(pasarAAduana).mockReset()
})

describe('bandeja de arribos pendientes (US-48)', () => {
  it('pide los pedidos en destino, lo que lleva más tiempo esperando primero', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(
      pagina([llegado(1, 10, '2026-10-14T15:00:00Z'), llegado(2, 20, '2026-10-18T15:00:00Z')]),
    )
    montar(<Bandeja />)

    const filas = await screen.findAllByRole('listitem')
    expect(filas.map((f) => f.getAttribute('aria-label'))).toEqual([
      'Pedido 4500012847 - 10',
      'Pedido 4500012847 - 20',
    ])
    expect(listarPedidos).toHaveBeenCalledWith(...CONSULTA_BANDEJA)
    expect(screen.getByText(/2 pedidos llegaron a destino/)).toBeInTheDocument()
    expect(within(filas[0]).getByText('14/10/2026 09:00', { exact: false })).toBeInTheDocument()
    expect(within(filas[0]).getByRole('link', { name: '4500012847 - 10' })).toHaveAttribute(
      'href',
      '/pedidos/1',
    )
  })

  it('vacía, lo dice en vez de mostrar una lista en blanco', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([]))
    montar(<Bandeja />)

    expect(await screen.findByText(/No hay arribos pendientes/)).toBeInTheDocument()
    expect(screen.queryByRole('listitem')).toBeNull()
  })

  it('si la consulta falla, lo dice', async () => {
    vi.mocked(listarPedidos).mockRejectedValue(new Error('se cayó la base'))
    montar(<Bandeja />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo cargar la bandeja: se cayó la base',
    )
  })

  it('el paso a aduana pide motivo, se registra y el pedido sale de la bandeja', async () => {
    vi.mocked(listarPedidos)
      .mockResolvedValueOnce(pagina([llegado(1, 10, '2026-10-14T15:00:00Z')]))
      .mockResolvedValue(pagina([]))
    vi.mocked(pasarAAduana).mockResolvedValue({
      ...pedido({ id: 1, etapa_viaje: 'EN_PROCESO_ADUANAL' }),
    } as PedidoDetalle)
    montar(<Bandeja />)

    await userEvent.click(await screen.findByRole('button', { name: 'Pasar a proceso aduanal' }))
    const confirmar = screen.getByRole('button', { name: 'Confirmar' })
    await userEvent.type(screen.getByRole('textbox', { name: /Motivo/ }), 'DUA')
    expect(confirmar).toBeDisabled() // menos de cinco caracteres

    await userEvent.type(screen.getByRole('textbox', { name: /Motivo/ }), ' presentado')
    await userEvent.click(confirmar)

    expect(pasarAAduana).toHaveBeenCalledWith(1, { motivo: 'DUA presentado' })
    expect(await screen.findByText(/No hay arribos pendientes/)).toBeInTheDocument()
  })

  it('si el backend rechaza el paso, muestra el motivo y el pedido sigue', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([llegado(1, 10, '2026-10-14T15:00:00Z')]))
    vi.mocked(pasarAAduana).mockRejectedValue(
      new AxiosError(
        '409',
        'ERR',
        undefined,
        {},
        {
          status: 409,
          statusText: '',
          headers: {},
          config: {} as never,
          data: { detail: 'El pedido no está en destino.' },
        },
      ),
    )
    montar(<Bandeja />)

    await userEvent.click(await screen.findByRole('button', { name: 'Pasar a proceso aduanal' }))
    await userEvent.type(screen.getByRole('textbox', { name: /Motivo/ }), 'DUA presentado')
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('El pedido no está en destino.')
    expect(screen.getByRole('listitem')).toBeInTheDocument()
  })

  it('para un rol que no gestiona aduana, explica de quién es y no consulta', async () => {
    montar(<Bandeja />, 'PLANTA')

    expect(
      screen.getByText(/La bandeja es de Planificación, Logística y Compras/),
    ).toBeInTheDocument()
    expect(listarPedidos).not.toHaveBeenCalled()
  })
})

describe('contador del encabezado (US-48)', () => {
  it('Planificación ve cuántos arribos esperan, con enlace a la bandeja', async () => {
    vi.mocked(listarPedidos).mockImplementation(async (_consulta, filtros) =>
      filtros?.etapa === 'EN_DESTINO'
        ? pagina([llegado(1, 10, '2026-10-14T15:00:00Z')], { total: 3 })
        : pagina([]),
    )
    montar(<Dashboard />)

    const enlace = await screen.findByRole('link', { name: 'Arribos pendientes (3 pendientes)' })
    expect(enlace).toHaveAttribute('href', '/bandeja')
  })

  it('Compras también lo ve, desde el 21/10: gestiona los arribos', async () => {
    vi.mocked(listarPedidos).mockImplementation(async (_consulta, filtros) =>
      filtros?.etapa === 'EN_DESTINO' ? pagina([], { total: 2 }) : pagina([]),
    )
    montar(<Dashboard />, 'COMPRAS')

    expect(
      await screen.findByRole('link', { name: 'Arribos pendientes (2 pendientes)' }),
    ).toBeInTheDocument()
  })

  it('Planta no lo ve: no puede resolver esos pendientes', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([]))
    montar(<Dashboard />, 'PLANTA')

    expect(await screen.findByRole('button', { name: 'Configuración' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Arribos pendientes/ })).toBeNull()
    expect(listarPedidos).not.toHaveBeenCalledWith(...CONSULTA_BANDEJA)
  })
})

describe('pantalla de planta (US-43)', () => {
  it('ve el panel con la grilla simple, sin enlaces de gestión', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([pedido()]))
    montar(<Dashboard />, 'PLANTA')

    const grilla = await screen.findByRole('table')
    expect(
      within(grilla)
        .getAllByRole('columnheader')
        .map((th) => th.textContent?.replace(/[▲▼↕]/g, '')),
    ).toEqual(['OC', 'POS', 'SOLPED', 'Material', 'Etapa', 'Cumplimiento'])
    expect(screen.getByRole('heading', { name: 'Filtros de consulta' })).toBeInTheDocument()
    expect(screen.getByLabelText(/SOLPED/)).toBeInTheDocument() // `US-63`, 26/10
    expect(screen.queryByRole('link', { name: /Arribos pendientes/ })).toBeNull()
    expect(listarPedidos).not.toHaveBeenCalledWith(...CONSULTA_BANDEJA)

    await userEvent.click(screen.getByRole('button', { name: 'Configuración' }))
    expect(screen.queryByRole('link', { name: /Z-tracking/ })).toBeNull()
    expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toBeInTheDocument()
  })

  it('los demás roles siguen viendo la grilla completa', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([pedido()]))
    montar(<Dashboard />, 'PLANIFICACION')

    const grilla = await screen.findByRole('table')
    expect(within(grilla).getAllByRole('columnheader')).toHaveLength(9)
    expect(screen.queryByLabelText(/SOLPED/)).toBeNull()
  })
})

describe('enlace a cambiar la contraseña (US-61)', () => {
  it.each(['COMPRAS', 'PLANTA'] as const)('%s lo ve en Configuración', async (rol) => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([]))
    montar(<Dashboard />, rol)

    await userEvent.click(await screen.findByRole('button', { name: 'Configuración' }))
    expect(screen.getByRole('link', { name: 'Cambiar contraseña' })).toHaveAttribute(
      'href',
      '/contrasena',
    )
  })
})

describe('botón de arribos pendientes, con el diseño de Arribos_Pendientes.png', () => {
  it('con pendientes, lleva la burbuja con el número', async () => {
    vi.mocked(listarPedidos).mockImplementation(async (_consulta, filtros) =>
      filtros?.etapa === 'EN_DESTINO' ? pagina([], { total: 1 }) : pagina([]),
    )
    montar(<Dashboard />)

    const boton = await screen.findByRole('link', { name: 'Arribos pendientes (1 pendiente)' })
    expect(within(boton).getByText('1')).toBeInTheDocument()
  })

  it('en cero queda como el diseño: sin burbuja', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([]))
    montar(<Dashboard />)

    const boton = await screen.findByRole('link', { name: 'Arribos pendientes (ninguno)' })
    expect(within(boton).queryByText('0')).toBeNull()
    expect(boton).toHaveAttribute('href', '/bandeja')
  })
})

describe('botón «Ajustes Z-tracking» en el panel (26/10)', () => {
  it('Compras lo ve junto a Configuración y Arribos pendientes', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([]))
    montar(<Dashboard />, 'COMPRAS')

    expect(await screen.findByRole('button', { name: /^Ajustes Z-tracking/ })).toBeInTheDocument()
  })

  it('Planta no: su pantalla no carga archivos', async () => {
    vi.mocked(listarPedidos).mockResolvedValue(pagina([]))
    montar(<Dashboard />, 'PLANTA')

    expect(await screen.findByRole('button', { name: 'Configuración' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Ajustes Z-tracking/ })).toBeNull()
  })
})
