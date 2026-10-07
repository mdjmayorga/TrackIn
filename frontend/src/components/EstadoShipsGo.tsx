/** La insignia de ShipsGo del encabezado; la regla vive en `utils/saludShipsGo`. */

import { useHealth } from '@/hooks/useHealth'
import { type Nivel, estadoShipsGo } from '@/utils/saludShipsGo'

const CLASES: Record<Nivel, string> = {
  ok: 'bg-estado-a-tiempo text-white',
  aviso: 'bg-amber-500 text-black',
  falla: 'bg-estado-retrasado text-white',
}

export function EstadoShipsGo() {
  const { data, isError } = useHealth()
  if (!data && !isError) return null
  const { nivel, texto, detalle } = estadoShipsGo(data, isError && !data)
  return (
    <span
      role="status"
      title={detalle}
      className={`rounded px-2 py-0.5 text-xs font-medium ${CLASES[nivel]}`}
    >
      {texto}
    </span>
  )
}
