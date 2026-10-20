/** Iniciar y cerrar sesión contra `/api/v1/auth` (`US-42`). */

import { guardarSesion, borrarSesion } from '@/auth/sesion'
import { API_V1, api } from '@/services/api'
import type { ContrasenaCambiada, SesionIniciada } from '@/types/api'

export async function iniciarSesion(
  usuario: string,
  contrasena: string,
  recordar: boolean,
): Promise<SesionIniciada> {
  const { data } = await api.post<SesionIniciada>(`${API_V1}/auth/login`, {
    usuario,
    contrasena,
    recordar,
  })
  guardarSesion({ token: data.token, usuario: data.usuario, recordada: data.recordada })
  return data
}

/**
 * Cambia la propia contraseña (`US-61`). La sesión del navegador sigue
 * abierta: el backend cierra las demás de la cuenta, no esta.
 */
export async function cambiarContrasena(
  actual: string,
  nueva: string,
): Promise<ContrasenaCambiada> {
  const { data } = await api.post<ContrasenaCambiada>(`${API_V1}/auth/contrasena`, {
    contrasena_actual: actual,
    contrasena_nueva: nueva,
  })
  return data
}

/**
 * Cierra la sesión en el servidor y en el navegador.
 *
 * La local se borra **siempre**, aunque el servidor no responda: quien pulsa
 * «Cerrar sesión» no puede quedarse dentro porque la red falló.
 */
export async function cerrarSesion(): Promise<void> {
  try {
    await api.post(`${API_V1}/auth/logout`)
  } catch {
    // Ya se registró en el interceptor; la sesión local se borra igual.
  } finally {
    borrarSesion()
  }
}
