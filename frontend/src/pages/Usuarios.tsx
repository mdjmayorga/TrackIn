/**
 * «Usuarios» (`US-62`): el Administrador crea y mantiene las cuentas sin la
 * consola ni la API. Todo lo que hace ya existía en `/api/v1/usuarios` desde
 * `US-42`; esta pantalla lo pone a mano.
 *
 * Las cuentas **no se borran, se desactivan**: la auditoría referencia a quien
 * hizo cada intervención. Desactivar y reiniciar la contraseña cierran las
 * sesiones abiertas de la cuenta, y la pantalla lo advierte antes, porque en
 * la cuenta compartida de Compras eso saca a todas las personas conectadas.
 *
 * Ninguna acción usa los diálogos del navegador: cada una abre su formulario
 * bajo la fila, con su confirmación.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, type ReactNode, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'

import { NOMBRES_ROL, puedeAdministrarUsuarios } from '@/auth/permisos'
import { useSesion } from '@/auth/useSesion'
import { mensajeDeError } from '@/services/api'
import {
  type CambiosUsuario,
  actualizarUsuario,
  crearUsuario,
  listarUsuarios,
  reiniciarContrasena,
} from '@/services/usuarios'
import type { Rol, UsuarioAdministrado } from '@/types/api'
import { formatearFechaHora } from '@/utils/fechas'

/** El mínimo del backend (`autenticacion.LONGITUD_MINIMA_CONTRASENA`). */
const LONGITUD_MINIMA = 10

const ROLES = Object.keys(NOMBRES_ROL) as Rol[]

const CLAVE = ['usuarios']

type Accion = 'editar' | 'estado' | 'contrasena'

export default function Usuarios() {
  const sesion = useSesion()
  if (!puedeAdministrarUsuarios(sesion?.usuario.rol)) return <Navigate to="/" replace />

  return (
    <div className="min-h-screen bg-panel-fondo text-slate-100">
      <header className="flex flex-wrap items-baseline justify-between gap-2 px-6 py-4">
        <h1 className="text-2xl font-bold">Usuarios</h1>
        <Link to="/" className="text-sm text-marca-300 underline hover:text-marca-200">
          ← Volver al panel
        </Link>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-6 pb-12">
        <Alta />
        <Lista idPropio={sesion!.usuario.id} />
      </main>
    </div>
  )
}

// --- Alta ---------------------------------------------------------------------------

function Alta() {
  const [abierta, setAbierta] = useState(false)
  const [creada, setCreada] = useState<string | null>(null)

  return (
    <section aria-labelledby="titulo-alta" className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="titulo-alta" className="text-lg font-semibold">
          Nueva cuenta
        </h2>
        {!abierta && (
          <button
            type="button"
            onClick={() => {
              setCreada(null)
              setAbierta(true)
            }}
            className="rounded bg-panel-cabecera px-3 py-1.5 text-sm hover:bg-slate-600"
          >
            Crear cuenta
          </button>
        )}
      </div>

      {creada && (
        <p role="status" className="rounded bg-emerald-900/60 px-4 py-3 text-sm">
          Cuenta <strong>{creada}</strong> creada. Entregue la contraseña inicial a quien la va a
          usar: puede cambiarla en Configuración → Cambiar contraseña.
        </p>
      )}

      {abierta && (
        <FormularioAlta
          onCreada={(usuario) => {
            setCreada(usuario)
            setAbierta(false)
          }}
          onCancelar={() => setAbierta(false)}
        />
      )}
    </section>
  )
}

function FormularioAlta({
  onCreada,
  onCancelar,
}: {
  onCreada: (usuario: string) => void
  onCancelar: () => void
}) {
  const queryClient = useQueryClient()
  const [usuario, setUsuario] = useState('')
  const [nombre, setNombre] = useState('')
  const [correo, setCorreo] = useState('')
  const [rol, setRol] = useState<Rol | ''>('')
  const [contrasena, setContrasena] = useState('')
  const [repetida, setRepetida] = useState('')

  const alta = useMutation({
    mutationFn: () =>
      crearUsuario({
        usuario: usuario.trim(),
        nombre_completo: nombre.trim(),
        correo: correo.trim() || null,
        rol: rol as Rol,
        contrasena,
      }),
    onSuccess: (creado) => {
      void queryClient.invalidateQueries({ queryKey: CLAVE })
      onCreada(creado.usuario)
    },
  })

  const problema = problemaContrasena(contrasena, repetida)
  const listo =
    usuario.trim().length >= 3 &&
    nombre.trim() !== '' &&
    rol !== '' &&
    contrasena !== '' &&
    repetida === contrasena &&
    problema === null &&
    !alta.isPending

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (listo) alta.mutate()
  }

  return (
    <form
      onSubmit={enviar}
      aria-label="Nueva cuenta"
      className="grid max-w-3xl gap-3 rounded border border-panel-borde bg-panel-superficie p-4 sm:grid-cols-2"
    >
      <Campo etiqueta="Usuario" ayuda="Al menos 3 caracteres; se guarda en minúsculas.">
        <input
          value={usuario}
          maxLength={50}
          autoComplete="off"
          onChange={(e) => setUsuario(e.target.value)}
          className={ESTILO_CAMPO}
        />
      </Campo>
      <Campo etiqueta="Nombre completo">
        <input
          value={nombre}
          maxLength={120}
          onChange={(e) => setNombre(e.target.value)}
          className={ESTILO_CAMPO}
        />
      </Campo>
      <Campo etiqueta="Correo (opcional)">
        <input
          type="email"
          value={correo}
          maxLength={120}
          onChange={(e) => setCorreo(e.target.value)}
          className={ESTILO_CAMPO}
        />
      </Campo>
      <Campo etiqueta="Rol">
        <SelectorRol valor={rol} onCambio={setRol} conVacio />
      </Campo>
      <Campo etiqueta="Contraseña inicial" ayuda={`Al menos ${LONGITUD_MINIMA} caracteres.`}>
        <input
          type="password"
          value={contrasena}
          autoComplete="new-password"
          onChange={(e) => setContrasena(e.target.value)}
          className={ESTILO_CAMPO}
        />
      </Campo>
      <Campo etiqueta="Repita la contraseña inicial">
        <input
          type="password"
          value={repetida}
          autoComplete="new-password"
          onChange={(e) => setRepetida(e.target.value)}
          className={ESTILO_CAMPO}
        />
      </Campo>

      <div className="space-y-3 sm:col-span-2">
        {problema && <p className="text-sm text-amber-200">{problema}</p>}
        <Error mutacion={alta} />
        <Botones listo={listo} guardando={alta.isPending} texto="Crear" onCancelar={onCancelar} />
      </div>
    </form>
  )
}

// --- Lista --------------------------------------------------------------------------

function Lista({ idPropio }: { idPropio: number }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: CLAVE,
    queryFn: listarUsuarios,
  })
  const [abierta, setAbierta] = useState<{ id: number; accion: Accion } | null>(null)

  if (isPending) return <p className="text-sm text-slate-500">Cargando…</p>
  if (isError) {
    return (
      <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-sm text-red-100">
        No se pudieron cargar las cuentas: {mensajeDeError(error)}
      </p>
    )
  }

  return (
    <section aria-labelledby="titulo-cuentas">
      <h2 id="titulo-cuentas" className="mb-3 text-lg font-semibold">
        Cuentas
      </h2>
      <div className="overflow-x-auto rounded-lg border border-panel-borde">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-panel-cabecera text-left">
            <tr>
              {['Usuario', 'Nombre', 'Correo', 'Rol', 'Estado', 'Último acceso', 'Acciones'].map(
                (t) => (
                  <th key={t} scope="col" className="whitespace-nowrap px-3 py-2 font-semibold">
                    {t}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody className="bg-panel-superficie">
            {data.map((cuenta) => {
              const propia = cuenta.id === idPropio
              const accion = abierta?.id === cuenta.id ? abierta.accion : null
              const alternar = (a: Accion) =>
                setAbierta(accion === a ? null : { id: cuenta.id, accion: a })
              return (
                <FilaCuenta
                  key={cuenta.id}
                  cuenta={cuenta}
                  propia={propia}
                  accion={accion}
                  onAccion={alternar}
                  onListo={() => setAbierta(null)}
                />
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

interface FilaProps {
  cuenta: UsuarioAdministrado
  propia: boolean
  accion: Accion | null
  onAccion: (accion: Accion) => void
  onListo: () => void
}

function FilaCuenta({ cuenta, propia, accion, onAccion, onListo }: FilaProps) {
  const boton = (a: Accion, texto: string) => (
    <button
      type="button"
      aria-expanded={accion === a}
      onClick={() => onAccion(a)}
      className={`rounded px-2 py-1 text-xs ${
        accion === a ? 'bg-slate-500' : 'bg-panel-cabecera'
      } hover:bg-slate-600`}
    >
      {texto}
    </button>
  )

  return (
    <>
      <tr aria-label={`Cuenta ${cuenta.usuario}`} className="border-t border-white/5 align-top">
        <td className="whitespace-nowrap px-3 py-2">
          {cuenta.usuario}
          {propia && <span className="ml-1 text-xs text-slate-400">(usted)</span>}
        </td>
        <td className="px-3 py-2">{cuenta.nombre_completo}</td>
        <td className="px-3 py-2 text-slate-300">{cuenta.correo ?? '–'}</td>
        <td className="whitespace-nowrap px-3 py-2">{NOMBRES_ROL[cuenta.rol]}</td>
        <td className="whitespace-nowrap px-3 py-2">
          <Estado cuenta={cuenta} />
        </td>
        <td className="whitespace-nowrap px-3 py-2 text-slate-300">
          {formatearFechaHora(cuenta.ultimo_acceso) ?? 'Nunca'}
        </td>
        <td className="px-3 py-2">
          <div className="flex flex-wrap gap-1.5">
            {boton('editar', 'Editar')}
            {boton('contrasena', 'Reiniciar contraseña')}
            {/* Un Administrador no puede desactivarse a sí mismo: el sistema
                quedaría sin quien administre cuentas (el backend responde 409). */}
            {!propia && boton('estado', cuenta.activo ? 'Desactivar' : 'Reactivar')}
          </div>
        </td>
      </tr>
      {accion && (
        <tr className="bg-panel-fondo/60">
          <td colSpan={7} className="px-3 py-3">
            {accion === 'editar' && (
              <FormularioEdicion cuenta={cuenta} propia={propia} onListo={onListo} />
            )}
            {accion === 'estado' && <ConfirmarEstado cuenta={cuenta} onListo={onListo} />}
            {accion === 'contrasena' && <FormularioReinicio cuenta={cuenta} onListo={onListo} />}
          </td>
        </tr>
      )}
    </>
  )
}

function bloqueada(cuenta: UsuarioAdministrado, ahora = new Date()): boolean {
  return cuenta.bloqueado_hasta !== null && new Date(cuenta.bloqueado_hasta) > ahora
}

function Estado({ cuenta }: { cuenta: UsuarioAdministrado }) {
  if (!cuenta.activo) return <span className="text-slate-400">Inactiva</span>
  if (bloqueada(cuenta)) {
    return (
      <span className="text-amber-200">
        Bloqueada hasta {formatearFechaHora(cuenta.bloqueado_hasta)}
      </span>
    )
  }
  return <span>Activa</span>
}

// --- Acciones sobre una cuenta -------------------------------------------------------

function useActualizar(id: number, onListo: () => void) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (cambios: CambiosUsuario) => actualizarUsuario(id, cambios),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: CLAVE })
      onListo()
    },
  })
}

function FormularioEdicion({
  cuenta,
  propia,
  onListo,
}: {
  cuenta: UsuarioAdministrado
  propia: boolean
  onListo: () => void
}) {
  const [nombre, setNombre] = useState(cuenta.nombre_completo)
  const [correo, setCorreo] = useState(cuenta.correo ?? '')
  const [rol, setRol] = useState<Rol>(cuenta.rol)
  const guardar = useActualizar(cuenta.id, onListo)

  // Solo se manda lo que cambió.
  const cambios: CambiosUsuario = {}
  if (nombre.trim() !== cuenta.nombre_completo) cambios.nombre_completo = nombre.trim()
  if ((correo.trim() || null) !== cuenta.correo) cambios.correo = correo.trim() || null
  if (rol !== cuenta.rol) cambios.rol = rol
  const listo = Object.keys(cambios).length > 0 && nombre.trim() !== '' && !guardar.isPending

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (listo) guardar.mutate(cambios)
  }

  return (
    <form
      onSubmit={enviar}
      aria-label={`Editar ${cuenta.usuario}`}
      className="grid max-w-3xl gap-3 sm:grid-cols-3"
    >
      <Campo etiqueta="Nombre completo">
        <input
          value={nombre}
          maxLength={120}
          onChange={(e) => setNombre(e.target.value)}
          className={ESTILO_CAMPO}
        />
      </Campo>
      <Campo etiqueta="Correo (opcional)">
        <input
          type="email"
          value={correo}
          maxLength={120}
          onChange={(e) => setCorreo(e.target.value)}
          className={ESTILO_CAMPO}
        />
      </Campo>
      <Campo
        etiqueta="Rol"
        ayuda={propia ? 'No puede quitarse a sí mismo el rol de Administrador.' : undefined}
      >
        <SelectorRol valor={rol} onCambio={(r) => setRol(r as Rol)} deshabilitado={propia} />
      </Campo>
      <div className="space-y-3 sm:col-span-3">
        <Error mutacion={guardar} />
        <Botones listo={listo} guardando={guardar.isPending} texto="Guardar" onCancelar={onListo} />
      </div>
    </form>
  )
}

function ConfirmarEstado({
  cuenta,
  onListo,
}: {
  cuenta: UsuarioAdministrado
  onListo: () => void
}) {
  const cambiar = useActualizar(cuenta.id, onListo)
  const desactivar = cuenta.activo

  return (
    <div className="max-w-2xl space-y-3 text-sm">
      <p>
        {desactivar ? (
          <>
            ¿Desactivar <strong>{cuenta.usuario}</strong>? Se cierran sus sesiones abiertas y no
            podrá entrar. La cuenta no se borra: la auditoría la conserva y puede reactivarse.
          </>
        ) : (
          <>
            ¿Reactivar <strong>{cuenta.usuario}</strong>? Podrá volver a entrar con su contraseña.
          </>
        )}
      </p>
      <Error mutacion={cambiar} />
      <div className="flex gap-3">
        <button
          type="button"
          disabled={cambiar.isPending}
          onClick={() => cambiar.mutate({ activo: !desactivar })}
          className="rounded bg-white px-4 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
        >
          {cambiar.isPending ? 'Guardando…' : desactivar ? 'Desactivar' : 'Reactivar'}
        </button>
        <button type="button" onClick={onListo} className="text-sm text-slate-300 underline">
          Cancelar
        </button>
      </div>
    </div>
  )
}

function FormularioReinicio({
  cuenta,
  onListo,
}: {
  cuenta: UsuarioAdministrado
  onListo: () => void
}) {
  const queryClient = useQueryClient()
  const [contrasena, setContrasena] = useState('')
  const [repetida, setRepetida] = useState('')

  const reinicio = useMutation({
    mutationFn: () => reiniciarContrasena(cuenta.id, contrasena),
    onSuccess: () => {
      // Queda desbloqueada: el estado de la fila cambia.
      void queryClient.invalidateQueries({ queryKey: CLAVE })
      onListo()
    },
  })

  const problema = problemaContrasena(contrasena, repetida)
  const listo =
    contrasena !== '' && repetida === contrasena && problema === null && !reinicio.isPending

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (listo) reinicio.mutate()
  }

  return (
    <form
      onSubmit={enviar}
      aria-label={`Reiniciar la contraseña de ${cuenta.usuario}`}
      className="max-w-2xl space-y-3"
    >
      <p className="text-sm">
        Se cierran <strong>todas</strong> las sesiones abiertas de {cuenta.usuario} y la cuenta
        queda desbloqueada. Si la comparten varias personas, todas tendrán que entrar con la
        contraseña nueva.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo etiqueta="Contraseña nueva" ayuda={`Al menos ${LONGITUD_MINIMA} caracteres.`}>
          <input
            type="password"
            value={contrasena}
            autoComplete="new-password"
            onChange={(e) => setContrasena(e.target.value)}
            className={ESTILO_CAMPO}
          />
        </Campo>
        <Campo etiqueta="Repita la contraseña nueva">
          <input
            type="password"
            value={repetida}
            autoComplete="new-password"
            onChange={(e) => setRepetida(e.target.value)}
            className={ESTILO_CAMPO}
          />
        </Campo>
      </div>
      {problema && <p className="text-sm text-amber-200">{problema}</p>}
      <Error mutacion={reinicio} />
      <Botones
        listo={listo}
        guardando={reinicio.isPending}
        texto="Reiniciar contraseña"
        onCancelar={onListo}
      />
    </form>
  )
}

// --- Piezas comunes -------------------------------------------------------------------

function problemaContrasena(contrasena: string, repetida: string): string | null {
  if (!contrasena) return null
  if (contrasena.length < LONGITUD_MINIMA) {
    return `La contraseña debe tener al menos ${LONGITUD_MINIMA} caracteres.`
  }
  if (repetida && repetida !== contrasena) return 'La repetición no coincide.'
  return null
}

function SelectorRol({
  valor,
  onCambio,
  conVacio = false,
  deshabilitado = false,
}: {
  valor: Rol | ''
  onCambio: (rol: Rol | '') => void
  conVacio?: boolean
  deshabilitado?: boolean
}) {
  return (
    <select
      value={valor}
      disabled={deshabilitado}
      onChange={(e) => onCambio(e.target.value as Rol | '')}
      className={`${ESTILO_CAMPO} disabled:opacity-60`}
    >
      {conVacio && <option value="">Elija un rol</option>}
      {ROLES.map((r) => (
        <option key={r} value={r}>
          {NOMBRES_ROL[r]}
        </option>
      ))}
    </select>
  )
}

function Error({ mutacion }: { mutacion: { isError: boolean; error: unknown } }) {
  if (!mutacion.isError) return null
  return (
    <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-sm text-red-100">
      {mensajeDeError(mutacion.error)}
    </p>
  )
}

function Botones({
  listo,
  guardando,
  texto,
  onCancelar,
}: {
  listo: boolean
  guardando: boolean
  texto: string
  onCancelar: () => void
}) {
  return (
    <div className="flex gap-3">
      <button
        type="submit"
        disabled={!listo}
        className="rounded bg-white px-4 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
      >
        {guardando ? 'Guardando…' : texto}
      </button>
      <button type="button" onClick={onCancelar} className="text-sm text-slate-300 underline">
        Cancelar
      </button>
    </div>
  )
}

const ESTILO_CAMPO =
  'mt-0.5 w-full rounded bg-panel-cabecera px-2 py-1.5 text-sm text-white [color-scheme:dark]'

function Campo({
  etiqueta,
  ayuda,
  children,
}: {
  etiqueta: string
  ayuda?: string
  children: ReactNode
}) {
  return (
    <label className="block text-xs text-slate-300">
      {etiqueta}
      {children}
      {ayuda && <span className="mt-0.5 block text-slate-500">{ayuda}</span>}
    </label>
  )
}
