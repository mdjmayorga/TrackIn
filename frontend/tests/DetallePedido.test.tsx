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
import {
  asociarReferencia,
  corregirReferencia,
  obtenerBitacora,
  obtenerPedido,
} from '@/services/pedidos'
import type { PedidoDetalle, Rol } from '@/types/api'
import {
  formatearCantidad,
  formatearDiasConSigno,
  formatearNudos,
  formatearPosicion,
} from '@/utils/detalle'
import { haceCuanto } from '@/utils/fechas'
import { seguirGuiaMadre } from '@/services/acciones'

import { pagina, pedido } from './fixtures'
import { USUARIO } from './sesion.test'

vi.mock('@/services/acciones', async (original) => ({
  ...(await original<typeof import('@/services/acciones')>()),
  seguirGuiaMadre: vi.fn(),
}))

vi.mock('@/services/pedidos', async (original) => ({
  ...(await original<typeof import('@/services/pedidos')>()),
  obtenerPedido: vi.fn(),
  obtenerBitacora: vi.fn(),
  asociarReferencia: vi.fn(),
  corregirReferencia: vi.fn(),
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
      transbordos: [],
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

  it('el país de origen normalizado, o que no hay dato (US-44)', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(
      detalle({ pais_origen: { codigo: 'IN', nombre: 'India' } }),
    )
    montar()

    expect(await screen.findByText(/País de origen:/)).toHaveTextContent('País de origen: India')
  })

  it('sin país de origen lo dice', async () => {
    montar()

    expect(await screen.findByText(/País de origen:/)).toHaveTextContent('País de origen: sin dato')
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

  it('los transbordos que informó ShipsGo, con puerto, fecha y los previstos (US-30)', async () => {
    const base = detalle()
    vi.mocked(obtenerPedido).mockResolvedValue({
      ...base,
      rastreo: {
        ...base.rastreo!,
        transbordos: [
          {
            vehiculo_anterior: 'MAERSK CHACHAI',
            vehiculo_nuevo: 'MAERSK NACALA',
            puerto: 'COCTG',
            puerto_nombre: 'CARTAGENA (COLOMBIA)',
            fecha: '2026-09-07T17:00:00Z',
            ocurrido: true,
          },
          {
            vehiculo_anterior: 'MAERSK NACALA',
            vehiculo_nuevo: 'MAERSK MONTE PASCOAL',
            puerto: 'PAMIT',
            puerto_nombre: null,
            fecha: null,
            ocurrido: false,
          },
        ],
      },
    })
    montar()
    await screen.findByRole('heading', { name: 'Elemento rastreado y arribo' })

    const e = bloque('Elemento rastreado y arribo')
    expect(
      e.getByText('MAERSK CHACHAI → MAERSK NACALA en CARTAGENA (COLOMBIA), 07/09/2026'),
    ).toBeInTheDocument()
    expect(
      e.getByText('MAERSK NACALA → MAERSK MONTE PASCOAL en PAMIT (previsto)'),
    ).toBeInTheDocument()
  })

  it('una guía hija con guía madre resuelta ofrece seguir por la madre (US-30)', async () => {
    const base = detalle()
    const hija = {
      ...base,
      via_transporte: 'AEREO' as const,
      rastreo: {
        ...base.rastreo!,
        tipo: 'HAWB',
        referencia: 'ZIVHYD017',
        via_transporte: 'AEREO' as const,
        nombre: null,
        guia_madre: '176-12345675',
      },
    }
    vi.mocked(obtenerPedido).mockResolvedValue(hija)
    vi.mocked(seguirGuiaMadre).mockResolvedValue({
      ...hija,
      rastreo: { ...hija.rastreo, tipo: 'MAWB', referencia: '176-12345675', guia_madre: null },
    })
    montar()

    await userEvent.click(await screen.findByRole('button', { name: 'Seguir por la guía madre' }))
    expect(seguirGuiaMadre).not.toHaveBeenCalled()
    const formulario = within(screen.getByRole('form', { name: 'Seguir por la guía madre' }))
    // Viene la de TICA: se confirma sin escribir, y no se manda como «escrita a mano».
    expect(formulario.getByLabelText(/Guía madre/)).toHaveValue('176-12345675')
    await userEvent.click(formulario.getByRole('button', { name: 'Confirmar' }))

    expect(seguirGuiaMadre).toHaveBeenCalledWith(hija.id, { numero: null, motivo: null })
  })

  it('sin la de TICA, la guía madre se escribe a mano (29/10)', async () => {
    const base = detalle()
    const hija = {
      ...base,
      via_transporte: 'AEREO' as const,
      rastreo: { ...base.rastreo!, tipo: 'HAWB', referencia: 'ZIVHYD017', guia_madre: null },
    }
    vi.mocked(obtenerPedido).mockResolvedValue(hija)
    vi.mocked(seguirGuiaMadre).mockResolvedValue(hija)
    montar()

    await userEvent.click(await screen.findByRole('button', { name: 'Indicar guía madre' }))
    const formulario = within(screen.getByRole('form', { name: 'Indicar guía madre' }))
    expect(formulario.getByRole('button', { name: 'Confirmar' })).toBeDisabled()
    await userEvent.type(formulario.getByLabelText(/Guía madre/), '020-50685434')
    await userEvent.click(formulario.getByRole('button', { name: 'Confirmar' }))

    expect(seguirGuiaMadre).toHaveBeenCalledWith(hija.id, {
      numero: '020-50685434',
      motivo: null,
    })
  })

  it('una guía madre que vino de una hija se puede corregir (29/10)', async () => {
    const base = detalle()
    const madre = {
      ...base,
      via_transporte: 'AEREO' as const,
      rastreo: {
        ...base.rastreo!,
        tipo: 'MAWB',
        referencia: '176-12345675',
        guia_madre: null,
        guia_hija: 'ZIVHYD017',
      },
    }
    vi.mocked(obtenerPedido).mockResolvedValue(madre)
    vi.mocked(seguirGuiaMadre).mockResolvedValue(madre)
    montar()

    expect(await screen.findByText('Viene de la guía hija ZIVHYD017')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Corregir guía madre' }))
    const formulario = within(screen.getByRole('form', { name: 'Corregir guía madre' }))
    expect(formulario.getByLabelText(/Guía madre/)).toHaveValue('')
    await userEvent.type(formulario.getByLabelText(/Guía madre/), '020-50685434')
    await userEvent.click(formulario.getByRole('button', { name: 'Confirmar' }))

    expect(seguirGuiaMadre).toHaveBeenCalledWith(madre.id, {
      numero: '020-50685434',
      motivo: null,
    })
  })

  it('una referencia mal escrita se corrige desde el detalle (29/10)', async () => {
    const base = detalle()
    const conError = {
      ...base,
      rastreo: { ...base.rastreo!, tipo: 'BL', referencia: 'BLMAEU274029064' },
    }
    vi.mocked(obtenerPedido).mockResolvedValue(conError)
    vi.mocked(corregirReferencia).mockResolvedValue(conError)
    montar()

    await userEvent.click(await screen.findByRole('button', { name: 'Corregir referencia' }))
    const formulario = within(screen.getByRole('form', { name: 'Corregir referencia' }))
    const numero = formulario.getByLabelText('Número')
    expect(numero).toHaveValue('BLMAEU274029064')
    expect(formulario.getByLabelText('Tipo')).toHaveValue('BL')
    // Sin cambiar nada no hay qué corregir; el motivo es opcional.
    expect(formulario.getByRole('button', { name: 'Corregir' })).toBeDisabled()
    await userEvent.clear(numero)
    await userEvent.type(numero, 'MAEU274029064')
    await userEvent.click(formulario.getByRole('button', { name: 'Corregir' }))

    expect(corregirReferencia).toHaveBeenCalledWith(conError.id, {
      tipo: 'BL',
      numero: 'MAEU274029064',
      motivo: null,
    })
  })

  it('Planificación no ve «Corregir referencia»', async () => {
    montar('PLANIFICACION')
    await screen.findByRole('heading', { name: 'Elemento rastreado y arribo' })

    expect(screen.queryByRole('button', { name: 'Corregir referencia' })).toBeNull()
  })

  it('una guía madre cargada directo, sin guía hija, no ofrece corregir', async () => {
    const base = detalle()
    vi.mocked(obtenerPedido).mockResolvedValue({
      ...base,
      rastreo: { ...base.rastreo!, tipo: 'MAWB', referencia: '176-12345675', guia_hija: null },
    })
    montar()
    await screen.findByRole('heading', { name: 'Elemento rastreado y arribo' })

    expect(screen.queryByRole('button', { name: 'Corregir guía madre' })).toBeNull()
  })

  it('Planificación no ve la opción de la guía madre', async () => {
    const base = detalle()
    vi.mocked(obtenerPedido).mockResolvedValue({
      ...base,
      rastreo: { ...base.rastreo!, tipo: 'HAWB', guia_madre: '176-12345675' },
    })
    montar('PLANIFICACION')
    await screen.findByRole('heading', { name: 'Elemento rastreado y arribo' })

    expect(screen.queryByRole('button', { name: 'Seguir por la guía madre' })).toBeNull()
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

  it('con el token del Embed, el mapa en vivo de ShipsGo en lugar del propio (21/10)', async () => {
    vi.stubEnv('VITE_SHIPSGO_EMBED_TOKEN', 'tok')
    try {
      montar()

      const mapa = await screen.findByTitle('Mapa en vivo de ShipsGo para MEDU1234567')
      expect(mapa.getAttribute('src')).toContain('query=MEDU1234567')
      expect(screen.queryByRole('heading', { name: 'Mapa del envío' })).toBeNull()
    } finally {
      vi.stubEnv('VITE_SHIPSGO_EMBED_TOKEN', '')
    }
  })
})

describe('mapa de un envío aéreo (02/11/2026)', () => {
  /** La guía `020-05128546`: ShipsGo no dibujaba el LH518 y TrackIn lo reconstruyó. */
  function aereo() {
    const base = detalle()
    return {
      ...base,
      via_transporte: 'AEREO' as const,
      rastreo: {
        ...base.rastreo!,
        tipo: 'MAWB',
        referencia: '020-05128546',
        via_transporte: 'AEREO' as const,
        trayecto: [
          {
            vuelo: 'LH8401',
            origen: 'PVG',
            destino: 'FRA',
            salida: '2026-10-27T02:01:00Z',
            llegada: '2026-10-27T15:23:00Z',
            ruta: [
              [31.1, 121.8],
              [50.0, 8.6],
            ] as Array<[number, number]>,
          },
          {
            vuelo: 'LH518',
            origen: 'FRA',
            destino: 'SJO',
            salida: '2026-10-30T13:33:00Z',
            llegada: '2026-10-31T01:09:00Z',
            ruta: [
              [50.0, 8.6],
              [10.0, -84.2],
            ] as Array<[number, number]>,
          },
        ],
        posicion_aerea: {
          latitud: 10.0,
          longitud: -84.2,
          situacion: 'FINALIZADO' as const,
          vuelo: 'LH518',
          lugar: 'SJO',
        },
      },
    }
  }

  it('dibuja la ruta propia con todos los vuelos, aunque haya token del Embed', async () => {
    vi.stubEnv('VITE_SHIPSGO_EMBED_TOKEN', 'tok')
    try {
      vi.mocked(obtenerPedido).mockResolvedValue(aereo())
      montar()

      expect(await screen.findByRole('heading', { name: 'Mapa del envío' })).toBeInTheDocument()
      expect(screen.queryByTitle(/Mapa en vivo de ShipsGo/)).toBeNull()
      expect(screen.getByText(/Vuelo LH518 concluido en SJO/)).toHaveTextContent(
        'PVG → FRA · FRA → SJO',
      )
    } finally {
      vi.stubEnv('VITE_SHIPSGO_EMBED_TOKEN', '')
    }
  })

  it('en un transbordo dice dónde espera', async () => {
    const guia = aereo()
    vi.mocked(obtenerPedido).mockResolvedValue({
      ...guia,
      rastreo: {
        ...guia.rastreo,
        posicion_aerea: {
          latitud: 50.0,
          longitud: 8.6,
          situacion: 'EN_TIERRA' as const,
          vuelo: 'LH8401',
          lugar: 'FRA',
        },
      },
    })
    montar()

    expect(await screen.findByText(/En tierra en FRA, esperando vuelo/)).toBeInTheDocument()
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

  it('asociar exige el número, y deja el pedido rastreable', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(detalle(SIN_RASTREO))
    vi.mocked(asociarReferencia).mockResolvedValue(detalle())
    montar('COMPRAS')

    const boton = await screen.findByRole('button', { name: 'Asociar' })
    expect(boton).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Número'), 'COSU6508789000')
    await userEvent.type(screen.getByLabelText(/Motivo/), 'El agente envió el BL por correo')
    await userEvent.click(boton)

    expect(asociarReferencia).toHaveBeenCalledWith(7, {
      tipo: 'BL',
      numero: 'COSU6508789000',
      motivo: 'El agente envió el BL por correo',
    })
    expect(await screen.findByText('BL MEDU1234567 · MSC BRUNELLA')).toBeInTheDocument()
  })

  // El motivo es opcional en todo el sistema (02/11/2026).
  it('asociar sin motivo también se puede', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(detalle(SIN_RASTREO))
    vi.mocked(asociarReferencia).mockResolvedValue(detalle())
    montar('COMPRAS')

    expect(await screen.findByLabelText('Motivo (opcional)')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Número'), 'COSU6508789000')
    await userEvent.click(screen.getByRole('button', { name: 'Asociar' }))

    expect(asociarReferencia).toHaveBeenCalledWith(7, {
      tipo: 'BL',
      numero: 'COSU6508789000',
      motivo: null,
    })
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

    expect(await screen.findByText('Sin intervenciones ni hitos registrados.')).toBeInTheDocument()
  })

  it('intercala los hitos del viaje de ShipsGo con las intervenciones (US-29)', async () => {
    const hito = (fecha_hora: string, campo: string, motivo: string, valor_nuevo: string) => ({
      fecha_hora,
      usuario: 'shipsgo',
      nombre_usuario: 'ShipsGo (automático)',
      rol: 'SISTEMA' as const,
      tipo: 'HITO_VIAJE',
      campo,
      valor_anterior: null,
      valor_nuevo,
      motivo,
    })
    vi.mocked(obtenerBitacora).mockResolvedValue([
      hito(
        '2026-10-27T02:01:00Z',
        'DEP',
        'Salida del origen: despegó de Shanghai Pudong International Airport (PVG), China',
        'Vuelo LH8401',
      ),
      {
        fecha_hora: '2026-10-28T15:00:00Z',
        usuario: 'compras@gutis.com',
        nombre_usuario: 'Compras',
        rol: 'COMPRAS',
        tipo: 'AJUSTE_MANUAL',
        campo: 'ajuste_manual_dias',
        valor_anterior: '0',
        valor_nuevo: '2',
        motivo: 'Aviso del agente',
      },
      hito(
        '2026-10-31T01:09:00Z',
        'ARR',
        'Llegada a destino: aterrizó en Juan Santamaría International Airport (SJO), Costa Rica',
        'Vuelo LH518',
      ),
    ])
    montar()

    const eventos = await screen.findAllByRole('listitem')
    // La más reciente arriba: la llegada, el ajuste y la salida del origen al final.
    expect(eventos[0]).toHaveTextContent(/^.*Llegada a destino: aterrizó en .*SJO.*Vuelo LH518/)
    expect(within(eventos[0]).getByText('ShipsGo (automático)')).toBeInTheDocument()
    expect(within(eventos[1]).getByText('Ajuste manual de días')).toBeInTheDocument()
    expect(eventos[2]).toHaveTextContent('Salida del origen: despegó de')
    // Un hito no es una intervención: sin comillas de motivo ni «— →».
    expect(eventos[2]).not.toHaveTextContent('«')
    expect(eventos[2]).not.toHaveTextContent('—')
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

describe('dar de alta en ShipsGo desde el detalle (US-55)', () => {
  const PENDIENTE = (base: PedidoDetalle): Partial<PedidoDetalle> => ({
    rastreo: {
      ...base.rastreo!,
      tipo: 'BL',
      referencia: 'COSU6508789000',
      ultima_consulta_exitosa: null,
    },
  })

  it('una referencia de ShipsGo que nunca respondió ofrece el alta a Compras', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(detalle(PENDIENTE(detalle())))
    montar('COMPRAS')

    expect(await screen.findByRole('link', { name: 'Dar de alta en ShipsGo' })).toHaveAttribute(
      'href',
      '/shipsgo/altas?ref=COSU6508789000',
    )
  })

  it('a Logística no, y a una referencia que ya responde tampoco', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(detalle(PENDIENTE(detalle())))
    montar('LOGISTICA')
    await screen.findByText(/COSU6508789000/)
    expect(screen.queryByRole('link', { name: 'Dar de alta en ShipsGo' })).toBeNull()
  })

  it('con la referencia ya en ShipsGo no se ofrece', async () => {
    vi.mocked(obtenerPedido).mockResolvedValue(detalle())
    montar('COMPRAS')
    await screen.findByText(/MEDU1234567/)
    expect(screen.queryByRole('link', { name: 'Dar de alta en ShipsGo' })).toBeNull()
  })
})
