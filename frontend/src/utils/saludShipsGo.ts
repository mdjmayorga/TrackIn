/**
 * La insignia verde del Figma: si ShipsGo está respondiendo.
 *
 * Sale de `/health`, donde el worker publica la salud de cada fuente (`US-51`).
 * «Online» exige dos cosas: que la fuente no esté degradada **y** que el último
 * contacto sea reciente. Sin lo segundo, con el worker detenido la insignia
 * seguiría en verde con datos de ayer (RNF-12: la antigüedad tiene que verse).
 */

import type { HealthResponse } from '@/types/api'

/** El worker consulta cada minuto: 15 sin contacto ya no es «en línea». */
export const ANTIGUEDAD_MAXIMA_S = 15 * 60

export type Nivel = 'ok' | 'aviso' | 'falla'

interface Estado {
  nivel: Nivel
  texto: string
  detalle?: string
}

export function estadoShipsGo(salud: HealthResponse | undefined, sinConexion: boolean): Estado {
  if (sinConexion) {
    return { nivel: 'falla', texto: 'Sin conexión con TrackIn', detalle: 'El backend no responde.' }
  }
  const fuente = salud?.fuentes?.find((f) => f.fuente === 'shipsgo')
  if (!fuente) {
    return {
      nivel: 'aviso',
      texto: 'ShipsGo sin datos',
      detalle: 'El worker de rastreo todavía no ha reportado.',
    }
  }
  if (fuente.degradada) {
    return {
      nivel: 'falla',
      texto: 'ShipsGo con fallas',
      detalle: fuente.motivo_ultimo_fallo ?? `${fuente.fallos_consecutivos} fallos seguidos.`,
    }
  }
  if (fuente.antiguedad_s === null || fuente.antiguedad_s > ANTIGUEDAD_MAXIMA_S) {
    return {
      nivel: 'aviso',
      texto: 'ShipsGo sin lectura reciente',
      detalle: '¿Está corriendo el worker de rastreo?',
    }
  }
  return { nivel: 'ok', texto: 'ShipsGo API Online' }
}
