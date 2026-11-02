/**
 * La ruta completa de una guía aérea (02/11/2026): un trazo por vuelo y un punto
 * por aeropuerto. La usan el detalle del pedido y el mapa del panel al elegir un
 * vuelo.
 *
 * Incluye los vuelos que ShipsGo no dibuja y TrackIn reconstruye con los eventos
 * (`shipsgo.completar_tramos`): sin ellos, una guía que llegó a SJO por
 * Fráncfort se veía terminar en Fráncfort.
 *
 * Un vuelo ya aterrizado va en trazo continuo; uno pendiente o en curso,
 * punteado.
 */

import { CircleMarker, Polyline, Tooltip } from 'react-leaflet'

import { BLANCO } from '@/components/paleta'
import type { TramoMapa } from '@/types/api'

export function RutaAerea({
  trayecto,
  color,
  ahora = new Date(),
}: {
  trayecto: TramoMapa[]
  color: string
  ahora?: Date
}) {
  const aeropuertos = new Map<string, [number, number]>()
  for (const tramo of trayecto) {
    if (tramo.origen && tramo.ruta.length) aeropuertos.set(tramo.origen, tramo.ruta[0])
    if (tramo.destino && tramo.ruta.length)
      aeropuertos.set(tramo.destino, tramo.ruta[tramo.ruta.length - 1])
  }
  return (
    <>
      {trayecto.map((tramo, i) => (
        <Polyline
          key={`${tramo.vuelo ?? 'tramo'}-${i}`}
          positions={tramo.ruta}
          pathOptions={{
            color,
            weight: 2,
            opacity: 0.8,
            dashArray: aterrizo(tramo, ahora) ? undefined : '4 6',
          }}
        >
          <Tooltip sticky className="rotulo-mapa">
            {`${tramo.vuelo ?? 'Vuelo'} ${tramo.origen ?? '?'} → ${tramo.destino ?? '?'}`}
          </Tooltip>
        </Polyline>
      ))}
      {[...aeropuertos].map(([codigo, posicion]) => (
        <CircleMarker
          key={codigo}
          center={posicion}
          radius={4}
          pathOptions={{ color: BLANCO, weight: 1, fillColor: color, fillOpacity: 1 }}
        >
          <Tooltip direction="top" offset={[0, -4]} className="rotulo-mapa">
            {codigo}
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  )
}

function aterrizo(tramo: TramoMapa, ahora: Date): boolean {
  return tramo.llegada !== null && new Date(tramo.llegada) <= ahora
}
