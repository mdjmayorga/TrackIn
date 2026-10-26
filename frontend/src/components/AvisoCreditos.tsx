/**
 * El aviso de créditos de ShipsGo en el panel (`US-57`): una franja centrada bajo
 * el subtítulo «Tracking aéreo-marítimo», encima de los KPIs y la grilla. La
 * ubicación la dejó Compras a criterio del desarrollador (26/10/2026).
 *
 * Solo para Compras y el Administrador, que son quienes autorizan las altas y la
 * compra de créditos. Aparece cuando el saldo pide atención —80 % consumido,
 * agotado, vencido, a 60 días del vencimiento o sin paquete registrado—; con el
 * saldo en orden no ocupa lugar.
 */

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { obtenerCreditos } from '@/services/shipsgo'
import type { EstadoCreditos } from '@/types/api'

/** Cada alta lo cambia, y las altas se ven en minutos: no hace falta más seguido. */
const REFRESCO_MS = 5 * 60_000

const URGENTES: ReadonlySet<EstadoCreditos['nivel']> = new Set(['AGOTADO', 'VENCIDO'])

export function AvisoCreditos() {
  const { data } = useQuery({
    queryKey: ['shipsgo', 'creditos'],
    queryFn: obtenerCreditos,
    refetchInterval: REFRESCO_MS,
  })
  if (!data || data.nivel === 'OK') return null
  const urgente = URGENTES.has(data.nivel)

  return (
    <div className="flex justify-center px-4 pb-3">
      <p
        role={urgente ? 'alert' : 'status'}
        aria-label="Créditos de ShipsGo"
        className={`max-w-3xl rounded px-4 py-2 text-center text-sm ${
          urgente ? 'bg-red-900/80 text-red-50' : 'bg-amber-900/60 text-amber-50'
        }`}
      >
        {data.mensaje}{' '}
        <Link to="/shipsgo/altas" className="font-semibold underline">
          {data.nivel === 'SIN_PAQUETE' ? 'Registrar el paquete' : 'Ver créditos'}
        </Link>
      </p>
    </div>
  )
}
