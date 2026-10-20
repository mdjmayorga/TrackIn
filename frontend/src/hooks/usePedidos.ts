import { keepPreviousData, useQuery } from '@tanstack/react-query'

import {
  type ConsultaPedidos,
  listarPedidos,
  obtenerBitacora,
  obtenerPedido,
  obtenerIndicadores,
  obtenerProximosArribos,
} from '@/services/pedidos'
import { FILTROS_VACIOS, type FiltrosPanel } from '@/utils/filtros'

// Las claves empiezan con `pedidos`: al cargar un Z-tracking se invalida
// `['pedidos']` y la grilla, los KPIs y los arribos se refrescan juntos. Los
// filtros van en la clave: cada combinación es su propia consulta en caché.
//
// `keepPreviousData` en los tres: al cambiar un filtro se conserva lo que hay
// en pantalla hasta que llega lo nuevo, en vez de vaciar los bloques (RNF-02:
// «sin recarga completa»).

/**
 * Una página de la grilla. Al ordenar o paginar se conserva la página anterior
 * en pantalla hasta que llega la nueva, en vez de vaciar la tabla (`US-19`).
 */
export function usePedidos(consulta: ConsultaPedidos, filtros: FiltrosPanel = FILTROS_VACIOS) {
  return useQuery({
    queryKey: ['pedidos', consulta, filtros],
    queryFn: () => listarPedidos(consulta, filtros),
    placeholderData: keepPreviousData,
  })
}

/** La cinta de KPIs (`US-22`). */
export function useIndicadores(filtros: FiltrosPanel = FILTROS_VACIOS) {
  return useQuery({
    queryKey: ['pedidos', 'indicadores', filtros],
    queryFn: () => obtenerIndicadores(filtros),
    placeholderData: keepPreviousData,
  })
}

/** Los próximos arribos (`US-28`). */
export function useProximosArribos(filtros: FiltrosPanel = FILTROS_VACIOS) {
  return useQuery({
    queryKey: ['pedidos', 'proximos-arribos', filtros],
    queryFn: () => obtenerProximosArribos(filtros),
    placeholderData: keepPreviousData,
  })
}

/** Cuántos arribos trae la bandeja como máximo: el tope del backend. */
export const LIMITE_BANDEJA = 200

/** Cada cuánto se vuelve a mirar la bandeja: el ciclo del worker es de 60 s. */
const REFRESCO_BANDEJA_MS = 60_000

/**
 * La bandeja de arribos pendientes de gestión (`US-48`): los pedidos en
 * `EN_DESTINO`, lo que lleva más tiempo esperando primero. La comparten el
 * contador del encabezado y la página, así que nunca dicen cifras distintas.
 *
 * Se vuelve a pedir sola cada minuto: un arribo lo detecta el worker, no una
 * acción de quien mira, y el aviso es dentro de la aplicación (sin correo).
 */
export function useBandejaArribos(habilitada = true) {
  return useQuery({
    queryKey: ['pedidos', 'bandeja'],
    queryFn: () =>
      listarPedidos(
        { orden: 'fecha_arribo', limite: LIMITE_BANDEJA, desplazamiento: 0 },
        { ...FILTROS_VACIOS, etapa: 'EN_DESTINO' },
      ),
    enabled: habilitada,
    refetchInterval: REFRESCO_BANDEJA_MS,
  })
}

/** El detalle de un pedido (`US-20`). Bajo `pedidos`: una carga lo refresca. */
export function usePedido(id: number) {
  return useQuery({ queryKey: ['pedidos', 'detalle', id], queryFn: () => obtenerPedido(id) })
}

/** Las intervenciones manuales del pedido, para la línea de tiempo (RF-14). */
export function useBitacora(id: number) {
  return useQuery({ queryKey: ['pedidos', 'bitacora', id], queryFn: () => obtenerBitacora(id) })
}
