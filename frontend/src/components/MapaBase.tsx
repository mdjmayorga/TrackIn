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
import { MapContainer, TileLayer, ZoomControl } from 'react-leaflet'

const MOSAICOS = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATRIBUCION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

export interface MapaBaseProps {
  titulo: string
  centro: LatLngExpression
  zoom: number
}

export function MapaBase({ titulo, centro, zoom }: MapaBaseProps) {
  const id = `mapa-${titulo.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="mb-2 text-xl font-semibold">
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
        </MapContainer>
      </div>
    </section>
  )
}
