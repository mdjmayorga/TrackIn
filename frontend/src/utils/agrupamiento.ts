/**
 * Agrupar los marcadores que se solapan (`US-25`, cuarto criterio).
 *
 * Varias naves en el mismo puerto quedan una encima de la otra al zoom del
 * panel. Se agrupan las que caen a menos de `RADIO_PX` píxeles **en pantalla**
 * —por eso se trabaja con puntos ya proyectados al zoom actual— y al acercar la
 * vista se separan solas, porque la misma distancia en grados ocupa más píxeles.
 *
 * Es un agrupamiento voraz, sin dependencias: con decenas de embarques no hace
 * falta más. Una función pura, para poder probarla sin Leaflet.
 */

/** Distancia en pantalla por debajo de la cual dos marcadores se agrupan. */
export const RADIO_PX = 28

export interface PuntoProyectado<T> {
  x: number
  y: number
  dato: T
}

export interface Grupo<T> {
  /** El centro del grupo en píxeles: el promedio de sus puntos. */
  x: number
  y: number
  datos: T[]
}

export function agrupar<T>(puntos: PuntoProyectado<T>[], radio = RADIO_PX): Grupo<T>[] {
  const grupos: Grupo<T>[] = []
  for (const punto of puntos) {
    const cercano = grupos.find((g) => Math.hypot(g.x - punto.x, g.y - punto.y) < radio)
    if (cercano) {
      const n = cercano.datos.length
      cercano.x = (cercano.x * n + punto.x) / (n + 1)
      cercano.y = (cercano.y * n + punto.y) / (n + 1)
      cercano.datos.push(punto.dato)
    } else {
      grupos.push({ x: punto.x, y: punto.y, datos: [punto.dato] })
    }
  }
  return grupos
}
