/**
 * De cuándo son los datos del panel (`US-23`, RF-20, RNF-12), bajo la insignia
 * de ShipsGo del encabezado, como en el Figma («Última actualización …»).
 *
 * Los datos tienen dos orígenes que envejecen a ritmos distintos, y se dicen
 * por separado:
 *
 * - **El rastreo**: lo consulta el worker cada minuto. Se muestra la última
 *   consulta buena a ShipsGo; si la fuente falla, la insignia lo dice y esta
 *   línea da la antigüedad del último dato válido.
 * - **El Z-tracking**: lo carga Compras cada semana. SAP se actualiza los lunes
 *   y la carga va a más tardar el martes (acuerdo del 22/10/2026). Hasta el día
 *   límite se recuerda; después se avisa, y a quien puede cargar se le ofrece
 *   el enlace.
 */

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { puedeCargar } from '@/auth/permisos'
import { useHealth } from '@/hooks/useHealth'
import { obtenerEstadoCargas } from '@/services/cargas'
import type { EstadoCargas, Rol } from '@/types/api'
import { formatearFechaHora, haceCuanto } from '@/utils/fechas'

const DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

/** La situación se recalcula sola: el aviso aparece el miércoles sin recargar la página. */
const REFRESCO_MS = 5 * 60_000

export function FrescuraDatos({ rol }: { rol: Rol }) {
  const salud = useHealth()
  // Bajo `pedidos`: una carga nueva invalida `pedidos` y esto se refresca con ella.
  const cargas = useQuery({
    queryKey: ['pedidos', 'estado-cargas'],
    queryFn: obtenerEstadoCargas,
    refetchInterval: REFRESCO_MS,
  })

  const contacto = salud.data?.fuentes?.find((f) => f.fuente === 'shipsgo')?.ultimo_contacto_ok

  return (
    <div className="space-y-1 text-right text-xs text-slate-300">
      <p>
        Última consulta a ShipsGo:{' '}
        {contacto ? (
          <>
            {formatearFechaHora(contacto)}{' '}
            <span className="text-slate-500">({haceCuanto(contacto)})</span>
          </>
        ) : (
          <span className="text-slate-500">todavía no hay</span>
        )}
      </p>
      {cargas.data && <LineaCarga estado={cargas.data} />}
      {cargas.data && <AvisoCarga estado={cargas.data} rol={rol} />}
    </div>
  )
}

function LineaCarga({ estado }: { estado: EstadoCargas }) {
  if (!estado.ultima) {
    return (
      <p>
        Z-tracking: <span className="text-slate-500">nunca se cargó desde TrackIn</span>
      </p>
    )
  }
  return (
    <p>
      Z-tracking: {formatearFechaHora(estado.ultima.realizada_en)}{' '}
      <span className="text-slate-500">(por {estado.ultima.usuario.nombre_completo})</span>
    </p>
  )
}

function AvisoCarga({ estado, rol }: { estado: EstadoCargas; rol: Rol }) {
  if (estado.situacion === 'AL_DIA') return null
  const limite = DIAS[estado.dia_limite - 1] ?? 'martes'
  const texto = {
    TOCA_CARGAR: `Toca cargar el Z-tracking de esta semana (a más tardar el ${limite}).`,
    ATRASADA: `Falta la carga del Z-tracking de esta semana: el plazo era el ${limite}.`,
    NUNCA: 'El Z-tracking todavía no se cargó desde TrackIn.',
  }[estado.situacion]
  const atrasada = estado.situacion === 'ATRASADA'

  return (
    <p
      role={atrasada ? 'alert' : 'status'}
      className={`inline-block rounded px-2 py-1 text-left ${
        atrasada ? 'bg-red-900/70 text-red-100' : 'bg-amber-900/50 text-amber-100'
      }`}
    >
      {texto}
      {puedeCargar(rol) && (
        <>
          {' '}
          <Link to="/cargas" className="font-semibold underline">
            Cargar Z-tracking
          </Link>
        </>
      )}
    </p>
  )
}
