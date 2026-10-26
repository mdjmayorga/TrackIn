import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { BarraFiltros, ESPERA_MS } from '@/components/BarraFiltros'
import { FILTROS_VACIOS } from '@/utils/filtros'

describe('filtro por SOLPED de la pantalla de planta (US-63, 26/10)', () => {
  it('solo aparece en la pantalla de planta', () => {
    const { rerender } = render(<BarraFiltros filtros={FILTROS_VACIOS} onCambio={vi.fn()} />)
    expect(screen.queryByLabelText(/SOLPED/)).toBeNull()

    rerender(<BarraFiltros filtros={FILTROS_VACIOS} onCambio={vi.fn()} conSolped />)
    expect(screen.getByLabelText(/SOLPED/)).toBeInTheDocument()
  })

  it('acepta solo dígitos y avisa al terminar de escribir, como la OC', async () => {
    const onCambio = vi.fn()
    render(<BarraFiltros filtros={FILTROS_VACIOS} onCambio={onCambio} conSolped />)

    await userEvent.type(screen.getByLabelText(/SOLPED/), '1000-03a35')

    expect(screen.getByLabelText(/SOLPED/)).toHaveValue('10000335')
    await new Promise((listo) => setTimeout(listo, ESPERA_MS + 100))
    expect(onCambio).toHaveBeenLastCalledWith({ solped: '10000335' })
    expect(onCambio).toHaveBeenCalledTimes(1)
  })
})
