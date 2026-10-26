/**
 * Los filtros del panel (`US-21`, Figma corregido el 30/09): Orden de compra ·
 * Posición · Material · Vía · Etapa · Cumplimiento.
 *
 * Un solo estado para todo el panel: la grilla, la cinta de KPIs y los próximos
 * arribos —y los mapas en el Sprint 7— tienen que mostrar el mismo subconjunto.
 * El backend acepta los mismos parámetros en los tres endpoints.
 */

import type { EtapaVisible } from '@/components/estados'
import type { Cumplimiento, Via } from '@/types/api'

/** El guion de la grilla —sin fecha proyectada— es una opción más del filtro. */
export type CumplimientoFiltro = Cumplimiento | 'SIN_PROYECCION'

export interface FiltrosPanel {
  /** Prefijo de la OC: «4500» trae todas las que empiezan así. */
  oc: string
  posicion: string
  /** Texto en el código o la descripción del material. */
  material: string
  via: Via | ''
  etapa: EtapaVisible | ''
  cumplimiento: CumplimientoFiltro | ''
  /** Prefijo de la solicitud de pedido: solo lo ofrece la pantalla de planta (`US-63`). */
  solped: string
}

export const FILTROS_VACIOS: FiltrosPanel = {
  oc: '',
  posicion: '',
  material: '',
  via: '',
  etapa: '',
  cumplimiento: '',
  solped: '',
}

export function hayFiltros(filtros: FiltrosPanel): boolean {
  return Object.values(filtros).some((valor) => valor.trim() !== '')
}

/** Cerrado y Cancelado traen los pedidos terminales, que por omisión no salen. */
export function filtraTerminales(filtros: FiltrosPanel): boolean {
  return filtros.etapa === 'CERRADO' || filtros.etapa === 'CANCELADO'
}

/** Los parámetros de la API; los vacíos no se mandan. */
export function aParametros(filtros: FiltrosPanel): Record<string, string> {
  const parametros: Record<string, string> = {}
  const texto = (valor: string) => valor.trim()
  if (texto(filtros.oc)) parametros.oc = texto(filtros.oc)
  if (texto(filtros.posicion)) parametros.posicion = texto(filtros.posicion)
  if (texto(filtros.material)) parametros.buscar_material = texto(filtros.material)
  if (filtros.via) parametros.via = filtros.via
  if (filtros.etapa) parametros.etapa = filtros.etapa
  if (filtros.cumplimiento) parametros.cumplimiento = filtros.cumplimiento
  if (texto(filtros.solped)) parametros.solped = texto(filtros.solped)
  return parametros
}

/** Solo dígitos: la OC y la posición son números en SAP. */
export function soloDigitos(valor: string, maximo: number): string {
  return valor.replace(/\D/g, '').slice(0, maximo)
}
