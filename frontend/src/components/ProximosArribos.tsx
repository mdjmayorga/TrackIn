/**
 * «Próximos Arribos» del Figma (RF-27): los cinco pedidos con fecha proyectada
 * más próxima dentro de los siguientes 7 días.
 *
 * **Por ahora muestra los cinco ejemplos del Figma**, pedidos tal cual para
 * revisar el diseño. No son pedidos reales: `US-28` los reemplaza por la
 * consulta, y entonces el cuadro de color será el cumplimiento de cada uno.
 */

import { IconoVia } from '@/components/IconoVia'
import type { Cumplimiento, Via } from '@/types/api'

interface Arribo {
  oc: string
  pos: number
  material: string
  via: Via
  destino: string
  fecha: string
  dias: number
  cumplimiento: Cumplimiento
}

const EJEMPLOS_FIGMA: Arribo[] = [
  {
    oc: '4500013044',
    pos: 10,
    material: 'Dióxido de Titanio',
    via: 'AEREO',
    destino: 'MROC',
    fecha: '28/08',
    dias: 3,
    cumplimiento: 'EN_RIESGO',
  },
  {
    oc: '4500012993',
    pos: 30,
    material: 'Celulosa microcristalina',
    via: 'MARITIMO',
    destino: 'Moín',
    fecha: '29/08',
    dias: 4,
    cumplimiento: 'RETRASADO',
  },
  {
    oc: '4500012760',
    pos: 40,
    material: 'Tapa polipropileno 28 mm',
    via: 'MARITIMO',
    destino: 'Moín',
    fecha: '30/08',
    dias: 5,
    cumplimiento: 'A_TIEMPO',
  },
  {
    oc: '4500012847',
    pos: 10,
    material: 'Lactosa monohidrato',
    via: 'MARITIMO',
    destino: 'Moín',
    fecha: '02/09',
    dias: 8,
    cumplimiento: 'A_TIEMPO',
  },
  {
    oc: '4500012847',
    pos: 20,
    material: 'Estearato de magnesio',
    via: 'AEREO',
    destino: 'MROC',
    fecha: '02/09',
    dias: 8,
    cumplimiento: 'A_TIEMPO',
  },
]

const COLOR: Record<Cumplimiento, string> = {
  A_TIEMPO: 'bg-estado-a-tiempo',
  EN_RIESGO: 'bg-estado-riesgo',
  RETRASADO: 'bg-estado-retrasado',
}

export function ProximosArribos() {
  return (
    <section aria-labelledby="titulo-arribos">
      <h2 id="titulo-arribos" className="mb-2 pl-10 text-base text-slate-100">
        Próximos Arribos
      </h2>
      <ul
        className="grid grid-cols-5 gap-1"
        title="Ejemplos del Figma: los arribos reales llegan con US-28"
      >
        {EJEMPLOS_FIGMA.map((a) => (
          <li
            key={`${a.oc}-${a.pos}`}
            className="grid min-w-0 grid-cols-[auto_1fr] gap-x-1 rounded bg-panel-cabecera p-1 text-[8px] leading-tight text-slate-300"
          >
            <span
              aria-hidden="true"
              className={`mt-px h-3 w-3 rounded-sm ${COLOR[a.cumplimiento]}`}
            />
            <span className="min-w-0">
              <span className="block whitespace-nowrap font-semibold tracking-tight">
                {a.oc} - {a.pos}
              </span>
              <span className="block min-h-[2.5em] break-words">{a.material}</span>
            </span>
            <IconoVia via={a.via} className="mt-0.5 h-3 w-4 text-slate-300" />
            <span className="mt-0.5 min-w-0">
              <span className="block">{a.destino}</span>
              <span className="block font-semibold">
                {a.fecha} - {a.dias}d
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
