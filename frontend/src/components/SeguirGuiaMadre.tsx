/**
 * «Seguir por la guía madre» (`US-30`, la excepción manual del transbordo).
 *
 * Una guía hija (HAWB) no la sigue ninguna fuente comercial. Cuando TICA
 * encuentra la guía madre que la ampara (`US-49`), el pedido puede pasar a
 * seguirse por ella: se cierra el tramo de la hija —su historial se conserva— y
 * se abre otro con la MAWB. Después queda pendiente su alta en ShipsGo, que
 * cuesta un crédito y decide Compras (`US-55`).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { refrescarTrasIntervenir } from '@/hooks/refrescar'
import { mensajeDeError } from '@/services/api'
import { seguirGuiaMadre } from '@/services/acciones'

export function SeguirGuiaMadre({ idPedido, guiaMadre }: { idPedido: number; guiaMadre: string }) {
  const queryClient = useQueryClient()
  const [confirmando, setConfirmando] = useState(false)
  const cambio = useMutation({
    mutationFn: () => seguirGuiaMadre(idPedido, { motivo: null }),
    onSuccess: (detalle) => refrescarTrasIntervenir(queryClient, detalle),
  })

  if (!confirmando) {
    return (
      <button
        type="button"
        onClick={() => setConfirmando(true)}
        className="mt-1 block text-xs text-marca-300 underline hover:text-marca-200"
      >
        Seguir por la guía madre
      </button>
    )
  }
  return (
    <div role="alertdialog" aria-labelledby="confirmar-guia-madre" className="mt-2 space-y-2">
      <p id="confirmar-guia-madre" className="text-xs text-slate-300">
        El pedido pasa a seguirse por la guía madre {guiaMadre}. El tramo de la guía hija queda en
        el historial, y la guía madre queda pendiente de alta en ShipsGo.
      </p>
      {cambio.isError && (
        <p role="alert" className="text-xs text-red-200">
          {mensajeDeError(cambio.error)}
        </p>
      )}
      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => cambio.mutate()}
          disabled={cambio.isPending}
          className="rounded bg-white px-3 py-1 text-xs font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
        >
          {cambio.isPending ? 'Guardando…' : 'Confirmar'}
        </button>
        <button
          type="button"
          onClick={() => setConfirmando(false)}
          className="text-xs text-slate-300 underline"
        >
          Cancelar
        </button>
      </div>
    </div>
  )
}
