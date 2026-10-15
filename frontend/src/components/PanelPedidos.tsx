import { useState } from 'react'

import { BarraFiltros } from '@/components/BarraFiltros'
import { GrillaPedidos } from '@/components/GrillaPedidos'
import { usePedidos } from '@/hooks/usePedidos'
import { mensajeDeError } from '@/services/api'
import type { Orden } from '@/types/api'
import { type FiltrosPanel, filtraTerminales, hayFiltros } from '@/utils/filtros'

/** 10 filas, como el Figma: la grilla cabe en la pantalla sin desplazarse. */
export const FILAS_POR_PAGINA = 10

/** Igual que el backend: lo primero que le importa a Compras es qué llega antes. */
const ORDEN_INICIAL: Orden = 'fecha_proyectada'

export interface PanelPedidosProps {
  filtros: FiltrosPanel
  onCambioFiltros: (cambios: Partial<FiltrosPanel>) => void
  onLimpiarFiltros: () => void
  /** Cambia al limpiar: la barra vuelve a nacer con los campos vacíos. */
  versionFiltros: number
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
          <BarraFiltros key={versionFiltros} filtros={filtros} onCambio={onCambioFiltros} />
        </div>

        {isPending && <p className="py-8 text-center text-slate-400">Cargando pedidos…</p>}

        {error && !data && (
          <p role="alert" className="rounded-lg bg-red-900/60 px-4 py-3 text-sm text-red-100">
            No se pudieron cargar los pedidos: {mensajeDeError(error)}
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
