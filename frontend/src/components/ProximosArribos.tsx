/**
 * «Próximos Arribos» del Figma (RF-27, `US-28`): los cinco pedidos activos con
 * fecha proyectada más próxima dentro de los siguientes 7 días.
 *
 * **Sin relleno** (RF-27 del 01/09): si hay menos de cinco, van menos, y si no
 * hay ninguno, se dice. Mostrar pedidos fuera del horizonte haría que el bloque
 * afirmara que algo llega pronto cuando no.
 */

import { IconoVia } from '@/components/IconoVia'
import { useProximosArribos } from '@/hooks/usePedidos'
import type { Cumplimiento, ProximoArribo } from '@/types/api'
import { destinoCorto } from '@/utils/formatos'

const COLOR: Record<Cumplimiento, string> = {
  A_TIEMPO: 'bg-estado-a-tiempo',
  EN_RIESGO: 'bg-estado-riesgo',
  RETRASADO: 'bg-estado-retrasado',
}

const TEXTO_CUMPLIMIENTO: Record<Cumplimiento, string> = {
  A_TIEMPO: 'A tiempo',
  EN_RIESGO: 'En riesgo',
  RETRASADO: 'Retrasado',
}

/** «2026-10-15» → «15/10», como en las tarjetas del Figma. */
function diaMes(fecha: string | null): string {
  if (!fecha) return ''
  const [, mes, dia] = fecha.split('-')
  return `${dia}/${mes}`
}

function Tarjeta({ arribo }: { arribo: ProximoArribo }) {
  const cumplimiento = arribo.estado_cumplimiento
  const texto = cumplimiento ? TEXTO_CUMPLIMIENTO[cumplimiento] : 'Sin evaluar'
  return (
    <li className="grid min-w-0 grid-cols-[auto_1fr] gap-x-1 rounded bg-panel-cabecera p-1 text-[8px] leading-tight text-slate-300">
      <span
        role="img"
        aria-label={texto}
        title={texto}
        className={`mt-px h-3 w-3 rounded-sm ${cumplimiento ? COLOR[cumplimiento] : 'bg-slate-600'}`}
      />
      <span className="min-w-0">
        <span className="block whitespace-nowrap font-semibold tracking-tight">
          {arribo.oc_numero} - {arribo.posicion_oc}
        </span>
        <span className="block min-h-[2.5em] break-words">{arribo.material.descripcion}</span>
      </span>
      <IconoVia via={arribo.via_transporte} className="mt-0.5 h-3 w-4 text-slate-300" />
      <span className="mt-0.5 min-w-0">
        <span className="block" title={arribo.destino.nombre}>
          {destinoCorto(arribo)}
        </span>
        <span className="block font-semibold">
          {diaMes(arribo.fecha_proyectada_disponible)} -{' '}
          {arribo.dias_restantes === 0 ? 'hoy' : `${arribo.dias_restantes}d`}
        </span>
      </span>
    </li>
  )
}

export function ProximosArribos() {
  const { data, isPending, isError } = useProximosArribos()

  return (
    <section aria-labelledby="titulo-arribos">
      <h2 id="titulo-arribos" className="mb-2 pl-10 text-base text-slate-100">
        Próximos Arribos
      </h2>

      {isPending && <p className="pl-10 text-xs text-slate-500">Cargando…</p>}
      {isError && (
        <p role="alert" className="pl-10 text-xs text-red-300">
          No se pudieron cargar los próximos arribos.
        </p>
      )}
      {data && data.items.length === 0 && (
        <p className="pl-10 text-xs text-slate-400">
          Ningún pedido tiene fecha proyectada en los próximos {data.horizonte_dias} días.
        </p>
      )}
      {data && data.items.length > 0 && (
        <ul className="grid grid-cols-5 gap-1">
          {data.items.map((arribo) => (
            <Tarjeta key={arribo.id} arribo={arribo} />
          ))}
        </ul>
      )}
    </section>
  )
}
