import { afterEach, describe, expect, it, vi } from 'vitest'

import { alCambiarSesion, borrarSesion, guardarSesion, sesionActual } from '@/auth/sesion'
import type { UsuarioPublico } from '@/types/api'

export const USUARIO: UsuarioPublico = {
  id: 1,
  usuario: 'compras@gutis.com',
  nombre_completo: 'Compras',
  correo: 'compras@gutis.com',
  rol: 'COMPRAS',
  activo: true,
  ultimo_acceso: null,
}

afterEach(() => {
  sessionStorage.clear()
  localStorage.clear()
})

describe('sesión del navegador', () => {
  it('una sesión normal vive en la pestaña y se borra al cerrarla', () => {
    guardarSesion({ token: 't1', usuario: USUARIO, recordada: false })

    expect(sessionStorage.getItem('trackin.sesion')).not.toBeNull()
    expect(localStorage.getItem('trackin.sesion')).toBeNull()
    expect(sesionActual()?.token).toBe('t1')
  })

  it('«Recordar sesión» sobrevive al cierre del navegador y desplaza a la otra', () => {
    guardarSesion({ token: 'corta', usuario: USUARIO, recordada: false })
    guardarSesion({ token: 'larga', usuario: USUARIO, recordada: true })

    expect(sessionStorage.getItem('trackin.sesion')).toBeNull()
    expect(sesionActual()?.token).toBe('larga')
  })

  it('cerrar borra las dos y avisa a quien escucha', () => {
    const oyente = vi.fn()
    const dejar = alCambiarSesion(oyente)
    guardarSesion({ token: 't', usuario: USUARIO, recordada: true })

    borrarSesion()
    dejar()
    guardarSesion({ token: 'otra', usuario: USUARIO, recordada: false })

    expect(sesionActual()?.token).toBe('otra')
    expect(oyente).toHaveBeenCalledTimes(2)
    expect(oyente).toHaveBeenLastCalledWith(null)
  })

  it('un valor corrupto cuenta como sin sesión, no rompe la app', () => {
    localStorage.setItem('trackin.sesion', '{no es json')

    expect(sesionActual()).toBeNull()
  })
})
