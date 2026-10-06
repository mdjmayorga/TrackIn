/**
 * Dónde vive la sesión del navegador (`US-42`).
 *
 * El backend distingue dos sesiones, y el navegador las imita:
 *
 * - **Normal**: se cierra por inactividad en el servidor. Aquí va a
 *   `sessionStorage`, que se borra al cerrar la pestaña.
 * - **«Recordar sesión»**: dura `sesion_recordada_dias`. Va a `localStorage`,
 *   que sobrevive al cierre del navegador.
 *
 * El token no se decodifica ni se valida aquí: es opaco. Quien decide si sigue
 * valiendo es el backend, y lo dice con un 401.
 */

import type { UsuarioPublico } from '@/types/api'

const CLAVE = 'trackin.sesion'

export interface SesionGuardada {
  token: string
  usuario: UsuarioPublico
  recordada: boolean
}

type Oyente = (sesion: SesionGuardada | null) => void
const oyentes = new Set<Oyente>()

function leer(almacen: Storage): SesionGuardada | null {
  try {
    const crudo = almacen.getItem(CLAVE)
    return crudo ? (JSON.parse(crudo) as SesionGuardada) : null
  } catch {
    // Un valor corrupto o un almacenamiento bloqueado no pueden tumbar la app:
    // se trata como «sin sesión» y el usuario vuelve a entrar.
    return null
  }
}

export function sesionActual(): SesionGuardada | null {
  return leer(sessionStorage) ?? leer(localStorage)
}

export function guardarSesion(sesion: SesionGuardada): void {
  const destino = sesion.recordada ? localStorage : sessionStorage
  const otro = sesion.recordada ? sessionStorage : localStorage
  otro.removeItem(CLAVE)
  destino.setItem(CLAVE, JSON.stringify(sesion))
  oyentes.forEach((oyente) => oyente(sesion))
}

export function borrarSesion(): void {
  sessionStorage.removeItem(CLAVE)
  localStorage.removeItem(CLAVE)
  oyentes.forEach((oyente) => oyente(null))
}

/** Avisa cada vez que la sesión cambia; devuelve cómo dejar de escuchar. */
export function alCambiarSesion(oyente: Oyente): () => void {
  oyentes.add(oyente)
  return () => {
    oyentes.delete(oyente)
  }
}
