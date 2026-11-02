/**
 * Asociar el identificador de rastreo a un pedido que no lo tiene (`US-20`,
 * wireframes §4.7). No hay botón que ejecute de un clic (§4.8); el motivo es
 * opcional, como en toda intervención (02/11/2026).
 *
 * La vía normal es el Z-tracking —las columnas de referencia del archivo—;
 * esto es para cuando la referencia llega por otro lado: un correo del agente,
 * un BL escaneado.
 *
 * **Con `corregir`** (29/10/2026) cambia una referencia mal escrita: un BL con
 * «BL» de más o con un dígito de menos no lo encuentra ShipsGo, y el pedido se
 * queda sin posición. Se cierra el tramo de la equivocada y se abre otro.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { refrescarTrasIntervenir } from '@/hooks/refrescar'
import { mensajeDeError } from '@/services/api'
import { asociarReferencia, corregirReferencia } from '@/services/pedidos'
import type { TipoReferencia, Via } from '@/types/api'

/**
 * Solo los tipos de la vía del pedido (21/10/2026): una guía aérea en un
 * marítimo, o un BL en un aéreo, iría a la fuente equivocada. El backend lo
 * rechaza igual (`referencia.tipos_de_via`); aquí ni se ofrece.
 */
function tipos(via: Via): Array<[TipoReferencia, string]> {
  if (via === 'AEREO') {
    return [
      ['MAWB', 'MAWB (guía madre)'],
      ['HAWB', 'HAWB (guía hija)'],
    ]
  }
  if (via === 'MARITIMO') {
    return [
      ['BL', 'BL'],
      ['CONTENEDOR', 'Contenedor'],
      ['BOOKING', 'Booking'],
    ]
  }
  return [] // la vía terrestre no se rastrea
}

export interface AsociarReferenciaProps {
  idPedido: number
  via: Via
  /** Corregir la referencia que ya tiene, en lugar de asociar una (29/10/2026). */
  corregir?: { tipo: string; numero: string }
  /** Al terminar bien: el detalle cierra el formulario de corrección. */
  onListo?: () => void
}

export function AsociarReferencia({ idPedido, via, corregir, onListo }: AsociarReferenciaProps) {
  const queryClient = useQueryClient()
  const opciones = tipos(via)
  const inicial = opciones.find(([clave]) => clave === corregir?.tipo)?.[0] ?? opciones[0]?.[0]
  const [tipo, setTipo] = useState<TipoReferencia | undefined>(inicial)
  const [numero, setNumero] = useState(corregir?.numero ?? '')
  const [motivo, setMotivo] = useState('')

  const asociar = useMutation({
    mutationFn: () =>
      (corregir ? corregirReferencia : asociarReferencia)(idPedido, {
        tipo: tipo!,
        numero,
        motivo: motivo.trim() || null,
      }),
    // Cambió la etapa: grilla, KPIs, arribos y bitácora se vuelven a pedir.
    onSuccess: (detalle) => {
      refrescarTrasIntervenir(queryClient, detalle)
      onListo?.()
    },
  })

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    asociar.mutate()
  }

  const mismo =
    corregir !== undefined && tipo === corregir.tipo && numero.trim() === corregir.numero
  const completo = numero.trim() !== '' && !mismo

  if (tipo === undefined) {
    return <p className="text-xs text-slate-400">La vía terrestre no se rastrea.</p>
  }

  return (
    <form
      onSubmit={enviar}
      aria-label={corregir ? 'Corregir referencia' : 'Asociar identificador de rastreo'}
      className="space-y-2"
    >
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
            placeholder={via === 'AEREO' ? '020-25244995' : 'COSU6508789000'}
            autoComplete="off"
            className="mt-0.5 rounded bg-panel-cabecera px-2 py-1 text-sm text-white placeholder:text-slate-500"
          />
        </label>
      </div>
      <label className="flex flex-col text-xs text-slate-300">
        Motivo (opcional)
        <textarea
          value={motivo}
          onChange={(e) => setMotivo(e.target.value.slice(0, 300))}
          rows={2}
          placeholder={
            corregir
              ? 'Qué estaba mal: «BL» de más, un dígito, otra naviera…'
              : 'Por qué se asocia a mano: de dónde salió la referencia'
          }
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
        {asociar.isPending ? 'Guardando…' : corregir ? 'Corregir' : 'Asociar'}
      </button>
    </form>
  )
}
