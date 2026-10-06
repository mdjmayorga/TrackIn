import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useSesion } from '@/auth/useSesion'

/**
 * Deja pasar solo con sesión. Sin ella, manda al login recordando a dónde se
 * quería ir, para volver ahí después de entrar.
 */
export function RutaProtegida({ children }: { children: ReactNode }) {
  const sesion = useSesion()
  const ubicacion = useLocation()

  if (!sesion) {
    return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />
  }
  return <>{children}</>
}
