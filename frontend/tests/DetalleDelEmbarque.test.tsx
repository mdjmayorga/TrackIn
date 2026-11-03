import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { DetalleDelEmbarque } from '@/components/DetalleDelEmbarque'
import type { MarcadorMapa } from '@/types/api'

function marcador(cambios: Partial<MarcadorMapa> = {}): MarcadorMapa {
  return {
    id_elemento: 1,
    tipo: 'BL',
    referencia: 'MAEU271108898',
    nombre: 'MAERSK NACALA',
    latitud: 9.3,
    longitud: -79.5,
    estado: 'EN_RIESGO',
    etapa: 'EN_TRANSITO',
    cumplimiento: 'EN_RIESGO',
    ultima_lectura: null,
    desactualizada: false,
    activo: true,
    pedidos: [
      {
        id: 31,
        oc_numero: '4500016172',
        posicion_oc: 20,
        estado_calculado: 'EN_RIESGO',
        etapa_viaje: 'EN_TRANSITO',
        estado_cumplimiento: 'EN_RIESGO',
        material: 'ACEITE DE PALMA RBD',
        proveedor: 'Proveedor del Caribe',
        eta: '2026-11-05',
        fecha_proyectada: '2026-11-07',
      },
      {
        id: 32,
        oc_numero: '4500016172',
        posicion_oc: 30,
        estado_calculado: 'A_TIEMPO',
        etapa_viaje: 'EN_TRANSITO',
        estado_cumplimiento: 'A_TIEMPO',
      },
    ],
    posicion_estimada: false,
    situacion: null,
    vuelo: null,
    lugar: null,
    ruta: null,
    ...cambios,
  }
}

function montar(
  m: MarcadorMapa = marcador(),
  extra: Partial<Parameters<typeof DetalleDelEmbarque>[0]> = {},
) {
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<DetalleDelEmbarque marcador={m} {...extra} />} />
        <Route path="/pedidos/:id" element={<p>Detalle del pedido</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('el recuadro de un marcador (US-27, RF-18)', () => {
  it('muestra OC, material, proveedor, ETA, fecha proyectada y estado de cada pedido', () => {
    montar()

    const embarque = screen.getByRole('region', { name: 'MAERSK NACALA (BL MAEU271108898)' })
    const [primero, segundo] = within(embarque).getAllByRole('listitem')
    expect(primero).toHaveTextContent('4500016172-20')
    expect(primero).toHaveTextContent('ACEITE DE PALMA RBD')
    expect(primero).toHaveTextContent('Proveedor del Caribe')
    expect(primero).toHaveTextContent('ETA 05/11/2026 · Proyectada 07/11/2026')
    // La etapa y el cumplimiento, juntos (03/11/2026).
    expect(primero).toHaveTextContent('En Tránsito')
    expect(primero).toHaveTextContent('En Riesgo')
    // Lo que falta se dice, no se deja en blanco.
    expect(segundo).toHaveTextContent('Material sin dato')
    expect(segundo).toHaveTextContent('ETA – · Proyectada –')
    expect(segundo).toHaveTextContent('A Tiempo')
  })

  it('cada pedido lleva a su detalle', async () => {
    montar()

    await userEvent.click(screen.getByRole('link', { name: '4500016172-20' }))

    expect(screen.getByText('Detalle del pedido')).toBeInTheDocument()
  })
})

const TRAYECTO = [
  {
    vuelo: 'POLAR BRASIL · viaje 637N',
    origen: 'COCTG',
    destino: 'CRPMN',
    salida: '2026-10-28T17:00:00Z',
    llegada: '2026-11-04T18:00:00Z',
    ruta: [
      [10.4, -75.5],
      [10.0, -83.0],
    ] as Array<[number, number]>,
  },
]

describe('elegir la ruta desde el recuadro de un grupo (03/11/2026)', () => {
  it('con trayecto ofrece «Ver ruta», y al tocarlo avisa', async () => {
    const onVerRuta = vi.fn()
    montar(marcador({ trayecto: TRAYECTO }), { onVerRuta })

    await userEvent.click(screen.getByRole('button', { name: 'Ver ruta' }))

    expect(onVerRuta).toHaveBeenCalledOnce()
  })

  it('con la ruta a la vista, ofrece ocultarla', () => {
    montar(marcador({ trayecto: TRAYECTO }), { onVerRuta: vi.fn(), rutaVisible: true })

    expect(screen.getByRole('button', { name: 'Ocultar ruta' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('sin trayecto, o fuera de un grupo, no hay botón', () => {
    montar(marcador({ trayecto: null }), { onVerRuta: vi.fn() })
    expect(screen.queryByRole('button', { name: 'Ver ruta' })).toBeNull()
  })

  it('fuera de un grupo el clic en el marcador ya muestra la ruta: no hay botón', () => {
    montar(marcador({ trayecto: TRAYECTO }))
    expect(screen.queryByRole('button', { name: 'Ver ruta' })).toBeNull()
  })
})
