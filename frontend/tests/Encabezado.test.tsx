import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CintaKpis } from '@/components/CintaKpis'
import { ProximosArribos } from '@/components/ProximosArribos'

describe('cinta de KPIs', () => {
  it('los cinco indicadores del Figma, en guion hasta US-22', () => {
    render(<CintaKpis />)

    const recuadros = screen.getAllByRole('listitem')
    expect(recuadros.map((r) => r.textContent)).toEqual([
      '–Pedidos Activos',
      '–(– pedidos)A Tiempo',
      '–(– pedidos)En Riesgo',
      '–(– pedidos)Retrasados',
      '–Lead Time Medio',
    ])
  })
})

describe('próximos arribos', () => {
  it('las cinco tarjetas de ejemplo del Figma, con su vía', () => {
    render(<ProximosArribos />)

    const tarjetas = screen.getAllByRole('listitem')
    expect(tarjetas).toHaveLength(5)
    const primera = within(tarjetas[0])
    expect(primera.getByText('4500013044 - 10')).toBeInTheDocument()
    expect(primera.getByText('Dióxido de Titanio')).toBeInTheDocument()
    expect(primera.getByRole('img', { name: 'Aéreo' })).toBeInTheDocument()
    expect(primera.getByText('28/08 - 3d')).toBeInTheDocument()
    expect(within(tarjetas[1]).getByRole('img', { name: 'Marítimo' })).toBeInTheDocument()
    expect(within(tarjetas[1]).getByText('Moín')).toBeInTheDocument()
  })
})
