/** La dirección del mapa en vivo de ShipsGo (Embed) para un envío. Ver `MapaShipsGo`. */

import type { Rastreo, Via } from '@/types/api'

const BASE = 'https://embed.shipsgo.com/'

/** Los tipos que ShipsGo sigue (`referencia._FUENTE_POR_TIPO`). */
const DE_SHIPSGO: ReadonlySet<string> = new Set(['BL', 'CONTENEDOR', 'BOOKING', 'MAWB'])

export function tokenEmbed(): string | undefined {
  const token = import.meta.env.VITE_SHIPSGO_EMBED_TOKEN?.trim()
  return token ? token : undefined
}

/**
 * La dirección del mapa para ese envío, o nula si no aplica: sin token, una
 * referencia que ShipsGo no sigue, o una que todavía no respondió nunca (no
 * está dada de alta, y el mapa saldría vacío).
 */
export function urlMapaShipsGo(
  rastreo: Rastreo | null,
  via: Via,
  token = tokenEmbed(),
): string | null {
  if (!token || !rastreo) return null
  if (!DE_SHIPSGO.has(rastreo.tipo) || !rastreo.ultima_consulta_exitosa) return null
  const parametros = new URLSearchParams({
    token,
    tabs: 'none',
    transport: via === 'AEREO' ? 'air' : 'ocean',
    query: rastreo.referencia,
  })
  return `${BASE}?${parametros.toString()}`
}
