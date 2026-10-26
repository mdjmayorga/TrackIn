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
 *
 * **Créditos (`US-57`).** Arriba, el saldo del paquete vigente y el registro de
 * cada compra. Con un paquete registrado, si lo marcado no alcanza con el saldo
 * —o el paquete venció— hay que aceptarlo antes de gastar: el saldo es el que
 * lleva TrackIn y puede no coincidir con el de ShipsGo.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'

import { puedeCargar } from '@/auth/permisos'
import { useSesion } from '@/auth/useSesion'
import { mensajeDeError } from '@/services/api'
import {
  comoSaldoInsuficiente,
  comoTopeSuperado,
  darDeAltaEnShipsGo,
  obtenerAltasPendientes,
  registrarPaquete,
} from '@/services/shipsgo'
import type { AltasHechas, AltasPendientes, EstadoCreditos, ReferenciaPendiente } from '@/types/api'
import { formatearFecha, formatearFechaHora } from '@/utils/fechas'

const CLAVE = ['shipsgo', 'altas-pendientes']
/** La del aviso del panel (`AvisoCreditos`): registrar o dar de alta la refresca. */
const CLAVE_CREDITOS = ['shipsgo', 'creditos']

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
      <SeccionCreditos estado={data.creditos} />
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
  const [aceptarSaldo, setAceptarSaldo] = useState(false)

  const n = elegidas.size
  const pasaTope = datos.altas_hoy + n > datos.altas_maximas_dia
  const saldo = datos.creditos
  // Sin paquete registrado no se sabe el saldo: no se frena por él (`US-57`).
  const faltaSaldo =
    saldo.paquete !== null &&
    (saldo.nivel === 'AGOTADO' || saldo.nivel === 'VENCIDO' || n > saldo.saldo)

  const alta = useMutation({
    mutationFn: () =>
      darDeAltaEnShipsGo({
        referencias: datos.pendientes
          .filter((p) => elegidas.has(p.numero))
          .map((p) => ({ tipo: p.tipo, numero: p.numero })),
        creditos_confirmados: n,
        superar_tope: superarTope,
        aceptar_saldo: aceptarSaldo,
      }),
    onSuccess: (hechas) => {
      onHechas(hechas)
      setConfirmando(false)
      void queryClient.invalidateQueries({ queryKey: CLAVE })
      void queryClient.invalidateQueries({ queryKey: CLAVE_CREDITOS })
      // El rastreo empieza en el próximo ciclo del worker: el panel se refresca.
      void queryClient.invalidateQueries({ queryKey: ['pedidos'] })
    },
  })
  const tope = comoTopeSuperado(alta.error)
  const sinSaldo = comoSaldoInsuficiente(alta.error)

  function alternar(numero: string) {
    setConfirmando(false)
    setElegidas((actuales) => {
      const nuevas = new Set(actuales)
      if (nuevas.has(numero)) nuevas.delete(numero)
      else nuevas.add(numero)
      return nuevas
    })
  }

  const listo =
    n > 0 && (!pasaTope || superarTope) && (!faltaSaldo || aceptarSaldo) && !alta.isPending

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
        {faltaSaldo && n > 0 && (
          <label className="flex items-start gap-2 text-sm text-red-100">
            <input
              type="checkbox"
              checked={aceptarSaldo}
              onChange={(e) => setAceptarSaldo(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              {saldo.nivel === 'VENCIDO'
                ? 'El paquete de créditos venció.'
                : `El saldo registrado es ${Math.max(saldo.saldo, 0)} y estas altas necesitan ${n}.`}{' '}
              Entiendo que pueden fallar si ShipsGo no tiene créditos.
            </span>
          </label>
        )}
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
            {tope?.detail ?? sinSaldo?.detail ?? mensajeDeError(alta.error)}
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

// --- Créditos (`US-57`) ----------------------------------------------------------------

function hoyCostaRica(): string {
  // `en-CA` da `AAAA-MM-DD`, el formato de un `<input type="date">`.
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Costa_Rica' }).format(new Date())
}

function SeccionCreditos({ estado }: { estado: EstadoCreditos }) {
  const [registrando, setRegistrando] = useState(false)
  const p = estado.paquete
  const atencion = estado.nivel !== 'OK'
  const urgente = estado.nivel === 'AGOTADO' || estado.nivel === 'VENCIDO'

  return (
    <section
      aria-labelledby="titulo-creditos"
      className="space-y-3 rounded border border-panel-borde bg-panel-superficie p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="titulo-creditos" className="text-lg font-semibold">
          Créditos de ShipsGo
        </h2>
        {!registrando && (
          <button
            type="button"
            onClick={() => setRegistrando(true)}
            className="rounded bg-panel-cabecera px-3 py-1.5 text-sm hover:bg-slate-600"
          >
            Registrar paquete comprado
          </button>
        )}
      </div>

      {p ? (
        <>
          <p className="text-2xl font-semibold">
            {estado.saldo}{' '}
            <span className="text-sm font-normal text-slate-400">
              de {estado.disponible} disponibles · {estado.consumidos} usados
            </span>
          </p>
          <p className="text-xs text-slate-400">
            Paquete vigente: {p.cantidad} créditos
            {p.saldo_arrastrado > 0 && ` + ${p.saldo_arrastrado} arrastrados`}, comprado el{' '}
            {formatearFecha(p.comprado_en)},{' '}
            {p.vence_en ? `vence el ${formatearFecha(p.vence_en)}` : 'sin vencimiento'}. Registrado
            por {p.registrado_por} el {formatearFechaHora(p.registrado_en)}.
          </p>
        </>
      ) : (
        <p className="text-sm text-slate-300">
          Registre como paquete vigente los créditos que tiene hoy la cuenta: los de prueba no
          vencen.
        </p>
      )}

      {atencion && (
        <p
          role={urgente ? 'alert' : 'status'}
          className={`rounded px-3 py-2 text-sm ${
            urgente ? 'bg-red-900/60 text-red-100' : 'bg-amber-900/50 text-amber-100'
          }`}
        >
          {estado.mensaje}
        </p>
      )}

      {registrando && <FormularioPaquete estado={estado} onListo={() => setRegistrando(false)} />}
    </section>
  )
}

function FormularioPaquete({ estado, onListo }: { estado: EstadoCreditos; onListo: () => void }) {
  const queryClient = useQueryClient()
  const [cantidad, setCantidad] = useState('')
  const [compradoEn, setCompradoEn] = useState(hoyCostaRica())
  const [venceEn, setVenceEn] = useState('')
  const [tope, setTope] = useState('')
  const [nota, setNota] = useState('')

  const registro = useMutation({
    mutationFn: () =>
      registrarPaquete({
        cantidad: Number(cantidad),
        comprado_en: compradoEn,
        vence_en: venceEn || null,
        altas_maximas_dia: tope ? Number(tope) : null,
        nota: nota.trim() || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: CLAVE })
      void queryClient.invalidateQueries({ queryKey: CLAVE_CREDITOS })
      onListo()
    },
  })

  const n = Number(cantidad)
  const valido =
    Number.isInteger(n) && n > 0 && compradoEn !== '' && (!venceEn || venceEn >= compradoEn)

  // Lo que pasaría con el saldo actual (condición de ShipsGo del 07/10/2026).
  const p = estado.paquete
  let arrastre: string | null = null
  if (p && estado.saldo > 0 && valido) {
    const vencido = p.vence_en !== null && p.vence_en < compradoEn
    const minima = estado.recompra_minima ?? 0
    arrastre = vencido
      ? `Los ${estado.saldo} créditos que quedan no se suman: el paquete vigente ya habrá vencido.`
      : n >= minima
        ? `Se suman los ${estado.saldo} que quedan: el paquete nuevo arranca con ${n + estado.saldo}.`
        : `Los ${estado.saldo} que quedan no se suman: para arrastrarlos hay que comprar al menos ${minima}.`
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (valido && !registro.isPending) registro.mutate()
      }}
      aria-label="Registrar paquete comprado"
      className="grid max-w-3xl gap-3 border-t border-panel-borde pt-3 sm:grid-cols-2"
    >
      <Campo etiqueta="Créditos comprados">
        <input
          type="number"
          min={1}
          step={1}
          value={cantidad}
          onChange={(e) => setCantidad(e.target.value)}
          className={ESTILO_CAMPO}
        />
      </Campo>
      <Campo etiqueta="Fecha de compra">
        <input
          type="date"
          value={compradoEn}
          onChange={(e) => setCompradoEn(e.target.value)}
          className={ESTILO_CAMPO}
        />
      </Campo>
      <Campo etiqueta="Vence (opcional)" ayuda="Vacío si no vence.">
        <input
          type="date"
          value={venceEn}
          min={compradoEn}
          onChange={(e) => setVenceEn(e.target.value)}
          className={ESTILO_CAMPO}
        />
      </Campo>
      <Campo
        etiqueta="Nuevo tope diario de altas (opcional)"
        ayuda="Con el paquete anual conviene subirlo: la carga semanal trae 20 a 25."
      >
        <input
          type="number"
          min={1}
          step={1}
          value={tope}
          onChange={(e) => setTope(e.target.value)}
          className={ESTILO_CAMPO}
        />
      </Campo>
      <div className="sm:col-span-2">
        <Campo etiqueta="Nota (opcional)">
          <input
            value={nota}
            maxLength={300}
            onChange={(e) => setNota(e.target.value)}
            className={ESTILO_CAMPO}
          />
        </Campo>
      </div>
      <div className="space-y-3 sm:col-span-2">
        {arrastre && <p className="text-sm text-slate-300">{arrastre}</p>}
        {registro.isError && (
          <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-sm text-red-100">
            {mensajeDeError(registro.error)}
          </p>
        )}
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={!valido || registro.isPending}
            className="rounded bg-white px-4 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
          >
            {registro.isPending ? 'Guardando…' : 'Registrar'}
          </button>
          <button type="button" onClick={onListo} className="text-sm text-slate-300 underline">
            Cancelar
          </button>
        </div>
      </div>
    </form>
  )
}

const ESTILO_CAMPO =
  'mt-0.5 w-full rounded bg-panel-cabecera px-2 py-1.5 text-sm text-white [color-scheme:dark]'

function Campo({
  etiqueta,
  ayuda,
  children,
}: {
  etiqueta: string
  ayuda?: string
  children: ReactNode
}) {
  return (
    <label className="block text-xs text-slate-300">
      {etiqueta}
      {children}
      {ayuda && <span className="mt-0.5 block text-slate-500">{ayuda}</span>}
    </label>
  )
}
