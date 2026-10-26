import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError } from 'axios'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ContextoSesion } from '@/auth/contexto'
import type { SesionGuardada } from '@/auth/sesion'
import AltasShipsGo from '@/pages/AltasShipsGo'
import { darDeAltaEnShipsGo, obtenerAltasPendientes, registrarPaquete } from '@/services/shipsgo'
import type { AltasPendientes, EstadoCreditos, ReferenciaPendiente, Rol } from '@/types/api'

import { USUARIO } from './sesion.test'

vi.mock('@/services/shipsgo', async (original) => ({
  ...(await original<typeof import('@/services/shipsgo')>()),
  obtenerAltasPendientes: vi.fn(),
  darDeAltaEnShipsGo: vi.fn(),
  registrarPaquete: vi.fn(),
}))

function ref(cambios: Partial<ReferenciaPendiente> = {}): ReferenciaPendiente {
  return {
    tipo: 'BL',
    numero: 'COSU6508789000',
    via_transporte: 'MARITIMO',
    lineas: [
      { id_pedido: 1, oc_numero: '4577000001', posicion_oc: 10 },
      { id_pedido: 2, oc_numero: '4577000001', posicion_oc: 20 },
    ],
    cubierta: null,
    aerolinea: null,
    ofrecible: true,
    ...cambios,
  }
}

const MAWB = ref({
  tipo: 'MAWB',
  numero: '020-50685434',
  via_transporte: 'AEREO',
  lineas: [{ id_pedido: 3, oc_numero: '4577000003', posicion_oc: 10 }],
  cubierta: true,
  aerolinea: 'LUFTHANSA CARGO',
})
const SIN_COBERTURA = ref({
  tipo: 'MAWB',
  numero: '111-12345675',
  via_transporte: 'AEREO',
  lineas: [{ id_pedido: 4, oc_numero: '4577000004', posicion_oc: 10 }],
  cubierta: false,
  ofrecible: false,
})

function saldo(cambios: Partial<EstadoCreditos> = {}): EstadoCreditos {
  return {
    nivel: 'OK',
    mensaje: 'Quedan 40 de 49 créditos de ShipsGo.',
    paquete: {
      cantidad: 49,
      saldo_arrastrado: 0,
      comprado_en: '2026-09-23',
      vence_en: null,
      registrado_en: '2026-10-26T15:00:00Z',
      registrado_por: 'Compras',
    },
    disponible: 49,
    consumidos: 9,
    saldo: 40,
    porcentaje_consumido: 9 / 49,
    dias_para_vencer: null,
    recompra_minima: 25,
    ...cambios,
  }
}

function datos(cambios: Partial<AltasPendientes> = {}): AltasPendientes {
  return {
    pendientes: [ref(), MAWB, SIN_COBERTURA],
    creditos_necesarios: 2,
    altas_hoy: 0,
    altas_maximas_dia: 5,
    creditos: saldo(),
    ...cambios,
  }
}

function montar(rol: Rol = 'COMPRAS', ruta = '/shipsgo/altas') {
  const sesion: SesionGuardada = { token: 't', usuario: { ...USUARIO, rol }, recordada: false }
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <ContextoSesion.Provider value={sesion}>
        <MemoryRouter initialEntries={[ruta]}>
          <Routes>
            <Route path="/shipsgo/altas" element={<AltasShipsGo />} />
            <Route path="/" element={<p>Panel</p>} />
          </Routes>
        </MemoryRouter>
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
}

const casilla = (nombre: string) => screen.getByRole('checkbox', { name: `Dar de alta ${nombre}` })

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.mocked(obtenerAltasPendientes).mockReset()
  vi.mocked(darDeAltaEnShipsGo).mockReset()
  vi.mocked(registrarPaquete).mockReset()
})

describe('Altas en ShipsGo (US-55)', () => {
  it('un rol que no es Compras ni Administrador vuelve al panel', () => {
    montar('LOGISTICA')

    expect(screen.getByText('Panel')).toBeInTheDocument()
    expect(obtenerAltasPendientes).not.toHaveBeenCalled()
  })

  it('trae marcado todo lo que se puede dar de alta, y dice cuántos créditos son', async () => {
    vi.mocked(obtenerAltasPendientes).mockResolvedValue(datos())
    montar()

    expect(await screen.findByRole('row', { name: 'BL COSU6508789000' })).toBeInTheDocument()
    expect(casilla('BL COSU6508789000')).toBeChecked()
    expect(casilla('MAWB 020-50685434')).toBeChecked()
    // La MAWB sin aerolínea se muestra pero no se ofrece: devolvería vacío.
    expect(casilla('MAWB 111-12345675')).toBeDisabled()
    expect(casilla('MAWB 111-12345675')).not.toBeChecked()
    expect(screen.getByText(/Sin cobertura en ShipsGo/)).toBeInTheDocument()
    // Un BL de dos líneas es un crédito.
    expect(screen.getByText('2 referencias marcadas: 2 créditos.')).toBeInTheDocument()
    const filaBl = within(screen.getByRole('row', { name: 'BL COSU6508789000' }))
    expect(filaBl.getByRole('link', { name: '4577000001 - 20' })).toHaveAttribute(
      'href',
      '/pedidos/2',
    )
  })

  it('desde el detalle de un pedido viene marcada solo su referencia', async () => {
    vi.mocked(obtenerAltasPendientes).mockResolvedValue(datos())
    montar('COMPRAS', '/shipsgo/altas?ref=020-50685434')

    await screen.findByRole('row', { name: 'MAWB 020-50685434' })
    expect(casilla('MAWB 020-50685434')).toBeChecked()
    expect(casilla('BL COSU6508789000')).not.toBeChecked()
    expect(screen.getByText('1 referencia marcada: 1 crédito.')).toBeInTheDocument()
  })

  it('no gasta nada sin confirmar, y con la confirmación da de alta lo marcado', async () => {
    vi.mocked(obtenerAltasPendientes).mockResolvedValue(datos())
    vi.mocked(darDeAltaEnShipsGo).mockResolvedValue({
      resultados: [
        {
          tipo: 'BL',
          numero: 'COSU6508789000',
          registrado: true,
          motivo: 'registrado',
          consumio_credito: true,
        },
        {
          tipo: 'MAWB',
          numero: '020-50685434',
          registrado: true,
          motivo: 'registrado',
          consumio_credito: true,
        },
      ],
      creditos_consumidos: 2,
    })
    montar()

    await userEvent.click(await screen.findByRole('button', { name: 'Dar de alta (2 créditos)' }))
    expect(darDeAltaEnShipsGo).not.toHaveBeenCalled()
    expect(screen.getByRole('alertdialog')).toHaveTextContent(
      'Se van a gastar 2 créditos de ShipsGo. No se puede deshacer.',
    )

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar: gastar 2 créditos' }))

    expect(darDeAltaEnShipsGo).toHaveBeenCalledWith({
      referencias: [
        { tipo: 'BL', numero: 'COSU6508789000' },
        { tipo: 'MAWB', numero: '020-50685434' },
      ],
      creditos_confirmados: 2,
      superar_tope: false,
      aceptar_saldo: false,
    })
    expect(await screen.findByRole('status', { name: 'Resultado de las altas' })).toHaveTextContent(
      'Altas hechas: 2 de 2. Créditos gastados: 2.',
    )
  })

  it('desmarcar una baja el costo', async () => {
    vi.mocked(obtenerAltasPendientes).mockResolvedValue(datos())
    montar()

    await userEvent.click(
      await screen.findByRole('checkbox', { name: 'Dar de alta BL COSU6508789000' }),
    )

    expect(screen.getByText('1 referencia marcada: 1 crédito.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Dar de alta (1 crédito)' })).toBeEnabled()
  })

  it('pasar el tope diario exige aceptarlo antes de poder seguir', async () => {
    vi.mocked(obtenerAltasPendientes).mockResolvedValue(
      datos({ altas_hoy: 4, altas_maximas_dia: 5 }),
    )
    vi.mocked(darDeAltaEnShipsGo).mockResolvedValue({ resultados: [], creditos_consumidos: 0 })
    montar()

    const boton = await screen.findByRole('button', { name: 'Dar de alta (2 créditos)' })
    expect(boton).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox', { name: /Entiendo que lo supero/ }))
    expect(boton).toBeEnabled()

    await userEvent.click(boton)
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar: gastar 2 créditos' }))

    expect(vi.mocked(darDeAltaEnShipsGo).mock.calls[0][0].superar_tope).toBe(true)
  })

  it('sin nada pendiente, lo dice', async () => {
    vi.mocked(obtenerAltasPendientes).mockResolvedValue(
      datos({ pendientes: [], creditos_necesarios: 0 }),
    )
    montar()

    expect(await screen.findByText(/No hay referencias pendientes de alta/)).toBeInTheDocument()
  })

  it('si ShipsGo no responde, muestra el motivo', async () => {
    vi.mocked(obtenerAltasPendientes).mockRejectedValue(
      new AxiosError(
        '503',
        'ERR',
        undefined,
        {},
        {
          status: 503,
          statusText: '',
          headers: {},
          config: {} as never,
          data: { detail: 'ShipsGo no está configurado en el servidor (falta SHIPSGO_API_TOKEN).' },
        },
      ),
    )
    montar()

    expect(await screen.findByRole('alert')).toHaveTextContent('falta SHIPSGO_API_TOKEN')
  })
})

describe('Créditos de ShipsGo (US-57)', () => {
  it('muestra el saldo del paquete vigente', async () => {
    vi.mocked(obtenerAltasPendientes).mockResolvedValue(datos())
    montar()

    const seccion = within(await screen.findByRole('region', { name: 'Créditos de ShipsGo' }))
    expect(seccion.getByText(/de 49 disponibles · 9 usados/)).toBeInTheDocument()
    expect(seccion.getByText(/sin vencimiento/)).toBeInTheDocument()
    // Con el saldo en orden no hay aviso.
    expect(seccion.queryByRole('status')).not.toBeInTheDocument()
  })

  it('si el saldo no alcanza, exige aceptarlo antes de gastar', async () => {
    vi.mocked(obtenerAltasPendientes).mockResolvedValue(
      datos({ creditos: saldo({ nivel: 'BAJO', saldo: 1, consumidos: 48 }) }),
    )
    vi.mocked(darDeAltaEnShipsGo).mockResolvedValue({ resultados: [], creditos_consumidos: 0 })
    montar()

    const boton = await screen.findByRole('button', { name: 'Dar de alta (2 créditos)' })
    expect(boton).toBeDisabled()
    await userEvent.click(
      screen.getByRole('checkbox', { name: /El saldo registrado es 1 y estas altas necesitan 2/ }),
    )
    await userEvent.click(boton)
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar: gastar 2 créditos' }))

    expect(vi.mocked(darDeAltaEnShipsGo).mock.calls[0][0].aceptar_saldo).toBe(true)
  })

  it('sin paquete registrado no frena el alta, y pide registrarlo', async () => {
    vi.mocked(obtenerAltasPendientes).mockResolvedValue(
      datos({
        creditos: saldo({
          nivel: 'SIN_PAQUETE',
          mensaje: 'No hay un paquete de créditos de ShipsGo registrado.',
          paquete: null,
          disponible: 0,
          consumidos: 0,
          saldo: 0,
          recompra_minima: null,
        }),
      }),
    )
    montar()

    expect(await screen.findByRole('button', { name: 'Dar de alta (2 créditos)' })).toBeEnabled()
    expect(screen.getByRole('status')).toHaveTextContent('No hay un paquete')
  })

  it('registra un paquete y anticipa si se arrastra el saldo', async () => {
    vi.mocked(obtenerAltasPendientes).mockResolvedValue(datos())
    vi.mocked(registrarPaquete).mockResolvedValue(saldo())
    montar()

    await userEvent.click(await screen.findByRole('button', { name: 'Registrar paquete comprado' }))
    const formulario = within(screen.getByRole('form', { name: 'Registrar paquete comprado' }))
    await userEvent.type(formulario.getByLabelText('Créditos comprados'), '1100')
    await userEvent.clear(formulario.getByLabelText('Fecha de compra'))
    await userEvent.type(formulario.getByLabelText('Fecha de compra'), '2026-11-06')
    await userEvent.type(formulario.getByLabelText(/^Vence/), '2027-11-06')
    await userEvent.type(formulario.getByLabelText(/^Nuevo tope diario/), '30')

    expect(
      formulario.getByText('Se suman los 40 que quedan: el paquete nuevo arranca con 1140.'),
    ).toBeInTheDocument()

    await userEvent.click(formulario.getByRole('button', { name: 'Registrar' }))

    expect(registrarPaquete).toHaveBeenCalledWith({
      cantidad: 1100,
      comprado_en: '2026-11-06',
      vence_en: '2027-11-06',
      altas_maximas_dia: 30,
      nota: null,
    })
  })

  it('una recompra chica avisa que el saldo no se arrastra', async () => {
    vi.mocked(obtenerAltasPendientes).mockResolvedValue(datos())
    montar()

    await userEvent.click(await screen.findByRole('button', { name: 'Registrar paquete comprado' }))
    await userEvent.type(screen.getByLabelText('Créditos comprados'), '20')

    expect(screen.getByText(/hay que comprar al menos 25/)).toBeInTheDocument()
  })
})
