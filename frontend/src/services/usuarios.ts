/** Las cuentas, contra `/api/v1/usuarios` (`US-42`, pantalla de `US-62`). Solo Administrador. */

import { API_V1, api } from '@/services/api'
import type { Rol, UsuarioAdministrado } from '@/types/api'

export interface UsuarioNuevo {
  usuario: string
  nombre_completo: string
  correo: string | null
  rol: Rol
  contrasena: string
}

export interface CambiosUsuario {
  nombre_completo?: string
  correo?: string | null
  rol?: Rol
  /** `false` cierra todas sus sesiones abiertas. */
  activo?: boolean
}

export async function listarUsuarios(): Promise<UsuarioAdministrado[]> {
  const { data } = await api.get<UsuarioAdministrado[]>(`${API_V1}/usuarios`)
  return data
}

export async function crearUsuario(nuevo: UsuarioNuevo): Promise<UsuarioAdministrado> {
  const { data } = await api.post<UsuarioAdministrado>(`${API_V1}/usuarios`, nuevo)
  return data
}

export async function actualizarUsuario(
  id: number,
  cambios: CambiosUsuario,
): Promise<UsuarioAdministrado> {
  const { data } = await api.patch<UsuarioAdministrado>(`${API_V1}/usuarios/${id}`, cambios)
  return data
}

/** Desbloquea la cuenta y cierra **todas** sus sesiones. */
export async function reiniciarContrasena(id: number, contrasena: string): Promise<void> {
  await api.post(`${API_V1}/usuarios/${id}/contrasena`, { contrasena })
}
