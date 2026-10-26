import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Dashboard from '@/pages/Dashboard'
import { obtenerHealth } from '@/services/health'
import { listarPedidos, obtenerIndicadores, obtenerProximosArribos } from '@/services/pedidos'
import {
  FILTROS_VACIOS,
  aParametros,
  filtraTerminales,
  hayFiltros,
  soloDigitos,
} from '@/utils/filtros'

import { pagina, pedido } from './fixtures'

vi.mock('@/services/health', () => ({ obtenerHealth: vi.fn() }))
vi.mock('@/services/pedidos', () => ({
  listarPedidos: vi.fn(),
  obtenerIndicadores: vi.fn(),
  obtenerProximosArribos: vi.fn(),
}))

const KPI_VACIO = {
  activos: 0,
  a_tiempo: { pedidos: 0, porcentaje: null },
  en_riesgo: { pedidos: 0, porcentaje: null },
  retrasados: { pedidos: 0, porcentaje: null },
  sin_proyeccion: 0,
  lead_time_medio_dias: null,
}

function montar() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** El último juego de filtros con que se llamó a un servicio. */
function ultimosFiltros(servicio: (...args: never[]) => unknown, posicion: number) {
  const llamadas = vi.mocked(servicio).mock.calls
  return llamadas[llamadas.length - 1][posicion]
}

beforeEach(() => {
  vi.mocked(obtenerHealth).mockRejectedValue(new Error('sin salud en estas pruebas'))
  vi.mocked(listarPedidos).mockResolvedValue(pagina([pedido()], { total: 30 }))
  vi.mocked(obtenerIndicadores).mockResolvedValue(KPI_VACIO)
  vi.mocked(obtenerProximosArribos).mockResolvedValue({
    hoy: '2026-10-14',
    horizonte_dias: 7,
    items: [],
  })
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('la barra del Figma', () => {
  it('tiene los seis filtros: tres campos y tres listas', async () => {
    montar()

    expect(await screen.findByRole('heading', { name: 'Filtros de consulta' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Orden de compra/)).toHaveAttribute('placeholder', '4500')
    expect(screen.getByLabelText(/Posición/)).toHaveAttribute('placeholder', 'Todos')
    expect(screen.getByLabelText(/Material/)).toHaveAttribute('placeholder', 'Buscar Material')
    for (const lista of ['Vía', 'Etapa', 'Cumplimiento']) {
      expect(screen.getByRole('combobox', { name: lista })).toHaveValue('')
    }
  })

  it('la vía ofrece solo las dos del alcance: marítima y aérea', async () => {
    montar()

    const via = await screen.findByRole('combobox', { name: 'Vía' })
    expect(
      within(via)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Vía', 'Marítimo', 'Aéreo'])
  })

  it('la OC y la posición solo aceptan dígitos', async () => {
    montar()

    await userEvent.type(screen.getByLabelText(/Orden de compra/), '45a0-0')
    await userEvent.type(screen.getByLabelText(/Posición/), 'x10')

    expect(screen.getByLabelText(/Orden de compra/)).toHaveValue('4500')
    expect(screen.getByLabelText(/Posición/)).toHaveValue('10')
  })
})

describe('un filtro mueve los tres bloques', () => {
  it('escribir en la OC filtra grilla, KPIs y arribos, una vez y al terminar de escribir', async () => {
    montar()
    await screen.findByRole('table')
    const antes = vi.mocked(listarPedidos).mock.calls.length

    await userEvent.type(screen.getByLabelText(/Orden de compra/), '4500016')

    await waitFor(() => expect(ultimosFiltros(listarPedidos, 1)).toMatchObject({ oc: '4500016' }))
    expect(ultimosFiltros(obtenerIndicadores, 0)).toMatchObject({ oc: '4500016' })
    expect(ultimosFiltros(obtenerProximosArribos, 0)).toMatchObject({ oc: '4500016' })
    // Siete teclas, una sola consulta: la espera agrupa lo escrito.
    expect(vi.mocked(listarPedidos).mock.calls.length - antes).toBe(1)
  })

  it('las listas filtran al instante', async () => {
    montar()
    await screen.findByRole('table')

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Vía' }), 'AEREO')
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Cumplimiento' }),
      'SIN_PROYECCION',
    )

    await waitFor(() =>
      expect(ultimosFiltros(obtenerIndicadores, 0)).toMatchObject({
        via: 'AEREO',
        cumplimiento: 'SIN_PROYECCION',
      }),
    )
  })

  it('filtrar vuelve a la primera página', async () => {
    montar()
    await userEvent.click(await screen.findByRole('button', { name: 'Siguiente' }))
    await waitFor(() =>
      expect(ultimosFiltros(listarPedidos, 0)).toMatchObject({ desplazamiento: 10 }),
    )

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Vía' }), 'MARITIMO')

    await waitFor(() =>
      expect(ultimosFiltros(listarPedidos, 0)).toMatchObject({ desplazamiento: 0 }),
    )
  })

  it('filtrar por Cerrado cambia la fecha proyectada por la de recepción', async () => {
    montar()
    await screen.findByRole('table')

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Etapa' }), 'CERRADO')

    expect(await screen.findByRole('columnheader', { name: /F\. Recepción/ })).toBeInTheDocument()
  })
})

describe('sin resultados', () => {
  it('lo dice y deja limpiar, y limpiar vacía también los campos', async () => {
    montar()
    await screen.findByRole('table')
    vi.mocked(listarPedidos).mockResolvedValue(pagina([]))

    await userEvent.type(screen.getByLabelText(/Material/), 'nada')
    const tabla = await screen.findByRole('table')
    expect(
      await within(tabla).findByText(/Ningún pedido coincide con los filtros/),
    ).toBeInTheDocument()

    await userEvent.click(within(tabla).getByRole('button', { name: 'Limpiar filtros' }))

    expect(screen.getByLabelText(/Material/)).toHaveValue('')
    await waitFor(() => expect(ultimosFiltros(listarPedidos, 1)).toEqual(FILTROS_VACIOS))
    expect(screen.queryByRole('button', { name: 'Limpiar filtros' })).toBeNull()
  })
})

describe('apoyos', () => {
  it('a parámetros de la API, sin mandar los vacíos', () => {
    expect(aParametros(FILTROS_VACIOS)).toEqual({})
    expect(
      aParametros({
        ...FILTROS_VACIOS,
        oc: ' 4500 ',
        posicion: '10',
        material: 'lactosa',
        etapa: 'EN_TRANSITO',
      }),
    ).toEqual({ oc: '4500', posicion: '10', buscar_material: 'lactosa', etapa: 'EN_TRANSITO' })
    // `US-63`: el de la pantalla de planta, con el mismo trato que la OC.
    expect(aParametros({ ...FILTROS_VACIOS, solped: ' 10000335 ' })).toEqual({ solped: '10000335' })
  })

  it('reconoce filtros activos y los terminales', () => {
    expect(hayFiltros(FILTROS_VACIOS)).toBe(false)
    expect(hayFiltros({ ...FILTROS_VACIOS, material: '  ' })).toBe(false)
    expect(hayFiltros({ ...FILTROS_VACIOS, via: 'AEREO' })).toBe(true)
    expect(filtraTerminales({ ...FILTROS_VACIOS, etapa: 'CANCELADO' })).toBe(true)
    expect(filtraTerminales({ ...FILTROS_VACIOS, etapa: 'EN_DESTINO' })).toBe(false)
  })

  it('solo dígitos, con tope', () => {
    expect(soloDigitos('45-00 01617199', 10)).toBe('4500016171')
  })
})
