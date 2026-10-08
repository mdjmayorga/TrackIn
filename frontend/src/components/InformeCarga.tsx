/**
 * El informe de una carga del Z-tracking (`US-58`): qué entró y qué no.
 *
 * Quien lo lee es quien corrige el archivo en SAP, así que se ordena para eso:
 * primero los totales, después los problemas agrupados por motivo —273 líneas
 * sin vía son *un* problema repetido, no 273—, y al final cada línea con su
 * OC y posición para ir a buscarla.
 */

import { useState } from 'react'

import type { CargaDetalle } from '@/types/api'
import { formatearFechaHora } from '@/utils/fechas'
import { QUE_HACER, nombreMotivo } from '@/utils/motivosCarga'

/** Cuántas líneas se muestran antes de «Ver todas»: el WK38 trae 373. */
const LINEAS_INICIALES = 15

export function InformeCarga({ carga }: { carga: CargaDetalle }) {
  const [todas, setTodas] = useState(false)
  const lineas = todas ? carga.incidencias : carga.incidencias.slice(0, LINEAS_INICIALES)

  return (
    <article aria-labelledby={`informe-${carga.id}`} className="space-y-5">
      <header>
        <h3 id={`informe-${carga.id}`} className="text-lg font-semibold">
          {carga.archivo}
        </h3>
        <p className="text-sm text-slate-400">
          Cargado por {carga.usuario.nombre_completo} el {formatearFechaHora(carga.realizada_en)}
        </p>
      </header>

      {carga.estado === 'RECHAZADA' ? (
        <p role="alert" className="rounded bg-red-900/60 px-4 py-3 text-sm text-red-100">
          No se cargó nada. {carga.motivo_rechazo}
        </p>
      ) : (
        <>
          <dl className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            <Total titulo="Líneas en el archivo" valor={carga.recibidas} />
            <Total titulo="Nuevos" valor={carga.insertadas} />
            <Total titulo="Actualizados" valor={carga.actualizadas} />
            <Total titulo="Sin cambios" valor={carga.sin_cambios} />
            <Total
              titulo="Ya no vienen"
              valor={carga.ausentes}
              ayuda="Estaban en TrackIn y no vinieron en este archivo. No se borran: quedan para revisión."
            />
            <Total titulo="No entraron" valor={carga.no_entraron} alerta={carga.no_entraron > 0} />
          </dl>

          {carga.incidencias.length === 0 ? (
            <p className="text-sm text-emerald-300">Todas las líneas entraron sin problemas.</p>
          ) : (
            <>
              <section aria-labelledby={`motivos-${carga.id}`}>
                <h4 id={`motivos-${carga.id}`} className="mb-2 font-semibold">
                  Qué corregir en SAP
                </h4>
                <ul className="space-y-1 text-sm">
                  {Object.entries(carga.por_motivo).map(([motivo, cuantas]) => (
                    <li key={motivo}>
                      <span className="font-semibold">{nombreMotivo(motivo)}</span>: {cuantas}{' '}
                      {cuantas === 1 ? 'línea' : 'líneas'}.{' '}
                      <span className="text-slate-400">{QUE_HACER[motivo]}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section aria-labelledby={`lineas-${carga.id}`}>
                <h4 id={`lineas-${carga.id}`} className="mb-2 font-semibold">
                  Líneas con problemas ({carga.incidencias.length})
                </h4>
                <div className="overflow-x-auto rounded border border-panel-borde">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-panel-cabecera">
                      <tr>
                        <th scope="col" className="px-2 py-1.5">
                          OC-POS u hoja!fila
                        </th>
                        <th scope="col" className="px-2 py-1.5">
                          Problema
                        </th>
                        <th scope="col" className="px-2 py-1.5">
                          Detalle
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-panel-superficie">
                      {lineas.map((i, n) => (
                        <tr key={`${i.clave}-${n}`} className="border-t border-white/5 align-top">
                          <td className="whitespace-nowrap px-2 py-1 font-mono">{i.clave}</td>
                          <td className="whitespace-nowrap px-2 py-1">
                            {nombreMotivo(i.motivo)}
                            {i.consecuencia === 'entro_sin_rastreo' && (
                              <span className="ml-1 text-amber-300">(entró sin rastreo)</span>
                            )}
                          </td>
                          <td className="px-2 py-1 text-slate-300">{i.detalle}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {carga.incidencias.length > LINEAS_INICIALES && (
                  <button
                    type="button"
                    onClick={() => setTodas((v) => !v)}
                    className="mt-2 text-sm text-marca-300 underline"
                  >
                    {todas ? 'Ver menos' : `Ver las ${carga.incidencias.length} líneas`}
                  </button>
                )}
              </section>
            </>
          )}

          {carga.avisos.length > 0 && (
            <section aria-labelledby={`avisos-${carga.id}`}>
              <h4 id={`avisos-${carga.id}`} className="mb-1 font-semibold">
                Entraron, pero conviene revisar en SAP ({carga.avisos.length})
              </h4>
              <ul className="list-inside list-disc text-sm text-slate-300">
                {carga.avisos.map((a) => (
                  <li key={`${a.clave}-${a.tipo}`}>
                    <span className="font-mono">{a.clave}</span>: {a.detalle}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </article>
  )
}

function Total({
  titulo,
  valor,
  ayuda,
  alerta = false,
}: {
  titulo: string
  valor: number
  ayuda?: string
  alerta?: boolean
}) {
  return (
    <div
      title={ayuda}
      className="flex flex-col-reverse rounded border border-panel-borde px-2 py-2 text-center"
    >
      <dt className="text-xs text-slate-400">{titulo}</dt>
      <dd className={`text-2xl font-bold ${alerta ? 'text-red-400' : 'text-white'}`}>{valor}</dd>
    </div>
  )
}
