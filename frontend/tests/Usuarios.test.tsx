import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError } from 'axios'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ContextoSesion } from '@/auth/contexto'
import type { SesionGuardada } from '@/auth/sesion'
import Usuarios from '@/pages/Usuarios'
import {
  actualizarUsuario,
  crearUsuario,
  listarUsuarios,
  reiniciarContrasena,
} from '@/services/usuarios'
import type { Rol, UsuarioAdministrado } from '@/types/api'

import { USUARIO } from './sesion.test'

vi.mock('@/services/usuarios', () => ({
  listarUsuarios: vi.fn(),
  crearUsuario: vi.fn(),
  actualizarUsuario: vi.fn(),
  reiniciarContrasena: vi.fn(),
}))

function cuenta(cambios: Partial<UsuarioAdministrado> = {}): UsuarioAdministrado {
  return {
    id: 2,
    usuario: 'compras@gutis.com',
    nombre_completo: 'Compras',
    correo: 'compras@gutis.com',
    rol: 'COMPRAS',
    activo: true,
    ultimo_acceso: null,
    bloqueado_hasta: null,
    ...cambios,
  }
}

const ADMIN = cuenta({
  id: 1,
  usuario: 'admin',
  nombre_completo: 'Admin',
  correo: null,
  rol: 'ADMINISTRADOR',
})

function montar(rol: Rol = 'ADMINISTRADOR') {
  const sesion: SesionGuardada = {
    token: 't',
    usuario: { ...USUARIO, id: 1, usuario: 'admin', rol },
    recordada: false,
  }
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ContextoSesion.Provider value={sesion}>
        <MemoryRouter initialEntries={['/usuarios']}>
          <Routes>
            <Route path="/usuarios" element={<Usuarios />} />
            <Route path="/" element={<p>Panel</p>} />
          </Routes>
        </MemoryRouter>
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
}

const fila = async (usuario: string) =>
  within(await screen.findByRole('row', { name: `Cuenta ${usuario}` }))

/** Por el comienzo de la etiqueta: algunas llevan su ayuda dentro («Al menos 10…»). */
async function escribir(etiqueta: string, texto: string) {
  await userEvent.type(screen.getByLabelText(new RegExp(`^${etiqueta}`)), texto)
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
  vi.mocked(listarUsuarios).mockResolvedValue([ADMIN, cuenta()])
})

afterEach(() => {
  vi.restoreAllMocks()
  for (const f of [listarUsuarios, crearUsuario, actualizarUsuario, reiniciarContrasena]) {
    vi.mocked(f).mockReset()
  }
})

describe('Usuarios (US-62)', () => {
  it('un rol que no es Administrador vuelve al panel', () => {
    montar('COMPRAS')

    expect(screen.getByText('Panel')).toBeInTheDocument()
    expect(listarUsuarios).not.toHaveBeenCalled()
  })

  it('lista las cuentas con rol, estado y último acceso', async () => {
    vi.mocked(listarUsuarios).mockResolvedValue([
      ADMIN,
      cuenta({ ultimo_acceso: '2026-10-20T15:30:00Z' }),
      cuenta({ id: 3, usuario: 'planta', correo: null, rol: 'PLANTA', activo: false }),
      cuenta({
        id: 4,
        usuario: 'logistica',
        correo: null,
        rol: 'LOGISTICA',
        bloqueado_hasta: '2999-01-01T12:00:00Z',
      }),
    ])
    montar()

    const compras = await fila('compras@gutis.com')
    expect(compras.getAllByText('Compras')).toHaveLength(2) // el nombre y el rol
    expect(compras.getByText('Activa')).toBeInTheDocument()
    expect(compras.getByText('20/10/2026 09:30')).toBeInTheDocument()
    expect((await fila('planta')).getByText('Inactiva')).toBeInTheDocument()
    expect((await fila('planta')).getByText('Planta (solo lectura)')).toBeInTheDocument()
    expect((await fila('logistica')).getByText(/Bloqueada hasta/)).toBeInTheDocument()
    expect((await fila('admin')).getByText('(usted)')).toBeInTheDocument()
  })

  it('la propia cuenta no se puede desactivar ni quitarse el rol', async () => {
    montar()

    const propia = await fila('admin')
    expect(propia.queryByRole('button', { name: 'Desactivar' })).toBeNull()
    await userEvent.click(propia.getByRole('button', { name: 'Editar' }))
    expect(screen.getByRole('combobox')).toBeDisabled()
    expect(screen.getByText(/No puede quitarse a sí mismo/)).toBeInTheDocument()
  })

  it('crea una cuenta con su rol y contraseña inicial', async () => {
    vi.mocked(crearUsuario).mockResolvedValue(cuenta({ id: 9, usuario: 'planif' }))
    montar()

    await userEvent.click(await screen.findByRole('button', { name: 'Crear cuenta' }))
    await escribir('Usuario', 'Planif')
    await escribir('Nombre completo', 'Planificación')
    await userEvent.selectOptions(screen.getByRole('combobox'), 'PLANIFICACION')
    await escribir('Contraseña inicial', 'corta')
    expect(screen.getByText(/al menos 10 caracteres/)).toBeInTheDocument()
    await escribir('Contraseña inicial', '-pero-ya-no')
    await escribir('Repita la contraseña inicial', 'corta-pero-ya-no')
    await userEvent.click(screen.getByRole('button', { name: 'Crear' }))

    expect(crearUsuario).toHaveBeenCalledWith({
      usuario: 'Planif',
      nombre_completo: 'Planificación',
      correo: null,
      rol: 'PLANIFICACION',
      contrasena: 'corta-pero-ya-no',
    })
    expect(await screen.findByRole('status')).toHaveTextContent('Cuenta planif creada.')
    expect(listarUsuarios).toHaveBeenCalledTimes(2) // la lista se vuelve a pedir
  })

  it('un usuario repetido muestra el motivo del backend', async () => {
    vi.mocked(crearUsuario).mockRejectedValue(
      new AxiosError(
        '409',
        'ERR',
        undefined,
        {},
        {
          status: 409,
          statusText: '',
          headers: {},
          config: {} as never,
          data: { detail: 'Ya existe el usuario planif.' },
        },
      ),
    )
    montar()

    await userEvent.click(await screen.findByRole('button', { name: 'Crear cuenta' }))
    await escribir('Usuario', 'planif')
    await escribir('Nombre completo', 'Planificación')
    await userEvent.selectOptions(screen.getByRole('combobox'), 'PLANIFICACION')
    await escribir('Contraseña inicial', 'una-clave-larga')
    await escribir('Repita la contraseña inicial', 'una-clave-larga')
    await userEvent.click(screen.getByRole('button', { name: 'Crear' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Ya existe el usuario planif.')
  })

  it('editar manda solo lo que cambió', async () => {
    vi.mocked(actualizarUsuario).mockResolvedValue(cuenta({ rol: 'LOGISTICA' }))
    montar()

    await userEvent.click((await fila('compras@gutis.com')).getByRole('button', { name: 'Editar' }))
    await userEvent.selectOptions(screen.getByRole('combobox'), 'LOGISTICA')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(actualizarUsuario).toHaveBeenCalledWith(2, { rol: 'LOGISTICA' })
  })

  it('desactivar pide confirmar, advierte de las sesiones y no borra', async () => {
    vi.mocked(actualizarUsuario).mockResolvedValue(cuenta({ activo: false }))
    montar()

    await userEvent.click(
      (await fila('compras@gutis.com')).getByRole('button', { name: 'Desactivar' }),
    )
    expect(screen.getByText(/Se cierran sus sesiones abiertas/)).toBeInTheDocument()
    expect(screen.getByText(/La cuenta no se borra/)).toBeInTheDocument()
    expect(actualizarUsuario).not.toHaveBeenCalled()

    const confirmar = screen.getAllByRole('button', { name: 'Desactivar' })
    await userEvent.click(confirmar[confirmar.length - 1])

    expect(actualizarUsuario).toHaveBeenCalledWith(2, { activo: false })
  })

  it('una cuenta inactiva se reactiva', async () => {
    vi.mocked(listarUsuarios).mockResolvedValue([ADMIN, cuenta({ activo: false })])
    vi.mocked(actualizarUsuario).mockResolvedValue(cuenta())
    montar()

    await userEvent.click(
      (await fila('compras@gutis.com')).getByRole('button', { name: 'Reactivar' }),
    )
    const confirmar = screen.getAllByRole('button', { name: 'Reactivar' })
    await userEvent.click(confirmar[confirmar.length - 1])

    expect(actualizarUsuario).toHaveBeenCalledWith(2, { activo: true })
  })

  it('reiniciar la contraseña advierte que saca a todos y la envía', async () => {
    vi.mocked(reiniciarContrasena).mockResolvedValue()
    montar()

    await userEvent.click(
      (await fila('compras@gutis.com')).getByRole('button', { name: 'Reiniciar contraseña' }),
    )
    expect(screen.getByText(/todas tendrán que entrar con la contraseña nueva/)).toBeInTheDocument()
    await escribir('Contraseña nueva', 'clave-nueva-larga')
    await escribir('Repita la contraseña nueva', 'clave-nueva-largx')
    expect(screen.getByText('La repetición no coincide.')).toBeInTheDocument()
    await userEvent.clear(screen.getByLabelText(/^Repita la contraseña nueva/))
    await escribir('Repita la contraseña nueva', 'clave-nueva-larga')

    const enviar = screen.getAllByRole('button', { name: 'Reiniciar contraseña' })
    await userEvent.click(enviar[enviar.length - 1])

    expect(reiniciarContrasena).toHaveBeenCalledWith(2, 'clave-nueva-larga')
  })
})
