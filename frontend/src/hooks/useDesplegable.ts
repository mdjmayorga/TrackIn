/**
 * Un botón que abre y cierra un panel (patrón «disclosure»): «Configuración» y
 * «Ajustes Z-tracking» del encabezado.
 *
 * El panel se cierra con Escape —devolviendo el foco al botón—, al hacer clic
 * fuera o cuando quien lo usa llama a `cerrar`, por ejemplo al elegir una opción.
 */

import { useCallback, useEffect, useId, useRef, useState } from 'react'

export function useDesplegable() {
  const [abierto, setAbierto] = useState(false)
  const contenedor = useRef<HTMLDivElement>(null)
  const boton = useRef<HTMLButtonElement>(null)
  const idPanel = useId()

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

  const alternar = useCallback(() => setAbierto((v) => !v), [])
  const cerrar = useCallback(() => setAbierto(false), [])

  return { abierto, alternar, cerrar, contenedor, boton, idPanel }
}
