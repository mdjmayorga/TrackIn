/**
 * La insignia de ShipsGo del encabezado; la regla vive en `utils/saludShipsGo`.
 *
 * **Al pasar el cursor** dice de cuándo es el rastreo (`US-23`, RF-20, RNF-12):
 * la última consulta buena a ShipsGo, que el worker repite cada minuto, y, si la
 * fuente falla, por qué. Desde el 26/10/2026 eso no ocupa una línea del panel:
 * va en un texto emergente de la insignia, a pedido de Compras.
 *
 * El texto emergente es propio y no el `title` del navegador: ese tarda en salir,
 * cambia de un navegador a otro y en algunos no aparece (visto el 26/10). Este
 * sale al instante con el cursor o al enfocar la insignia con el teclado.
 */

import { useId } from 'react'

import { useHealth } from '@/hooks/useHealth'
import { formatearFechaHora, haceCuanto } from '@/utils/fechas'
import { type Nivel, estadoShipsGo } from '@/utils/saludShipsGo'

const CLASES: Record<Nivel, string> = {
  // Letra negra, como el distintivo «A Tiempo»: con blanca no llega a 4,5:1 (`US-24`).
  ok: 'bg-estado-a-tiempo text-black',
  aviso: 'bg-amber-500 text-black',
  falla: 'bg-estado-retrasado text-white',
}

export function EstadoShipsGo() {
  const { data, isError } = useHealth()
  const idEmergente = useId()
  if (!data && !isError) return null
  const { nivel, texto, detalle } = estadoShipsGo(data, isError && !data)
  const contacto = data?.fuentes?.find((f) => f.fuente === 'shipsgo')?.ultimo_contacto_ok
  const ultima = contacto
    ? `Última consulta a ShipsGo: ${formatearFechaHora(contacto)} (${haceCuanto(contacto)})`
    : 'Todavía no hay consultas a ShipsGo.'

  return (
    <span className="group relative inline-block">
      <span
        role="status"
        // Enfocable, para que el texto emergente también se lea con el teclado.
        tabIndex={0}
        aria-describedby={idEmergente}
        className={`inline-block cursor-default rounded px-2 py-0.5 text-xs font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-marca-400 ${CLASES[nivel]}`}
      >
        {texto}
      </span>
      <span
        id={idEmergente}
        role="tooltip"
        className="pointer-events-none invisible absolute left-0 top-full z-[1100] mt-1 w-max max-w-xs rounded border border-panel-borde bg-panel-superficie px-3 py-2 text-left text-xs text-slate-100 opacity-0 shadow-lg transition-opacity group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100 lg:left-auto lg:right-0"
      >
        {detalle && <span className="mb-1 block text-slate-300">{detalle}</span>}
        <span className="block">{ultima}</span>
      </span>
    </span>
  )
}
