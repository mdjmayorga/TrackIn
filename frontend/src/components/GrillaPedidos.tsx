/**
 * La grilla de pedidos (`US-19`, RF-04), con las nueve columnas del Figma
 * aprobado el 06/10: OC · POS · Material · Etapa · Cumplimiento · F. Proyectada
 * · F. Comprometida · Vía · Destino.
 *
 * Es presentacional: recibe la página y avisa cuando se pide otro orden u otra
 * página. Ordena y pagina el backend, sobre el total filtrado; ordenar solo lo
 * que hay en pantalla daría un orden falso apenas hubiera más de una página.
 */

import type { ReactNode } from 'react'

import { Distintivo } from '@/components/Distintivo'
import { CUMPLIMIENTOS, ETAPAS, etapaVisible } from '@/components/estados'
import type { ColumnaOrden, Orden, PaginaPedidos, PedidoResumen, Via } from '@/types/api'
import { formatearFecha } from '@/utils/fechas'

const VIAS: Record<Via, string> = {
  AEREO: 'Aéreo',
  MARITIMO: 'Marítimo',
  TERRESTRE: 'Terrestre',
}

interface Columna {
  titulo: string
  /** Sin clave no se ordena: POS ordena junto con la OC. */
  orden?: ColumnaOrden
  celda: (pedido: PedidoResumen) => ReactNode
  alinear?: 'izquierda'
}

/** El guion: «no evaluable», sin etiqueta adicional (validado el 01/09). */
function Guion({ motivo }: { motivo: string }) {
  return (
    <span aria-label={motivo} title={motivo} className="text-slate-500">
      –
    </span>
  )
}

function fecha(valor: string | null, motivo: string) {
  return formatearFecha(valor) ?? <Guion motivo={motivo} />
}

/**
 * Destino como en el Figma: el aeropuerto por su código («MROC»), el puerto
 * por su nombre («Puerto Limón»). El nombre completo queda en el `title`.
 */
function destino(pedido: PedidoResumen) {
  const { codigo, nombre } = pedido.destino
  return <span title={nombre}>{pedido.via_transporte === 'AEREO' ? codigo : nombre}</span>
}

function columnas(terminales: boolean): Columna[] {
  // Con los cerrados en pantalla importa cuándo llegaron, no cuándo se
  // proyectaba que llegaran (criterio validado el 01/09).
  const proyectada: Columna = terminales
    ? {
        titulo: 'F. Recepción',
        celda: (p) => fecha(p.fecha_recepcion_planta, 'Sin recepción registrada'),
      }
    : {
        titulo: 'F. Proyectada',
        orden: 'fecha_proyectada',
        celda: (p) => fecha(p.fecha_proyectada_disponible, 'Sin fecha proyectada'),
      }

  return [
    { titulo: 'OC', orden: 'oc', celda: (p) => p.oc_numero },
    { titulo: 'POS', celda: (p) => p.posicion_oc },
    {
      titulo: 'Material',
      orden: 'material',
      alinear: 'izquierda',
      celda: (p) => `${p.material.codigo} ${p.material.descripcion}`,
    },
    {
      titulo: 'Etapa',
      orden: 'etapa',
      celda: (p) => <Distintivo {...ETAPAS[etapaVisible(p)]} />,
    },
    {
      titulo: 'Cumplimiento',
      orden: 'cumplimiento',
      celda: (p) =>
        p.estado_cumplimiento ? (
          <Distintivo {...CUMPLIMIENTOS[p.estado_cumplimiento]} />
        ) : (
          <Guion motivo="Cumplimiento no evaluable" />
        ),
    },
    proyectada,
    {
      titulo: 'F. Comprometida',
      orden: 'fecha_comprometida',
      celda: (p) => formatearFecha(p.fecha_entrega_pedido),
    },
    { titulo: 'Vía', orden: 'via', celda: (p) => VIAS[p.via_transporte] },
    { titulo: 'Destino', orden: 'destino', celda: destino },
  ]
}

export interface GrillaPedidosProps {
  pagina: PaginaPedidos | undefined
  orden: Orden
  onOrdenar: (orden: Orden) => void
  onPaginar: (desplazamiento: number) => void
  /** Hay una consulta en vuelo; la página anterior sigue a la vista. */
  actualizando?: boolean
  /** Se filtra por un estado terminal: cambia la columna de fecha. */
  terminales?: boolean
}

export function GrillaPedidos({
  pagina,
  orden,
  onOrdenar,
  onPaginar,
  actualizando = false,
  terminales = false,
}: GrillaPedidosProps) {
  const cols = columnas(terminales)
  const columnaActual = orden.replace(/^-/, '')
  const descendente = orden.startsWith('-')

  function ordenarPor(columna: ColumnaOrden) {
    // Otra columna empieza ascendente; la misma alterna el sentido.
    onOrdenar(columna === columnaActual && !descendente ? `-${columna}` : columna)
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-panel-borde">
        <table className="w-full border-collapse text-xs text-slate-100">
          <caption className="sr-only">
            Pedidos en tránsito. Los encabezados con botón ordenan la grilla.
          </caption>
          <thead className="bg-panel-cabecera text-sm">
            <tr>
              {cols.map((col) => {
                const activa = col.orden === columnaActual
                return (
                  <th
                    key={col.titulo}
                    scope="col"
                    aria-sort={activa ? (descendente ? 'descending' : 'ascending') : undefined}
                    className="whitespace-nowrap px-2 py-2 font-semibold"
                  >
                    {col.orden ? (
                      <button
                        type="button"
                        onClick={() => ordenarPor(col.orden!)}
                        className="inline-flex items-center gap-1 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-marca-400"
                      >
                        {col.titulo}
                        <span aria-hidden="true" className={activa ? '' : 'text-slate-500'}>
                          {activa ? (descendente ? '▼' : '▲') : '↕'}
                        </span>
                      </button>
                    ) : (
                      col.titulo
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody
            aria-busy={actualizando}
            className={`bg-panel-superficie transition-opacity ${actualizando ? 'opacity-60' : ''}`}
          >
            {pagina?.items.map((pedido) => (
              <tr key={pedido.id} className="border-t border-white/5">
                {cols.map((col) => (
                  <td
                    key={col.titulo}
                    className={`whitespace-nowrap px-2 py-1.5 ${
                      col.alinear === 'izquierda' ? 'text-left' : 'text-center'
                    }`}
                  >
                    {col.celda(pedido)}
                  </td>
                ))}
              </tr>
            ))}
            {pagina && pagina.items.length === 0 && (
              <tr>
                <td colSpan={cols.length} className="px-3 py-8 text-center text-slate-400">
                  No hay pedidos que mostrar.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {pagina && pagina.total > 0 && <Paginador pagina={pagina} onPaginar={onPaginar} />}
    </div>
  )
}

function Paginador({
  pagina,
  onPaginar,
}: {
  pagina: PaginaPedidos
  onPaginar: (desplazamiento: number) => void
}) {
  const { total, limite, desplazamiento, items } = pagina
  const desde = desplazamiento + 1
  const hasta = desplazamiento + items.length
  const boton =
    'rounded border border-panel-borde px-2 py-0.5 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40'

  return (
    <nav
      aria-label="Paginación de pedidos"
      className="mt-2 flex items-center justify-between text-xs text-slate-300"
    >
      <p>
        {desde}–{hasta} de {total} pedidos
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          className={boton}
          disabled={desplazamiento === 0}
          onClick={() => onPaginar(Math.max(0, desplazamiento - limite))}
        >
          Anterior
        </button>
        <button
          type="button"
          className={boton}
          disabled={hasta >= total}
          onClick={() => onPaginar(desplazamiento + limite)}
        >
          Siguiente
        </button>
      </div>
    </nav>
  )
}
