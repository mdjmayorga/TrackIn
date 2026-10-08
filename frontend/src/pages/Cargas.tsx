/**
 * «Cargar Z-tracking» (`US-58`): subir el Excel exportado de SAP y ver qué
 * entró y qué no. Desde el 07/10 es la única vía de entrada de los pedidos.
 *
 * Suben Compras y el Administrador; el historial lo ve cualquiera, porque
 * explica por qué un pedido está o no está en el panel.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { puedeCargar } from '@/auth/permisos'
import { useSesion } from '@/auth/useSesion'
import { InformeCarga } from '@/components/InformeCarga'
import { mensajeDeError } from '@/services/api'
import { listarCargas, obtenerCarga, subirZtracking } from '@/services/cargas'
import { formatearFechaHora } from '@/utils/fechas'

export default function Cargas() {
  const sesion = useSesion()
  const habilitado = puedeCargar(sesion?.usuario.rol)
  const [seleccionada, setSeleccionada] = useState<number | null>(null)

  return (
    <div className="min-h-screen bg-panel-fondo text-slate-100">
      <header className="flex flex-wrap items-baseline justify-between gap-2 px-6 py-4">
        <h1 className="text-2xl font-bold">Cargar Z-tracking</h1>
        <Link to="/" className="text-sm text-marca-300 underline hover:text-marca-200">
          ← Volver al panel
        </Link>
      </header>

      <main className="mx-auto max-w-5xl space-y-10 px-6 pb-12">
        {habilitado ? (
          <FormularioCarga onCargada={setSeleccionada} />
        ) : (
          <p className="text-sm text-slate-400">
            Las cargas las hacen Compras y el Administrador. Aquí puede ver el historial.
          </p>
        )}

        <Historial seleccionada={seleccionada} onSeleccionar={setSeleccionada} />
      </main>
    </div>
  )
}

function FormularioCarga({ onCargada }: { onCargada: (id: number) => void }) {
  const queryClient = useQueryClient()
  const entrada = useRef<HTMLInputElement>(null)
  const [archivo, setArchivo] = useState<File | null>(null)

  const carga = useMutation({
    mutationFn: subirZtracking,
    onSuccess: (resultado) => {
      // Los pedidos cambiaron: la grilla y el historial se vuelven a pedir.
      void queryClient.invalidateQueries({ queryKey: ['pedidos'] })
      // El informe ya vino en la respuesta: no hace falta volver a pedirlo.
      queryClient.setQueryData(['cargas', resultado.id], resultado)
      onCargada(resultado.id)
      setArchivo(null)
      if (entrada.current) entrada.current.value = ''
    },
    onSettled: () => {
      // Solo la lista: `exact` evita volver a pedir el informe que acaba de llegar.
      void queryClient.invalidateQueries({ queryKey: ['cargas'], exact: true })
    },
  })

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (archivo) carga.mutate(archivo)
  }

  return (
    <section aria-labelledby="titulo-subir" className="space-y-3">
      <h2 id="titulo-subir" className="text-lg font-semibold">
        Subir el archivo
      </h2>
      <p className="max-w-3xl text-sm text-slate-300">
        Exporte el Z-tracking de SAP como Excel (.xlsx) y súbalo aquí. Se toman las hojas PRODUCCION
        e IDA. Los pedidos nuevos se agregan, los existentes se actualizan, y los que{' '}
        <strong>ya no vengan</strong> en el archivo quedan marcados para revisión: no se borran.
      </p>

      <form onSubmit={enviar} className="flex flex-wrap items-center gap-3">
        <label htmlFor="archivo-ztracking" className="sr-only">
          Archivo Z-tracking
        </label>
        <input
          ref={entrada}
          id="archivo-ztracking"
          type="file"
          accept=".xlsx,.xlsm"
          onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
          className="text-sm file:mr-3 file:rounded file:border-0 file:bg-panel-cabecera file:px-3 file:py-1.5 file:text-slate-100"
        />
        <button
          type="submit"
          disabled={!archivo || carga.isPending}
          className="rounded bg-white px-4 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
        >
          {carga.isPending ? 'Cargando…' : 'Cargar'}
        </button>
      </form>

      {carga.isPending && (
        <p role="status" className="text-sm text-slate-400">
          Cargando y recalculando los pedidos. Puede tardar unos segundos.
        </p>
      )}
      {carga.isError && (
        <p role="alert" className="rounded bg-red-900/60 px-4 py-3 text-sm text-red-100">
          {mensajeDeError(carga.error)}
        </p>
      )}
    </section>
  )
}

function Historial({
  seleccionada,
  onSeleccionar,
}: {
  seleccionada: number | null
  onSeleccionar: (id: number) => void
}) {
  const cargas = useQuery({ queryKey: ['cargas'], queryFn: listarCargas })
  const detalle = useQuery({
    queryKey: ['cargas', seleccionada],
    queryFn: () => obtenerCarga(seleccionada!),
    enabled: seleccionada !== null,
    // Una carga registrada no cambia nunca: su informe no se vuelve a pedir.
    staleTime: Infinity,
  })

  return (
    <section aria-labelledby="titulo-historial" className="space-y-4">
      <h2 id="titulo-historial" className="text-lg font-semibold">
        Cargas recientes
      </h2>

      {cargas.isPending && <p className="text-sm text-slate-400">Cargando historial…</p>}
      {cargas.isError && (
        <p role="alert" className="text-sm text-red-300">
          {mensajeDeError(cargas.error)}
        </p>
      )}
      {cargas.data?.length === 0 && (
        <p className="text-sm text-slate-400">Todavía no se ha cargado ningún archivo.</p>
      )}

      {cargas.data && cargas.data.length > 0 && (
        <div className="overflow-x-auto rounded border border-panel-borde">
          <table className="w-full text-left text-xs">
            <thead className="bg-panel-cabecera">
              <tr>
                {[
                  'Fecha',
                  'Archivo',
                  'Quién',
                  'Resultado',
                  'Nuevos',
                  'Actualizados',
                  'No entraron',
                ].map((t) => (
                  <th key={t} scope="col" className="whitespace-nowrap px-2 py-1.5">
                    {t}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-panel-superficie">
              {cargas.data.map((c) => (
                <tr
                  key={c.id}
                  aria-selected={c.id === seleccionada}
                  className={`border-t border-white/5 ${c.id === seleccionada ? 'bg-white/10' : ''}`}
                >
                  <td className="whitespace-nowrap px-2 py-1">
                    {formatearFechaHora(c.realizada_en)}
                  </td>
                  <td className="px-2 py-1">
                    <button
                      type="button"
                      onClick={() => onSeleccionar(c.id)}
                      className="text-left text-marca-300 underline hover:text-marca-200"
                    >
                      {c.archivo}
                    </button>
                  </td>
                  <td className="whitespace-nowrap px-2 py-1">{c.usuario.nombre_completo}</td>
                  <td className="whitespace-nowrap px-2 py-1">
                    {c.estado === 'APLICADA' ? (
                      'Aplicada'
                    ) : (
                      <span className="text-red-300">Rechazada</span>
                    )}
                  </td>
                  <td className="px-2 py-1">{c.estado === 'APLICADA' ? c.insertadas : '–'}</td>
                  <td className="px-2 py-1">{c.estado === 'APLICADA' ? c.actualizadas : '–'}</td>
                  <td className="px-2 py-1">{c.estado === 'APLICADA' ? c.no_entraron : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detalle.data && <InformeCarga carga={detalle.data} />}
    </section>
  )
}
