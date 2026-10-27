import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SesionGuardada } from '@/auth/sesion'
import { MenuConfiguracion } from '@/components/MenuConfiguracion'
import { cerrarSesion } from '@/services/auth'
import type { Rol } from '@/types/api'

import { USUARIO } from './sesion.test'

vi.mock('@/services/auth', async (original) => ({
  ...(await original<typeof import('@/services/auth')>()),
  cerrarSesion: vi.fn(),
}))

function montar(rol: Rol = 'COMPRAS') {
  const sesion: SesionGuardada = { token: 't', usuario: { ...USUARIO, rol }, recordada: false }
  render(
    <MemoryRouter>
      <p>Fuera del menú</p>
      <MenuConfiguracion sesion={sesion} />
    </MemoryRouter>,
  )
}

const boton = () => screen.getByRole('button', { name: 'Configuración' })
const opciones = () => screen.queryAllByRole('listitem').map((li) => li.textContent?.trim())

afterEach(() => {
  vi.mocked(cerrarSesion).mockReset()
})

describe('menú Configuración', () => {
  it('cerrado, no ocupa espacio: solo el botón', () => {
    montar()

    expect(boton()).toHaveAttribute('aria-expanded', 'false')
    expect(opciones()).toEqual([])
  })

  it('abierto, dice quién está conectado y ofrece las tres opciones', async () => {
    montar()

    await userEvent.click(boton())

    expect(boton()).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Compras')).toBeInTheDocument()
    expect(screen.getByText('COMPRAS')).toBeInTheDocument()
    // La carga del Z-tracking vive en «Ajustes Z-tracking» desde el 26/10.
    expect(opciones()).toEqual(['Integración con SAP', 'Cambiar contraseña', 'Cerrar sesión'])
  })

  it('Planta tiene lo mismo: cambiar su contraseña y cerrar sesión', async () => {
    montar('PLANTA')

    await userEvent.click(boton())

    expect(opciones()).toEqual(['Cambiar contraseña', 'Cerrar sesión'])
  })

  it('cerrar sesión cierra el menú y la sesión', async () => {
    montar()

    await userEvent.click(boton())
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))

    expect(cerrarSesion).toHaveBeenCalledOnce()
    expect(opciones()).toEqual([])
  })

  it('se cierra con Escape, devolviendo el foco al botón, y al hacer clic fuera', async () => {
    montar()

    await userEvent.click(boton())
    await userEvent.keyboard('{Escape}')
    expect(opciones()).toEqual([])
    expect(boton()).toHaveFocus()

    await userEvent.click(boton())
    await userEvent.click(screen.getByText('Fuera del menú'))
    expect(opciones()).toEqual([])
  })
})

describe('menú Configuración del Administrador (US-62)', () => {
  it('ofrece además «Usuarios»', async () => {
    montar('ADMINISTRADOR')

    await userEvent.click(boton())

    expect(opciones()).toEqual([
      'Usuarios',
      'Integración con SAP',
      'Cambiar contraseña',
      'Cerrar sesión',
    ])
    expect(screen.getByRole('link', { name: 'Integración con SAP' })).toHaveAttribute(
      'href',
      '/configuracion/sap',
    )
    expect(screen.getByRole('link', { name: 'Usuarios' })).toHaveAttribute('href', '/usuarios')
  })
})
