import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError } from 'axios'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import CambiarContrasena from '@/pages/CambiarContrasena'
import { cambiarContrasena } from '@/services/auth'

vi.mock('@/services/auth', async (original) => ({
  ...(await original<typeof import('@/services/auth')>()),
  cambiarContrasena: vi.fn(),
}))

function montar() {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <CambiarContrasena />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const campo = (nombre: string) => screen.getByLabelText(nombre)
const boton = () => screen.getByRole('button', { name: 'Cambiar contraseña' })

async function llenar(actual: string, nueva: string, repetida = nueva) {
  await userEvent.type(campo('Contraseña actual'), actual)
  await userEvent.type(campo('Contraseña nueva'), nueva)
  await userEvent.type(campo('Repita la contraseña nueva'), repetida)
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.mocked(cambiarContrasena).mockReset()
})

describe('cambiar la propia contraseña (US-61)', () => {
  it('advierte antes que se cerrarán las demás sesiones de la cuenta', () => {
    montar()

    expect(screen.getByText(/se cierran las demás sesiones abiertas/)).toBeInTheDocument()
    expect(boton()).toBeDisabled()
  })

  it.each([
    ['corta', 'una-clave-larga', 'corta', 'corta', /al menos 10 caracteres/],
    ['igual a la actual', 'una-clave-larga', 'una-clave-larga', 'una-clave-larga', /distinta/],
    ['mal repetida', 'una-clave-larga', 'otra-clave-larga', 'otra-clave-largx', /no coincide/],
  ])('una nueva %s se señala y no se puede enviar', async (_, actual, nueva, repetida, motivo) => {
    montar()

    await llenar(actual, nueva, repetida)

    expect(screen.getByText(motivo)).toBeInTheDocument()
    expect(boton()).toBeDisabled()
  })

  it('al cambiarla dice cuántas otras sesiones se cerraron y vacía los campos', async () => {
    vi.mocked(cambiarContrasena).mockResolvedValue({ sesiones_cerradas: 2 })
    montar()

    await llenar('una-clave-larga', 'otra-clave-larga')
    await userEvent.click(boton())

    expect(cambiarContrasena).toHaveBeenCalledWith('una-clave-larga', 'otra-clave-larga')
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Contraseña cambiada. Se cerraron 2 sesiones abiertas en otros equipos.',
    )
    expect(campo('Contraseña actual')).toHaveValue('')
    expect(campo('Contraseña nueva')).toHaveValue('')
  })

  it('sin otras sesiones abiertas, lo dice', async () => {
    vi.mocked(cambiarContrasena).mockResolvedValue({ sesiones_cerradas: 0 })
    montar()

    await llenar('una-clave-larga', 'otra-clave-larga')
    await userEvent.click(boton())

    expect(await screen.findByRole('status')).toHaveTextContent('No había otras sesiones abiertas.')
  })

  it('si la actual es incorrecta, muestra el motivo del backend', async () => {
    vi.mocked(cambiarContrasena).mockRejectedValue(
      new AxiosError(
        '403',
        'ERR',
        undefined,
        {},
        {
          status: 403,
          statusText: '',
          headers: {},
          config: {} as never,
          data: { detail: 'La contraseña actual no es correcta.' },
        },
      ),
    )
    montar()

    await llenar('no-es-esta-clave', 'otra-clave-larga')
    await userEvent.click(boton())

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'La contraseña actual no es correcta.',
    )
    expect(screen.queryByRole('status')).toBeNull()
  })
})

describe('ver lo que se escribe (21/10)', () => {
  it('cada uno de los tres campos tiene su ojo, y dice de cuál es', async () => {
    montar()

    for (const [etiqueta, boton] of [
      ['Contraseña actual', 'Mostrar contraseña actual'],
      ['Contraseña nueva', 'Mostrar contraseña nueva'],
      ['Repita la contraseña nueva', 'Mostrar repetición de la contraseña nueva'],
    ]) {
      expect(campo(etiqueta)).toHaveAttribute('type', 'password')
      await userEvent.click(screen.getByRole('button', { name: boton }))
      expect(campo(etiqueta)).toHaveAttribute('type', 'text')
    }
  })
})
