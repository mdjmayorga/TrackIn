/**
 * «Ajustes Z-tracking» (pedido del 26/10/2026): todo lo de la carga semanal del
 * archivo en un botón del encabezado, con el mismo estilo que «Arribos
 * pendientes». Al abrirlo: el estado de la carga de la semana, la última carga y
 * el enlace para cargar —Compras y Administrador— o para ver el historial.
 *
 * **La burbuja avisa sin abrir el menú**, con el color de la urgencia (`US-23`):
 *
 * | Situación | Burbuja |
 * |---|---|
 * | Al día | Ninguna |
 * | Toca cargar (hasta el día límite) o nunca se cargó | Naranja, el de «En Riesgo» |
 * | Atrasada (pasó el día límite) | Roja, el de «Retrasado» |
 *
 * SAP se actualiza los lunes y Compras carga a más tardar el martes (acuerdo del
 * 22/10/2026, parámetro `dia_limite_carga`). La situación la calcula el backend
 * en hora de Costa Rica (`GET /api/v1/cargas/estado`).
 */

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { puedeCargar } from '@/auth/permisos'
import { useDesplegable } from '@/hooks/useDesplegable'
import { obtenerEstadoCargas } from '@/services/cargas'
import type { EstadoCargas, Rol } from '@/types/api'
import { formatearFechaHora } from '@/utils/fechas'

const DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

/** Se recalcula solo: el aviso cambia el miércoles sin recargar la página. */
const REFRESCO_MS = 5 * 60_000

type Situacion = EstadoCargas['situacion']

const BURBUJA: Record<Exclude<Situacion, 'AL_DIA'>, string> = {
  TOCA_CARGAR: 'bg-estado-riesgo text-black',
  NUNCA: 'bg-estado-riesgo text-black',
  ATRASADA: 'bg-estado-retrasado text-white',
}

function mensaje(estado: EstadoCargas): string {
  const limite = DIAS[estado.dia_limite - 1] ?? 'martes'
  return {
    AL_DIA: 'La carga de esta semana está hecha.',
    TOCA_CARGAR: `Toca cargar el Z-tracking de esta semana (a más tardar el ${limite}).`,
    ATRASADA: `Falta la carga del Z-tracking de esta semana: el plazo era el ${limite}.`,
    NUNCA: 'El Z-tracking todavía no se cargó desde TrackIn.',
  }[estado.situacion]
}

/** Lo que dice el nombre accesible: la burbuja sola no se lee. */
const LECTURA: Record<Situacion, string> = {
  AL_DIA: 'al día',
  TOCA_CARGAR: 'toca cargar',
  ATRASADA: 'carga atrasada',
  NUNCA: 'nunca cargado',
}

const OPCION =
  'block w-full px-4 py-2 text-left text-sm text-slate-100 hover:bg-white/10 focus:bg-white/10 focus:outline-none'

export function MenuZtracking({ rol }: { rol: Rol }) {
  const { abierto, alternar, cerrar, contenedor, boton, idPanel } = useDesplegable()
  // Bajo `pedidos`: una carga nueva invalida `pedidos` y esto se refresca con ella.
  const { data } = useQuery({
    queryKey: ['pedidos', 'estado-cargas'],
    queryFn: obtenerEstadoCargas,
    refetchInterval: REFRESCO_MS,
  })
  const situacion = data?.situacion
  const urgente = situacion !== undefined && situacion !== 'AL_DIA'

  return (
    <div ref={contenedor} className="relative inline-block">
      <button
        ref={boton}
        type="button"
        aria-expanded={abierto}
        aria-controls={idPanel}
        aria-label={`Ajustes Z-tracking${situacion ? ` (${LECTURA[situacion]})` : ''}`}
        onClick={alternar}
        className="group relative inline-flex items-center gap-2 rounded-lg bg-panel-cabecera py-1.5 pl-2.5 pr-3.5 text-sm text-slate-50 hover:bg-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-marca-400"
      >
        <IconoHoja />
        Ajustes Z-tracking
        {urgente && (
          <span
            aria-hidden="true"
            className={`absolute -right-2 -top-2 min-w-[1.375rem] rounded-full px-1.5 text-center text-xs font-bold leading-[1.375rem] ring-2 ring-panel-fondo ${BURBUJA[situacion]}`}
          >
            !
          </span>
        )}
      </button>

      {abierto && (
        <div
          id={idPanel}
          className="absolute left-0 z-[1100] mt-1 w-72 overflow-hidden rounded border border-panel-borde bg-panel-superficie shadow-lg"
        >
          {data ? (
            <div className="space-y-2 border-b border-panel-borde px-4 py-3 text-sm">
              <p
                role={situacion === 'ATRASADA' ? 'alert' : 'status'}
                className={
                  situacion === 'ATRASADA'
                    ? 'font-semibold text-red-300'
                    : urgente
                      ? 'font-semibold text-amber-200'
                      : 'text-slate-200'
                }
              >
                {mensaje(data)}
              </p>
              <p className="text-xs text-slate-400">
                {data.ultima ? (
                  <>
                    Última carga: {formatearFechaHora(data.ultima.realizada_en)}, por{' '}
                    {data.ultima.usuario.nombre_completo}
                  </>
                ) : (
                  'Todavía no hay cargas hechas desde TrackIn.'
                )}
              </p>
            </div>
          ) : (
            <p className="border-b border-panel-borde px-4 py-3 text-sm text-slate-400">
              Cargando…
            </p>
          )}
          <ul>
            <li>
              <Link to="/cargas" onClick={cerrar} className={OPCION}>
                {puedeCargar(rol) ? 'Cargar Z-tracking' : 'Historial de cargas'}
              </Link>
            </li>
          </ul>
        </div>
      )}
    </div>
  )
}

/** Una hoja de cálculo: el Excel del Z-tracking. */
function IconoHoja() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M4 9h16M4 15h16M10 3v18" />
    </svg>
  )
}
