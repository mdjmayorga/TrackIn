import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ContextoSesion } from '@/auth/contexto'
import { AccionesPedido } from '@/components/AccionesPedido'
import {
  ajustarDias,
  cerrarForzado,
  confirmarDesembarco,
  liberarCalidad,
  pasarAAduana,
  registrarRecepcion,
} from '@/services/acciones'
import { api } from '@/services/api'
import type { PedidoDetalle, Rol } from '@/types/api'
import { ahoraParaCampo, campoAInstante } from '@/utils/fechas'

import { pedido } from './fixtures'
import { USUARIO } from './sesion.test'

vi.mock('@/services/acciones', async (original) => ({
  ...(await original<typeof import('@/services/acciones')>()),
  confirmarDesembarco: vi.fn(),
  pasarAAduana: vi.fn(),
  registrarRecepcion: vi.fn(),
  cerrarForzado: vi.fn(),
  liberarCalidad: vi.fn(),
  ajustarDias: vi.fn(),
}))

const MOTIVO = 'Confirmado con el agente aduanal'

function detalle(cambios: Partial<PedidoDetalle> = {}): PedidoDetalle {
  return {
    ...pedido({ id: 7, etapa_viaje: 'EN_TRANSITO', estado_calculado: 'A_TIEMPO' }),
    cantidad_pedida: '1000.000',
    unidad_medida: 'KG',
    incoterm: null,
    temperatura: null,
    tipo_proveedor: null,
    fabricante: null,
    pais_origen: null,
    rastreo: null,
    arribos: { confirmado: null, fuente: null, inferido: null },
    calculo: {
      origen: null,
      eta_utilizada: null,
      lead_time_dias: 6,
      lead_time_maestro_dias: 6,
      ajuste_manual_dias: 2,
      fecha_proyectada: '2026-09-10',
      fecha_comprometida: '2026-10-30',
      ventana_aduanal_dias: null,
      margen_dias: null,
      umbral_riesgo_dias: 2,
      desglose: '',
      al_dia: true,
      desglose_actual: null,
      fecha_ultimo_recalculo: null,
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

function montar(p: PedidoDetalle = detalle(), rol: Rol = 'LOGISTICA') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ContextoSesion.Provider
        value={{ token: 't', usuario: { ...USUARIO, rol }, recordada: false }}
      >
        <AccionesPedido pedido={p} />
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
  return queryClient
}

function conflicto(datos: object) {
  return new AxiosError(
    '409',
    'ERR',
    undefined,
    {},
    {
      status: 409,
      statusText: '',
      headers: {},
      config: {} as never,
      data: datos,
    },
  )
}

async function abrirYEscribirMotivo(titulo: string) {
  await userEvent.click(screen.getByRole('button', { name: titulo }))
  await userEvent.type(screen.getByLabelText(/Motivo/), MOTIVO)
}

const boton = (nombre: string) => screen.getByRole('button', { name: nombre })

beforeEach(() => {
  for (const servicio of [
    confirmarDesembarco,
    pasarAAduana,
    registrarRecepcion,
    cerrarForzado,
    liberarCalidad,
    ajustarDias,
  ]) {
    vi.mocked(servicio).mockResolvedValue(detalle())
  }
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('quién ve qué', () => {
  // Compras, igual que el Administrador y Logística, desde el 21/10/2026.
  it.each(['LOGISTICA', 'COMPRAS', 'ADMINISTRADOR'] as const)('%s: las cinco acciones', (rol) => {
    montar(detalle(), rol)

    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Confirmar desembarco',
      'Pasar a proceso aduanal',
      'Registrar recepción en planta',
      'Registrar liberación de Calidad',
      'Ajustar días',
    ])
  })

  it('Planificación: el paso a aduana y la liberación', () => {
    montar(detalle(), 'PLANIFICACION')

    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Pasar a proceso aduanal',
      'Registrar liberación de Calidad',
    ])
  })

  it('Planta no interviene: no hay barra', () => {
    montar(detalle(), 'PLANTA')

    expect(screen.queryByRole('region', { name: 'Acciones del pedido' })).toBeNull()
  })
})

describe('lo que no aplica se ve, deshabilitado y con el porqué', () => {
  it('en tránsito: confirmar y ajustar sí; aduana, recepción y liberación no', () => {
    montar()

    expect(boton('Confirmar desembarco')).toBeEnabled()
    expect(boton('Ajustar días')).toBeEnabled()
    expect(boton('Pasar a proceso aduanal')).toBeDisabled()
    expect(boton('Pasar a proceso aduanal')).toHaveAttribute(
      'title',
      'Solo desde «En destino»: confirme antes la llegada.',
    )
    expect(boton('Registrar recepción en planta')).toHaveAttribute(
      'title',
      'Exige que el pedido haya pasado aduana.',
    )
    expect(boton('Registrar liberación de Calidad')).toBeDisabled()
  })

  it('cada etapa habilita la suya', () => {
    montar(detalle({ etapa_viaje: 'EN_DESTINO' }))
    expect(boton('Pasar a proceso aduanal')).toBeEnabled()
  })

  it('un pedido cerrado no admite nada (RN-13)', () => {
    montar(detalle({ estado_calculado: 'CERRADO', etapa_viaje: 'RECIBIDO_EN_PLANTA' }))

    for (const b of screen.getAllByRole('button')) {
      expect(b).toBeDisabled()
      expect(b).toHaveAttribute('title', 'El pedido está cerrado: no admite cambios (RN-13).')
    }
  })
})

describe('ninguna acción es de un clic (RF-14)', () => {
  it('abrir no ejecuta, y sin motivo no se confirma', async () => {
    montar()

    await userEvent.click(boton('Ajustar días'))
    expect(ajustarDias).not.toHaveBeenCalled()
    expect(boton('Confirmar')).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/Motivo/), 'ok')
    expect(boton('Confirmar')).toBeDisabled()
  })

  it('cancelar cierra el formulario sin hacer nada', async () => {
    montar()

    await abrirYEscribirMotivo('Ajustar días')
    await userEvent.click(boton('Cancelar'))

    expect(screen.queryByLabelText(/Motivo/)).toBeNull()
    expect(ajustarDias).not.toHaveBeenCalled()
  })
})

describe('cada acción', () => {
  it('confirmar desembarco: la fecha va en hora de Costa Rica', async () => {
    montar()

    await abrirYEscribirMotivo('Confirmar desembarco')
    const campo = screen.getByLabelText('Fecha y hora de llegada')
    await userEvent.clear(campo)
    await userEvent.type(campo, '2026-10-14T08:15')
    await userEvent.click(boton('Confirmar'))

    expect(confirmarDesembarco).toHaveBeenCalledWith(7, {
      motivo: MOTIVO,
      ata: '2026-10-14T08:15:00-06:00',
      confirmar: false,
    })
    // Terminó: el formulario se cierra.
    expect(screen.queryByLabelText(/Motivo/)).toBeNull()
  })

  it('si ya había llegada confirmada, la muestra y pide confirmar el reemplazo', async () => {
    vi.mocked(confirmarDesembarco).mockRejectedValueOnce(
      conflicto({
        detail: 'Ya hay una llegada confirmada.',
        ata_confirmada_actual: '2026-10-13T14:00:00Z',
        requiere_confirmacion: true,
      }),
    )
    montar()

    await abrirYEscribirMotivo('Confirmar desembarco')
    await userEvent.click(boton('Confirmar'))

    expect(await screen.findByRole('alert')).toHaveTextContent('13/10/2026 08:00')
    await userEvent.click(boton('Reemplazar la llegada'))
    expect(confirmarDesembarco).toHaveBeenLastCalledWith(
      7,
      expect.objectContaining({ confirmar: true }),
    )
  })

  it('pasar a aduana: solo el motivo', async () => {
    montar(detalle({ etapa_viaje: 'EN_DESTINO' }), 'PLANIFICACION')

    await abrirYEscribirMotivo('Pasar a proceso aduanal')
    expect(screen.queryByLabelText(/Fecha/)).toBeNull()
    await userEvent.click(boton('Confirmar'))

    expect(pasarAAduana).toHaveBeenCalledWith(7, { motivo: MOTIVO })
  })

  it('pasar a aduana: el motivo es opcional (27/10)', async () => {
    montar(detalle({ etapa_viaje: 'EN_DESTINO' }), 'PLANIFICACION')

    await userEvent.click(boton('Pasar a proceso aduanal'))
    expect(screen.getByLabelText(/^Motivo \(opcional\)/)).toBeInTheDocument()
    await userEvent.click(boton('Confirmar'))

    expect(pasarAAduana).toHaveBeenCalledWith(7, { motivo: null })
  })

  it('recepción: propone la cantidad pedida', async () => {
    montar(detalle({ etapa_viaje: 'EN_PROCESO_ADUANAL' }))

    await abrirYEscribirMotivo('Registrar recepción en planta')
    expect(screen.getByLabelText(/Cantidad recibida/)).toHaveValue(1000)
    await userEvent.click(boton('Confirmar'))

    expect(registrarRecepcion).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ cantidad: '1000', motivo: MOTIVO }),
    )
  })

  it('recepción bajo el mínimo de RN-10: lo explica y ofrece cerrar con lo recibido', async () => {
    vi.mocked(registrarRecepcion).mockRejectedValueOnce(
      conflicto({
        detail: 'No llega al mínimo conforme.',
        cantidad_pedida: '1000.000',
        cantidad_recibida: '600.000',
        minimo_conforme: '900.000',
        ofrece_cierre_forzado: true,
      }),
    )
    montar(detalle({ etapa_viaje: 'EN_PROCESO_ADUANAL' }))

    await abrirYEscribirMotivo('Registrar recepción en planta')
    const cantidad = screen.getByLabelText(/Cantidad recibida/)
    await userEvent.clear(cantidad)
    await userEvent.type(cantidad, '600')
    await userEvent.click(boton('Confirmar'))

    expect(await screen.findByRole('alert')).toHaveTextContent(/900 kg de 1\s000 kg/)
    await userEvent.click(boton('Cerrar con recepción parcial'))
    expect(cerrarForzado).toHaveBeenCalledWith(7, expect.objectContaining({ cantidad: '600' }))
  })

  it('liberación: propone lo que falta liberar', async () => {
    montar(
      detalle({
        etapa_viaje: 'RECIBIDO_EN_PLANTA',
        cierre: {
          ...detalle().cierre,
          cantidad_recibida: '950.000',
          cantidad_liberada: '200.000',
        },
      }),
    )

    await abrirYEscribirMotivo('Registrar liberación de Calidad')
    expect(screen.getByLabelText(/Cantidad liberada/)).toHaveValue(750)
    await userEvent.click(boton('Confirmar'))

    expect(liberarCalidad).toHaveBeenCalledWith(7, expect.objectContaining({ cantidad: '750' }))
  })

  it('ajustar días: se elige la nueva fecha y se manda el ajuste en días', async () => {
    // Proyectada 10/09 con +2 de ajuste: la calculada sin ajuste es el 08/09.
    montar(detalle({ calculo: { ...detalle().calculo, fecha_proyectada: '2026-09-10' } }))

    await abrirYEscribirMotivo('Ajustar días')
    const fecha = screen.getByLabelText(/Nueva fecha proyectada/)
    expect(fecha).toHaveValue('2026-09-10')
    expect(screen.getByText(/Fecha calculada sin ajuste: 08\/09\/2026/)).toBeInTheDocument()
    // Sin mover la fecha no hay nada que guardar.
    expect(boton('Confirmar')).toBeDisabled()

    await userEvent.clear(fecha)
    await userEvent.type(fecha, '2026-09-05')
    expect(screen.getByText(/el ajuste queda en −3 días/)).toBeInTheDocument()
    await userEvent.click(boton('Confirmar'))

    expect(ajustarDias).toHaveBeenCalledWith(7, { motivo: MOTIVO, dias: -3 })
  })

  it('volver a la fecha calculada quita el ajuste', async () => {
    montar(detalle({ calculo: { ...detalle().calculo, fecha_proyectada: '2026-09-10' } }))

    await abrirYEscribirMotivo('Ajustar días')
    const fecha = screen.getByLabelText(/Nueva fecha proyectada/)
    await userEvent.clear(fecha)
    await userEvent.type(fecha, '2026-09-08')
    expect(screen.getByText(/Con esta fecha no queda ajuste/)).toBeInTheDocument()
    await userEvent.click(boton('Confirmar'))

    expect(ajustarDias).toHaveBeenCalledWith(7, { motivo: MOTIVO, dias: 0 })
  })

  it('sin fecha proyectada no hay qué ajustar', () => {
    montar(detalle({ calculo: { ...detalle().calculo, fecha_proyectada: null } }))

    expect(boton('Ajustar días')).toBeDisabled()
    expect(boton('Ajustar días')).toHaveAttribute(
      'title',
      'Sin fecha proyectada: no hay fecha que ajustar.',
    )
  })

  it('cualquier otro rechazo muestra el mensaje del backend', async () => {
    vi.mocked(confirmarDesembarco).mockRejectedValueOnce(
      conflicto({ detail: 'La llegada no puede ser futura.' }),
    )
    montar()

    await abrirYEscribirMotivo('Confirmar desembarco')
    await userEvent.click(boton('Confirmar'))

    expect(await screen.findByRole('alert')).toHaveTextContent('La llegada no puede ser futura.')
  })

  it('al terminar, el detalle se actualiza con la respuesta', async () => {
    const actualizado = detalle({ etapa_viaje: 'EN_DESTINO' })
    vi.mocked(confirmarDesembarco).mockResolvedValueOnce(actualizado)
    const queryClient = montar()

    await abrirYEscribirMotivo('Confirmar desembarco')
    await userEvent.click(boton('Confirmar'))

    expect(queryClient.getQueryData(['pedidos', 'detalle', 7])).toEqual(actualizado)
  })
})

describe('apoyos', () => {
  it('el campo de fecha en hora de Costa Rica, y de vuelta a instante', () => {
    expect(ahoraParaCampo(new Date('2026-10-15T02:30:00Z'))).toBe('2026-10-14T20:30')
    expect(campoAInstante('2026-10-14T20:30')).toBe('2026-10-14T20:30:00-06:00')
  })

  it('cada acción va a su ruta', async () => {
    const real = await vi.importActual<typeof import('@/services/acciones')>('@/services/acciones')
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} })

    await real.confirmarDesembarco(7, { motivo: 'm', ata: 'x' })
    await real.pasarAAduana(7, { motivo: 'm' })
    await real.registrarRecepcion(7, { motivo: 'm', fecha: 'x', cantidad: '1' })
    await real.cerrarForzado(7, { motivo: 'm', fecha: 'x', cantidad: '1' })
    await real.liberarCalidad(7, { motivo: 'm', fecha: 'x', cantidad: '1' })
    await real.ajustarDias(7, { motivo: 'm', dias: 1 })

    expect(post.mock.calls.map((c) => c[0])).toEqual([
      '/api/v1/pedidos/7/desembarco',
      '/api/v1/pedidos/7/paso-aduanal',
      '/api/v1/pedidos/7/recepcion',
      '/api/v1/pedidos/7/cierre-forzado',
      '/api/v1/pedidos/7/liberacion-calidad',
      '/api/v1/pedidos/7/ajuste-manual',
    ])
  })

  it('un error que no es 409 no se toma por conflicto', async () => {
    const { comoConflictoDesembarco, comoRecepcionCorta } =
      await vi.importActual<typeof import('@/services/acciones')>('@/services/acciones')

    expect(comoConflictoDesembarco(new Error('x'))).toBeNull()
    expect(comoRecepcionCorta(conflicto({ detail: 'otro 409' }))).toBeNull()
  })
})
