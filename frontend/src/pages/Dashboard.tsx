import type { ReactNode } from 'react'

import { useHealth } from '@/hooks/useHealth'
import { API_BASE_URL, mensajeDeError } from '@/services/api'

/**
 * Placeholder del dashboard.
 *
 * Además del texto de la Sprint 1, muestra el estado de la conexión con el
 * backend: sirve para confirmar de un vistazo que el stack completo
 * (frontend -> API -> PostgreSQL/PostGIS) está levantado.
 */
export default function Dashboard() {
  const { data, isPending, isError, error } = useHealth()

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header className="mb-10">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">TrackIn Dashboard</h1>
        <p className="mt-2 text-slate-600">Sprint 1 pendiente</p>
      </header>

      <section
        aria-labelledby="estado-stack"
        className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h2 id="estado-stack" className="text-sm font-medium uppercase tracking-wide text-slate-500">
          Estado del entorno
        </h2>

        <dl className="mt-4 space-y-3 text-sm">
          <Fila etiqueta="API">
            <code className="text-slate-700">{API_BASE_URL}</code>
          </Fila>

          {isPending && <Fila etiqueta="Backend">Consultando…</Fila>}

          {isError && (
            <Fila etiqueta="Backend">
              <span className="text-estado-critico">Sin conexión — {mensajeDeError(error)}</span>
            </Fila>
          )}

          {data && (
            <>
              <Fila etiqueta="Backend">
                <Insignia ok={data.status === 'ok'}>
                  {data.status === 'ok' ? 'OK' : 'Degradado'}
                </Insignia>
                <span className="ml-2 text-slate-500">v{data.version}</span>
              </Fila>
              <Fila etiqueta="PostgreSQL">
                <Insignia ok={data.database === 'up'}>
                  {data.database === 'up' ? 'Conectada' : 'Sin conexión'}
                </Insignia>
              </Fila>
              <Fila etiqueta="PostGIS">
                {data.postgis ? (
                  <span className="text-slate-700">{data.postgis}</span>
                ) : (
                  <span className="text-slate-400">no disponible</span>
                )}
              </Fila>
            </>
          )}
        </dl>
      </section>
    </main>
  )
}

function Fila({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3">
      <dt className="w-28 shrink-0 text-slate-500">{etiqueta}</dt>
      <dd className="text-slate-800">{children}</dd>
    </div>
  )
}

function Insignia({ ok, children }: { ok: boolean; children: ReactNode }) {
  const clases = ok ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${clases}`}>{children}</span>
  )
}
