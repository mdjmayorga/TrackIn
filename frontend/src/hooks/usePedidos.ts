import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { type ConsultaPedidos, listarPedidos } from '@/services/pedidos'

/**
 * Una página de la grilla. Al ordenar o paginar se conserva la página anterior
 * en pantalla hasta que llega la nueva, en vez de vaciar la tabla (`US-19`:
 * «sin recargar la página»).
 */
export function usePedidos(consulta: ConsultaPedidos) {
  return useQuery({
    queryKey: ['pedidos', consulta],
    queryFn: () => listarPedidos(consulta),
    placeholderData: keepPreviousData,
  })
}
