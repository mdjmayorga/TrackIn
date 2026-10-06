import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { guardarSesion, sesionActual } from '@/auth/sesion'
import { agregarToken, manejarError, mensajeDeError } from '@/services/api'

import { USUARIO } from './sesion.test'

function config(url = '/api/v1/pedidos'): InternalAxiosRequestConfig {
  return { url, headers: new AxiosHeaders() } as InternalAxiosRequestConfig
}

function errorHttp(status: number, data: unknown, url = '/api/v1/pedidos'): AxiosError {
  const cfg = config(url)
  return new AxiosError(
    'fallo',
    'ERR',
    cfg,
    {},
    {
      status,
      data,
      statusText: '',
      headers: {},
      config: cfg,
    },
  )
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})

afterEach(() => {
  sessionStorage.clear()
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('mensajeDeError', () => {
  it('usa el detalle del backend cuando es texto', () => {
    expect(mensajeDeError(errorHttp(409, { detail: 'Ya existe' }))).toBe('Ya existe')
  })

  it('con un 422 de validación, cuyo detalle es una lista, da el código', () => {
    expect(mensajeDeError(errorHttp(422, { detail: [{ msg: 'x' }] }))).toBe(
      'El servidor respondió 422',
    )
  })

  it('sin respuesta, dice que el backend no contesta', () => {
    const sinRespuesta = new AxiosError('Network Error', 'ERR_NETWORK', config(), {})
    expect(mensajeDeError(sinRespuesta)).toMatch(/No se pudo contactar la API/)
  })

  it('cualquier otro error da su mensaje', () => {
    expect(mensajeDeError(new Error('raro'))).toBe('raro')
    expect(mensajeDeError('ni siquiera un Error')).toBe('Error desconocido')
  })
})

describe('agregarToken', () => {
  it('pone el token de la sesión en la cabecera', () => {
    guardarSesion({ token: 'abc', usuario: USUARIO, recordada: false })

    expect(agregarToken(config()).headers.get('Authorization')).toBe('Bearer abc')
  })

  it('sin sesión, no pone nada', () => {
    expect(agregarToken(config()).headers.get('Authorization')).toBeUndefined()
  })
})

describe('manejarError', () => {
  it('un 401 fuera del login borra la sesión: venció en el servidor', async () => {
    guardarSesion({ token: 'abc', usuario: USUARIO, recordada: false })

    await expect(manejarError(errorHttp(401, { detail: 'vencida' }))).rejects.toBeInstanceOf(
      AxiosError,
    )
    expect(sesionActual()).toBeNull()
  })

  it('el 401 del login no borra nada: son credenciales incorrectas', async () => {
    guardarSesion({ token: 'abc', usuario: USUARIO, recordada: false })

    await expect(
      manejarError(errorHttp(401, { detail: 'incorrectos' }, '/api/v1/auth/login')),
    ).rejects.toBeInstanceOf(AxiosError)
    expect(sesionActual()?.token).toBe('abc')
  })

  it('otros errores tampoco tocan la sesión', async () => {
    guardarSesion({ token: 'abc', usuario: USUARIO, recordada: false })

    await expect(manejarError(errorHttp(500, {}))).rejects.toBeInstanceOf(AxiosError)
    expect(sesionActual()?.token).toBe('abc')
  })
})
