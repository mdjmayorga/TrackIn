/**
 * Lo que necesita la pantalla de planta para quedar encendida sola (`US-33`, RNF-11).
 *
 * - **Que no se apague:** pide al navegador un *wake lock* de pantalla mientras
 *   el panel esté abierto, y lo vuelve a pedir al volver a la pestaña (el
 *   navegador lo suelta cuando la pestaña se oculta). Si el navegador no lo
 *   admite —o la página no es segura—, no pasa nada: queda la configuración de
 *   energía del equipo.
 * - **Pantalla completa:** el botón del encabezado. Entrar exige un gesto del
 *   usuario (lo pide el navegador): se hace una vez al encender la pantalla.
 */

import { useCallback, useEffect, useState } from 'react'

interface WakeLockSentinelLike {
  release: () => Promise<void>
}

export function useWakeLock(activo: boolean): void {
  useEffect(() => {
    if (!activo) return
    const nav = navigator as Navigator & {
      wakeLock?: { request: (tipo: 'screen') => Promise<WakeLockSentinelLike> }
    }
    if (!nav.wakeLock) return

    let candado: WakeLockSentinelLike | null = null
    let vigente = true
    const pedir = () => {
      if (document.visibilityState !== 'visible') return
      nav.wakeLock
        ?.request('screen')
        .then((obtenido) => {
          if (vigente) candado = obtenido
          else void obtenido.release()
        })
        .catch(() => undefined) // sin permiso o sin soporte: no es un error de la app
    }
    pedir()
    document.addEventListener('visibilitychange', pedir)
    return () => {
      vigente = false
      document.removeEventListener('visibilitychange', pedir)
      void candado?.release().catch(() => undefined)
    }
  }, [activo])
}

export function usePantallaCompleta(): { activa: boolean; alternar: () => void; posible: boolean } {
  const [activa, setActiva] = useState(() => Boolean(document.fullscreenElement))
  useEffect(() => {
    const cambio = () => setActiva(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', cambio)
    return () => document.removeEventListener('fullscreenchange', cambio)
  }, [])
  const alternar = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined)
    else void document.documentElement.requestFullscreen?.().catch(() => undefined)
  }, [])
  return {
    activa,
    alternar,
    posible: typeof document.documentElement.requestFullscreen === 'function',
  }
}
