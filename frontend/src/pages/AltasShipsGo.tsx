/**
 * «Altas en ShipsGo» (`US-55`): dar de alta desde TrackIn las referencias que
 * todavía no están en la cuenta, una o en bloque.
 *
 * Lo autorizan Compras y el Administrador (reunión del 29/09/2026). Cada martes,
 * con la carga semanal del Z-tracking, entran unas 20 a 25 referencias nuevas: la
 * pantalla las trae todas marcadas, y se desmarca lo que no se quiere pagar.
 *
 * **Cada alta cuesta un crédito**, así que nada se gasta sin dos pasos: se elige
 * qué dar de alta y se confirma cuántos créditos son. Si con eso se pasa el tope
 * diario (`altas_maximas_dia`), hay que aceptarlo explícitamente. Una MAWB cuya
 * aerolínea ShipsGo no cubre se muestra pero no se ofrece: costaría un crédito y
 * devolvería vacío. Ver lo pendiente es gratis.
 *
 * Desde el detalle de un pedido se llega con `?ref=<número>`: entonces viene
 * marcada solo esa referencia.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'

import { puedeCargar } from '@/auth/permisos'
import { useSesion } from '@/auth/useSesion'
import { mensajeDeError } from '@/services/api'
import { comoTopeSuperado, darDeAltaEnShipsGo, obtenerAltasPendientes } from '@/services/shipsgo'
import type { AltasHechas, AltasPendientes, ReferenciaPendiente } from '@/types/api'

const CLAVE = ['shipsgo', 'altas-pendientes']

const TIPOS: Record<string, string> = {
  BL: 'BL',
  CONTENEDOR: 'Contenedor',
  BOOKING: 'Booking',
  MAWB: 'MAWB',
}

function creditos(n: number): string {
  return `${n} ${n === 1 ? 'crédito' : 'créditos'}`
}

export default function AltasShipsGo() {
  const sesion = useSesion()
  if (!puedeCargar(sesion?.usuario.rol)) return <Navigate to="/" replace />

  return (
    <div className="min-h-screen bg-panel-fondo text-slate-100">
      <header className="flex flex-wrap items-baseline justify-between gap-2 px-6 py-4">
        <h1 className="text-2xl font-bold">Altas en ShipsGo</h1>
        <Link to="/" className="text-sm text-marca-300 underline hover:text-marca-200">
          ← Volver al panel
        </Link>
      </header>
      <main className="mx-auto max-w-5xl space-y-6 px-6 pb-12">
        <p className="text-sm text-slate-400">
          Las referencias de pedidos activos que todavía no están en la cuenta de ShipsGo. Cada una
          cuesta <strong className="text-slate-200">un crédito</strong>, aunque la compartan varias
          líneas. Ver esta lista no gasta nada.
        </p>
        <Contenido />
      </main>
    </div>
  )
}

function Contenido() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: CLAVE,
    queryFn: obtenerAltasPendientes,
    // Cada consulta lista la cuenta de ShipsGo: no hace falta repetirla sola.
    refetchOnMount: 'always',
    staleTime: Infinity,
  })
  const [hechas, setHechas] = useState<AltasHechas | null>(null)

  if (isPending) return <p className="text-sm text-slate-500">Consultando ShipsGo…</p>
  if (isError) {
    return (
      <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-sm text-red-100">
        No se pudo consultar ShipsGo: {mensajeDeError(error)}
      </p>
    )
  }
  return (
    <>
      {hechas && <Resultados hechas={hechas} />}
      {data.pendientes.length === 0 ? (
        <p className="rounded border border-panel-borde bg-panel-superficie px-4 py-6 text-center text-slate-300">
          No hay referencias pendientes de alta: todo lo que tienen los pedidos activos ya está en
          ShipsGo.
        </p>
      ) : (
        <Seleccion datos={data} onHechas={setHechas} />
      )}
    </>
  )
}

function Seleccion({
  datos,
  onHechas,
}: {
  datos: AltasPendientes
  onHechas: (hechas: AltasHechas) => void
}) {
  const queryClient = useQueryClient()
  const [parametros] = useSearchParams()
  const pedida = parametros.get('ref')
  const ofrecibles = datos.pendientes.filter((p) => p.ofrecible)
  const [elegidas, setElegidas] = useState<Set<string>>(
    () => new Set(ofrecibles.filter((p) => !pedida || p.numero === pedida).map((p) => p.numero)),
  )
  const [confirmando, setConfirmando] = useState(false)
  const [superarTope, setSuperarTope] = useState(false)

  const n = elegidas.size
  const pasaTope = datos.altas_hoy + n > datos.altas_maximas_dia

  const alta = useMutation({
    mutationFn: () =>
      darDeAltaEnShipsGo({
        referencias: datos.pendientes
          .filter((p) => elegidas.has(p.numero))
          .map((p) => ({ tipo: p.tipo, numero: p.numero })),
        creditos_confirmados: n,
        superar_tope: superarTope,
      }),
    onSuccess: (hechas) => {
      onHechas(hechas)
      setConfirmando(false)
      void queryClient.invalidateQueries({ queryKey: CLAVE })
      // El rastreo empieza en el próximo ciclo del worker: el panel se refresca.
      void queryClient.invalidateQueries({ queryKey: ['pedidos'] })
    },
  })
  const tope = comoTopeSuperado(alta.error)

  function alternar(numero: string) {
    setConfirmando(false)
    setElegidas((actuales) => {
      const nuevas = new Set(actuales)
      if (nuevas.has(numero)) nuevas.delete(numero)
      else nuevas.add(numero)
      return nuevas
    })
  }

  const listo = n > 0 && (!pasaTope || superarTope) && !alta.isPending

  return (
    <section aria-labelledby="titulo-pendientes" className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="titulo-pendientes" className="text-lg font-semibold">
          Pendientes de alta
        </h2>
        <p className="text-sm text-slate-400">
          Altas que costaron hoy: {datos.altas_hoy} · tope diario: {datos.altas_maximas_dia}
        </p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-panel-borde">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-panel-cabecera text-left">
            <tr>
              <th scope="col" className="w-10 px-3 py-2">
                <span className="sr-only">Dar de alta</span>
              </th>
              <th scope="col" className="px-3 py-2">
                Referencia
              </th>
              <th scope="col" className="px-3 py-2">
                Vía
              </th>
              <th scope="col" className="px-3 py-2">
                Líneas
              </th>
              <th scope="col" className="px-3 py-2">
                Cobertura
              </th>
            </tr>
          </thead>
          <tbody className="bg-panel-superficie">
            {datos.pendientes.map((p) => (
              <Fila
                key={p.numero}
                pendiente={p}
                elegida={elegidas.has(p.numero)}
                onAlternar={() => alternar(p.numero)}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="space-y-3 rounded border border-panel-borde bg-panel-superficie p-4">
        <p className="text-sm">
          {n === 0
            ? 'No hay ninguna referencia marcada.'
            : `${n} ${n === 1 ? 'referencia marcada' : 'referencias marcadas'}: ${creditos(n)}.`}
        </p>
        {pasaTope && n > 0 && (
          <label className="flex items-start gap-2 text-sm text-amber-100">
            <input
              type="checkbox"
              checked={superarTope}
              onChange={(e) => setSuperarTope(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              Con estas altas serían {datos.altas_hoy + n} hoy, más que el tope diario de{' '}
              {datos.altas_maximas_dia}. Entiendo que lo supero.
            </span>
          </label>
        )}

        {!confirmando ? (
          <button
            type="button"
            disabled={!listo}
            onClick={() => setConfirmando(true)}
            className="rounded bg-white px-4 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
          >
            Dar de alta ({creditos(n)})
          </button>
        ) : (
          <div role="alertdialog" aria-label="Confirmar el gasto" className="space-y-2">
            <p className="text-sm font-semibold text-amber-100">
              Se van a gastar {creditos(n)} de ShipsGo. No se puede deshacer.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                disabled={!listo}
                onClick={() => alta.mutate()}
                className="rounded bg-white px-4 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
              >
                {alta.isPending ? 'Dando de alta…' : `Confirmar: gastar ${creditos(n)}`}
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

        {alta.isError && (
          <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-sm text-red-100">
            {tope ? tope.detail : mensajeDeError(alta.error)}
          </p>
        )}
      </div>
    </section>
  )
}

function Fila({
  pendiente,
  elegida,
  onAlternar,
}: {
  pendiente: ReferenciaPendiente
  elegida: boolean
  onAlternar: () => void
}) {
  const nombre = `${TIPOS[pendiente.tipo] ?? pendiente.tipo} ${pendiente.numero}`
  return (
    <tr aria-label={nombre} className="border-t border-white/5 align-top">
      <td className="px-3 py-2">
        <input
          type="checkbox"
          aria-label={`Dar de alta ${nombre}`}
          checked={elegida}
          disabled={!pendiente.ofrecible}
          onChange={onAlternar}
        />
      </td>
      <td className="whitespace-nowrap px-3 py-2">{nombre}</td>
      <td className="px-3 py-2">{pendiente.via_transporte === 'AEREO' ? 'Aérea' : 'Marítima'}</td>
      <td className="px-3 py-2">
        <ul className="space-y-0.5">
          {pendiente.lineas.map((l) => (
            <li key={l.id_pedido}>
              <Link
                to={`/pedidos/${l.id_pedido}`}
                className="underline decoration-slate-500 underline-offset-2 hover:text-white"
              >
                {l.oc_numero} - {l.posicion_oc}
              </Link>
            </li>
          ))}
        </ul>
      </td>
      <td className="px-3 py-2 text-slate-300">
        {pendiente.tipo !== 'MAWB' ? (
          '–'
        ) : pendiente.cubierta === false ? (
          <span className="text-amber-200">
            Sin cobertura en ShipsGo: no se ofrece (devolvería vacío)
          </span>
        ) : pendiente.cubierta ? (
          pendiente.aerolinea
        ) : (
          'No se pudo comprobar la aerolínea'
        )}
      </td>
    </tr>
  )
}

function Resultados({ hechas }: { hechas: AltasHechas }) {
  const fallidas = hechas.resultados.filter((r) => !r.registrado)
  return (
    <section
      role="status"
      aria-label="Resultado de las altas"
      className="space-y-2 rounded bg-emerald-900/40 px-4 py-3 text-sm"
    >
      <p>
        Altas hechas: {hechas.resultados.length - fallidas.length} de {hechas.resultados.length}.{' '}
        Créditos gastados: {hechas.creditos_consumidos}. El rastreo empieza en el próximo ciclo del
        worker, en un par de minutos.
      </p>
      {fallidas.length > 0 && (
        <ul className="list-disc pl-5 text-amber-100">
          {fallidas.map((r) => (
            <li key={r.numero}>
              {r.numero}: no se dio de alta ({r.motivo.replaceAll('_', ' ')}).
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
