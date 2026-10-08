import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError } from 'axios'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ContextoSesion } from '@/auth/contexto'
import type { SesionGuardada } from '@/auth/sesion'
import { InformeCarga } from '@/components/InformeCarga'
import Cargas from '@/pages/Cargas'
import { api } from '@/services/api'
import { listarCargas, obtenerCarga, subirZtracking } from '@/services/cargas'
import type { CargaDetalle, Rol } from '@/types/api'
import { formatearFechaHora } from '@/utils/fechas'
import { nombreMotivo } from '@/utils/motivosCarga'

import { USUARIO } from './sesion.test'

vi.mock('@/services/cargas', async (original) => ({
  ...(await original<typeof import('@/services/cargas')>()),
  listarCargas: vi.fn(),
  obtenerCarga: vi.fn(),
  subirZtracking: vi.fn(),
}))

function carga(cambios: Partial<CargaDetalle> = {}): CargaDetalle {
  return {
    id: 7,
    archivo: '2026 - OCTUBRE - WK40.xlsx',
    tamano_bytes: 349_000,
    realizada_en: '2026-10-08T15:30:00Z',
    estado: 'APLICADA',
    motivo_rechazo: null,
    usuario: { usuario: 'compras@gutis.com', nombre_completo: 'Compras' },
    recibidas: 465,
    insertadas: 12,
    actualizadas: 80,
    sin_cambios: 0,
    ausentes: 3,
    no_entraron: 373,
    entraron_sin_rastreo: 0,
    por_motivo: { sin_via_transporte: 273, sin_destino_resoluble: 100 },
    incidencias: [
      {
        clave: '4500016171-90',
        motivo: 'sin_via_transporte',
        detalle: 'la vía «N/A» no es Aéreo, Marítimo ni Terrestre',
        consecuencia: 'no_entro',
      },
    ],
    avisos: [],
    ...cambios,
  }
}

function montar(rol: Rol = 'COMPRAS') {
  const sesion: SesionGuardada = { token: 't', usuario: { ...USUARIO, rol }, recordada: false }
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ContextoSesion.Provider value={sesion}>
        <MemoryRouter>
          <Cargas />
        </MemoryRouter>
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
}

function excel(nombre = 'WK40.xlsx') {
  return new File(['contenido'], nombre, {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
}

beforeEach(() => {
  vi.mocked(listarCargas).mockResolvedValue([])
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('subir el Z-tracking', () => {
  it('sube el archivo y muestra el informe sin volver a pedirlo', async () => {
    vi.mocked(subirZtracking).mockResolvedValue(carga())
    montar()

    const boton = screen.getByRole('button', { name: 'Cargar' })
    expect(boton).toBeDisabled()
    await userEvent.upload(screen.getByLabelText('Archivo Z-tracking'), excel())
    await userEvent.click(boton)

    expect(vi.mocked(subirZtracking).mock.calls[0][0]).toMatchObject({ name: 'WK40.xlsx' })
    expect(
      await screen.findByRole('heading', { name: '2026 - OCTUBRE - WK40.xlsx' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Qué corregir en SAP' })).toBeInTheDocument()
    expect(obtenerCarga).not.toHaveBeenCalled()
  })

  it('si el archivo no es un Z-tracking, muestra el motivo del backend', async () => {
    const respuesta = {
      status: 422,
      statusText: '',
      headers: {},
      config: {} as never,
      data: { detail: '«otro.xlsx» no parece el Z-tracking: le faltan las hojas IDA.' },
    }
    vi.mocked(subirZtracking).mockRejectedValue(
      new AxiosError('422', 'ERR', undefined, {}, respuesta),
    )
    montar()

    await userEvent.upload(screen.getByLabelText('Archivo Z-tracking'), excel('otro.xlsx'))
    await userEvent.click(screen.getByRole('button', { name: 'Cargar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('le faltan las hojas IDA')
  })

  it('Planificación ve el historial, pero no puede subir', async () => {
    vi.mocked(listarCargas).mockResolvedValue([carga()])
    montar('PLANIFICACION')

    expect(screen.queryByLabelText('Archivo Z-tracking')).toBeNull()
    expect(screen.getByText(/Las cargas las hacen Compras y el Administrador/)).toBeInTheDocument()
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })
})

describe('historial', () => {
  it('lista las cargas y abre el informe de la que se elige', async () => {
    vi.mocked(listarCargas).mockResolvedValue([
      carga(),
      carga({ id: 6, archivo: 'roto.xlsx', estado: 'RECHAZADA', motivo_rechazo: 'Dañado.' }),
    ])
    vi.mocked(obtenerCarga).mockResolvedValue(
      carga({ id: 6, archivo: 'roto.xlsx', estado: 'RECHAZADA', motivo_rechazo: 'Dañado.' }),
    )
    montar()

    const tabla = await screen.findByRole('table')
    const filas = within(tabla).getAllByRole('row')
    expect(within(filas[2]).getByText('Rechazada')).toBeInTheDocument()
    expect(within(filas[2]).getAllByText('–')).toHaveLength(3)

    await userEvent.click(screen.getByRole('button', { name: 'roto.xlsx' }))

    expect(obtenerCarga).toHaveBeenCalledWith(6)
    expect(await screen.findByText(/No se cargó nada\. Dañado\./)).toBeInTheDocument()
  })

  it('sin cargas lo dice', async () => {
    montar()

    expect(await screen.findByText('Todavía no se ha cargado ningún archivo.')).toBeInTheDocument()
  })
})

describe('informe de la carga', () => {
  it('muestra los totales y qué corregir en SAP', () => {
    render(<InformeCarga carga={carga()} />)

    expect(screen.getByText('Líneas en el archivo').nextSibling).toHaveTextContent('465')
    expect(screen.getByText('No entraron').nextSibling).toHaveTextContent('373')
    expect(screen.getByText(/Complete la vía/)).toBeInTheDocument()
    expect(screen.getByText('4500016171-90')).toBeInTheDocument()
  })

  it('con muchas líneas muestra las primeras y deja ver todas', async () => {
    const incidencias = Array.from({ length: 20 }, (_, i) => ({
      clave: `45000000${String(i).padStart(2, '0')}-10`,
      motivo: 'sin_destino_resoluble',
      detalle: 'sin destino',
      consecuencia: 'no_entro' as const,
    }))
    render(<InformeCarga carga={carga({ incidencias })} />)

    expect(screen.getAllByText('sin destino')).toHaveLength(15)
    await userEvent.click(screen.getByRole('button', { name: 'Ver las 20 líneas' }))
    expect(screen.getAllByText('sin destino')).toHaveLength(20)
    await userEvent.click(screen.getByRole('button', { name: 'Ver menos' }))
    expect(screen.getAllByText('sin destino')).toHaveLength(15)
  })

  it('sin incidencias lo celebra; con avisos los lista; lo que entró sin rastreo se marca', () => {
    const { unmount } = render(
      <InformeCarga carga={carga({ incidencias: [], por_motivo: {}, no_entraron: 0 })} />,
    )
    expect(screen.getByText('Todas las líneas entraron sin problemas.')).toBeInTheDocument()
    unmount()

    render(
      <InformeCarga
        carga={carga({
          incidencias: [
            {
              clave: '4500000001-10',
              motivo: 'referencia_invalida',
              detalle: 'dígito verificador',
              consecuencia: 'entro_sin_rastreo',
            },
          ],
          avisos: [{ clave: '4500000002-10', tipo: 'destino_discrepante', detalle: 'Moín' }],
        })}
      />,
    )
    expect(screen.getByText('(entró sin rastreo)')).toBeInTheDocument()
    expect(screen.getByText(/conviene revisar en SAP \(1\)/)).toBeInTheDocument()
  })
})

describe('apoyos', () => {
  it('los motivos conocidos se traducen; los otros se leen igual', () => {
    expect(nombreMotivo('sin_via_transporte')).toBe('Sin vía de transporte')
    expect(nombreMotivo('algo_nuevo')).toBe('algo nuevo')
  })

  it('fecha y hora en Costa Rica', () => {
    expect(formatearFechaHora('2026-10-08T15:30:00Z')).toBe('08/10/2026 09:30')
    expect(formatearFechaHora(null)).toBeNull()
    expect(formatearFechaHora('nada')).toBeNull()
  })
})

describe('servicio de cargas', () => {
  it('manda el archivo como formulario, con más tiempo de espera', async () => {
    const { subirZtracking: subirReal } =
      await vi.importActual<typeof import('@/services/cargas')>('@/services/cargas')
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: carga() })

    await subirReal(excel())

    const [url, cuerpo, opciones] = post.mock.calls[0]
    expect(url).toBe('/api/v1/cargas')
    expect((cuerpo as FormData).get('archivo')).toBeInstanceOf(File)
    expect(opciones).toMatchObject({ timeout: 60_000 })
  })

  it('el historial y el detalle piden lo suyo', async () => {
    const real = await vi.importActual<typeof import('@/services/cargas')>('@/services/cargas')
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: [] })

    await real.listarCargas()
    await real.obtenerCarga(7)

    expect(get).toHaveBeenNthCalledWith(1, '/api/v1/cargas')
    expect(get).toHaveBeenNthCalledWith(2, '/api/v1/cargas/7')
  })
})
