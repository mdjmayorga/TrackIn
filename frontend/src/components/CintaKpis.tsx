/**
 * La cinta de indicadores del Figma (RF-15, `US-22`): cinco recuadros en una
 * sola línea, centrados entre los dos mapas.
 *
 * Los porcentajes son sobre los activos **con fecha proyectada**, y suman
 * 100 % como en el Figma. Los activos sin proyección se dicen debajo: sin esa
 * línea, «33 % a tiempo» sobre 9 de 107 pedidos parecería hablar de todos.
 */

import { useIndicadores } from '@/hooks/usePedidos'
import type { IndicadoresKpi, Porcentaje } from '@/types/api'
import type { FiltrosPanel } from '@/utils/filtros'
import { formatearDias, formatearPorcentaje } from '@/utils/formatos'

interface Recuadro {
  titulo: string
  valor: string | null
  conteo?: number
}

function recuadros(kpi: IndicadoresKpi | undefined): Recuadro[] {
  const cumplimiento = (titulo: string, dato: Porcentaje | undefined): Recuadro => ({
    titulo,
    valor: dato ? formatearPorcentaje(dato.porcentaje) : null,
    conteo: dato?.pedidos,
  })
  return [
    { titulo: 'Pedidos Activos', valor: kpi ? String(kpi.activos) : null },
    cumplimiento('A Tiempo', kpi?.a_tiempo),
    cumplimiento('En Riesgo', kpi?.en_riesgo),
    cumplimiento('Retrasados', kpi?.retrasados),
    { titulo: 'Lead Time Medio', valor: kpi ? formatearDias(kpi.lead_time_medio_dias) : null },
  ]
}

export function CintaKpis({ filtros }: { filtros?: FiltrosPanel }) {
  const { data, isError } = useIndicadores(filtros)

  return (
    <section aria-label="Indicadores de los pedidos activos">
      <ul className="mx-auto grid max-w-md grid-cols-5 gap-1.5">
        {recuadros(data).map(({ titulo, valor, conteo }) => (
          <li
            key={titulo}
            className="flex min-w-0 flex-col items-center justify-center rounded border border-slate-400/70 px-0.5 py-1 text-center"
          >
            <p className="whitespace-nowrap text-lg font-bold leading-none tracking-tight text-white">
              {valor ?? '–'}
            </p>
            <p className="mt-1 text-[9px] leading-tight text-slate-300">
              {conteo !== undefined && (
                <>
                  ({conteo} {conteo === 1 ? 'pedido' : 'pedidos'})
                  <br />
                </>
              )}
              {titulo}
            </p>
          </li>
        ))}
      </ul>
      {data && data.sin_proyeccion > 0 && (
        <p className="mt-1 text-center text-[10px] text-slate-400">
          {data.sin_proyeccion} de {data.activos} activos sin fecha proyectada: no entran en los
          porcentajes.
        </p>
      )}
      {isError && (
        <p role="alert" className="mt-1 text-center text-[10px] text-red-300">
          No se pudieron calcular los indicadores.
        </p>
      )}
    </section>
  )
}
