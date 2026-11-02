/**
 * La guía madre de una guía hija (`US-30`, la excepción manual del transbordo).
 *
 * Una guía hija (HAWB) no la sigue ninguna fuente comercial; la guía madre
 * (MAWB) que la ampara, sí. Dos usos:
 *
 * - **Desde la guía hija:** seguir por su guía madre. Si TICA la resolvió
 *   (`US-49`) viene escrita; si no —o si el agente dio otra—, se escribe a mano.
 * - **Corregirla** (29/10/2026): el pedido ya pasó de la hija a una madre que
 *   era la equivocada. Se escribe la correcta.
 *
 * En los dos casos se cierra el tramo vigente —su historial se conserva— y se
 * abre otro. La guía madre queda pendiente de alta en ShipsGo (`US-55`).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { refrescarTrasIntervenir } from '@/hooks/refrescar'
import { seguirGuiaMadre } from '@/services/acciones'
import { mensajeDeError } from '@/services/api'

export interface SeguirGuiaMadreProps {
  idPedido: number
  /** La que resolvió TICA, si la hay: viene precargada. */
  resueltaPorTica?: string | null
  /** `true` si el pedido ya se sigue por una guía madre y se quiere corregir. */
  corregir?: boolean
}

export function SeguirGuiaMadre({ idPedido, resueltaPorTica, corregir }: SeguirGuiaMadreProps) {
  const queryClient = useQueryClient()
  const [abierto, setAbierto] = useState(false)
  const [numero, setNumero] = useState(corregir ? '' : (resueltaPorTica ?? ''))
  const escrito = numero.trim()
  const cambio = useMutation({
    // Si quedó la de TICA tal cual, no se manda: así la bitácora dice «resolvió TICA».
    mutationFn: () =>
      seguirGuiaMadre(idPedido, {
        numero: escrito && escrito !== resueltaPorTica ? escrito : null,
        motivo: null,
      }),
    onSuccess: (detalle) => {
      refrescarTrasIntervenir(queryClient, detalle)
      setAbierto(false)
    },
  })

  const etiqueta = corregir
    ? 'Corregir guía madre'
    : resueltaPorTica
      ? 'Seguir por la guía madre'
      : 'Indicar guía madre'

  if (!abierto) {
    return (
      <button
        type="button"
        onClick={() => setAbierto(true)}
        className="mt-1 block text-xs text-marca-300 underline hover:text-marca-200"
      >
        {etiqueta}
      </button>
    )
  }
  return (
    <form
      aria-label={etiqueta}
      onSubmit={(e) => {
        e.preventDefault()
        if (escrito && !cambio.isPending) cambio.mutate()
      }}
      className="mt-2 space-y-2"
    >
      <label className="block text-xs text-slate-300">
        Guía madre (MAWB)
        <input
          value={numero}
          onChange={(e) => setNumero(e.target.value.toUpperCase())}
          placeholder="176-12345675"
          maxLength={20}
          className="mt-0.5 block w-48 rounded bg-panel-cabecera px-2 py-1 text-sm text-white"
        />
      </label>
      <p className="text-xs text-slate-400">
        {corregir
          ? 'Se cierra el tramo de la guía madre actual —queda en el historial— y se sigue por esta.'
          : 'Se cierra el tramo de la guía hija —queda en el historial— y se sigue por esta.'}{' '}
        La guía madre queda pendiente de alta en ShipsGo.
      </p>
      {cambio.isError && (
        <p role="alert" className="text-xs text-red-200">
          {mensajeDeError(cambio.error)}
        </p>
      )}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={!escrito || cambio.isPending}
          className="rounded bg-white px-3 py-1 text-xs font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
        >
          {cambio.isPending ? 'Guardando…' : 'Confirmar'}
        </button>
        <button
          type="button"
          onClick={() => setAbierto(false)}
          className="text-xs text-slate-300 underline"
        >
          Cancelar
        </button>
      </div>
    </form>
  )
}
