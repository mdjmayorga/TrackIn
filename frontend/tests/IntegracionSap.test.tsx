import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ContextoSesion } from '@/auth/contexto'
import type { SesionGuardada } from '@/auth/sesion'
import IntegracionSap from '@/pages/IntegracionSap'
import { cambiarEscuchaSap, obtenerEscuchaSap } from '@/services/sap'
import type { CargaResumen, EstadoEscuchaSap, Rol } from '@/types/api'

import { USUARIO } from './sesion.test'

vi.mock('@/services/sap', () => ({ obtenerEscuchaSap: vi.fn(), cambiarEscuchaSap: vi.fn() }))

function estado(cambios: Partial<EstadoEscuchaSap> = {}): EstadoEscuchaSap {
  return {
    habilitada: false,
    cambiada_por: null,
    cambiada_en: null,
    clave_configurada: true,
    ultima_recepcion: null,
    ...cambios,
  }
}

const LOTE = {
  id: 9,
  archivo: 'Lote SAP-20261027-080000',
  tamano_bytes: 2217,
  realizada_en: '2026-10-27T14:00:00Z',
  estado: 'APLICADA',
  motivo_rechazo: null,
  origen: 'API_SAP',
  usuario: null,
  recibidas: 2,
  insertadas: 1,
  actualizadas: 1,
  sin_cambios: 0,
  ausentes: 0,
  no_entraron: 0,
  entraron_sin_rastreo: 0,
} satisfies CargaResumen

function montar(rol: Rol = 'ADMINISTRADOR') {
  const sesion: SesionGuardada = { token: 't', usuario: { ...USUARIO, rol }, recordada: false }
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <ContextoSesion.Provider value={sesion}>
        <MemoryRouter initialEntries={['/configuracion/sap']}>
          <Routes>
            <Route path="/configuracion/sap" element={<IntegracionSap />} />
            <Route path="/" element={<p>Panel</p>} />
          </Routes>
        </MemoryRouter>
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
}

const interruptor = () => screen.findByRole('switch', { name: 'Escucha de la API de SAP' })

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.mocked(obtenerEscuchaSap).mockReset()
  vi.mocked(cambiarEscuchaSap).mockReset()
})

describe('Integración con SAP (US-66)', () => {
  it('arranca apagada y sin recepciones', async () => {
    vi.mocked(obtenerEscuchaSap).mockResolvedValue(estado())
    montar()

    expect(await interruptor()).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText('Apagada')).toBeInTheDocument()
    expect(screen.getByText(/nadie la cambió todavía/)).toBeInTheDocument()
    expect(screen.getByText('Sin recepciones todavía.')).toBeInTheDocument()
  })

  it('el Administrador la enciende, con confirmación', async () => {
    vi.mocked(obtenerEscuchaSap).mockResolvedValue(estado())
    vi.mocked(cambiarEscuchaSap).mockResolvedValue(
      estado({
        habilitada: true,
        cambiada_por: { usuario: 'admin', nombre_completo: 'Administrador' },
        cambiada_en: '2026-10-27T15:00:00Z',
      }),
    )
    montar()

    await userEvent.click(await interruptor())
    expect(cambiarEscuchaSap).not.toHaveBeenCalled()
    expect(screen.getByRole('alertdialog')).toHaveTextContent('empezará a aceptar')

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar: encender la escucha' }))

    expect(cambiarEscuchaSap).toHaveBeenCalledWith(true)
    expect(await interruptor()).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText(/Cambiada por Administrador el/)).toBeInTheDocument()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it.each<Rol>(['COMPRAS', 'LOGISTICA', 'PLANIFICACION'])(
    '%s ve el estado pero no puede cambiarlo',
    async (rol) => {
      vi.mocked(obtenerEscuchaSap).mockResolvedValue(estado({ habilitada: true }))
      montar(rol)

      expect(await interruptor()).toBeDisabled()
      expect(screen.getByText('Solo el Administrador puede cambiarla.')).toBeInTheDocument()
    },
  )

  it('Planta vuelve al panel', () => {
    montar('PLANTA')

    expect(screen.getByText('Panel')).toBeInTheDocument()
    expect(obtenerEscuchaSap).not.toHaveBeenCalled()
  })

  it('avisa si el servidor no tiene la clave de integración', async () => {
    vi.mocked(obtenerEscuchaSap).mockResolvedValue(estado({ clave_configurada: false }))
    montar()

    expect(await screen.findByRole('status')).toHaveTextContent('SAP_INTEGRACION_CLAVE')
  })

  it('muestra la última recepción desde SAP', async () => {
    vi.mocked(obtenerEscuchaSap).mockResolvedValue(
      estado({ habilitada: true, ultima_recepcion: LOTE }),
    )
    montar()

    expect(await screen.findByRole('link', { name: 'Lote SAP-20261027-080000' })).toHaveAttribute(
      'href',
      '/cargas',
    )
    expect(screen.getByText(/2 recibidas, 1 nuevas, 1 actualizadas/)).toBeInTheDocument()
  })
})
