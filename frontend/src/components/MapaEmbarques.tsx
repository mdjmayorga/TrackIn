/**
 * El mapa de una vía con sus embarques (`US-25`): un marcador por buque —un BL
 * lleva varias líneas—.
 *
 * - **Relleno y ruta con el color de la etapa; anillo con el del peor
 *   cumplimiento** (`wireframes.md` §2.2 y el Figma de los mapas): rojo si algo va
 *   retrasado, naranja si algo va en riesgo, blanco si no. Corregido el 03/11/2026:
 *   el mapa usaba el estado de la grilla, que es una etapa o un cumplimiento
 *   según el caso, y la ruta salía a veces del color del cumplimiento.
 * - **Los filtros del panel se aplican** (`US-21`): el mapa muestra el mismo
 *   subconjunto que la grilla.
 * - **Una lectura vieja se distingue**: borde punteado y relleno tenue, y la
 *   antigüedad en el rótulo. «Vieja» es más del doble de la frecuencia de
 *   consulta de la vía (lo decide el backend).
 * - **Los que se solapan se agrupan** en un círculo con el número, que al hacer
 *   clic acerca la vista hasta separarlos (`utils/agrupamiento`). Los que no se
 *   separan ni de cerca —dos guías en el mismo aeropuerto— muestran al clic el
 *   detalle de cada uno (02/11/2026), con «Ver ruta» para elegir cuál (03/11/2026).
 * - **Al pasar el cursor**, el rótulo corto; **al hacer clic**, el recuadro con
 *   cada pedido y el enlace a su detalle (`US-27`, `DetalleDelEmbarque`).
 *
 * Debajo del mapa, la leyenda (`LeyendaMapa`, 03/11/2026) y una lista solo para lectores de pantalla repite lo que el
 * mapa muestra: un mapa no se puede recorrer con el teclado.
 */

import L, { type LatLngExpression } from 'leaflet'
import { useState } from 'react'
import { CircleMarker, Marker, Polyline, Popup, Tooltip, useMap, useMapEvents } from 'react-leaflet'

import { DetalleDelEmbarque } from '@/components/DetalleDelEmbarque'
import { ETAPAS, colorDelAnillo, etapaMenosAvanzada, peorCumplimiento } from '@/components/estados'
import { LeyendaMapa } from '@/components/LeyendaMapa'
import { MapaBase } from '@/components/MapaBase'
import { RutaEmbarque } from '@/components/RutaEmbarque'
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
  /**
   * El panel pone la leyenda en otro lugar, contra el borde de la pantalla, para
   * darle ancho a la grilla (04/11/2026): ver `LeyendaDeCapa`.
   */
  leyendaAparte?: boolean
}

export function MapaEmbarques({
  titulo,
  capa,
  centro,
  zoom,
  filtros = FILTROS_VACIOS,
  leyendaAparte = false,
}: MapaEmbarquesProps) {
  const { data } = useMapa(capa, filtros)
  const marcadores = data?.marcadores ?? []
  const pedidos = marcadores.reduce((n, m) => n + m.pedidos.length, 0)

  return (
    <div>
      <MapaBase titulo={titulo} centro={centro} zoom={zoom} compacto>
        <CapaAgrupada marcadores={marcadores} />
      </MapaBase>
      {data && (
        <p className="mt-1 text-xs text-slate-400">
          {marcadores.length === 0
            ? 'Ningún embarque con posición'
            : `${marcadores.length} ${marcadores.length === 1 ? 'embarque' : 'embarques'} · ${pedidos} ${pedidos === 1 ? 'pedido' : 'pedidos'}`}
          {data.sin_posicion > 0 && ` · ${data.sin_posicion} sin posición`}
          {marcadores.some((m) => m.situacion === 'EN_VUELO') &&
            ' · ✈ posición estimada según el horario del vuelo'}
          {marcadores.some((m) => m.situacion === 'NAVEGANDO' || m.situacion === 'EN_PUERTO') &&
            ' · posición del barco estimada según su itinerario'}
          {marcadores.some((m) => m.trayecto?.length) && ' · clic en un embarque para ver su ruta'}
        </p>
      )}
      {data && !leyendaAparte && (
        <LeyendaMapa marcadores={marcadores} umbralHoras={data.umbral_desactualizada_h} />
      )}
      <ul aria-label={`Embarques en el ${titulo}`} className="sr-only">
        {marcadores.map((m) => (
          <li key={m.id_elemento}>{rotulo(m)}</li>
        ))}
      </ul>
    </div>
  )
}

/**
 * Una sola leyenda para los dos mapas del panel (04/11/2026): las dos decían lo
 * mismo salvo el umbral de lectura vieja, y el espacio de la segunda pasó a la
 * grilla. Las etapas son las de los dos mapas juntos. Pide los mismos datos que
 * los mapas, y React Query los comparte: no hay una consulta más.
 */
export function LeyendaDelPanel({ filtros = FILTROS_VACIOS }: { filtros?: FiltrosPanel }) {
  const maritimo = useMapa('MARITIMO', filtros).data
  const aereo = useMapa('AEREO', filtros).data
  if (!maritimo || !aereo) return null
  return (
    <LeyendaMapa
      marcadores={[...maritimo.marcadores, ...aereo.marcadores]}
      umbralesPorVia={{
        maritimo: maritimo.umbral_desactualizada_h,
        aereo: aereo.umbral_desactualizada_h,
      }}
      nombre="Leyenda de los mapas"
    />
  )
}

function CapaAgrupada({ marcadores }: { marcadores: MarcadorMapa[] }) {
  const mapa = useMap()
  const [zoom, setZoom] = useState(() => mapa.getZoom())
  // El embarque elegido muestra su ruta completa: un vuelo (02/11/2026) o un barco
  // (03/11/2026). Un clic en el fondo la oculta.
  const [elegido, setElegido] = useState<number | null>(null)
  useMapEvents({ zoomend: () => setZoom(mapa.getZoom()), click: () => setElegido(null) })
  const conRuta = marcadores.find((m) => m.id_elemento === elegido && m.trayecto?.length)
  const alternar = (m: MarcadorMapa) =>
    setElegido((actual) => (actual === m.id_elemento ? null : m.id_elemento))
  // Desde el recuadro de un grupo: además se cierra el recuadro y se encuadra la
  // ruta, que puede cruzar medio mundo desde donde está el grupo.
  const verRutaDesdeGrupo = (m: MarcadorMapa) => {
    if (elegido === m.id_elemento) {
      setElegido(null)
      return
    }
    setElegido(m.id_elemento)
    mapa.closePopup()
    const puntos = (m.trayecto ?? []).flatMap((tramo) => tramo.ruta)
    if (puntos.length) mapa.fitBounds(L.latLngBounds(puntos), { padding: [30, 30] })
  }

  const grupos = agrupar(
    marcadores.map((m) => {
      const punto = mapa.project([m.latitud, m.longitud], zoom)
      return { x: punto.x, y: punto.y, dato: m }
    }),
  )

  return (
    <>
      {conRuta?.trayecto && (
        <RutaEmbarque trayecto={conRuta.trayecto} color={ETAPAS[conRuta.etapa].fondo} />
      )}
      {grupos.map((g) =>
        g.datos.length === 1 ? (
          <Embarque
            key={g.datos[0].id_elemento}
            marcador={g.datos[0]}
            onElegir={g.datos[0].trayecto?.length ? alternar : undefined}
          />
        ) : (
          <Grupo
            key={g.datos.map((m) => m.id_elemento).join('-')}
            marcadores={g.datos}
            centro={mapa.unproject([g.x, g.y], zoom)}
            elegido={elegido}
            onVerRuta={verRutaDesdeGrupo}
          />
        ),
      )}
    </>
  )
}

function Embarque({
  marcador,
  onElegir,
}: {
  marcador: MarcadorMapa
  onElegir?: (m: MarcadorMapa) => void
}) {
  const eventos = onElegir ? { click: () => onElegir(marcador) } : undefined
  if (marcador.situacion === 'EN_VUELO') return <EnVuelo marcador={marcador} eventos={eventos} />
  const vieja = marcador.desactualizada
  return (
    <CircleMarker
      center={[marcador.latitud, marcador.longitud]}
      radius={7}
      eventHandlers={eventos}
      // Sin esto el clic llega también al mapa, que oculta la ruta recién elegida.
      bubblingMouseEvents={false}
      pathOptions={{
        color: colorDelAnillo(marcador.cumplimiento),
        weight: 3,
        dashArray: vieja ? '3 3' : undefined,
        fillColor: ETAPAS[marcador.etapa].fondo,
        fillOpacity: vieja ? 0.45 : 1,
      }}
    >
      <Tooltip direction="top" offset={[0, -6]} className="rotulo-mapa">
        <RotuloEnLineas marcador={marcador} />
      </Tooltip>
      <RecuadroDelEmbarque marcador={marcador} />
    </CircleMarker>
  )
}

/**
 * Un avión en vuelo (`US-26`): un ✈ del color del estado sobre su ruta punteada.
 * La posición es estimada con el horario del vuelo, y el rótulo lo dice.
 */
function EnVuelo({
  marcador,
  eventos,
}: {
  marcador: MarcadorMapa
  eventos?: { click: () => void }
}) {
  const apariencia = ETAPAS[marcador.etapa]
  const anillo = colorDelAnillo(marcador.cumplimiento)
  const icono = L.divIcon({
    className: '',
    iconSize: [24, 24],
    html: `<span style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:9999px;border:3px ${marcador.desactualizada ? 'dashed' : 'solid'} ${anillo};background:${apariencia.fondo};color:${apariencia.letra};font-size:13px;opacity:${marcador.desactualizada ? 0.6 : 1}">✈</span>`,
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
        eventHandlers={eventos}
        title={`${marcador.tipo} ${marcador.referencia}: en vuelo`}
      >
        <Tooltip direction="top" offset={[0, -12]} className="rotulo-mapa">
          <RotuloEnLineas marcador={marcador} />
        </Tooltip>
        <RecuadroDelEmbarque marcador={marcador} />
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
      <span className="block text-slate-500">Clic para ver los pedidos.</span>
    </>
  )
}

/** `US-27`: Leaflet lo abre al hacer clic en el marcador. */
function RecuadroDelEmbarque({ marcador }: { marcador: MarcadorMapa }) {
  return (
    <Popup className="rotulo-mapa">
      <DetalleDelEmbarque marcador={marcador} />
    </Popup>
  )
}

/** Hasta dónde acerca el clic en un grupo: más cerca ya no aporta en un mapa de panel. */
const ZOOM_MAXIMO_GRUPO = 12

function Grupo({
  marcadores,
  centro,
  elegido,
  onVerRuta,
}: {
  marcadores: MarcadorMapa[]
  centro: L.LatLng
  elegido: number | null
  onVerRuta: (m: MarcadorMapa) => void
}) {
  const mapa = useMap()
  // Si ni con el zoom máximo se separan, acercar no sirve: el 02/11/2026 dos MAWB
  // concluidas en SJO quedaban en un «2» sin forma de ver sus pedidos.
  const separables =
    agrupar(
      marcadores.map((m) => {
        const punto = mapa.project([m.latitud, m.longitud], ZOOM_MAXIMO_GRUPO)
        return { x: punto.x, y: punto.y, dato: m }
      }),
    ).length > 1
  const apariencia = ETAPAS[etapaMenosAvanzada(marcadores.map((m) => m.etapa))]
  const anillo = colorDelAnillo(peorCumplimiento(marcadores.map((m) => m.cumplimiento)))
  const icono = L.divIcon({
    className: '',
    iconSize: [30, 30],
    html: `<span style="display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:9999px;border:3px solid ${anillo};background:${apariencia.fondo};color:${apariencia.letra};font:600 12px sans-serif">${marcadores.length}</span>`,
  })
  const limites = L.latLngBounds(marcadores.map((m) => [m.latitud, m.longitud]))

  return (
    <Marker
      position={centro}
      icon={icono}
      title={
        separables
          ? `${marcadores.length} embarques: acercar`
          : `${marcadores.length} embarques en el mismo lugar: ver detalle`
      }
      eventHandlers={
        separables
          ? {
              click: () =>
                mapa.fitBounds(limites, { padding: [40, 40], maxZoom: ZOOM_MAXIMO_GRUPO }),
            }
          : undefined
      }
    >
      <Tooltip direction="top" offset={[0, -12]} className="rotulo-mapa">
        {separables
          ? `${marcadores.length} embarques. Clic para acercar.`
          : `${marcadores.length} embarques en el mismo lugar. Clic para ver el detalle.`}
      </Tooltip>
      {/* Sin manejador de clic, Leaflet abre el recuadro al hacer clic. */}
      {!separables && (
        <Popup className="rotulo-mapa">
          <DetalleDelGrupo marcadores={marcadores} elegido={elegido} onVerRuta={onVerRuta} />
        </Popup>
      )}
    </Marker>
  )
}

/**
 * El recuadro de un grupo que no se separa: cada embarque con sus pedidos
 * (`US-27`) y, si tiene trayecto, el botón para ver su ruta (03/11/2026).
 */
export function DetalleDelGrupo({
  marcadores,
  elegido = null,
  onVerRuta,
}: {
  marcadores: MarcadorMapa[]
  elegido?: number | null
  onVerRuta?: (m: MarcadorMapa) => void
}) {
  return (
    <ul aria-label="Embarques en este lugar" className="max-h-72 space-y-3 overflow-y-auto">
      {marcadores.map((m) => (
        <li
          key={m.id_elemento}
          className="border-t-2 border-slate-300 pt-2 first:border-0 first:pt-0"
        >
          <DetalleDelEmbarque
            marcador={m}
            rutaVisible={elegido === m.id_elemento}
            onVerRuta={onVerRuta && (() => onVerRuta(m))}
          />
        </li>
      ))}
    </ul>
  )
}
