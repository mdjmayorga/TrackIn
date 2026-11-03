/**
 * El recuadro de un marcador del mapa (`US-27`, RF-18): se abre al hacer clic.
 *
 * Arriba, el embarque —quién, dónde está, cuándo se leyó—; debajo, cada pedido
 * que lleva con OC, material, proveedor, ETA, fecha proyectada, etapa y
 * cumplimiento —los dos juntos, no el estado de la grilla, que muestra uno u
 * otro según el caso (03/11/2026)—, y un enlace a su detalle. Al pasar el cursor el marcador sigue mostrando el rótulo
 * corto: con varios pedidos, todo esto no cabe en un tooltip.
 *
 * Va aparte del mapa para poder probarlo: en jsdom Leaflet no abre recuadros.
 */

import { Link } from 'react-router-dom'

import { CUMPLIMIENTOS, ETAPAS, type Apariencia } from '@/components/estados'
import type { MarcadorMapa } from '@/types/api'
import { formatearFecha } from '@/utils/fechas'
import { partesDelRotulo } from '@/utils/rotuloMapa'

export function DetalleDelEmbarque({
  marcador,
  rutaVisible = false,
  onVerRuta,
}: {
  marcador: MarcadorMapa
  rutaVisible?: boolean
  /**
   * En un grupo que no se separa (03/11/2026): no hay un marcador propio donde
   * hacer clic, así que la ruta se elige desde aquí.
   */
  onVerRuta?: () => void
}) {
  const p = partesDelRotulo(marcador)
  return (
    <section aria-label={p.quien}>
      <strong className="block">{p.quien}</strong>
      <span className="block">{p.estado}</span>
      <span className="block text-slate-500">{p.lectura}</span>
      {onVerRuta && marcador.trayecto?.length ? (
        <button
          type="button"
          onClick={onVerRuta}
          aria-pressed={rutaVisible}
          className="mt-1 rounded bg-slate-700 px-2 py-0.5 text-[11px] font-semibold text-white hover:bg-slate-600"
        >
          {rutaVisible ? 'Ocultar ruta' : 'Ver ruta'}
        </button>
      ) : null}
      <ul aria-label={`Pedidos de ${p.quien}`} className="mt-1.5 space-y-1.5">
        {marcador.pedidos.map((pedido) => {
          return (
            <li key={pedido.id} className="border-t border-slate-200 pt-1.5">
              <div className="flex items-center justify-between gap-2">
                <Link to={`/pedidos/${pedido.id}`} className="font-semibold text-sky-700 underline">
                  {pedido.oc_numero}-{pedido.posicion_oc}
                </Link>
                <span className="flex gap-1">
                  <Distintivo apariencia={ETAPAS[pedido.etapa_viaje]} />
                  {pedido.estado_cumplimiento ? (
                    <Distintivo apariencia={CUMPLIMIENTOS[pedido.estado_cumplimiento]} />
                  ) : (
                    <span className="text-[10px] text-slate-500">Sin fecha proyectada</span>
                  )}
                </span>
              </div>
              <span className="block">{pedido.material ?? 'Material sin dato'}</span>
              <span className="block text-slate-500">
                {pedido.proveedor ?? 'Proveedor sin dato'}
              </span>
              <span className="block">
                ETA {formatearFecha(pedido.eta) ?? '–'} · Proyectada{' '}
                {formatearFecha(pedido.fecha_proyectada) ?? '–'}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function Distintivo({ apariencia }: { apariencia: Apariencia }) {
  return (
    <span
      className="whitespace-nowrap rounded px-1.5 py-px text-[10px] font-semibold"
      style={{ background: apariencia.fondo, color: apariencia.letra }}
    >
      {apariencia.texto}
    </span>
  )
}
