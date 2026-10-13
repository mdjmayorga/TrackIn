import { keepPreviousData, useQuery } from '@tanstack/react-query'

import {
  type ConsultaPedidos,
  listarPedidos,
  obtenerIndicadores,
  obtenerProximosArribos,
} from '@/services/pedidos'

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

// Las claves empiezan con `pedidos`: al cargar un Z-tracking se invalida
// `['pedidos']` y la grilla, los KPIs y los arribos se refrescan juntos.

/** La cinta de KPIs (`US-22`). */
export function useIndicadores() {
  return useQuery({ queryKey: ['pedidos', 'indicadores'], queryFn: obtenerIndicadores })
}

/** Los próximos arribos (`US-28`). */
export function useProximosArribos() {
  return useQuery({ queryKey: ['pedidos', 'proximos-arribos'], queryFn: obtenerProximosArribos })
}
