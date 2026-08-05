import { useQuery } from '@tanstack/react-query'

import { obtenerHealth } from '@/services/health'

/** Estado de salud del backend. Se refresca solo cada 30 s. */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: obtenerHealth,
    refetchInterval: 30_000,
    // Si el backend está caído no tiene sentido insistir mucho: el estado
    // "sin conexión" es información válida para mostrar.
    retry: 1,
  })
}
