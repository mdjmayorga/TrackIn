/**
 * «Arribos pendientes de gestión» (`US-48`, RF-32): los pedidos que llegaron a
 * destino y esperan que alguien registre el paso a proceso aduanal (`US-14`).
 *
 * Es la lista de trabajo de Planificación: lo que lleva más tiempo esperando
 * va primero, y el paso a aduana se registra desde aquí mismo, con el motivo
 * obligatorio de RF-14. Al registrarlo el pedido deja `EN_DESTINO` y sale de
 * la bandeja. El aviso es solo dentro de la aplicación: no hay correo
 * (decisión del 04/09).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { puedeVerBandeja } from '@/auth/permisos'
import { useSesion } from '@/auth/useSesion'
import { MOTIVO_MINIMO } from '@/components/AccionesPedido'
import { IconoVia } from '@/components/IconoVia'
import { refrescarTrasIntervenir } from '@/hooks/refrescar'
import { useBandejaArribos } from '@/hooks/usePedidos'
import { pasarAAduana } from '@/services/acciones'
import { mensajeDeError } from '@/services/api'
import type { PedidoResumen } from '@/types/api'
import { formatearFecha, formatearFechaHora, haceCuanto } from '@/utils/fechas'
import { destinoCorto } from '@/utils/formatos'

export default function Bandeja() {
  const sesion = useSesion()
  const habilitada = puedeVerBandeja(sesion?.usuario.rol)

  return (
    <div className="min-h-screen bg-panel-fondo text-slate-100">
      <header className="flex flex-wrap items-baseline justify-between gap-2 px-6 py-4">
        <h1 className="text-2xl font-bold">Arribos pendientes de gestión</h1>
        <Link to="/" className="text-sm text-marca-300 underline hover:text-marca-200">
          ← Volver al panel
        </Link>
      </header>

      <main className="mx-auto max-w-5xl px-6 pb-12">
        {habilitada ? (
          <Lista />
        ) : (
          <p className="text-sm text-slate-400">
            La bandeja es de Planificación, Logística y Compras, que registran el paso a proceso
            aduanal.
          </p>
        )}
      </main>
    </div>
  )
}

function Lista() {
  const { data, isPending, isError, error } = useBandejaArribos()
  const [abierto, setAbierto] = useState<number | null>(null)

  if (isPending) return <p className="text-sm text-slate-500">Cargando…</p>
  if (isError) {
    return (
      <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-sm text-red-100">
        No se pudo cargar la bandeja: {mensajeDeError(error)}
      </p>
    )
  }
  if (data.items.length === 0) {
    return (
      <p className="rounded border border-panel-borde bg-panel-superficie px-4 py-6 text-center text-slate-300">
        No hay arribos pendientes. Cuando un pedido llegue a destino aparecerá aquí para registrar
        su paso a proceso aduanal.
      </p>
    )
  }

  return (
    <section aria-label="Arribos pendientes">
      <p className="mb-3 text-sm text-slate-400">
        {data.total === 1
          ? '1 pedido llegó a destino y espera el paso a proceso aduanal.'
          : `${data.total} pedidos llegaron a destino y esperan el paso a proceso aduanal.`}{' '}
        Primero los que llevan más tiempo esperando.
        {data.total > data.items.length && ` Se muestran los ${data.items.length} más antiguos.`}
      </p>

      <ul className="space-y-3">
        {data.items.map((pedido) => (
          <Arribo
            key={pedido.id}
            pedido={pedido}
            abierto={abierto === pedido.id}
            onAbrir={() => setAbierto(abierto === pedido.id ? null : pedido.id)}
            onListo={() => setAbierto(null)}
          />
        ))}
      </ul>
    </section>
  )
}

interface ArriboProps {
  pedido: PedidoResumen
  abierto: boolean
  onAbrir: () => void
  onListo: () => void
}

function Arribo({ pedido, abierto, onAbrir, onListo }: ArriboProps) {
  const clave = `${pedido.oc_numero} - ${pedido.posicion_oc}`
  const espera = haceCuanto(pedido.fecha_arribo)

  return (
    <li
      aria-label={`Pedido ${clave}`}
      className="rounded border border-panel-borde bg-panel-superficie p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <Link
            to={`/pedidos/${pedido.id}`}
            className="font-semibold text-marca-300 underline hover:text-marca-200"
          >
            {clave}
          </Link>
          <p className="text-sm text-slate-300">
            {pedido.material.codigo} · {pedido.material.descripcion}
          </p>
          <p className="flex items-center gap-2 text-sm text-slate-300">
            <IconoVia via={pedido.via_transporte} className="h-3.5 w-5" />
            <span title={pedido.destino.nombre}>{destinoCorto(pedido)}</span>
          </p>
        </div>

        <dl className="grid grid-cols-[auto_auto] gap-x-3 gap-y-1 text-sm">
          <dt className="text-slate-400">Llegó</dt>
          <dd>
            {formatearFechaHora(pedido.fecha_arribo) ?? 'Sin fecha registrada'}
            {espera && <span className="text-slate-400"> ({espera})</span>}
          </dd>
          <dt className="text-slate-400">F. Comprometida</dt>
          <dd>{formatearFecha(pedido.fecha_entrega_pedido)}</dd>
        </dl>

        <button
          type="button"
          aria-expanded={abierto}
          onClick={onAbrir}
          className={`rounded px-4 py-2 text-sm ${
            abierto ? 'bg-slate-500' : 'bg-panel-cabecera'
          } text-slate-100 hover:bg-slate-600`}
        >
          Pasar a proceso aduanal
        </button>
      </div>

      {abierto && <FormularioAduana pedido={pedido} onListo={onListo} />}
    </li>
  )
}

function FormularioAduana({ pedido, onListo }: { pedido: PedidoResumen; onListo: () => void }) {
  const queryClient = useQueryClient()
  const [motivo, setMotivo] = useState('')

  const registrar = useMutation({
    mutationFn: () => pasarAAduana(pedido.id, { motivo }),
    onSuccess: (detalle) => {
      // Se vuelve a pedir todo `pedidos`, la bandeja incluida: el pedido sale de
      // la lista y el contador del encabezado baja.
      refrescarTrasIntervenir(queryClient, detalle)
      onListo()
    },
  })

  const listo = motivo.trim().length >= MOTIVO_MINIMO && !registrar.isPending

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    registrar.mutate()
  }

  return (
    <form
      onSubmit={enviar}
      aria-label={`Paso a proceso aduanal de ${pedido.oc_numero} - ${pedido.posicion_oc}`}
      className="mt-4 max-w-xl space-y-3"
    >
      <label className="block text-xs text-slate-300">
        Motivo (obligatorio)
        <textarea
          value={motivo}
          rows={2}
          onChange={(e) => setMotivo(e.target.value.slice(0, 300))}
          className="mt-0.5 w-full rounded bg-panel-cabecera px-2 py-1 text-sm text-white"
        />
        <span className="mt-0.5 block text-slate-500">Queda en la bitácora del pedido.</span>
      </label>

      {registrar.isError && (
        <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-sm text-red-100">
          {mensajeDeError(registrar.error)}
        </p>
      )}

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={!listo}
          className="rounded bg-white px-4 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
        >
          {registrar.isPending ? 'Guardando…' : 'Confirmar'}
        </button>
        <button type="button" onClick={onListo} className="text-sm text-slate-300 underline">
          Cancelar
        </button>
      </div>
    </form>
  )
}
