/**
 * «Configuración»: lo que antes ocupaba la esquina del panel —quién está
 * conectado, la carga del Z-tracking, el cambio de contraseña y el cierre de
 * sesión— queda en un menú desplegable, para dejarle el espacio al tablero
 * (pedido del 20/10).
 *
 * Es un botón que muestra y oculta una lista de enlaces (patrón «disclosure»),
 * no un `role="menu"` de escritorio: se recorre con Tab como cualquier enlace.
 * Se cierra con Escape, al hacer clic fuera o al elegir una opción.
 */

import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { esPantallaPlanta, puedeAdministrarUsuarios, puedeCargar } from '@/auth/permisos'
import type { SesionGuardada } from '@/auth/sesion'
import { cerrarSesion } from '@/services/auth'

const OPCION =
  'block w-full px-4 py-2 text-left text-sm text-slate-100 hover:bg-white/10 focus:bg-white/10 focus:outline-none'

export function MenuConfiguracion({ sesion }: { sesion: SesionGuardada }) {
  const [abierto, setAbierto] = useState(false)
  const contenedor = useRef<HTMLDivElement>(null)
  const boton = useRef<HTMLButtonElement>(null)
  const idPanel = useId()
  const { rol } = sesion.usuario

  useEffect(() => {
    if (!abierto) return
    function alClicFuera(evento: MouseEvent) {
      if (!contenedor.current?.contains(evento.target as Node)) setAbierto(false)
    }
    function alTeclear(evento: KeyboardEvent) {
      if (evento.key === 'Escape') {
        setAbierto(false)
        boton.current?.focus()
      }
    }
    document.addEventListener('mousedown', alClicFuera)
    document.addEventListener('keydown', alTeclear)
    return () => {
      document.removeEventListener('mousedown', alClicFuera)
      document.removeEventListener('keydown', alTeclear)
    }
  }, [abierto])

  const cerrar = () => setAbierto(false)

  return (
    <div ref={contenedor} className="relative inline-block">
      <button
        ref={boton}
        type="button"
        aria-expanded={abierto}
        aria-controls={idPanel}
        onClick={() => setAbierto((v) => !v)}
        className="inline-flex items-center gap-2 rounded bg-panel-cabecera px-3 py-1.5 text-sm text-slate-100 hover:bg-slate-600"
      >
        <IconoEngranaje />
        Configuración
        <span aria-hidden="true" className="text-xs text-slate-400">
          {abierto ? '▲' : '▼'}
        </span>
      </button>

      {abierto && (
        <div
          id={idPanel}
          className="absolute left-0 z-[1100] mt-1 w-64 overflow-hidden rounded border border-panel-borde bg-panel-superficie shadow-lg"
        >
          <p className="border-b border-panel-borde px-4 py-2 text-sm">
            {sesion.usuario.nombre_completo}
            <span className="block text-xs text-slate-400">{rol}</span>
          </p>
          <ul>
            {/* Planta no gestiona cargas: su rol solo lee (`US-43`). */}
            {!esPantallaPlanta(rol) && (
              <li>
                <Link to="/cargas" onClick={cerrar} className={OPCION}>
                  {puedeCargar(rol) ? 'Cargar Z-tracking' : 'Cargas del Z-tracking'}
                </Link>
              </li>
            )}
            {puedeAdministrarUsuarios(rol) && (
              <li>
                <Link to="/usuarios" onClick={cerrar} className={OPCION}>
                  Usuarios
                </Link>
              </li>
            )}
            {/* Cualquier rol, también Planta: es de la cuenta, no del negocio (`US-61`). */}
            <li>
              <Link to="/contrasena" onClick={cerrar} className={OPCION}>
                Cambiar contraseña
              </Link>
            </li>
            <li className="border-t border-panel-borde">
              <button
                type="button"
                onClick={() => {
                  cerrar()
                  void cerrarSesion()
                }}
                className={OPCION}
              >
                Cerrar sesión
              </button>
            </li>
          </ul>
        </div>
      )}
    </div>
  )
}

function IconoEngranaje() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}
