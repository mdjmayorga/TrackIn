/**
 * «Cambiar contraseña» (`US-61`): cualquier rol cambia la suya, con la vigente.
 *
 * Al cambiarla, el backend cierra las **demás** sesiones de la cuenta y deja
 * abierta esta. En la cuenta compartida de Compras eso significa que las otras
 * personas tienen que volver a entrar con la nueva (decisión del 20/10): la
 * pantalla lo advierte antes y dice después cuántas sesiones se cerraron.
 *
 * Lo que se puede comprobar aquí —largo, repetición, que no sea la misma— se
 * dice antes de enviar. El backend lo vuelve a verificar.
 */

import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { EntradaContrasena } from '@/components/EntradaContrasena'
import { mensajeDeError } from '@/services/api'
import { cambiarContrasena } from '@/services/auth'

/** El mínimo del backend (`autenticacion.LONGITUD_MINIMA_CONTRASENA`). */
const LONGITUD_MINIMA = 10

/** Por qué todavía no se puede enviar, o nulo si ya se puede. */
function problemaDelFormulario(actual: string, nueva: string, repetida: string) {
  if (!actual || !nueva) return null // nada que señalar hasta que escriba
  if (nueva.length < LONGITUD_MINIMA) {
    return `La contraseña nueva debe tener al menos ${LONGITUD_MINIMA} caracteres.`
  }
  if (nueva === actual) return 'La contraseña nueva tiene que ser distinta de la actual.'
  if (repetida && repetida !== nueva) return 'La repetición no coincide con la contraseña nueva.'
  return null
}

export default function CambiarContrasena() {
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetida, setRepetida] = useState('')

  const cambio = useMutation({
    mutationFn: () => cambiarContrasena(actual, nueva),
    onSuccess: () => {
      setActual('')
      setNueva('')
      setRepetida('')
    },
  })

  const problema = problemaDelFormulario(actual, nueva, repetida)
  const listo =
    actual !== '' && nueva !== '' && repetida === nueva && problema === null && !cambio.isPending

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (listo) cambio.mutate()
  }

  const cerradas = cambio.data?.sesiones_cerradas ?? 0

  return (
    <div className="min-h-screen bg-panel-fondo text-slate-100">
      <header className="flex flex-wrap items-baseline justify-between gap-2 px-6 py-4">
        <h1 className="text-2xl font-bold">Cambiar contraseña</h1>
        <Link to="/" className="text-sm text-marca-300 underline hover:text-marca-200">
          ← Volver al panel
        </Link>
      </header>

      <main className="mx-auto max-w-md px-6 pb-12">
        <p className="mb-6 text-sm text-slate-400">
          Al cambiarla se cierran las demás sesiones abiertas con esta cuenta, en cualquier equipo;
          esta sigue abierta. Si la cuenta la comparten varias personas, todas tendrán que entrar
          con la contraseña nueva.
        </p>

        {cambio.isSuccess && (
          <p role="status" className="mb-6 rounded bg-emerald-900/60 px-4 py-3 text-sm">
            Contraseña cambiada.{' '}
            {cerradas === 0
              ? 'No había otras sesiones abiertas.'
              : cerradas === 1
                ? 'Se cerró 1 sesión abierta en otro equipo.'
                : `Se cerraron ${cerradas} sesiones abiertas en otros equipos.`}
          </p>
        )}

        <form onSubmit={enviar} aria-label="Cambiar contraseña" className="space-y-4">
          <Campo
            id="actual"
            etiqueta="Contraseña actual"
            nombre="contraseña actual"
            valor={actual}
            onCambio={setActual}
            autocompletar="current-password"
          />
          <Campo
            id="nueva"
            etiqueta="Contraseña nueva"
            nombre="contraseña nueva"
            ayuda={`Al menos ${LONGITUD_MINIMA} caracteres.`}
            valor={nueva}
            onCambio={setNueva}
            autocompletar="new-password"
          />
          <Campo
            id="repetida"
            etiqueta="Repita la contraseña nueva"
            nombre="repetición de la contraseña nueva"
            valor={repetida}
            onCambio={setRepetida}
            autocompletar="new-password"
          />

          {problema && (
            <p className="text-sm text-amber-200" aria-live="polite">
              {problema}
            </p>
          )}
          {cambio.isError && (
            <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-sm text-red-100">
              {mensajeDeError(cambio.error)}
            </p>
          )}

          <button
            type="submit"
            disabled={!listo}
            className="rounded bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
          >
            {cambio.isPending ? 'Guardando…' : 'Cambiar contraseña'}
          </button>
        </form>
      </main>
    </div>
  )
}

interface CampoProps {
  id: string
  etiqueta: string
  /** Lo que nombra el botón del ojo: «Mostrar contraseña nueva». */
  nombre: string
  ayuda?: string
  valor: string
  onCambio: (valor: string) => void
  autocompletar: 'current-password' | 'new-password'
}

function Campo({ id, etiqueta, nombre, ayuda, valor, onCambio, autocompletar }: CampoProps) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm text-slate-300">
        {etiqueta}
      </label>
      <div className="mt-1">
        <EntradaContrasena
          id={id}
          nombre={nombre}
          autoComplete={autocompletar}
          valor={valor}
          maxLength={200}
          onCambio={onCambio}
          className="w-full rounded bg-panel-cabecera px-3 py-2 text-white"
        />
      </div>
      {ayuda && <p className="mt-1 text-xs text-slate-500">{ayuda}</p>}
    </div>
  )
}
