import { useEffect, useState } from 'react'

import { BarraFiltros } from '@/components/BarraFiltros'
import { GrillaPedidos, type VistaGrilla } from '@/components/GrillaPedidos'
import { usePedidos } from '@/hooks/usePedidos'
import { mensajeDeError } from '@/services/api'
import type { Orden } from '@/types/api'
import { type FiltrosPanel, filtraTerminales, hayFiltros } from '@/utils/filtros'

/** 10 filas, como el Figma: la grilla cabe en la pantalla sin desplazarse. */
export const FILAS_POR_PAGINA = 10

/**
 * La pantalla de planta pasa sola de página (`US-33`): nadie la toca, y con 10
 * filas por página las demás no se verían nunca. Al llegar a la última, vuelve
 * a la primera.
 */
export const ROTACION_MS = 20_000

/** Igual que el backend: lo primero que le importa a Compras es qué llega antes. */
const ORDEN_INICIAL: Orden = 'fecha_proyectada'

export interface PanelPedidosProps {
  filtros: FiltrosPanel
  onCambioFiltros: (cambios: Partial<FiltrosPanel>) => void
  onLimpiarFiltros: () => void
  /** Cambia al limpiar: la barra vuelve a nacer con los campos vacíos. */
  versionFiltros: number
  /** La grilla simple de la pantalla de planta (`US-43`); los filtros son los mismos. */
  vista?: VistaGrilla
  /** Pasar de página solo cada `ROTACION_MS` (`US-33`, pantalla de planta). */
  rotarPaginas?: boolean
}

/**
 * «Grilla de Pedidos» del dashboard: el recuadro «Filtros de consulta» del
 * Figma, con la barra de filtros (`US-21`) y la grilla (`US-19`) dentro.
 *
 * Los filtros viven en el dashboard, no aquí: también los usan la cinta de
 * KPIs y los próximos arribos.
 */
export function PanelPedidos({
  filtros,
  onCambioFiltros,
  onLimpiarFiltros,
  versionFiltros,
  vista = 'completa',
  rotarPaginas = false,
}: PanelPedidosProps) {
  const [orden, setOrden] = useState<Orden>(ORDEN_INICIAL)
  // La página se recuerda junto con los filtros con que se pidió: otro filtro
  // es otra lista, y seguir en la página 5 de la anterior no tendría sentido.
  const claveFiltros = JSON.stringify(filtros)
  const [pagina, setPagina] = useState({ clave: claveFiltros, desplazamiento: 0 })
  const desplazamiento = pagina.clave === claveFiltros ? pagina.desplazamiento : 0

  const { data, error, isPending, isFetching, isPlaceholderData } = usePedidos(
    { orden, limite: FILAS_POR_PAGINA, desplazamiento },
    filtros,
  )
  const filtrado = hayFiltros(filtros)
  const total = data?.total ?? 0

  useEffect(() => {
    if (!rotarPaginas || total <= FILAS_POR_PAGINA) return
    const temporizador = window.setInterval(() => {
      setPagina((actual) => {
        const desde = actual.clave === claveFiltros ? actual.desplazamiento : 0
        const siguiente = desde + FILAS_POR_PAGINA
        return { clave: claveFiltros, desplazamiento: siguiente >= total ? 0 : siguiente }
      })
    }, ROTACION_MS)
    return () => window.clearInterval(temporizador)
  }, [rotarPaginas, total, claveFiltros])

  function paginar(nuevo: number) {
    setPagina({ clave: claveFiltros, desplazamiento: nuevo })
  }

  function ordenar(nuevo: Orden) {
    setOrden(nuevo)
    // Otro orden es otra lista: volver a la primera página.
    paginar(0)
  }

  return (
    <section aria-labelledby="titulo-grilla">
      <h2 id="titulo-grilla" className="mb-2 pl-1 text-base text-slate-100">
        Grilla de Pedidos
      </h2>

      <div className="rounded border border-panel-borde bg-panel-superficie/40 p-1.5">
        <div className="mb-1.5 flex items-baseline justify-between gap-2">
          <h3 className="text-sm text-slate-100">Filtros de consulta</h3>
          {filtrado && (
            <button
              type="button"
              onClick={onLimpiarFiltros}
              className="text-xs text-marca-300 underline hover:text-marca-200"
            >
              Limpiar filtros
            </button>
          )}
        </div>
        <div className="mb-2">
          <BarraFiltros
            key={versionFiltros}
            filtros={filtros}
            onCambio={onCambioFiltros}
            conSolped={vista === 'simple'}
          />
        </div>

        {isPending && <p className="py-8 text-center text-slate-400">Cargando pedidos…</p>}

        {error && !data && (
          <p role="alert" className="rounded-lg bg-red-900/60 px-4 py-3 text-sm text-red-100">
            No se pudieron cargar los pedidos: {mensajeDeError(error)}
          </p>
        )}

        {rotarPaginas && total > FILAS_POR_PAGINA && (
          <p className="mb-1 text-right text-xs text-slate-400">
            Las páginas cambian solas cada {ROTACION_MS / 1000} s
          </p>
        )}

        {data && (
          <GrillaPedidos
            pagina={data}
            orden={orden}
            onOrdenar={ordenar}
            onPaginar={paginar}
            actualizando={isFetching && isPlaceholderData}
            terminales={filtraTerminales(filtros)}
            vista={vista}
            vacio={
              filtrado ? (
                <>
                  Ningún pedido coincide con los filtros.{' '}
                  <button
                    type="button"
                    onClick={onLimpiarFiltros}
                    className="text-marca-300 underline hover:text-marca-200"
                  >
                    Limpiar filtros
                  </button>
                </>
              ) : undefined
            }
          />
        )}
      </div>
    </section>
  )
}
