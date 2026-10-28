/**
 * El mapa de una vía con sus embarques (`US-25`): un marcador por buque —un BL
 * lleva varias líneas—, coloreado por el estado más urgente de sus pedidos con
 * el mismo color de la grilla (`US-24`).
 *
 * - **Los filtros del panel se aplican** (`US-21`): el mapa muestra el mismo
 *   subconjunto que la grilla.
 * - **Una lectura vieja se distingue**: borde punteado y relleno tenue, y la
 *   antigüedad en el rótulo. «Vieja» es más del doble de la frecuencia de
 *   consulta de la vía (lo decide el backend).
 * - **Los que se solapan se agrupan** en un círculo con el número, que al hacer
 *   clic acerca la vista hasta separarlos (`utils/agrupamiento`).
 *
 * Debajo del mapa, una lista solo para lectores de pantalla repite lo que el
 * mapa muestra: un mapa no se puede recorrer con el teclado.
 */

import L, { type LatLngExpression } from 'leaflet'
import { useState } from 'react'
import { CircleMarker, Marker, Polyline, Tooltip, useMap, useMapEvents } from 'react-leaflet'

import { aparienciaDeEstado, estadoMasUrgente } from '@/components/estados'
import { MapaBase } from '@/components/MapaBase'
import { BLANCO } from '@/components/paleta'
import { useMapa } from '@/hooks/usePedidos'
import type { MarcadorMapa } from '@/types/api'
import { agrupar } from '@/utils/agrupamiento'
import { FILTROS_VACIOS, type FiltrosPanel } from '@/utils/filtros'
import { partesDelRotulo, rotulo } from '@/utils/rotuloMapa'

export interface MapaEmbarquesProps {
  titulo: string
  capa: 'MARITIMO' | 'AEREO'
  centro: LatLngExpression
  zoom: number
  filtros?: FiltrosPanel
}

export function MapaEmbarques({
  titulo,
  capa,
  centro,
  zoom,
  filtros = FILTROS_VACIOS,
}: MapaEmbarquesProps) {
  const { data } = useMapa(capa, filtros)
  const marcadores = data?.marcadores ?? []
  const pedidos = marcadores.reduce((n, m) => n + m.pedidos.length, 0)

  return (
    <div>
      <MapaBase titulo={titulo} centro={centro} zoom={zoom}>
        <CapaAgrupada marcadores={marcadores} />
      </MapaBase>
      {data && (
        <p className="mt-1 text-xs text-slate-400">
          {marcadores.length === 0
            ? 'Ningún embarque con posición'
            : `${marcadores.length} ${marcadores.length === 1 ? 'embarque' : 'embarques'} · ${pedidos} ${pedidos === 1 ? 'pedido' : 'pedidos'}`}
          {data.sin_posicion > 0 && ` · ${data.sin_posicion} sin posición`}
          {marcadores.some((m) => m.desactualizada) &&
            ` · borde punteado: sin lectura en más de ${data.umbral_desactualizada_h} h`}
          {marcadores.some((m) => m.situacion === 'EN_VUELO') &&
            ' · ✈ posición estimada según el horario del vuelo'}
        </p>
      )}
      <ul aria-label={`Embarques en el ${titulo}`} className="sr-only">
        {marcadores.map((m) => (
          <li key={m.id_elemento}>{rotulo(m)}</li>
        ))}
      </ul>
    </div>
  )
}

function CapaAgrupada({ marcadores }: { marcadores: MarcadorMapa[] }) {
  const mapa = useMap()
  const [zoom, setZoom] = useState(() => mapa.getZoom())
  useMapEvents({ zoomend: () => setZoom(mapa.getZoom()) })

  const grupos = agrupar(
    marcadores.map((m) => {
      const punto = mapa.project([m.latitud, m.longitud], zoom)
      return { x: punto.x, y: punto.y, dato: m }
    }),
  )

  return (
    <>
      {grupos.map((g) =>
        g.datos.length === 1 ? (
          <Embarque key={g.datos[0].id_elemento} marcador={g.datos[0]} />
        ) : (
          <Grupo
            key={g.datos.map((m) => m.id_elemento).join('-')}
            marcadores={g.datos}
            centro={mapa.unproject([g.x, g.y], zoom)}
          />
        ),
      )}
    </>
  )
}

function Embarque({ marcador }: { marcador: MarcadorMapa }) {
  if (marcador.situacion === 'EN_VUELO') return <EnVuelo marcador={marcador} />
  const vieja = marcador.desactualizada
  return (
    <CircleMarker
      center={[marcador.latitud, marcador.longitud]}
      radius={7}
      pathOptions={{
        color: BLANCO,
        weight: 2,
        dashArray: vieja ? '3 3' : undefined,
        fillColor: aparienciaDeEstado(marcador.estado).fondo,
        fillOpacity: vieja ? 0.45 : 1,
      }}
    >
      <Tooltip direction="top" offset={[0, -6]} className="rotulo-mapa">
        <RotuloEnLineas marcador={marcador} />
      </Tooltip>
    </CircleMarker>
  )
}

/**
 * Un avión en vuelo (`US-26`): un ✈ del color del estado sobre su ruta punteada.
 * La posición es estimada con el horario del vuelo, y el rótulo lo dice.
 */
function EnVuelo({ marcador }: { marcador: MarcadorMapa }) {
  const apariencia = aparienciaDeEstado(marcador.estado)
  const icono = L.divIcon({
    className: '',
    iconSize: [24, 24],
    html: `<span style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:9999px;border:2px ${marcador.desactualizada ? 'dashed' : 'solid'} ${BLANCO};background:${apariencia.fondo};color:${apariencia.letra};font-size:13px;opacity:${marcador.desactualizada ? 0.6 : 1}">✈</span>`,
  })
  return (
    <>
      {marcador.ruta && (
        <Polyline
          positions={marcador.ruta}
          pathOptions={{ color: apariencia.fondo, weight: 2, dashArray: '4 6', opacity: 0.7 }}
        />
      )}
      <Marker
        position={[marcador.latitud, marcador.longitud]}
        icon={icono}
        title={`${marcador.tipo} ${marcador.referencia}: en vuelo`}
      >
        <Tooltip direction="top" offset={[0, -12]} className="rotulo-mapa">
          <RotuloEnLineas marcador={marcador} />
        </Tooltip>
      </Marker>
    </>
  )
}

/**
 * El rótulo del marcador en cuatro líneas cortas, no en una frase. Leaflet dibuja
 * el tooltip en una sola línea sin cortes: con el rótulo completo se salía del
 * recuadro del mapa y quedaba ilegible (pedido del 28/10/2026). La clase
 * `rotulo-mapa` (`index.css`) le da letra chica y un ancho máximo.
 */
function RotuloEnLineas({ marcador }: { marcador: MarcadorMapa }) {
  const p = partesDelRotulo(marcador)
  return (
    <>
      <strong className="block">{p.quien}</strong>
      <span className="block">{p.estado}</span>
      <span className="block">{p.pedidos}</span>
      <span className="block text-slate-500">{p.lectura}</span>
    </>
  )
}

function Grupo({ marcadores, centro }: { marcadores: MarcadorMapa[]; centro: L.LatLng }) {
  const mapa = useMap()
  const apariencia = aparienciaDeEstado(estadoMasUrgente(marcadores.map((m) => m.estado)))
  const icono = L.divIcon({
    className: '',
    iconSize: [30, 30],
    html: `<span style="display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:9999px;border:2px solid ${BLANCO};background:${apariencia.fondo};color:${apariencia.letra};font:600 12px sans-serif">${marcadores.length}</span>`,
  })
  const limites = L.latLngBounds(marcadores.map((m) => [m.latitud, m.longitud]))

  return (
    <Marker
      position={centro}
      icon={icono}
      title={`${marcadores.length} embarques: acercar`}
      eventHandlers={{
        // Acercar hasta separarlos; si están en el mismo punto, al máximo útil.
        click: () => mapa.fitBounds(limites, { padding: [40, 40], maxZoom: 12 }),
      }}
    >
      <Tooltip direction="top" offset={[0, -12]} className="rotulo-mapa">
        {`${marcadores.length} embarques. Clic para acercar.`}
      </Tooltip>
    </Marker>
  )
}
