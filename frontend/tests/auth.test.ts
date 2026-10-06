import { afterEach, describe, expect, it, vi } from 'vitest'

import { guardarSesion, sesionActual } from '@/auth/sesion'
import { api } from '@/services/api'
import { cerrarSesion, iniciarSesion } from '@/services/auth'

import { USUARIO } from './sesion.test'

afterEach(() => {
  sessionStorage.clear()
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('servicio de autenticación', () => {
  it('iniciar sesión guarda el token y el usuario', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      data: { token: 'nuevo', tipo: 'bearer', recordada: true, usuario: USUARIO },
    })

    await iniciarSesion('compras@gutis.com', 'una-clave-larga', true)

    expect(post).toHaveBeenCalledWith('/api/v1/auth/login', {
      usuario: 'compras@gutis.com',
      contrasena: 'una-clave-larga',
      recordar: true,
    })
    expect(sesionActual()).toMatchObject({ token: 'nuevo', recordada: true })
  })

  it('cerrar sesión borra la local aunque el servidor no responda', async () => {
    guardarSesion({ token: 'abc', usuario: USUARIO, recordada: false })
    vi.spyOn(api, 'post').mockRejectedValue(new Error('sin red'))

    await cerrarSesion()

    expect(sesionActual()).toBeNull()
  })
})
