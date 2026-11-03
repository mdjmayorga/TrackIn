import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LeyendaMapa } from '@/components/LeyendaMapa'
import type { MarcadorMapa } from '@/types/api'

function marcador(cambios: Partial<MarcadorMapa> = {}): MarcadorMapa {
  return {
    id_elemento: 1,
    tipo: 'BL',
    referencia: 'MAEU271108898',
    nombre: null,
    latitud: 9.3,
    longitud: -79.5,
    estado: 'EN_TRANSITO',
    etapa: 'EN_TRANSITO',
    cumplimiento: null,
    ultima_lectura: null,
    desactualizada: false,
    activo: true,
    pedidos: [],
    posicion_estimada: false,
    situacion: null,
    vuelo: null,
    lugar: null,
    ruta: null,
    ...cambios,
  }
}

const grupo = (titulo: string) =>
  screen.getByRole('heading', { name: titulo }).parentElement as HTMLElement

describe('la leyenda de los mapas (RNF-08, wireframes §2.4 y §3.9, 03/11/2026)', () => {
  it('muestra solo las etapas que hay en el mapa, en orden', () => {
    render(
      <LeyendaMapa
        marcadores={[
          marcador({ etapa: 'EN_DESTINO' }),
          marcador({ id_elemento: 2, etapa: 'EN_TRANSITO' }),
          marcador({ id_elemento: 3, etapa: 'EN_TRANSITO' }),
        ]}
        umbralHoras={12}
      />,
    )

    expect(
      within(grupo('Relleno: etapa'))
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['En Tránsito', 'En Destino'])
  })

  it('explica el anillo y la opacidad, con el umbral de la vía', () => {
    render(<LeyendaMapa marcadores={[marcador()]} umbralHoras={2} />)

    expect(
      within(grupo('Anillo: cumplimiento'))
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['Todos a tiempo', 'Alguno en riesgo', 'Alguno retrasado'])
    expect(grupo('Opacidad: lectura')).toHaveTextContent('Sin lectura en más de 2 h')
  })

  it('el trazo aparece solo si algún embarque tiene ruta', () => {
    const { rerender } = render(<LeyendaMapa marcadores={[marcador()]} umbralHoras={12} />)
    expect(screen.queryByRole('heading', { name: 'Trazo: ruta' })).toBeNull()

    const tramo = {
      vuelo: 'LH518',
      origen: 'FRA',
      destino: 'SJO',
      salida: null,
      llegada: null,
      ruta: [[50, 8.5]] as Array<[number, number]>,
    }
    rerender(<LeyendaMapa marcadores={[marcador({ trayecto: [tramo] })]} umbralHoras={12} />)
    expect(grupo('Trazo: ruta')).toHaveTextContent('RecorridoPrevisto')
  })

  it('sin embarques en el mapa no hay leyenda', () => {
    render(<LeyendaMapa marcadores={[]} umbralHoras={12} />)
    expect(screen.queryByRole('region', { name: 'Leyenda del mapa' })).toBeNull()
  })
})
