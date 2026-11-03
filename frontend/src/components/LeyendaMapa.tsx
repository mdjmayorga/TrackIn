/**
 * La leyenda de los mapas del panel (`US-25`, `US-26`; RNF-08; `wireframes.md`
 * §2.4 y §3.9; el Figma de los dos mapas). Agregada el 03/11/2026: los
 * criterios de las historias no la nombraban y había quedado como una línea de
 * texto.
 *
 * Las mismas codificaciones que dibuja el mapa, con los mismos colores
 * (`estados.ts`), para que no puedan discrepar:
 *
 * - **Relleno:** la etapa. Solo las que hay en el mapa (§2.4).
 * - **Anillo:** el peor cumplimiento a bordo (§2.2).
 * - **Opacidad:** una lectura vieja se ve tenue y con borde punteado (RNF-12).
 * - **Trazo:** la ruta, continua lo recorrido y punteada lo previsto. Solo si
 *   hay embarques con ruta.
 */

import type { ReactNode } from 'react'

import { CUMPLIMIENTOS, ETAPAS, ORDEN_ETAPAS } from '@/components/estados'
import { BLANCO } from '@/components/paleta'
import type { MarcadorMapa } from '@/types/api'

/** El tono neutro de las muestras que no hablan de la etapa. */
const NEUTRO = ETAPAS.EN_TRANSITO.fondo

export function LeyendaMapa({
  marcadores,
  umbralHoras,
}: {
  marcadores: MarcadorMapa[]
  umbralHoras: number
}) {
  const etapas = ORDEN_ETAPAS.filter((e) => marcadores.some((m) => m.etapa === e))
  const conRuta = marcadores.some((m) => m.trayecto?.length)
  if (marcadores.length === 0) return null

  return (
    <section
      aria-label="Leyenda del mapa"
      className="mt-2 flex flex-wrap gap-x-8 gap-y-2 rounded border border-panel-borde px-3 py-2 text-xs text-slate-300"
    >
      <Grupo titulo="Relleno: etapa">
        {etapas.map((e) => (
          <Item key={e} muestra={<Punto relleno={ETAPAS[e].fondo} />}>
            {ETAPAS[e].texto}
          </Item>
        ))}
      </Grupo>
      <Grupo titulo="Anillo: cumplimiento">
        <Item muestra={<Punto relleno={NEUTRO} />}>Todos a tiempo</Item>
        <Item muestra={<Punto relleno={NEUTRO} anillo={CUMPLIMIENTOS.EN_RIESGO.fondo} />}>
          Alguno en riesgo
        </Item>
        <Item muestra={<Punto relleno={NEUTRO} anillo={CUMPLIMIENTOS.RETRASADO.fondo} />}>
          Alguno retrasado
        </Item>
      </Grupo>
      <Grupo titulo="Opacidad: lectura">
        <Item muestra={<Punto relleno={NEUTRO} />}>Lectura reciente</Item>
        <Item muestra={<Punto relleno={NEUTRO} vieja />}>
          Sin lectura en más de {umbralHoras} h
        </Item>
      </Grupo>
      {conRuta && (
        <Grupo titulo="Trazo: ruta">
          <Item muestra={<Linea />}>Recorrido</Item>
          <Item muestra={<Linea prevista />}>Previsto</Item>
        </Grupo>
      )}
    </section>
  )
}

function Grupo({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div>
      <h3 className="mb-1 font-semibold text-slate-200">{titulo}</h3>
      <ul className="space-y-0.5">{children}</ul>
    </div>
  )
}

function Item({ muestra, children }: { muestra: ReactNode; children: ReactNode }) {
  return (
    <li className="flex items-center gap-2">
      <span aria-hidden="true" className="flex w-6 justify-center">
        {muestra}
      </span>
      {children}
    </li>
  )
}

/** Como el marcador del mapa: relleno de la etapa, anillo de 3 px, tenue si es viejo. */
function Punto({
  relleno,
  anillo = BLANCO,
  vieja = false,
}: {
  relleno: string
  anillo?: string
  vieja?: boolean
}) {
  return (
    <span
      className="inline-block h-3.5 w-3.5 rounded-full"
      style={{
        background: relleno,
        border: `3px ${vieja ? 'dashed' : 'solid'} ${anillo}`,
        opacity: vieja ? 0.45 : 1,
      }}
    />
  )
}

function Linea({ prevista = false }: { prevista?: boolean }) {
  return (
    <span
      className="inline-block w-6"
      style={{ borderTop: `2px ${prevista ? 'dashed' : 'solid'} ${NEUTRO}` }}
    />
  )
}
