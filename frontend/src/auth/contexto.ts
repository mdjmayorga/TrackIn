import { createContext } from 'react'

import type { SesionGuardada } from '@/auth/sesion'

/** La sesión vigente, o `null`. La provee `AuthProvider`. */
export const ContextoSesion = createContext<SesionGuardada | null>(null)
