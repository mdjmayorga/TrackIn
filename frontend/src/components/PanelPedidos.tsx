import { useState } from 'react'

import { GrillaPedidos } from '@/components/GrillaPedidos'
import { usePedidos } from '@/hooks/usePedidos'
import { mensajeDeError } from '@/services/api'
import type { Orden } from '@/types/api'

/** 10 filas, como el Figma: la grilla cabe en la pantalla sin desplazarse. */
export const FILAS_POR_PAGINA = 10

/** Igual que el backend: lo primero que le importa a Compras es qué llega antes. */
const ORDEN_INICIAL: Orden = 'fecha_proyectada'

/** «Grilla de Pedidos» del dashboard: la grilla con su consulta y su estado. */
export function PanelPedidos() {
  const [orden, setOrden] = useState<Orden>(ORDEN_INICIAL)
  const [desplazamiento, setDesplazamiento] = useState(0)
  const { data, error, isPending, isFetching, isPlaceholderData } = usePedidos({
    orden,
    limite: FILAS_POR_PAGINA,
    desplazamiento,
  })

  function ordenar(nuevo: Orden) {
    setOrden(nuevo)
    // Otro orden es otra lista: volver a la primera página.
    setDesplazamiento(0)
  }

  return (
    <section aria-labelledby="titulo-grilla">
      <h2 id="titulo-grilla" className="mb-2 text-base text-slate-100">
        Grilla de Pedidos
      </h2>

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
          onPaginar={setDesplazamiento}
          actualizando={isFetching && isPlaceholderData}
        />
      )}
    </section>
  )
}
