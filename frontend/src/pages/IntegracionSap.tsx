/**
 * «Integración con SAP» (`US-66`): el interruptor de la escucha de la API de SAP.
 *
 * Reunión de entrega del Informe 2 (27/10/2026): TrackIn queda listo para
 * recibir los pedidos de SAP el día que la API exista, con la escucha
 * **apagada** hasta entonces. Solo el Administrador la cambia (decisión del
 * 27/10); los demás roles ven el estado. Encender pide confirmación, porque a
 * partir de ahí SAP puede crear y actualizar pedidos.
 *
 * El contrato que tiene que cumplir SAP está en `docs/integraciones/sap/` (`US-64`).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, Navigate } from 'react-router-dom'

import { esPantallaPlanta, puedeCambiarEscuchaSap } from '@/auth/permisos'
import { useSesion } from '@/auth/useSesion'
import { mensajeDeError } from '@/services/api'
import { cambiarEscuchaSap, obtenerEscuchaSap } from '@/services/sap'
import type { EstadoEscuchaSap } from '@/types/api'
import { formatearFechaHora } from '@/utils/fechas'

const CLAVE = ['sap', 'escucha']
const ENDPOINT = '/api/v1/integraciones/sap/pedidos'

export default function IntegracionSap() {
  const sesion = useSesion()
  if (!sesion || esPantallaPlanta(sesion.usuario.rol)) return <Navigate to="/" replace />

  return (
    <div className="min-h-screen bg-panel-fondo text-slate-100">
      <header className="flex flex-wrap items-baseline justify-between gap-2 px-6 py-4">
        <h1 className="text-2xl font-bold">Integración con SAP</h1>
        <Link to="/" className="text-sm text-marca-300 underline hover:text-marca-200">
          ← Volver al panel
        </Link>
      </header>
      <main className="mx-auto max-w-3xl space-y-6 px-6 pb-12">
        <p className="text-sm text-slate-400">
          Cuando exista la API de SAP, SAP enviará los pedidos a TrackIn por{' '}
          <code className="text-slate-300">{ENDPOINT}</code>. Entran por el mismo camino que el
          Excel del Z-tracking, que sigue siendo la carga de los martes. Mientras la escucha esté
          apagada, TrackIn rechaza esos envíos sin tocar nada.
        </p>
        <Contenido puedeCambiar={puedeCambiarEscuchaSap(sesion.usuario.rol)} />
      </main>
    </div>
  )
}

function Contenido({ puedeCambiar }: { puedeCambiar: boolean }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: CLAVE,
    queryFn: obtenerEscuchaSap,
  })

  if (isPending) return <p className="text-sm text-slate-500">Cargando…</p>
  if (isError) {
    return (
      <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-sm text-red-100">
        No se pudo leer el estado de la escucha: {mensajeDeError(error)}
      </p>
    )
  }
  return (
    <>
      <Interruptor estado={data} puedeCambiar={puedeCambiar} />
      <UltimaRecepcion estado={data} />
    </>
  )
}

function Interruptor({
  estado,
  puedeCambiar,
}: {
  estado: EstadoEscuchaSap
  puedeCambiar: boolean
}) {
  const queryClient = useQueryClient()
  const [confirmando, setConfirmando] = useState(false)
  const cambio = useMutation({
    mutationFn: (habilitada: boolean) => cambiarEscuchaSap(habilitada),
    onSuccess: (nuevo) => {
      queryClient.setQueryData(CLAVE, nuevo)
      setConfirmando(false)
    },
  })
  const encendida = estado.habilitada
  const accion = encendida ? 'Apagar la escucha' : 'Encender la escucha'

  return (
    <section
      aria-labelledby="titulo-escucha"
      className="space-y-4 rounded border border-panel-borde bg-panel-superficie p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 id="titulo-escucha" className="text-lg font-semibold">
            Escucha de la API de SAP
          </h2>
          <p className="text-sm text-slate-400">
            {estado.cambiada_por && estado.cambiada_en
              ? `Cambiada por ${estado.cambiada_por.nombre_completo} el ${formatearFechaHora(estado.cambiada_en)}.`
              : 'Apagada desde la instalación: nadie la cambió todavía.'}
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={encendida}
          aria-label="Escucha de la API de SAP"
          disabled={!puedeCambiar || cambio.isPending}
          onClick={() => setConfirmando(true)}
          className="flex items-center gap-3 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span
            aria-hidden="true"
            className={`relative inline-block h-7 w-12 rounded-full transition-colors ${
              encendida ? 'bg-emerald-600' : 'bg-slate-600'
            }`}
          >
            <span
              className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-all ${
                encendida ? 'left-6' : 'left-1'
              }`}
            />
          </span>
          <span className="text-base font-semibold">{encendida ? 'Encendida' : 'Apagada'}</span>
        </button>
      </div>

      {!puedeCambiar && (
        <p className="text-sm text-slate-400">Solo el Administrador puede cambiarla.</p>
      )}

      {!estado.clave_configurada && (
        <p role="status" className="rounded bg-amber-900/50 px-3 py-2 text-sm text-amber-100">
          El servidor no tiene configurada la clave de integración (
          <code>SAP_INTEGRACION_CLAVE</code>): aunque la escucha se encienda, SAP no podrá enviar
          pedidos.
        </p>
      )}

      {confirmando && (
        <div
          role="alertdialog"
          aria-labelledby="confirmar-escucha"
          className="space-y-3 rounded border border-amber-700 bg-amber-950/40 p-3"
        >
          <p id="confirmar-escucha" className="text-sm">
            {encendida
              ? 'TrackIn dejará de aceptar los pedidos que envíe SAP. Lo ya cargado no cambia.'
              : 'TrackIn empezará a aceptar los pedidos que envíe SAP: los crea y actualiza como la carga del Excel, sin marcar ausentes.'}
          </p>
          {cambio.isError && (
            <p role="alert" className="text-sm text-red-200">
              {mensajeDeError(cambio.error)}
            </p>
          )}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => cambio.mutate(!encendida)}
              disabled={cambio.isPending}
              className="rounded bg-white px-4 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
            >
              {cambio.isPending ? 'Guardando…' : `Confirmar: ${accion.toLowerCase()}`}
            </button>
            <button
              type="button"
              onClick={() => setConfirmando(false)}
              className="text-sm text-slate-300 underline"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </section>
  )
}

function UltimaRecepcion({ estado }: { estado: EstadoEscuchaSap }) {
  const ultima = estado.ultima_recepcion
  return (
    <section
      aria-labelledby="titulo-recepcion"
      className="space-y-2 rounded border border-panel-borde bg-panel-superficie p-4"
    >
      <h2 id="titulo-recepcion" className="text-lg font-semibold">
        Última recepción desde SAP
      </h2>
      {ultima ? (
        <p className="text-sm">
          <Link to="/cargas" className="text-marca-300 underline hover:text-marca-200">
            {ultima.archivo}
          </Link>
          , el {formatearFechaHora(ultima.realizada_en)}: {ultima.recibidas} recibidas,{' '}
          {ultima.insertadas} nuevas, {ultima.actualizadas} actualizadas y {ultima.no_entraron} no
          entraron.
        </p>
      ) : (
        <p className="text-sm text-slate-400">Sin recepciones todavía.</p>
      )}
    </section>
  )
}
