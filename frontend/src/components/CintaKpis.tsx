/**
 * La cinta de indicadores del Figma (RF-15): cinco recuadros en una sola línea,
 * centrados entre los dos mapas. Los valores llegan con `US-22` —pedidos
 * activos, el reparto por cumplimiento sobre los activos y el lead time
 * medio—; hasta entonces van en guion, para no mostrar cifras inventadas.
 */

const INDICADORES = [
  { titulo: 'Pedidos Activos', conConteo: false },
  { titulo: 'A Tiempo', conConteo: true },
  { titulo: 'En Riesgo', conConteo: true },
  { titulo: 'Retrasados', conConteo: true },
  { titulo: 'Lead Time Medio', conConteo: false },
]

export function CintaKpis() {
  return (
    <section
      aria-label="Indicadores de los pedidos activos"
      title="Los indicadores llegan con US-22"
    >
      <ul className="mx-auto grid max-w-md grid-cols-5 gap-1.5">
        {INDICADORES.map(({ titulo, conConteo }) => (
          <li
            key={titulo}
            className="flex min-w-0 flex-col items-center justify-center rounded border border-slate-400/70 px-0.5 py-1 text-center"
          >
            <p className="text-xl font-bold leading-none text-white">–</p>
            <p className="mt-1 text-[9px] leading-tight text-slate-300">
              {conConteo && (
                <>
                  (– pedidos)
                  <br />
                </>
              )}
              {titulo}
            </p>
          </li>
        ))}
      </ul>
    </section>
  )
}
