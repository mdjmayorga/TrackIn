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
import { descargarPlantilla, listarCargas, obtenerCarga, subirZtracking } from '@/services/cargas'
import type { CargaDetalle, Rol } from '@/types/api'
import { formatearFechaHora } from '@/utils/fechas'
import { nombreMotivo } from '@/utils/motivosCarga'

import { USUARIO } from './sesion.test'

vi.mock('@/services/cargas', async (original) => ({
  ...(await original<typeof import('@/services/cargas')>()),
  listarCargas: vi.fn(),
  obtenerCarga: vi.fn(),
  subirZtracking: vi.fn(),
  descargarPlantilla: vi.fn(),
}))

function carga(cambios: Partial<CargaDetalle> = {}): CargaDetalle {
  return {
    id: 7,
    archivo: '2026 - OCTUBRE - WK40.xlsx',
    tamano_bytes: 349_000,
    realizada_en: '2026-10-08T15:30:00Z',
    estado: 'APLICADA',
    motivo_rechazo: null,
    origen: 'EXCEL',
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
    expect(screen.queryByRole('button', { name: 'Descargar plantilla' })).toBeNull()
    expect(screen.getByText(/Las cargas las hacen Compras y el Administrador/)).toBeInTheDocument()
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })
})

describe('la plantilla (US-59)', () => {
  it('Compras la descarga desde la pantalla de carga', async () => {
    vi.mocked(descargarPlantilla).mockResolvedValue()
    montar()

    await userEvent.click(screen.getByRole('button', { name: 'Descargar plantilla' }))

    expect(descargarPlantilla).toHaveBeenCalledOnce()
  })

  it('si la descarga falla, lo dice', async () => {
    vi.mocked(descargarPlantilla).mockRejectedValue(new Error('sin conexión'))
    montar()

    await userEvent.click(screen.getByRole('button', { name: 'Descargar plantilla' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('sin conexión')
  })

  it('el servicio la pide como archivo y la guarda con su nombre', async () => {
    const real = await vi.importActual<typeof import('@/services/cargas')>('@/services/cargas')
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: new Blob(['xlsx']) })
    URL.createObjectURL = vi.fn(() => 'blob:plantilla')
    URL.revokeObjectURL = vi.fn()
    const clic = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    await real.descargarPlantilla()

    expect(get).toHaveBeenCalledWith('/api/v1/cargas/plantilla', { responseType: 'blob' })
    const enlace = clic.mock.contexts[0] as HTMLAnchorElement
    expect(enlace.download).toBe('Plantilla Z-tracking.xlsx')
    expect(enlace.href).toBe('blob:plantilla')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:plantilla')
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

  it('un lote de la API de SAP figura como tal, sin persona (US-65)', async () => {
    const lote = carga({
      id: 8,
      archivo: 'Lote SAP-20261027-080000',
      origen: 'API_SAP',
      usuario: null,
    })
    vi.mocked(listarCargas).mockResolvedValue([lote])
    vi.mocked(obtenerCarga).mockResolvedValue(lote)
    montar()

    const fila = within(await screen.findByRole('table')).getAllByRole('row')[1]
    expect(within(fila).getByText('API de SAP')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Lote SAP-20261027-080000' }))

    expect(await screen.findByText(/^Recibido de la API de SAP el/)).toBeInTheDocument()
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

  it('sin referencia: la línea no entra, dice qué hacer, y lista los cerrados (04/11/2026)', () => {
    render(
      <InformeCarga
        carga={carga({
          por_motivo: { sin_referencia: 1 },
          incidencias: [
            {
              clave: '4500000003-10',
              motivo: 'sin_referencia',
              detalle: 'no trae BL, contenedor ni booking',
              consecuencia: 'no_entro',
            },
          ],
          cerrados_sin_referencia: ['4500016171-90', '4500016172-30'],
        })}
      />,
    )

    expect(screen.getAllByText(/Sin referencia de embarque/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Sin referencia el pedido no se puede seguir/)).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /Cerrados por no tener referencia de embarque \(2\)/ }),
    ).toBeInTheDocument()
    expect(screen.getByText('4500016171-90, 4500016172-30')).toBeInTheDocument()
  })

  it('el formato inválido dice el campo, y el dato descartado se marca (US-59)', () => {
    render(
      <InformeCarga
        carga={carga({
          por_motivo: { formato_invalido: 1, dato_descartado: 1 },
          incidencias: [
            {
              clave: 'PRODUCCION!103',
              motivo: 'formato_invalido',
              detalle: '4500018201-10: «Fecha Entrega» trae «30/11.2026»; se espera una fecha',
              consecuencia: 'no_entro',
            },
            {
              clave: '4500018201-20',
              motivo: 'dato_descartado',
              detalle: '«ETA CR (fecha)» trae «fin de mes»; se espera una fecha',
              consecuencia: 'entro_sin_dato',
            },
          ],
        })}
      />,
    )
    expect(screen.getByText(/«Fecha Entrega» trae «30\/11.2026»/)).toBeInTheDocument()
    expect(screen.getByText('(entró sin ese dato)')).toBeInTheDocument()
    expect(screen.getAllByText('Formato inválido').length).toBeGreaterThan(0)
  })
})

describe('las terrestres, fuera del alcance (21/10)', () => {
  it('tienen su propio motivo y dicen que no hay nada que corregir', () => {
    render(
      <InformeCarga
        carga={carga({
          por_motivo: { via_fuera_de_alcance: 4 },
          incidencias: [
            {
              clave: '4500017780-10',
              motivo: 'via_fuera_de_alcance',
              detalle:
                'vía terrestre: fuera del alcance de TrackIn, que sigue envíos aéreos y marítimos',
              consecuencia: 'no_entro',
            },
          ],
        })}
      />,
    )

    expect(screen.getAllByText(/Vía fuera del alcance/).length).toBeGreaterThan(0)
    expect(screen.getByText(/No hay nada que corregir/)).toBeInTheDocument()
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
