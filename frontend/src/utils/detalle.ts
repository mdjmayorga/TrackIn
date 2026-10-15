/** Textos y formatos del detalle de un pedido (`US-20`). */

const dosDecimales = new Intl.NumberFormat('es-CR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const unDecimal = new Intl.NumberFormat('es-CR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const cantidad = new Intl.NumberFormat('es-CR', { maximumFractionDigits: 3 })

/** De dónde salió la fecha base, por la precedencia de RN-14. */
export const ORIGENES: Record<string, string> = {
  ATA_CONFIRMADA: 'llegada confirmada a mano',
  ATA_FUENTE: 'llegada reportada por la fuente',
  ATA_INFERIDA: 'llegada inferida por la geocerca',
  ETA_FUENTE: 'ETA de la fuente de rastreo',
  ETA_ESTIMADA: 'ETA estimada por posición y velocidad',
  ETA_DECLARADA: 'ETA CR del Z-tracking',
}

export const INTERVENCIONES: Record<string, string> = {
  CONFIRMACION_DESEMBARCO: 'Desembarco confirmado',
  PASO_A_ADUANAL: 'Paso a proceso aduanal',
  RECEPCION_PLANTA: 'Recepción en planta',
  LIBERACION_CALIDAD: 'Liberación de Calidad',
  TRANSBORDO: 'Transbordo',
  AJUSTE_MANUAL: 'Ajuste manual de días',
  CIERRE_FORZADO: 'Cierre forzado',
  ASOCIACION_TRACKING: 'Identificador de rastreo asociado',
}

/** «10,42 N | 81,90 W», como en el Figma. */
export function formatearPosicion(latitud: number, longitud: number): string {
  const lat = `${dosDecimales.format(Math.abs(latitud))} ${latitud >= 0 ? 'N' : 'S'}`
  const lon = `${dosDecimales.format(Math.abs(longitud))} ${longitud >= 0 ? 'E' : 'W'}`
  return `${lat} | ${lon}`
}

export function formatearNudos(nudos: string | null): string | null {
  return nudos === null ? null : `${unDecimal.format(Number(nudos))} nudos`
}

/** «12000.000» y «KG» → «12 000 kg». */
export function formatearCantidad(valor: string, unidad: string): string {
  return `${cantidad.format(Number(valor))} ${unidad.toLowerCase()}`
}

/** «+ 7 días», «− 3 días», «0 días». */
export function formatearDiasConSigno(dias: number): string {
  const unidad = Math.abs(dias) === 1 ? 'día' : 'días'
  if (dias === 0) return `0 ${unidad}`
  return `${dias > 0 ? '+' : '−'} ${Math.abs(dias)} ${unidad}`
}
