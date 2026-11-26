/**
 * Elegir el puerto de destino a mano (26/11/2026).
 *
 * Corrida en vivo con Compras: muchos marítimos todavía no tienen incoterm y la
 * carga los dejaba fuera. Ahora entran con el destino «Por definir» y aquí se
 * elige el puerto. También corrige uno ya asignado. Lo elegido a mano no lo
 * cambia el Z-tracking; ShipsGo sí, porque la naviera manda (`US-54`).
 *
 * Solo se ofrecen los destinos activos de la vía del pedido: un marítimo no
 * descarga en el aeropuerto. El backend lo vuelve a verificar.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { refrescarTrasIntervenir } from '@/hooks/refrescar'
import { mensajeDeError } from '@/services/api'
import { asignarDestino, listarDestinos } from '@/services/pedidos'
import type { Via } from '@/types/api'

export interface AsignarDestinoProps {
  idPedido: number
  via: Via
  /** El código del destino que ya tiene, para no ofrecerlo otra vez. */
  actual?: string | null
  /** Al terminar bien: el detalle cierra el formulario de cambio. */
  onListo?: () => void
}

export function AsignarDestino({ idPedido, via, actual = null, onListo }: AsignarDestinoProps) {
  const queryClient = useQueryClient()
  const destinos = useQuery({ queryKey: ['destinos'], queryFn: listarDestinos })
  const [codigo, setCodigo] = useState('')
  const [motivo, setMotivo] = useState('')

  const opciones = (destinos.data ?? [])
    .filter((d) => d.via_transporte === via && d.codigo !== actual)
    .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))

  const asignar = useMutation({
    mutationFn: () => asignarDestino(idPedido, { codigo, motivo: motivo.trim() || null }),
    // Cambia el lead time y la fecha proyectada: se vuelve a pedir todo.
    onSuccess: (detalle) => {
      refrescarTrasIntervenir(queryClient, detalle)
      onListo?.()
    },
  })

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    asignar.mutate()
  }

  return (
    <form onSubmit={enviar} aria-label="Asignar puerto de destino" className="space-y-2">
      <label className="flex flex-col text-xs text-slate-300">
        Puerto
        <select
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
          className="mt-0.5 rounded bg-panel-cabecera px-2 py-1 text-sm text-white"
        >
          <option value="">Elija un puerto</option>
          {opciones.map((d) => (
            <option key={d.codigo} value={d.codigo}>
              {d.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col text-xs text-slate-300">
        Motivo (opcional)
        <textarea
          value={motivo}
          onChange={(e) => setMotivo(e.target.value.slice(0, 300))}
          rows={2}
          placeholder="De dónde salió el puerto: el agente de carga, el proveedor…"
          className="mt-0.5 rounded bg-panel-cabecera px-2 py-1 text-sm text-white placeholder:text-slate-500"
        />
      </label>
      {(asignar.isError || destinos.isError) && (
        <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-xs text-red-100">
          {mensajeDeError(asignar.error ?? destinos.error)}
        </p>
      )}
      <button
        type="submit"
        disabled={codigo === '' || asignar.isPending}
        className="rounded bg-white px-3 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
      >
        {asignar.isPending ? 'Guardando…' : 'Asignar'}
      </button>
    </form>
  )
}
