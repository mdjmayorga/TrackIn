/** Qué puede hacer cada rol en la interfaz. El backend lo vuelve a verificar. */

import type { Rol } from '@/types/api'

/** Subir el Z-tracking (`US-58`): `requiere_rol(COMPRAS)`, más el Administrador. */
export const PUEDEN_CARGAR: readonly Rol[] = ['COMPRAS', 'ADMINISTRADOR']

export function puedeCargar(rol: Rol | undefined): boolean {
  return rol !== undefined && PUEDEN_CARGAR.includes(rol)
}
