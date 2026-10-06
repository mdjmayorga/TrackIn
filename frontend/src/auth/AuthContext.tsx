/**
 * La sesión disponible para toda la app (`US-42`).
 *
 * Se sincroniza con `sesion.ts`: cuando el cliente HTTP recibe un 401 y borra
 * la sesión, este proveedor se entera y las rutas protegidas mandan al login.
 */

import { useEffect, useState, type ReactNode } from 'react'

import { ContextoSesion } from '@/auth/contexto'
import { alCambiarSesion, sesionActual, type SesionGuardada } from '@/auth/sesion'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<SesionGuardada | null>(sesionActual)

  useEffect(() => alCambiarSesion(setSesion), [])

  return <ContextoSesion.Provider value={sesion}>{children}</ContextoSesion.Provider>
}
