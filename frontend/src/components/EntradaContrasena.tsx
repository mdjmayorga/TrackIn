/**
 * Un campo de contraseña con el botón de ojo del login, para ver lo que se
 * escribe (pedido del 06/10 para el login; del 21/10 para el resto).
 *
 * Lo usan todos los lugares donde se escribe una contraseña: el login, el
 * cambio de la propia (`US-61`) y, en «Usuarios», la contraseña inicial y el
 * reinicio (`US-62`). Cada campo tiene su propio botón, y el botón dice de qué
 * campo es —«Mostrar contraseña nueva»—, porque en un formulario con tres
 * campos «Mostrar contraseña» a secas no diría cuál. El botón no envía el
 * formulario.
 */

import { type InputHTMLAttributes, useState } from 'react'

type Atributos = Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'onChange' | 'value'>

export interface EntradaContrasenaProps extends Atributos {
  valor: string
  onCambio: (valor: string) => void
  /** Qué campo es, en minúsculas: «contraseña nueva». El botón lo nombra. */
  nombre?: string
  /** Clases del `<input>`; el espacio para el botón lo agrega el componente. */
  className?: string
  /** Tamaño del ojo: el login lo lleva más grande. */
  icono?: 'normal' | 'grande'
}

export function EntradaContrasena({
  valor,
  onCambio,
  nombre = 'contraseña',
  className = '',
  icono = 'normal',
  ...atributos
}: EntradaContrasenaProps) {
  const [visible, setVisible] = useState(false)
  const grande = icono === 'grande'

  return (
    <div className="relative">
      <input
        {...atributos}
        type={visible ? 'text' : 'password'}
        value={valor}
        onChange={(e) => onCambio(e.target.value)}
        className={`${className} ${grande ? 'pr-14' : 'pr-9'}`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={`${visible ? 'Ocultar' : 'Mostrar'} ${nombre}`}
        aria-pressed={visible}
        aria-controls={atributos.id}
        className={`absolute inset-y-0 right-0 flex items-center justify-center text-slate-300 hover:text-white focus:text-white focus:outline-none ${
          grande ? 'w-14 rounded-r-xl' : 'w-9 rounded-r'
        }`}
      >
        <IconoOjo tachado={visible} className={grande ? 'h-6 w-6' : 'h-4 w-4'} />
      </button>
    </div>
  )
}

export function IconoOjo({ tachado, className }: { tachado: boolean; className: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
      {tachado && <path d="M3 3l18 18" />}
    </svg>
  )
}
