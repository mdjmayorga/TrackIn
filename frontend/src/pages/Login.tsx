import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useSesion } from '@/auth/useSesion'
import { EntradaContrasena } from '@/components/EntradaContrasena'
import { mensajeDeError } from '@/services/api'
import { iniciarSesion } from '@/services/auth'

/**
 * Pantalla de inicio de sesión — wireframe `US-41` (§0.1), backend `US-42`.
 *
 * El mensaje de error es el que devuelve el backend, que es genérico a
 * propósito: no dice si falló el usuario, la contraseña o si la cuenta está
 * bloqueada. Por la misma razón **no** se muestran los intentos restantes,
 * aunque el wireframe los dibujaba (ver la nota de `US-42` en el backlog).
 */
export default function Login() {
  const sesion = useSesion()
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? '/'

  const [usuario, setUsuario] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [recordar, setRecordar] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [mostrarAyuda, setMostrarAyuda] = useState(false)

  if (sesion) return <Navigate to={destino} replace />

  async function entrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      await iniciarSesion(usuario.trim(), contrasena, recordar)
      navegar(destino, { replace: true })
    } catch (falla) {
      setError(mensajeDeError(falla))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main
      // La foto del edificio (Figma «Login Form») ya viene oscurecida desde la
      // exportación: no lleva velo encima. Si faltara, queda el azul marino.
      style={{ backgroundImage: "url('/login-fondo.jpg')" }}
      className="relative flex min-h-screen items-center justify-center bg-slate-900 bg-cover bg-center px-4 py-10"
    >
      <form
        onSubmit={entrar}
        aria-labelledby="titulo-login"
        className="relative w-full max-w-xl text-white"
      >
        <header className="mb-12 text-center">
          <h1 id="titulo-login" className="text-5xl font-bold tracking-tight sm:text-6xl">
            TrackIn
          </h1>
          <p className="mt-3 text-lg font-light text-slate-100 sm:text-2xl">
            Seguimiento logístico <span aria-hidden="true">|</span> Laboratorios Gutis
          </p>
        </header>

        {/* Se entra con el nombre de usuario o con el correo de la cuenta (21/10). */}
        <label className="block text-base font-semibold" htmlFor="usuario">
          Usuario o correo
        </label>
        <input
          id="usuario"
          autoComplete="username"
          required
          maxLength={120}
          placeholder="usuario@gutis/gutiscorp.com"
          value={usuario}
          onChange={(e) => setUsuario(e.target.value)}
          className="mt-2 w-full rounded-xl border border-slate-600 bg-slate-800/95 px-5 py-4 text-white placeholder:text-slate-400 focus:border-marca-400 focus:outline-none"
        />

        <label className="mt-6 block text-base font-semibold" htmlFor="contrasena">
          Contraseña
        </label>
        <div className="mt-2">
          <EntradaContrasena
            id="contrasena"
            autoComplete="current-password"
            required
            placeholder="Su contraseña"
            valor={contrasena}
            onCambio={setContrasena}
            icono="grande"
            className="w-full rounded-xl border border-slate-600 bg-slate-800/95 py-4 pl-5 text-white placeholder:text-slate-400 focus:border-marca-400 focus:outline-none"
          />
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
          <label className="flex items-center gap-2 text-slate-100">
            <input
              type="checkbox"
              checked={recordar}
              onChange={(e) => setRecordar(e.target.checked)}
            />
            Recordar sesión
          </label>
          <button
            type="button"
            onClick={() => setMostrarAyuda((v) => !v)}
            className="text-marca-300 underline hover:text-marca-200"
          >
            ¿Olvidó su contraseña?
          </button>
        </div>
        {mostrarAyuda && (
          <p className="mt-2 text-right text-sm text-slate-100">
            Pida al Administrador de TrackIn que la reinicie. No hay recuperación por correo.
          </p>
        )}

        {error && (
          <p role="alert" className="mt-4 rounded-lg bg-red-600/90 px-4 py-3 text-sm text-white">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={enviando}
          className="mt-8 w-full rounded-xl bg-white px-4 py-4 text-lg font-semibold text-slate-900 hover:bg-slate-100 disabled:opacity-70"
        >
          {enviando ? 'Iniciando sesión…' : 'Iniciar sesión'}
        </button>
      </form>
    </main>
  )
}
