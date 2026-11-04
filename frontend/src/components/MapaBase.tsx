/**
 * El fondo de los mapas: el mapa cartográfico, el encuadre del Caribe y
 * Centroamérica y los controles de zoom del Figma. Los marcadores van como
 * hijos: los embarques del panel (`MapaEmbarques`, `US-25`) o el punto único
 * del detalle (`marcador`).
 *
 * Los mosaicos son de OpenStreetMap (wireframes §2.8: la red de Gutis no los
 * bloquea). Su política exige la atribución visible, que Leaflet pone abajo a
 * la derecha. El tono gris oscuro del Figma sale de un filtro CSS sobre los
 * mosaicos (`.mapa-oscuro` en `index.css`), no de otro proveedor.
 */

import 'leaflet/dist/leaflet.css'

import type { LatLngExpression } from 'leaflet'
import type { ReactNode } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip, ZoomControl } from 'react-leaflet'

import { BLANCO } from '@/components/paleta'

const MOSAICOS = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATRIBUCION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

export interface MapaBaseProps {
  titulo: string
  centro: LatLngExpression
  zoom: number
  /** Sin título visible, como el mapa del detalle; queda para lectores de pantalla. */
  ocultarTitulo?: boolean
  /**
   * Un solo punto: la última posición del envío en el detalle (`US-20`). Como
   * en los mapas del panel, el relleno es el de la etapa y el anillo el del
   * cumplimiento (`colorDelAnillo`, 03/11/2026).
   */
  marcador?: { posicion: LatLngExpression; etiqueta: string; color: string; anillo?: string }
  /** Capas propias, dentro del `MapContainer`: los embarques del panel. */
  children?: ReactNode
  /**
   * Más bajo (16:10 en vez de 5:4) para que en el panel la grilla se vea sin
   * deslizar (04/11/2026). El detalle del pedido conserva el alto de siempre.
   */
  compacto?: boolean
}

export function MapaBase({
  titulo,
  centro,
  zoom,
  ocultarTitulo,
  marcador,
  compacto = false,
  children,
}: MapaBaseProps) {
  const id = `mapa-${titulo.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className={ocultarTitulo ? 'sr-only' : 'mb-2 text-xl font-semibold'}>
        {titulo}
      </h2>
      <div
        className={`mapa-oscuro ${compacto ? 'aspect-[16/10]' : 'aspect-[5/4]'} overflow-hidden rounded border border-panel-borde`}
      >
        <MapContainer
          center={centro}
          zoom={zoom}
          minZoom={2}
          zoomControl={false}
          worldCopyJump
          className="h-full w-full bg-panel-mapa"
        >
          <TileLayer url={MOSAICOS} attribution={ATRIBUCION} />
          <ZoomControl position="bottomleft" />
          {marcador && (
            <CircleMarker
              center={marcador.posicion}
              radius={7}
              pathOptions={{
                color: marcador.anillo ?? BLANCO,
                weight: 3,
                fillColor: marcador.color,
                fillOpacity: 1,
              }}
            >
              <Tooltip direction="top" offset={[0, -6]}>
                {marcador.etiqueta}
              </Tooltip>
            </CircleMarker>
          )}
          {children}
        </MapContainer>
      </div>
    </section>
  )
}
