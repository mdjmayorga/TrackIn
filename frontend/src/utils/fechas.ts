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
