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
 * Modalidad carrusel: la grilla pasa sola de página. Nació para la pantalla de
 * planta (`US-33`), donde nadie la toca y con 10 filas por página las demás no se
 * verían nunca; desde el 04/11/2026 corre en todas las vistas. Al llegar a la
 * última página vuelve a la primera.
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
  /** Modalidad carrusel: pasar de página solo cada `ROTACION_MS`. */
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
  rotarPaginas = true,
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

  // Quien está leyendo u operando la grilla no debe perder la página: el carrusel
  // se detiene con el cursor encima, y se puede pausar a mano.
  const [pausado, setPausado] = useState(false)
  const [encima, setEncima] = useState(false)
  const carrusel = rotarPaginas && total > FILAS_POR_PAGINA
  const girando = carrusel && !pausado && !encima

  useEffect(() => {
    if (!girando) return
    // Depende del desplazamiento: pasar de página a mano vuelve a contar los 20 s.
    const temporizador = window.setTimeout(() => {
      const siguiente = desplazamiento + FILAS_POR_PAGINA
      setPagina({ clave: claveFiltros, desplazamiento: siguiente >= total ? 0 : siguiente })
    }, ROTACION_MS)
    return () => window.clearTimeout(temporizador)
  }, [girando, desplazamiento, total, claveFiltros])

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
          <div className="flex items-baseline gap-3">
            {carrusel && (
              <p className="text-xs text-slate-400">
                {pausado
                  ? 'Carrusel en pausa'
                  : encima
                    ? 'Carrusel detenido mientras el cursor está sobre la grilla'
                    : `Las páginas cambian solas cada ${ROTACION_MS / 1000} s`}{' '}
                <button
                  type="button"
                  onClick={() => setPausado(!pausado)}
                  className="text-marca-300 underline hover:text-marca-200"
                >
                  {pausado ? 'Reanudar' : 'Pausar'}
                </button>
              </p>
            )}
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
          <div onMouseEnter={() => setEncima(true)} onMouseLeave={() => setEncima(false)}>
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
          </div>
        )}
      </div>
    </section>
  )
}
