/**
 * Asociar el identificador de rastreo a un pedido que no lo tiene (`US-20`,
 * wireframes §4.7). Como toda intervención, pide el motivo (RF-14): no hay
 * botón que ejecute de un clic (§4.8).
 *
 * La vía normal es el Z-tracking —las columnas de referencia del archivo—;
 * esto es para cuando la referencia llega por otro lado: un correo del agente,
 * un BL escaneado.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { refrescarTrasIntervenir } from '@/hooks/refrescar'
import { mensajeDeError } from '@/services/api'
import { asociarReferencia } from '@/services/pedidos'
import type { TipoReferencia, Via } from '@/types/api'

/** Las del aéreo primero si el pedido es aéreo: es lo que se va a elegir. */
function tipos(via: Via): Array<[TipoReferencia, string]> {
  const maritimos: Array<[TipoReferencia, string]> = [
    ['BL', 'BL'],
    ['CONTENEDOR', 'Contenedor'],
    ['BOOKING', 'Booking'],
  ]
  const aereos: Array<[TipoReferencia, string]> = [
    ['MAWB', 'MAWB (guía madre)'],
    ['HAWB', 'HAWB (guía hija)'],
  ]
  return via === 'AEREO' ? [...aereos, ...maritimos] : [...maritimos, ...aereos]
}

/** El mínimo del backend (`auditoria.LONGITUD_MINIMA_MOTIVO`). */
const MOTIVO_MINIMO = 5

export function AsociarReferencia({ idPedido, via }: { idPedido: number; via: Via }) {
  const queryClient = useQueryClient()
  const opciones = tipos(via)
  const [tipo, setTipo] = useState<TipoReferencia>(opciones[0][0])
  const [numero, setNumero] = useState('')
  const [motivo, setMotivo] = useState('')

  const asociar = useMutation({
    mutationFn: () => asociarReferencia(idPedido, { tipo, numero, motivo }),
    // Cambió la etapa: grilla, KPIs, arribos y bitácora se vuelven a pedir.
    onSuccess: (detalle) => refrescarTrasIntervenir(queryClient, detalle),
  })

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    asociar.mutate()
  }

  const completo = numero.trim() !== '' && motivo.trim().length >= MOTIVO_MINIMO

  return (
    <form onSubmit={enviar} aria-label="Asociar identificador de rastreo" className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <label className="flex flex-col text-xs text-slate-300">
          Tipo
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoReferencia)}
            className="mt-0.5 rounded bg-panel-cabecera px-2 py-1 text-sm text-white"
          >
            {opciones.map(([clave, texto]) => (
              <option key={clave} value={clave}>
                {texto}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 flex-col text-xs text-slate-300">
          Número
          <input
            value={numero}
            onChange={(e) => setNumero(e.target.value.slice(0, 40))}
            placeholder="COSU6508789000"
            autoComplete="off"
            className="mt-0.5 rounded bg-panel-cabecera px-2 py-1 text-sm text-white placeholder:text-slate-500"
          />
        </label>
      </div>
      <label className="flex flex-col text-xs text-slate-300">
        Motivo (obligatorio)
        <textarea
          value={motivo}
          onChange={(e) => setMotivo(e.target.value.slice(0, 300))}
          rows={2}
          placeholder="Por qué se asocia a mano: de dónde salió la referencia"
          className="mt-0.5 rounded bg-panel-cabecera px-2 py-1 text-sm text-white placeholder:text-slate-500"
        />
      </label>
      {asociar.isError && (
        <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-xs text-red-100">
          {mensajeDeError(asociar.error)}
        </p>
      )}
      <button
        type="submit"
        disabled={!completo || asociar.isPending}
        className="rounded bg-white px-3 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
      >
        {asociar.isPending ? 'Asociando…' : 'Asociar'}
      </button>
    </form>
  )
}
