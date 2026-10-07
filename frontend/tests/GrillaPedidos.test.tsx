import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { GrillaPedidos, type GrillaPedidosProps } from '@/components/GrillaPedidos'

import { pagina, pedido } from './fixtures'

function montar(props: Partial<GrillaPedidosProps> = {}) {
  const onOrdenar = vi.fn()
  const onPaginar = vi.fn()
  render(
    <GrillaPedidos
      pagina={pagina([pedido()])}
      orden="fecha_proyectada"
      onOrdenar={onOrdenar}
      onPaginar={onPaginar}
      {...props}
    />,
  )
  return { onOrdenar, onPaginar }
}

function encabezados() {
  return screen.getAllByRole('columnheader').map((th) => th.textContent?.replace(/[▲▼↕]/g, ''))
}

/** La fila 0 es la de encabezados. */
function fila(n: number) {
  return within(screen.getAllByRole('row')[n])
}

describe('columnas', () => {
  it('las nueve del Figma, en su orden', () => {
    montar()

    expect(encabezados()).toEqual([
      'OC',
      'POS',
      'Material',
      'Etapa',
      'Cumplimiento',
      'F. Proyectada',
      'F. Comprometida',
      'Vía',
      'Destino',
    ])
  })

  it('una fila completa: código y nombre del material, fechas dd/mm/aaaa', () => {
    montar()

    const celdas = fila(1)
      .getAllByRole('cell')
      .map((td) => td.textContent)
    expect(celdas).toEqual([
      '4500012847',
      '10',
      '13002006 Lactosa monohidrato',
      'En Tránsito',
      'A Tiempo',
      '08/09/2026',
      '15/09/2026',
      'Marítimo',
      'Puerto Limón',
    ])
  })

  it('el aeropuerto se muestra por su código, con el nombre a mano', () => {
    montar({
      pagina: pagina([
        pedido({
          via_transporte: 'AEREO',
          destino: { id: 1, codigo: 'MROC', nombre: 'Aeropuerto Juan Santamaría' },
        }),
      ]),
    })

    expect(screen.getByText('MROC')).toHaveAttribute('title', 'Aeropuerto Juan Santamaría')
  })

  it('sin proyección, cumplimiento y fecha llevan el guion', () => {
    montar({
      pagina: pagina([
        pedido({
          etapa_viaje: 'SIN_TRACKING',
          estado_calculado: 'SIN_TRACKING',
          estado_cumplimiento: null,
          fecha_proyectada_disponible: null,
        }),
      ]),
    })

    expect(fila(1).getByText('Sin Tracking')).toBeInTheDocument()
    expect(fila(1).getByLabelText('Cumplimiento no evaluable')).toHaveTextContent('–')
    expect(fila(1).getByLabelText('Sin fecha proyectada')).toHaveTextContent('–')
  })
})

describe('filas terminales (wireframes §1.11)', () => {
  it('la etapa muestra el estado terminal, no la etapa congelada', () => {
    montar({
      pagina: pagina([
        pedido({ id: 1, etapa_viaje: 'EN_PROCESO_ADUANAL', estado_calculado: 'CERRADO' }),
        pedido({
          id: 2,
          etapa_viaje: 'EN_TRANSITO',
          estado_calculado: 'CANCELADO',
          estado_cumplimiento: null,
        }),
      ]),
    })

    expect(fila(1).getByText('Cerrado')).toBeInTheDocument()
    expect(fila(1).queryByText('P. Aduanal')).toBeNull()
    // El cumplimiento de un cerrado es el veredicto del proveedor: se conserva.
    expect(fila(1).getByText('A Tiempo')).toBeInTheDocument()
    expect(fila(2).getByText('Cancelado')).toBeInTheDocument()
    expect(fila(2).getByLabelText('Cumplimiento no evaluable')).toBeInTheDocument()
  })

  it('al listar terminales, la fecha proyectada cede su lugar a la recepción', () => {
    montar({
      terminales: true,
      pagina: pagina([
        pedido({ estado_calculado: 'CERRADO', fecha_recepcion_planta: '2026-08-28T15:00:00Z' }),
      ]),
    })

    expect(encabezados()).toContain('F. Recepción')
    expect(encabezados()).not.toContain('F. Proyectada')
    expect(fila(1).getByText('28/08/2026')).toBeInTheDocument()
  })
})

describe('ordenar', () => {
  it('marca la columna activa para los lectores de pantalla', () => {
    montar({ orden: '-fecha_comprometida' })

    expect(screen.getByRole('columnheader', { name: /F\. Comprometida/ })).toHaveAttribute(
      'aria-sort',
      'descending',
    )
    expect(screen.getByRole('columnheader', { name: /^OC/ })).not.toHaveAttribute('aria-sort')
  })

  it('otra columna empieza ascendente; la misma alterna el sentido', async () => {
    const { onOrdenar } = montar({ orden: 'fecha_proyectada' })

    await userEvent.click(screen.getByRole('button', { name: /Material/ }))
    await userEvent.click(screen.getByRole('button', { name: /F\. Proyectada/ }))

    expect(onOrdenar).toHaveBeenNthCalledWith(1, 'material')
    expect(onOrdenar).toHaveBeenNthCalledWith(2, '-fecha_proyectada')
  })

  it('descendente vuelve a ascendente', async () => {
    const { onOrdenar } = montar({ orden: '-oc' })

    await userEvent.click(screen.getByRole('button', { name: /^OC/ }))

    expect(onOrdenar).toHaveBeenCalledWith('oc')
  })

  it('POS no ordena por su cuenta: va con la OC', () => {
    montar()

    expect(screen.queryByRole('button', { name: /POS/ })).toBeNull()
  })
})

describe('paginar', () => {
  it('muestra el tramo y avanza de a una página', async () => {
    const items = Array.from({ length: 25 }, (_, i) => pedido({ id: i + 1 }))
    const { onPaginar } = montar({
      pagina: pagina(items, { total: 107, limite: 25, desplazamiento: 25 }),
    })

    expect(screen.getByText('26–50 de 107 pedidos')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await userEvent.click(screen.getByRole('button', { name: 'Anterior' }))

    expect(onPaginar).toHaveBeenNthCalledWith(1, 50)
    expect(onPaginar).toHaveBeenNthCalledWith(2, 0)
  })

  it('en la primera y la última página, el botón que no lleva a nada se apaga', () => {
    montar({ pagina: pagina([pedido()], { total: 1 }) })

    expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled()
  })

  it('sin pedidos lo dice, y no hay paginador', () => {
    montar({ pagina: pagina([]) })

    expect(screen.getByText('No hay pedidos que mostrar.')).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).toBeNull()
  })
})
