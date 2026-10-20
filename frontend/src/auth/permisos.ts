/** Qué puede hacer cada rol en la interfaz. El backend lo vuelve a verificar. */

import type { Rol } from '@/types/api'

/** Subir el Z-tracking (`US-58`): `requiere_rol(COMPRAS)`, más el Administrador. */
export const PUEDEN_CARGAR: readonly Rol[] = ['COMPRAS', 'ADMINISTRADOR']

export function puedeCargar(rol: Rol | undefined): boolean {
  return rol !== undefined && PUEDEN_CARGAR.includes(rol)
}

/** Asociar el identificador de rastreo (`US-20`): `requiere_rol(LOGISTICA, COMPRAS)`. */
export const PUEDEN_ASOCIAR: readonly Rol[] = ['LOGISTICA', 'COMPRAS', 'ADMINISTRADOR']

export function puedeAsociar(rol: Rol | undefined): boolean {
  return rol !== undefined && PUEDEN_ASOCIAR.includes(rol)
}

/**
 * Las intervenciones del detalle (`US-60`), con los roles de su endpoint. El
 * Administrador puede todas (`requiere_rol` lo deja pasar siempre).
 */
export const ROLES_ACCION = {
  desembarco: ['LOGISTICA', 'ADMINISTRADOR'],
  aduana: ['PLANIFICACION', 'LOGISTICA', 'ADMINISTRADOR'],
  recepcion: ['LOGISTICA', 'ADMINISTRADOR'],
  liberacion: ['PLANIFICACION', 'LOGISTICA', 'ADMINISTRADOR'],
  ajuste: ['LOGISTICA', 'ADMINISTRADOR'],
} as const satisfies Record<string, readonly Rol[]>

export type Accion = keyof typeof ROLES_ACCION

export function puedeIntervenir(accion: Accion, rol: Rol | undefined): boolean {
  return rol !== undefined && (ROLES_ACCION[accion] as readonly Rol[]).includes(rol)
}

/**
 * La pantalla permanente de planta (`US-43`, RNF-11): ve el panel con la grilla
 * simple del Figma y no tiene ninguna acción. No figura en ninguna de las
 * listas de arriba, así que tampoco puede intervenir pedidos ni cargar.
 */
export function esPantallaPlanta(rol: Rol | undefined): boolean {
  return rol === 'PLANTA'
}

/**
 * La bandeja de arribos (`US-48`) es para quien puede gestionarlos: pasar un
 * pedido a proceso aduanal. Para los demás, el contador sería un pendiente que
 * no pueden resolver.
 */
export function puedeVerBandeja(rol: Rol | undefined): boolean {
  return puedeIntervenir('aduana', rol)
}
