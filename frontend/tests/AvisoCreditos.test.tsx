import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AvisoCreditos } from '@/components/AvisoCreditos'
import { obtenerCreditos } from '@/services/shipsgo'
import type { EstadoCreditos } from '@/types/api'

vi.mock('@/services/shipsgo', () => ({ obtenerCreditos: vi.fn() }))

function estado(nivel: EstadoCreditos['nivel'], mensaje: string): EstadoCreditos {
  return {
    nivel,
    mensaje,
    paquete: null,
    disponible: 0,
    consumidos: 0,
    saldo: 0,
    porcentaje_consumido: null,
    dias_para_vencer: null,
    recompra_minima: null,
  }
}

function montar() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AvisoCreditos />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.mocked(obtenerCreditos).mockReset()
})

describe('AvisoCreditos (US-57)', () => {
  it('con el saldo en orden no ocupa lugar', async () => {
    vi.mocked(obtenerCreditos).mockResolvedValue(estado('OK', 'Quedan 40 de 49.'))
    const { container } = montar()

    await vi.waitFor(() => expect(obtenerCreditos).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('al 80 % avisa y lleva a ver los créditos', async () => {
    vi.mocked(obtenerCreditos).mockResolvedValue(estado('BAJO', 'Quedan 9 de 49 créditos.'))
    montar()

    const aviso = await screen.findByRole('status', { name: 'Créditos de ShipsGo' })
    expect(aviso).toHaveTextContent('Quedan 9 de 49 créditos.')
    expect(screen.getByRole('link', { name: 'Ver créditos' })).toHaveAttribute(
      'href',
      '/shipsgo/altas',
    )
  })

  it('agotado es una alerta', async () => {
    vi.mocked(obtenerCreditos).mockResolvedValue(estado('AGOTADO', 'Se agotaron.'))
    montar()

    expect(await screen.findByRole('alert', { name: 'Créditos de ShipsGo' })).toHaveTextContent(
      'Se agotaron.',
    )
  })

  it('sin paquete registrado invita a registrarlo', async () => {
    vi.mocked(obtenerCreditos).mockResolvedValue(estado('SIN_PAQUETE', 'No hay paquete.'))
    montar()

    expect(await screen.findByRole('link', { name: 'Registrar el paquete' })).toBeInTheDocument()
  })
})
