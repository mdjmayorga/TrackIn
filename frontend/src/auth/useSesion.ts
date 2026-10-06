import { useContext } from 'react'

import { ContextoSesion } from '@/auth/contexto'
import type { SesionGuardada } from '@/auth/sesion'

/** La sesión vigente, o `null` si no hay. */
export function useSesion(): SesionGuardada | null {
  return useContext(ContextoSesion)
}
