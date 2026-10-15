import type { QueryClient } from '@tanstack/react-query'

import type { PedidoDetalle } from '@/types/api'

/**
 * Tras una intervención: el detalle que devolvió la API se guarda tal cual, y
 * todo lo demás de `pedidos` —grilla, KPIs, arribos, bitácora— se vuelve a
 * pedir. El detalle no: acaba de llegar, y pedirlo otra vez solo arriesga
 * pisarlo con una respuesta vieja.
 */
export function refrescarTrasIntervenir(queryClient: QueryClient, detalle: PedidoDetalle): void {
  const clave = ['pedidos', 'detalle', detalle.id]
  queryClient.setQueryData(clave, detalle)
  void queryClient.invalidateQueries({
    queryKey: ['pedidos'],
    predicate: (consulta) => JSON.stringify(consulta.queryKey) !== JSON.stringify(clave),
  })
}
