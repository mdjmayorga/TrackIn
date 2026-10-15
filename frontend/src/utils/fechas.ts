/**
 * Fechas como las lee Compras: `dd/mm/aaaa`, en hora de Costa Rica.
 *
 * Las fechas sin hora (`AAAA-MM-DD`) se reacomodan como texto: pasarlas por
 * `Date` las interpretaría en UTC y, a las seis de la tarde de Costa Rica, las
 * correría un día hacia atrás.
 */

const ZONA = 'America/Costa_Rica'

const formatoFechaHora = new Intl.DateTimeFormat('es-CR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: ZONA,
})

export function formatearFecha(fecha: string | null | undefined): string | null {
  if (!fecha) return null
  const soloFecha = /^(\d{4})-(\d{2})-(\d{2})$/.exec(fecha)
  if (soloFecha) {
    const [, anio, mes, dia] = soloFecha
    return `${dia}/${mes}/${anio}`
  }
  const instante = new Date(fecha)
  if (Number.isNaN(instante.getTime())) return null
  return formatoFechaHora.format(instante)
}

const formatoHora = new Intl.DateTimeFormat('es-CR', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: ZONA,
})

/** `dd/mm/aaaa hh:mm`, en hora de Costa Rica. */
export function formatearFechaHora(instante: string | null | undefined): string | null {
  if (!instante) return null
  const fecha = new Date(instante)
  if (Number.isNaN(fecha.getTime())) return null
  return `${formatoFechaHora.format(fecha)} ${formatoHora.format(fecha)}`
}

/**
 * «hace 3 min», «hace 2 h», «hace 5 días»: la antigüedad de una lectura, que
 * RNF-12 pide que se vea. Lo futuro (relojes desfasados) cuenta como «ahora».
 */
export function haceCuanto(instante: string | null | undefined, ahora = new Date()): string | null {
  if (!instante) return null
  const fecha = new Date(instante)
  if (Number.isNaN(fecha.getTime())) return null
  const minutos = Math.floor((ahora.getTime() - fecha.getTime()) / 60_000)
  if (minutos < 1) return 'ahora'
  if (minutos < 60) return `hace ${minutos} min`
  const horas = Math.floor(minutos / 60)
  if (horas < 24) return `hace ${horas} h`
  const dias = Math.floor(horas / 24)
  return `hace ${dias} ${dias === 1 ? 'día' : 'días'}`
}

/**
 * Para los campos `datetime-local`: el instante actual en Costa Rica,
 * `AAAA-MM-DDTHH:mm`. Costa Rica no tiene horario de verano: siempre UTC−6.
 */
export function ahoraParaCampo(ahora = new Date()): string {
  const enCostaRica = new Date(ahora.getTime() - 6 * 60 * 60_000)
  return enCostaRica.toISOString().slice(0, 16)
}

/** Lo que escribió el usuario en un `datetime-local`, como instante de Costa Rica. */
export function campoAInstante(valor: string): string {
  return `${valor}:00-06:00`
}

const DIA_MS = 24 * 60 * 60_000

function aUtc(fecha: string): number {
  const [anio, mes, dia] = fecha.split('-').map(Number)
  return Date.UTC(anio, mes - 1, dia)
}

/** `AAAA-MM-DD` más `n` días. En UTC: así ninguna zona horaria corre el día. */
export function sumarDias(fecha: string, dias: number): string {
  return new Date(aUtc(fecha) + dias * DIA_MS).toISOString().slice(0, 10)
}

/** Días de `desde` a `hasta`, ambas `AAAA-MM-DD`. Negativo si `hasta` es antes. */
export function diasEntre(desde: string, hasta: string): number {
  return Math.round((aUtc(hasta) - aUtc(desde)) / DIA_MS)
}
