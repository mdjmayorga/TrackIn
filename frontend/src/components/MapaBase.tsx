/**
 * Un mapa del dashboard, por ahora sin marcadores: el fondo cartográfico, el
 * encuadre del Caribe y Centroamérica y los controles de zoom del Figma.
 * Los marcadores llegan con `US-35` (naves) y `US-36` (aeronaves).
 *
 * Los mosaicos son de OpenStreetMap (wireframes §2.8: la red de Gutis no los
 * bloquea). Su política exige la atribución visible, que Leaflet pone abajo a
 * la derecha. El tono gris oscuro del Figma sale de un filtro CSS sobre los
 * mosaicos (`.mapa-oscuro` en `index.css`), no de otro proveedor.
 */

import 'leaflet/dist/leaflet.css'

import type { LatLngExpression } from 'leaflet'
import { CircleMarker, MapContainer, TileLayer, Tooltip, ZoomControl } from 'react-leaflet'

const MOSAICOS = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATRIBUCION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

export interface MapaBaseProps {
  titulo: string
  centro: LatLngExpression
  zoom: number
  /** Sin título visible, como el mapa del detalle; queda para lectores de pantalla. */
  ocultarTitulo?: boolean
  /** Un solo punto: la última posición del envío en el detalle (`US-20`). */
  marcador?: { posicion: LatLngExpression; etiqueta: string }
}

export function MapaBase({ titulo, centro, zoom, ocultarTitulo, marcador }: MapaBaseProps) {
  const id = `mapa-${titulo.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className={ocultarTitulo ? 'sr-only' : 'mb-2 text-xl font-semibold'}>
        {titulo}
      </h2>
      <div className="mapa-oscuro aspect-[5/4] overflow-hidden rounded border border-panel-borde">
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
              pathOptions={{ color: '#ffffff', weight: 2, fillColor: '#0b4dff', fillOpacity: 1 }}
            >
              <Tooltip direction="top" offset={[0, -6]}>
                {marcador.etiqueta}
              </Tooltip>
            </CircleMarker>
          )}
        </MapContainer>
      </div>
    </section>
  )
}
