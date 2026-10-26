/** Altas en ShipsGo desde TrackIn (`/api/v1/shipsgo/altas`, `US-55`). Compras y Administrador. */

import { AxiosError } from 'axios'

import { API_V1, api } from '@/services/api'
import type { AltasHechas, AltasPendientes, EstadoCreditos } from '@/types/api'

/** Listar la cuenta y el catálogo de ShipsGo: gratis, pero varias páginas. */
const ESPERA_MS = 60_000

export async function obtenerAltasPendientes(): Promise<AltasPendientes> {
  const { data } = await api.get<AltasPendientes>(`${API_V1}/shipsgo/altas/pendientes`, {
    timeout: ESPERA_MS,
  })
  return data
}

export interface SolicitudAltas {
  referencias: Array<{ tipo: string; numero: string }>
  /** Quien autoriza repite cuántos créditos se gastan: uno por referencia. */
  creditos_confirmados: number
  /** Acepta pasar del tope diario `altas_maximas_dia`. */
  superar_tope: boolean
  /** Acepta seguir aunque el saldo registrado no alcance (`US-57`). */
  aceptar_saldo: boolean
}

/** **Cuesta un crédito por referencia.** */
export async function darDeAltaEnShipsGo(solicitud: SolicitudAltas): Promise<AltasHechas> {
  const { data } = await api.post<AltasHechas>(`${API_V1}/shipsgo/altas`, solicitud, {
    timeout: ESPERA_MS,
  })
  return data
}

/** El saldo de créditos y el aviso que corresponde (`US-57`). No consulta ShipsGo. */
export async function obtenerCreditos(): Promise<EstadoCreditos> {
  const { data } = await api.get<EstadoCreditos>(`${API_V1}/shipsgo/creditos`)
  return data
}

export interface PaqueteNuevo {
  cantidad: number
  /** `AAAA-MM-DD`. */
  comprado_en: string
  vence_en: string | null
  /** Sube el tope diario de altas en el mismo paso. */
  altas_maximas_dia: number | null
  nota: string | null
}

/** Registra una compra de créditos; queda como el paquete vigente. */
export async function registrarPaquete(paquete: PaqueteNuevo): Promise<EstadoCreditos> {
  const { data } = await api.post<EstadoCreditos>(`${API_V1}/shipsgo/creditos/paquetes`, paquete)
  return data
}

/** El 409 de saldo insuficiente, si es eso lo que respondió el backend (`US-57`). */
export function comoSaldoInsuficiente(error: unknown): { detail: string; saldo: number } | null {
  if (error instanceof AxiosError && error.response?.status === 409) {
    const datos = error.response.data as { requiere_aceptar_saldo?: boolean } | undefined
    if (datos?.requiere_aceptar_saldo) {
      return error.response.data as { detail: string; saldo: number }
    }
  }
  return null
}

/** El 409 del tope diario, si es eso lo que respondió el backend. */
export function comoTopeSuperado(
  error: unknown,
): { detail: string; altas_hoy: number; altas_maximas_dia: number } | null {
  if (error instanceof AxiosError && error.response?.status === 409) {
    const datos = error.response.data as { requiere_superar_tope?: boolean } | undefined
    if (datos?.requiere_superar_tope) {
      return error.response.data as { detail: string; altas_hoy: number; altas_maximas_dia: number }
    }
  }
  return null
}
