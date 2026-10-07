import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Rutas } from '@/App'
import { AuthProvider } from '@/auth/AuthContext'
import { guardarSesion, sesionActual } from '@/auth/sesion'
import { api } from '@/services/api'

import { USUARIO } from './sesion.test'

vi.mock('@/services/pedidos', () => ({
  listarPedidos: vi.fn().mockResolvedValue({ total: 0, limite: 10, desplazamiento: 0, items: [] }),
}))

vi.mock('@/services/health', () => ({
  obtenerHealth: vi.fn().mockResolvedValue({
    status: 'ok',
    version: '0.1.0',
    environment: 'test',
    database: 'up',
    postgis: '3.6',
    detail: null,
  }),
}))

function montar(ruta = '/') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[ruta]}>
          <Rutas />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
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

describe('rutas protegidas', () => {
  it('sin sesión, el dashboard manda al login', () => {
    montar('/')

    expect(screen.getByRole('heading', { name: 'TrackIn' })).toBeInTheDocument()
    expect(screen.getByLabelText('Usuario')).toBeInTheDocument()
  })

  it('con sesión, entra al dashboard y muestra quién es', () => {
    guardarSesion({ token: 't', usuario: USUARIO, recordada: false })
    montar('/')

    expect(screen.getByRole('heading', { name: /Panel de Control Logístico/ })).toBeInTheDocument()
    expect(screen.getByText('COMPRAS')).toBeInTheDocument()
  })

  it('una ruta desconocida vuelve al inicio', () => {
    guardarSesion({ token: 't', usuario: USUARIO, recordada: false })
    montar('/no-existe')

    expect(screen.getByRole('heading', { name: /Panel de Control Logístico/ })).toBeInTheDocument()
  })

  it('cerrar sesión vuelve al login', async () => {
    guardarSesion({ token: 't', usuario: USUARIO, recordada: false })
    vi.spyOn(api, 'post').mockResolvedValue({ data: null })
    montar('/')

    await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))

    expect(await screen.findByLabelText('Usuario')).toBeInTheDocument()
    expect(sesionActual()).toBeNull()
  })
})

describe('pantalla de login', () => {
  it('con credenciales válidas entra y vuelve a donde quería ir', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({
      data: { token: 'nuevo', tipo: 'bearer', recordada: false, usuario: USUARIO },
    })
    montar('/')

    await userEvent.type(screen.getByLabelText('Usuario'), 'compras@gutis.com')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'una-clave-larga')
    await userEvent.click(screen.getByRole('button', { name: 'Iniciar sesión' }))

    expect(
      await screen.findByRole('heading', { name: /Panel de Control Logístico/ }),
    ).toBeInTheDocument()
  })

  it('con credenciales inválidas muestra el mensaje genérico del backend', async () => {
    const { AxiosError } = await import('axios')
    vi.spyOn(api, 'post').mockRejectedValue(
      new AxiosError(
        '401',
        'ERR',
        undefined,
        {},
        {
          status: 401,
          statusText: '',
          headers: {},
          config: {} as never,
          data: { detail: 'Usuario o contraseña incorrectos, o la cuenta está bloqueada.' },
        },
      ),
    )
    montar('/login')

    await userEvent.type(screen.getByLabelText('Usuario'), 'x')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'y')
    await userEvent.click(screen.getByRole('button', { name: 'Iniciar sesión' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /incorrectos, o la cuenta está bloqueada/,
    )
    expect(sesionActual()).toBeNull()
  })

  it('«¿Olvidó su contraseña?» explica que la reinicia el Administrador', async () => {
    montar('/login')

    await userEvent.click(screen.getByRole('button', { name: '¿Olvidó su contraseña?' }))

    expect(screen.getByText(/Pida al Administrador/)).toBeInTheDocument()
  })

  it('con sesión ya abierta, el login no se muestra', () => {
    guardarSesion({ token: 't', usuario: USUARIO, recordada: false })
    montar('/login')

    expect(screen.getByRole('heading', { name: /Panel de Control Logístico/ })).toBeInTheDocument()
  })
})

describe('mostrar la contraseña', () => {
  it('el ojo alterna entre ver y ocultar lo escrito', async () => {
    montar('/login')
    const campo = screen.getByLabelText('Contraseña')
    await userEvent.type(campo, 'una-clave-larga')
    expect(campo).toHaveAttribute('type', 'password')

    await userEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña' }))
    expect(campo).toHaveAttribute('type', 'text')
    expect(campo).toHaveValue('una-clave-larga')

    await userEvent.click(screen.getByRole('button', { name: 'Ocultar contraseña' }))
    expect(campo).toHaveAttribute('type', 'password')
  })

  it('el ojo no envía el formulario', async () => {
    const post = vi.spyOn(api, 'post')
    montar('/login')

    await userEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña' }))

    expect(post).not.toHaveBeenCalled()
  })
})
