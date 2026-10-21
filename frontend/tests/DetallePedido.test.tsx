import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError } from 'axios'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ContextoSesion } from '@/auth/contexto'
import { GrillaPedidos } from '@/components/GrillaPedidos'
import DetallePedido from '@/pages/DetallePedido'
import { api } from '@/services/api'
import { asociarReferencia, obtenerBitacora, obtenerPedido } from '@/services/pedidos'
import type { PedidoDetalle, Rol } from '@/types/api'
import {
  formatearCantidad,
  formatearDiasConSigno,
  formatearNudos,
  formatearPosicion,
} from '@/utils/detalle'
import { haceCuanto } from '@/utils/fechas'

import { pagina, pedido } from './fixtures'
import { USUARIO } from './sesion.test'

vi.mock('@/services/pedidos', async (original) => ({
  ...(await original<typeof import('@/services/pedidos')>()),
  obtenerPedido: vi.fn(),
  obtenerBitacora: vi.fn(),
  asociarReferencia: vi.fn(),
}))

/** El pedido del Figma: 4500012847 · 10, marítimo, en tránsito, a tiempo. */
function detalle(cambios: Partial<PedidoDetalle> = {}): PedidoDetalle {
  return {
    ...pedido({
      id: 7,
      destino: { id: 3, codigo: 'CRMOB', nombre: 'Moín' },
      proveedor: { id: 1, codigo: 'P1', nombre: 'DFE Pharma' },
      material: { id: 1, codigo: '13002006', descripcion: 'Lactosa monohidrato 200M' },
    }),
    cantidad_pedida: '12000.000',
    unidad_medida: 'KG',
    incoterm: 'CIF',
    temperatura: null,
    tipo_proveedor: null,
    fabricante: null,
    pais_origen: null,
    rastreo: {
      tipo: 'BL',
      referencia: 'MEDU1234567',
      via_transporte: 'MARITIMO',
      nombre: 'MSC BRUNELLA',
      imo: 9000001,
      eta_fuente: '2026-09-02T14:00:00Z',
      ata_fuente: null,
      posicion: { latitud: 10.42, longitud: -81.9 },
      velocidad_nudos: '12.4',
      ultima_consulta_exitosa: new Date(Date.now() - 3 * 60_000).toISOString(),
      guia_madre: null,
      manifiesto_aduana: null,
      activo: true,
    },
    arribos: { confirmado: null, fuente: null, inferido: null },
    calculo: {
      origen: 'ETA_FUENTE',
      eta_utilizada: '2026-09-02T14:00:00Z',
      lead_time_dias: 6,
      lead_time_maestro_dias: 6,
      ajuste_manual_dias: 0,
      fecha_proyectada: '2026-09-08',
      fecha_comprometida: '2026-09-15',
      ventana_aduanal_dias: 13,
      margen_dias: 7,
      umbral_riesgo_dias: 2,
      desglose: '02/09/2026 + 6 d + 0 d = 08/09/2026',
      al_dia: true,
      desglose_actual: null,
      fecha_ultimo_recalculo: '2026-09-01T12:00:00Z',
    },
    cierre: {
      fecha_recepcion_planta: null,
      cantidad_recibida: null,
      liberacion_estimada: null,
      cantidad_liberada: null,
      fecha_liberacion_calidad: null,
      motivo_cierre: null,
    },
    fecha_ultima_carga: null,
    ...cambios,
  }
}

const SIN_RASTREO: Partial<PedidoDetalle> = {
  rastreo: null,
  rastreable: false,
  etapa_viaje: 'SIN_TRACKING',
  estado_calculado: 'SIN_TRACKING',
  estado_cumplimiento: null,
}

function montar(rol: Rol = 'LOGISTICA') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ContextoSesion.Provider
        value={{ token: 't', usuario: { ...USUARIO, rol }, recordada: false }}
      >
        <MemoryRouter initialEntries={['/pedidos/7']}>
          <Routes>
            <Route path="/pedidos/:id" element={<DetallePedido />} />
          </Routes>
        </MemoryRouter>
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
}

function bloque(titulo: string) {
  return within(screen.getByRole('heading', { name: titulo }).closest('section')!)
}

beforeEach(() => {
  vi.mocked(obtenerPedido).mockResolvedValue(detalle())
  vi.mocked(obtenerBitacora).mockResolvedValue([])
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('encabezado', () => {
  it('OC · POS, material, proveedor, cantidad y las dos dimensiones del estado', async () => {
    montar()

    expect(await screen.findByRole('heading', { name: '4500012847 · 10' })).toBeInTheDocument()
    expect(
      screen.getByText('13002006 | Lactosa monohidrato 200M | DFE Pharma | 12 000 kg'),
    ).toBeInTheDocument()
    expect(screen.getByText('En Tránsito')).toBeInTheDocument()
    expect(screen.getByText('A Tiempo')).toBeInTheDocument()
    expect(obtenerPedido).toHaveBeenCalledWith(7)
  })

  it('vuelve al dashboard', async () => {
    montar()

    expect(await screen.findByRole('link', { name: /Volver al dashboard/ })).toHaveAttribute(
      'href',
      '/',
    )
  })

  it('si el pedido no existe, lo dice', async () => {
    vi.mocked(obtenerPedido).mockRejectedValue(
      new AxiosError(
        '404',
        'ERR',
        undefined,
        {},
        {
          status: 404,
          statusText: '',
          headers: {},
          config: {} as never,
          data: { detail: 'No existe el pedido 7.' },
        },
      ),
    )
    montar()

    expect(await screen.findByRole('alert')).toHaveTextContent('No existe el pedido 7.')
  })
})

describe('desglose del cálculo (RF-05)', () => {
  it('la operación de RN-01, sumando por sumando, con el origen de la fecha base', async () => {
    montar()
    await screen.findByRole('heading', { name: 'Desglose del cálculo' })

    const d = bloque('Desglose del cálculo')
    expect(d.getByText('ETA de la fuente de rastreo')).toBeInTheDocument()
    expect(d.getByText('6 días')).toBeInTheDocument()
    expect(d.getByText('0 días')).toBeInTheDocument()
    expect(d.getByText('08/09/2026')).toBeInTheDocument()
    expect(d.getByText('15/09/2026')).toBeInTheDocument()
    expect(d.getByText('+ 7 días')).toBeInTheDocument()
  })

  it('sin fecha base: «No estimable» y la causa, sin inventar', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(
      detalle({
        calculo: {
          ...detalle().calculo,
          origen: null,
          eta_utilizada: null,
          fecha_proyectada: null,
          margen_dias: null,
          desglose: 'Sin fecha base: no hay ETA de ninguna fuente.',
        },
      }),
    )
    montar()
    await screen.findByRole('heading', { name: 'Desglose del cálculo' })

    const d = bloque('Desglose del cálculo')
    expect(d.getByText('Sin fecha de llegada')).toBeInTheDocument()
    expect(d.getByText('No estimable')).toBeInTheDocument()
    expect(d.getByText('Sin fecha base: no hay ETA de ninguna fuente.')).toBeInTheDocument()
  })

  it('avisa si un insumo cambió y falta recalcular, y si el maestro tiene otro lead time', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(
      detalle({
        calculo: {
          ...detalle().calculo,
          al_dia: false,
          lead_time_maestro_dias: 8,
          desglose_actual: '02/09/2026 + 8 d = 10/09/2026',
          margen_dias: -2,
        },
      }),
    )
    montar()

    expect(await screen.findByText(/Un insumo cambió y falta el recálculo/)).toHaveTextContent(
      '02/09/2026 + 8 d = 10/09/2026',
    )
    expect(screen.getByText(/El maestro dice hoy 8 días/)).toBeInTheDocument()
    expect(screen.getByText('− 2 días')).toBeInTheDocument()
  })
})

describe('elemento rastreado y arribo', () => {
  it('identificador, nave, posición, velocidad y la antigüedad de la última consulta', async () => {
    montar()
    await screen.findByRole('heading', { name: 'Elemento rastreado y arribo' })

    const e = bloque('Elemento rastreado y arribo')
    expect(e.getByText('BL MEDU1234567 · MSC BRUNELLA')).toBeInTheDocument()
    expect(e.getByText('Marítima | destino Moín')).toBeInTheDocument()
    expect(e.getByText('10,42 N | 81,90 W | 12,4 nudos')).toBeInTheDocument()
    expect(e.getByText(/hace 3 min/)).toBeInTheDocument()
  })

  it('los tres arribos por separado, con su vacío explicado', async () => {
    montar()
    await screen.findByRole('heading', { name: 'Arribo' })

    const a = bloque('Arribo')
    expect(a.getByText('Sin confirmar')).toBeInTheDocument()
    expect(a.getByText('Sin reportar')).toBeInTheDocument()
    expect(a.getByText('Fuera de la geocerca')).toBeInTheDocument()
  })

  it('con posición, el mapa del envío; sin ella, lo dice', async () => {
    montar()
    expect(await screen.findByRole('heading', { name: 'Mapa del envío' })).toBeInTheDocument()
  })
})

describe('sin identificador: no rastreable (RN-02, §4.7)', () => {
  it('lo dice y ofrece asociar uno a Logística', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(detalle(SIN_RASTREO))
    montar('LOGISTICA')

    expect(await screen.findByText('No rastreable: sin identificador')).toBeInTheDocument()
    expect(
      screen.getByRole('form', { name: 'Asociar identificador de rastreo' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Sin posición conocida/)).toBeInTheDocument()
  })

  it('Planificación ve el estado, pero no el formulario', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(detalle(SIN_RASTREO))
    montar('PLANIFICACION')

    expect(await screen.findByText('La asocian Logística y Compras.')).toBeInTheDocument()
    expect(screen.queryByRole('form')).toBeNull()
  })

  it('asociar exige número y motivo, y deja el pedido rastreable', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(detalle(SIN_RASTREO))
    vi.mocked(asociarReferencia).mockResolvedValue(detalle())
    montar('COMPRAS')

    const boton = await screen.findByRole('button', { name: 'Asociar' })
    expect(boton).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Número'), 'COSU6508789000')
    expect(boton).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/Motivo/), 'El agente envió el BL por correo')
    await userEvent.click(boton)

    expect(asociarReferencia).toHaveBeenCalledWith(7, {
      tipo: 'BL',
      numero: 'COSU6508789000',
      motivo: 'El agente envió el BL por correo',
    })
    expect(await screen.findByText('BL MEDU1234567 · MSC BRUNELLA')).toBeInTheDocument()
  })

  // Solo los tipos de la vía del pedido (21/10/2026).
  it('en un pedido aéreo solo ofrece guías aéreas, la madre primero', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(detalle({ ...SIN_RASTREO, via_transporte: 'AEREO' }))
    montar()

    const tipo = await screen.findByLabelText('Tipo')
    expect(tipo).toHaveValue('MAWB')
    expect(
      within(tipo)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['MAWB (guía madre)', 'HAWB (guía hija)'])
  })

  it('en un pedido marítimo no ofrece guías aéreas', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(detalle(SIN_RASTREO))
    montar()

    const tipo = await screen.findByLabelText('Tipo')
    expect(
      within(tipo)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['BL', 'Contenedor', 'Booking'])
  })

  it('si el backend rechaza la referencia, muestra el motivo', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(detalle(SIN_RASTREO))
    vi.mocked(asociarReferencia).mockRejectedValue(
      new AxiosError(
        '422',
        'ERR',
        undefined,
        {},
        {
          status: 422,
          statusText: '',
          headers: {},
          config: {} as never,
          data: { detail: 'Dígito de control inválido: esperado 0, viene 1.' },
        },
      ),
    )
    montar()

    await userEvent.type(await screen.findByLabelText('Número'), 'MRSU8132491')
    await userEvent.type(screen.getByLabelText(/Motivo/), 'Contenedor del correo del agente')
    await userEvent.click(screen.getByRole('button', { name: 'Asociar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Dígito de control inválido')
  })
})

describe('línea de tiempo', () => {
  it('las intervenciones, la más reciente arriba, con quién y por qué', async () => {
    vi.mocked(obtenerBitacora).mockResolvedValue([
      {
        fecha_hora: '2026-08-09T17:30:00Z',
        usuario: 'logistica',
        nombre_usuario: 'Logística',
        rol: 'LOGISTICA',
        tipo: 'ASOCIACION_TRACKING',
        campo: 'id_elemento_rastreado',
        valor_anterior: null,
        valor_nuevo: 'BL:MEDU1234567',
        motivo: 'BL recibido por correo',
      },
      {
        fecha_hora: '2026-08-20T15:41:00Z',
        usuario: 'compras@gutis.com',
        nombre_usuario: 'Compras',
        rol: 'COMPRAS',
        tipo: 'AJUSTE_MANUAL',
        campo: 'ajuste_manual_dias',
        valor_anterior: '0',
        valor_nuevo: '2',
        motivo: 'La naviera avisó de congestión en Moín',
      },
    ])
    montar()

    const eventos = await screen.findAllByRole('listitem')
    expect(within(eventos[0]).getByText('Ajuste manual de días')).toBeInTheDocument()
    expect(within(eventos[0]).getByText('0 → 2')).toBeInTheDocument()
    expect(within(eventos[0]).getByText('Compras (COMPRAS)')).toBeInTheDocument()
    expect(within(eventos[1]).getByText('Identificador de rastreo asociado')).toBeInTheDocument()
    expect(within(eventos[1]).getByText('— → BL:MEDU1234567')).toBeInTheDocument()
  })

  it('sin intervenciones lo dice', async () => {
    montar()

    expect(await screen.findByText('Sin intervenciones registradas.')).toBeInTheDocument()
  })
})

describe('recepción y cierre', () => {
  it('aparece solo cuando hay recepción o cierre', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(
      detalle({
        cierre: {
          fecha_recepcion_planta: '2026-09-09T15:00:00Z',
          cantidad_recibida: '11950.000',
          liberacion_estimada: { desde: '2026-09-11', hasta: '2026-09-16' },
          cantidad_liberada: null,
          fecha_liberacion_calidad: null,
          motivo_cierre: null,
        },
      }),
    )
    montar()

    const c = await screen.findByRole('heading', { name: 'Recepción y cierre' })
    const s = within(c.closest('section')!)
    expect(s.getByText(/11 950 kg/)).toBeInTheDocument()
    expect(s.getByText('11/09/2026 a 16/09/2026')).toBeInTheDocument()
  })
})

describe('la grilla abre el detalle', () => {
  it('la OC es un enlace al pedido', () => {
    render(
      <MemoryRouter>
        <GrillaPedidos
          pagina={pagina([pedido({ id: 42 })])}
          orden="oc"
          onOrdenar={() => undefined}
          onPaginar={() => undefined}
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: '4500012847' })).toHaveAttribute('href', '/pedidos/42')
  })
})

describe('formatos del detalle', () => {
  it('posición, nudos, cantidad y días con signo', () => {
    expect(formatearPosicion(-12.5, 81.9)).toBe('12,50 S | 81,90 E')
    expect(formatearNudos('12.4')).toBe('12,4 nudos')
    expect(formatearNudos(null)).toBeNull()
    expect(formatearCantidad('1.500', 'UN')).toBe('1,5 un')
    expect(formatearDiasConSigno(1)).toBe('+ 1 día')
    expect(formatearDiasConSigno(0)).toBe('0 días')
  })

  it('antigüedad de una lectura', () => {
    const ahora = new Date('2026-10-15T12:00:00Z')
    expect(haceCuanto('2026-10-15T11:59:40Z', ahora)).toBe('ahora')
    expect(haceCuanto('2026-10-15T09:00:00Z', ahora)).toBe('hace 3 h')
    expect(haceCuanto('2026-10-14T11:00:00Z', ahora)).toBe('hace 1 día')
    expect(haceCuanto('2026-10-10T11:00:00Z', ahora)).toBe('hace 5 días')
    expect(haceCuanto(null)).toBeNull()
    expect(haceCuanto('x')).toBeNull()
  })
})

describe('servicio', () => {
  it('pide el detalle y la bitácora, y asocia por POST', async () => {
    const real = await vi.importActual<typeof import('@/services/pedidos')>('@/services/pedidos')
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: {} })
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} })

    await real.obtenerPedido(7)
    await real.obtenerBitacora(7)
    await real.asociarReferencia(7, { tipo: 'BL', numero: 'X', motivo: 'motivo' })

    expect(get).toHaveBeenNthCalledWith(1, '/api/v1/pedidos/7')
    expect(get).toHaveBeenNthCalledWith(2, '/api/v1/pedidos/7/bitacora')
    expect(post).toHaveBeenCalledWith('/api/v1/pedidos/7/referencia', {
      tipo: 'BL',
      numero: 'X',
      motivo: 'motivo',
    })
  })
})
