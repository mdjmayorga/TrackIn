/**
 * Detalle de un pedido (`US-20`, RF-05, Figma «US-37 Detalle de pedido»).
 *
 * La vista existe para hacer **auditable un número** (wireframes §4.1): de
 * dónde sale la fecha proyectada, con qué insumos, y qué tan viejos son. Por
 * eso cada dato del desglose viene con su origen, y la última consulta a la
 * fuente con su antigüedad (RNF-12).
 *
 * Fuera de esta historia, aunque el Figma los muestre: los hitos del viaje y el
 * trayecto en la línea de tiempo y el mapa (`US-29`, `US-44`). La barra de
 * acciones del pie es `US-60` (`AccionesPedido`).
 */

import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'

import { puedeAsociar } from '@/auth/permisos'
import { useSesion } from '@/auth/useSesion'
import { AccionesPedido } from '@/components/AccionesPedido'
import { AsociarReferencia } from '@/components/AsociarReferencia'
import { Distintivo } from '@/components/Distintivo'
import { CUMPLIMIENTOS, ETAPAS, etapaVisible } from '@/components/estados'
import { MapaBase } from '@/components/MapaBase'
import { useBitacora, usePedido } from '@/hooks/usePedidos'
import { mensajeDeError } from '@/services/api'
import type { AsientoBitacora, PedidoDetalle } from '@/types/api'
import {
  INTERVENCIONES,
  ORIGENES,
  formatearCantidad,
  formatearDiasConSigno,
  formatearNudos,
  formatearPosicion,
} from '@/utils/detalle'
import { formatearFecha, formatearFechaHora, haceCuanto } from '@/utils/fechas'
import { destinoCorto } from '@/utils/formatos'

export default function DetallePedido() {
  const { id } = useParams()
  const idPedido = Number(id)
  const { data: pedido, error, isPending } = usePedido(idPedido)

  return (
    <div className="min-h-screen bg-panel-fondo px-4 pb-12 pt-4 text-slate-100 sm:px-8">
      <Link to="/" className="text-sm text-slate-200 hover:text-white">
        ← Volver al dashboard
      </Link>

      {isPending && <p className="mt-10 text-slate-400">Cargando el pedido…</p>}
      {error && (
        <p role="alert" className="mt-10 rounded bg-red-900/60 px-4 py-3 text-sm text-red-100">
          No se pudo cargar el pedido: {mensajeDeError(error)}
        </p>
      )}
      {pedido && <Contenido pedido={pedido} />}
    </div>
  )
}

function Contenido({ pedido }: { pedido: PedidoDetalle }) {
  const cumplimiento = pedido.estado_cumplimiento
  return (
    <>
      <header className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">
            {pedido.oc_numero} · {pedido.posicion_oc}
          </h1>
          <p className="mt-2 text-lg text-slate-200">
            {pedido.material.codigo} | {pedido.material.descripcion} | {pedido.proveedor.nombre} |{' '}
            {formatearCantidad(pedido.cantidad_pedida, pedido.unidad_medida)}
          </p>
        </div>
        <p className="flex flex-wrap items-center gap-2 text-lg">
          Etapa: <Distintivo {...ETAPAS[etapaVisible(pedido)]} />
          <span aria-hidden="true">|</span>
          Cumplimiento:{' '}
          {cumplimiento ? (
            <Distintivo {...CUMPLIMIENTOS[cumplimiento]} />
          ) : (
            <span title="Sin fecha proyectada: no se puede evaluar">–</span>
          )}
        </p>
      </header>

      <div className="mt-10 grid gap-10 lg:grid-cols-2">
        <Desglose pedido={pedido} />
        <div className="space-y-8">
          <ElementoRastreado pedido={pedido} />
          <BloqueArribo pedido={pedido} />
          <Cierre pedido={pedido} />
        </div>
      </div>

      <div className="mt-10 grid gap-10 lg:grid-cols-[2fr_3fr]">
        <LineaDeTiempo idPedido={pedido.id} />
        <MapaDelEnvio pedido={pedido} />
      </div>

      <AccionesPedido pedido={pedido} />
    </>
  )
}

// --- Bloques --------------------------------------------------------------------

function Bloque({ titulo, children }: { titulo: string; children: ReactNode }) {
  const id = `bloque-${titulo.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="mb-3 text-xl font-semibold underline underline-offset-4">
        {titulo}
      </h2>
      {children}
    </section>
  )
}

function Fila({
  etiqueta,
  children,
  fuerte = false,
}: {
  etiqueta: string
  children: ReactNode
  fuerte?: boolean
}) {
  return (
    <div className={`grid grid-cols-2 gap-4 py-1.5 ${fuerte ? 'font-semibold' : ''}`}>
      <dt className="text-slate-300">{etiqueta}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function SinDato({ children }: { children: ReactNode }) {
  return <span className="italic text-slate-400">{children}</span>
}

function Desglose({ pedido }: { pedido: PedidoDetalle }) {
  const c = pedido.calculo
  return (
    <Bloque titulo="Desglose del cálculo">
      <dl>
        <Fila etiqueta="ETA utilizada">
          {c.eta_utilizada ? (
            <>
              {formatearFechaHora(c.eta_utilizada)}
              {c.origen && (
                <span className="block text-xs text-slate-400">
                  {ORIGENES[c.origen] ?? c.origen}
                </span>
              )}
            </>
          ) : (
            <SinDato>Sin fecha de llegada</SinDato>
          )}
        </Fila>
        <Fila etiqueta="+ Lead time del destino">
          {c.lead_time_dias} días
          {c.lead_time_maestro_dias !== c.lead_time_dias && (
            <span className="block text-xs text-amber-300">
              El maestro dice hoy {c.lead_time_maestro_dias} días; se aplica en el próximo
              recálculo.
            </span>
          )}
        </Fila>
        <Fila etiqueta="+ Ajuste manual">{c.ajuste_manual_dias} días</Fila>
        <div className="my-2 border-t border-slate-500" />
        <Fila etiqueta="= Fecha proyectada" fuerte>
          {formatearFecha(c.fecha_proyectada) ?? <SinDato>No estimable</SinDato>}
        </Fila>
        <Fila etiqueta="Fecha comprometida">{formatearFecha(c.fecha_comprometida)}</Fila>
        <Fila etiqueta="Margen">
          {c.margen_dias === null ? (
            <SinDato>–</SinDato>
          ) : (
            <span className={c.margen_dias < 0 ? 'text-red-300' : ''}>
              {formatearDiasConSigno(c.margen_dias)}
            </span>
          )}
        </Fila>
      </dl>
      {/* «No estimable» no es un error y hay que decirlo con su causa (§4.4). */}
      <p className="mt-3 text-sm text-slate-400">{c.desglose}</p>
      {!c.al_dia && c.desglose_actual && (
        <p className="mt-2 rounded bg-amber-900/40 px-3 py-2 text-sm text-amber-100">
          Un insumo cambió y falta el recálculo. Con los datos de hoy: {c.desglose_actual}
        </p>
      )}
    </Bloque>
  )
}

function ElementoRastreado({ pedido }: { pedido: PedidoDetalle }) {
  const sesion = useSesion()
  const r = pedido.rastreo
  const via = pedido.via_transporte === 'AEREO' ? 'Aérea' : 'Marítima'
  const destino = `${via} | destino ${destinoCorto(pedido)}`

  if (!r) {
    return (
      <Bloque titulo="Elemento rastreado y arribo">
        <dl>
          <Fila etiqueta="Tracking">
            <SinDato>No rastreable: sin identificador</SinDato>
          </Fila>
          <Fila etiqueta="Vía">{destino}</Fila>
        </dl>
        <div className="mt-3 rounded border border-panel-borde p-3">
          <p className="mb-3 text-sm text-slate-300">
            Sin BL, contenedor o guía no hay fuente que consultar: la fecha proyectada depende de la
            ETA escrita en el Z-tracking. Lo normal es que la referencia llegue en las columnas del
            archivo; si la tiene por otro medio, puede asociarla aquí.
          </p>
          {puedeAsociar(sesion?.usuario.rol) ? (
            <AsociarReferencia idPedido={pedido.id} via={pedido.via_transporte} />
          ) : (
            <p className="text-sm text-slate-400">La asocian Logística y Compras.</p>
          )}
        </div>
      </Bloque>
    )
  }

  const nudos = formatearNudos(r.velocidad_nudos)
  return (
    <Bloque titulo="Elemento rastreado y arribo">
      <dl>
        <Fila etiqueta="Tracking">
          {r.tipo} {r.referencia}
          {r.nombre && ` · ${r.nombre}`}
          {r.guia_madre && (
            <span className="block text-xs text-slate-400">Guía madre {r.guia_madre}</span>
          )}
        </Fila>
        <Fila etiqueta="Vía">{destino}</Fila>
        <Fila etiqueta="Últ. posición">
          {r.posicion ? (
            <>
              {formatearPosicion(r.posicion.latitud, r.posicion.longitud)}
              {nudos && ` | ${nudos}`}
            </>
          ) : (
            <SinDato>Sin posición conocida</SinDato>
          )}
        </Fila>
        <Fila etiqueta="Últ. consulta">
          {r.ultima_consulta_exitosa ? (
            `${formatearFechaHora(r.ultima_consulta_exitosa)} | ${haceCuanto(r.ultima_consulta_exitosa)}`
          ) : (
            <SinDato>La fuente todavía no respondió</SinDato>
          )}
          {!r.activo && (
            <span className="block text-xs text-slate-400">Ya arribó: no se consulta más.</span>
          )}
        </Fila>
      </dl>
    </Bloque>
  )
}

function BloqueArribo({ pedido }: { pedido: PedidoDetalle }) {
  const a = pedido.arribos
  const fecha = (valor: string | null, vacio: string) =>
    valor ? formatearFechaHora(valor) : <SinDato>{vacio}</SinDato>
  return (
    <Bloque titulo="Arribo">
      {/* Tres arribos distintos, y esta es la única vista que los distingue (§4.3). */}
      <dl>
        <Fila etiqueta="Manual">{fecha(a.confirmado, 'Sin confirmar')}</Fila>
        <Fila etiqueta="Fuente">{fecha(a.fuente, 'Sin reportar')}</Fila>
        <Fila etiqueta="Inferido">{fecha(a.inferido, 'Fuera de la geocerca')}</Fila>
      </dl>
    </Bloque>
  )
}

function Cierre({ pedido }: { pedido: PedidoDetalle }) {
  const c = pedido.cierre
  if (!c.fecha_recepcion_planta && !c.motivo_cierre) return null
  return (
    <Bloque titulo="Recepción y cierre">
      <dl>
        {c.fecha_recepcion_planta && (
          <Fila etiqueta="Recepción en planta">
            {formatearFechaHora(c.fecha_recepcion_planta)}
            {c.cantidad_recibida &&
              ` | ${formatearCantidad(c.cantidad_recibida, pedido.unidad_medida)}`}
          </Fila>
        )}
        {c.liberacion_estimada && !c.fecha_liberacion_calidad && (
          <Fila etiqueta="Liberación estimada">
            {formatearFecha(c.liberacion_estimada.desde)} a{' '}
            {formatearFecha(c.liberacion_estimada.hasta)}
          </Fila>
        )}
        {c.fecha_liberacion_calidad && (
          <Fila etiqueta="Liberado por Calidad">
            {formatearFechaHora(c.fecha_liberacion_calidad)}
          </Fila>
        )}
        {c.motivo_cierre && <Fila etiqueta="Motivo de cierre">{c.motivo_cierre}</Fila>}
      </dl>
    </Bloque>
  )
}

function LineaDeTiempo({ idPedido }: { idPedido: number }) {
  const { data, isPending, error } = useBitacora(idPedido)
  return (
    <Bloque titulo="Línea de tiempo">
      {isPending && <p className="text-sm text-slate-400">Cargando…</p>}
      {error && (
        <p role="alert" className="text-sm text-red-300">
          No se pudo cargar la bitácora.
        </p>
      )}
      {data && data.length === 0 && (
        <p className="text-sm text-slate-400">Sin intervenciones registradas.</p>
      )}
      {data && data.length > 0 && (
        <ol className="space-y-4 border-l border-dotted border-slate-400 pl-4">
          {/* La más reciente arriba, como en el Figma. */}
          {[...data].reverse().map((asiento, n) => (
            <Evento key={`${asiento.fecha_hora}-${n}`} asiento={asiento} />
          ))}
        </ol>
      )}
      <p className="mt-4 text-xs text-slate-500">
        Por ahora, las intervenciones manuales. Los hitos del viaje se agregan con el historial de
        rastreo.
      </p>
    </Bloque>
  )
}

function Evento({ asiento }: { asiento: AsientoBitacora }) {
  const cambio =
    asiento.valor_anterior || asiento.valor_nuevo
      ? `${asiento.valor_anterior ?? '—'} → ${asiento.valor_nuevo ?? '—'}`
      : null
  return (
    <li className="relative text-sm">
      <span
        aria-hidden="true"
        className="absolute -left-[1.4rem] top-1 h-2.5 w-2.5 rounded-full bg-slate-300"
      />
      <p className="text-slate-400">{formatearFechaHora(asiento.fecha_hora)}</p>
      <p className="font-semibold">{INTERVENCIONES[asiento.tipo] ?? asiento.tipo}</p>
      {cambio && <p className="text-slate-300">{cambio}</p>}
      <p className="text-slate-300">«{asiento.motivo}»</p>
      <p className="text-xs text-slate-500">
        {asiento.nombre_usuario} ({asiento.rol})
      </p>
    </li>
  )
}

function MapaDelEnvio({ pedido }: { pedido: PedidoDetalle }) {
  const posicion = pedido.rastreo?.posicion
  if (!posicion) {
    return (
      <div className="flex min-h-[16rem] items-center justify-center rounded border border-panel-borde bg-panel-mapa px-6 text-center text-sm text-slate-400">
        Sin posición conocida: el mapa del envío aparece cuando la fuente reporta una.
      </div>
    )
  }
  const centro: [number, number] = [posicion.latitud, posicion.longitud]
  const r = pedido.rastreo!
  return (
    <MapaBase
      titulo="Mapa del envío"
      ocultarTitulo
      centro={centro}
      zoom={5}
      marcador={{ posicion: centro, etiqueta: r.nombre ?? `${r.tipo} ${r.referencia}` }}
    />
  )
}
